import logging
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone
from rest_framework.response import Response

from crudkit.audit import audit
from crudkit.authorization import has_model_permission, has_object_permission
from crudkit.decorators import crm_action
from crudkit.models import BaseCrudKitModel, CrudKitPositiveIntegerField

logger = logging.getLogger(__name__)


def uuid4_hex() -> str:
    return uuid4().hex


class AssistantProposal(BaseCrudKitModel):
    """
    A pending mutation the assistant, an MCP client or an agent has proposed,
    waiting for its creator to Confirm or Skip it in the chat window or the
    Inbox.

    Proposers never mutate objects directly: they only write rows to this
    table. The actual @crm_action / PATCH / create / note runs in apply() —
    called by the sidebar consumer or the `confirm` action when the user
    clicks Confirm.
    """

    TYPE_ID = "ASP"

    class Kind(models.TextChoices):
        ACTION = "action", "Run action"
        PATCH = "patch", "Update fields"
        NOTE = "note", "Add note"
        REVERT = "revert", "Revert change"
        CREATE = "create", "Create record"

    class Source(models.TextChoices):
        ASSISTANT = "assistant", "Assistant"
        MCP = "mcp", "MCP"
        AGENT = "agent", "Agent"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    # For a create, the model to create; the object id is set once it exists.
    target_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+", editable=False)
    target_object_id = CrudKitPositiveIntegerField(null=True, blank=True, editable=False)
    target = GenericForeignKey("target_content_type", "target_object_id")

    # The sidebar conversation that proposed it; empty for MCP and agents.
    session_key = models.CharField(max_length=64, db_index=True, blank=True, default="")
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.ASSISTANT, editable=False)
    client = models.CharField(max_length=255, blank=True, default="", editable=False)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    label = models.CharField(max_length=255, help_text="Human-readable summary for the Confirm card.")
    reasoning = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, help_text="Action name + args, patch or create fields, or note body.")
    outcome = models.JSONField(null=True, blank=True, help_text="What the action returned or error info.")

    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assistant_proposal_confirmed_set",
    )

    class Meta:
        indexes = [
            models.Index(fields=["session_key", "status"]),
            models.Index(fields=["target_content_type", "target_object_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.label or super().__str__()

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        owner_access = True

        @staticmethod
        def get_authorized_queryset(user, queryset, action):
            return queryset.filter(created_by=user)

        @staticmethod
        def has_action_permission(user, instance, action_name):
            return instance.status == AssistantProposal.Status.PENDING

    def can_apply(self, user) -> bool:
        if self.kind == self.Kind.CREATE:
            return has_model_permission(user, self.target_content_type.model_class(), "add")
        target = self.target
        return target is not None and has_object_permission(user, target, "change")

    def apply(self, user, request=None):
        """Execute the proposed mutation as its own change set, attributed to
        where the proposal came from. Imported lazily to avoid app-loading cycles."""
        from crudkit_assistant.execution import execute_proposal

        try:
            with audit(self.source, client=self.client, user=user, change_set=uuid4()) as context:
                outcome = execute_proposal(self, user, request=request)
            if context.logged and isinstance(outcome, dict):
                outcome = {**outcome, "change_set": str(context.change_set)}
            self.outcome = outcome
            self.status = self.Status.CONFIRMED
        except Exception as exc:
            logger.exception("AssistantProposal %s apply failed", self.pk)
            self.outcome = {"error": str(exc)}
            self.status = self.Status.FAILED
        self.confirmed_at = timezone.now()
        self.confirmed_by = user
        self.save(update_fields=["outcome", "status", "confirmed_at", "confirmed_by", "updated_at", "updated_by"])
        return self.outcome

    def mark_skipped(self, user):
        self.status = self.Status.SKIPPED
        self.confirmed_at = timezone.now()
        self.confirmed_by = user
        self.save(update_fields=["status", "confirmed_at", "confirmed_by", "updated_at", "updated_by"])

    @crm_action("Confirm")
    def confirm(self, request):
        if not self.can_apply(request.user):
            raise PermissionDenied
        outcome = self.apply(request.user)
        if self.status == self.Status.FAILED:
            return Response({"errors": [outcome.get("error", "Failed")]}, status=400)
        return Response({"messages": [f"Confirmed: {self.label}"], "outcome": outcome})

    @crm_action("Skip")
    def skip(self, request):
        self.mark_skipped(request.user)
        return Response({"messages": [f"Skipped: {self.label}"]})


class AssistantConversation(BaseCrudKitModel):
    """
    One sidebar chat, owned by `created_by`. `messages` is the pydantic-ai history the model sees
    (user turns include the `[Screen]` block); `transcript` is what the
    sidebar renders: {role: user|assistant|system, text} items and
    {role: proposal, id} references to AssistantProposal rows, whose status
    is read live when the conversation is reopened.
    """

    TYPE_ID = "ASC"
    TITLE_LENGTH = 120

    session_key = models.CharField(max_length=64, unique=True, default=uuid4_hex, editable=False)
    title = models.CharField(max_length=TITLE_LENGTH, blank=True, default="")
    messages = models.JSONField(default=list, blank=True)
    transcript = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversation {self.id}"

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        @staticmethod
        def get_authorized_queryset(user, queryset, action):
            return queryset.filter(created_by=user)
