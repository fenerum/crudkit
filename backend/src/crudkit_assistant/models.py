import logging

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from crudkit.models import BaseCrudKitModel, CrudKitPositiveIntegerField

logger = logging.getLogger(__name__)


class AssistantProposal(BaseCrudKitModel):
    """
    A pending mutation the assistant has proposed for a CrudKit object,
    waiting for the staff user to Confirm or Skip in the chat window.

    The assistant never mutates objects directly: its proposal tools only
    write rows to this table and emit a WS event. The actual @crm_action /
    PATCH / note creation runs in apply() — called by the consumer when the
    user clicks Confirm.
    """

    TYPE_ID = "ASP"

    class Kind(models.TextChoices):
        ACTION = "action", "Run action"
        PATCH = "patch", "Update fields"
        NOTE = "note", "Add note"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    target_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    target_object_id = CrudKitPositiveIntegerField(editable=False)
    target = GenericForeignKey("target_content_type", "target_object_id")

    session_key = models.CharField(max_length=64, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    label = models.CharField(max_length=255, help_text="Human-readable summary for the Confirm card.")
    reasoning = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, help_text="Action name + args, patch fields, or note body.")
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

    def apply(self, user, request=None):
        """Execute the proposed mutation. Imported lazily to avoid app-loading cycles."""
        from crudkit_assistant.execution import execute_proposal

        try:
            outcome = execute_proposal(self, user, request=request)
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

    def skip(self, user):
        self.status = self.Status.SKIPPED
        self.confirmed_at = timezone.now()
        self.confirmed_by = user
        self.save(update_fields=["status", "confirmed_at", "confirmed_by", "updated_at", "updated_by"])
