import logging
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.utils import timezone
from rest_framework.response import Response

from crudkit.audit import audit
from crudkit.authorization import has_model_permission, has_object_permission, requires_approval
from crudkit.decorators import crm_action
from crudkit.fields import ModelField
from crudkit.models import BaseCrudKitModel, ChangeLog, CrudKitPositiveIntegerField, View
from crudkit.utils import get_model_types
from crudkit_api.records import get_exposed_models
from crudkit_api.services import revert_change_set, revert_requires_approval

logger = logging.getLogger(__name__)

ALREADY_RESOLVED = "This proposal was already confirmed or skipped."


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

    # What a proposal does is fixed once it is filed: Confirm applies exactly
    # what was proposed. Status and outcome only change through apply()/skip.
    LOCKED_FIELDS = [
        "kind",
        "status",
        "label",
        "reasoning",
        "payload",
        "outcome",
        "session_key",
        "source",
        "client",
        "target_content_type_id",
        "target_object_id",
        "confirmed_at",
        "confirmed_by_id",
    ]

    def clean(self):
        if self.pk is None:
            return
        stored = type(self).objects.filter(pk=self.pk).values(*self.LOCKED_FIELDS).first()
        # Compared as the database sees them: an in-memory id may be a CK-ID
        # ("CUS1") where the stored one is 1.
        fields = {f.attname: f for f in self._meta.concrete_fields}
        if stored and any(
            fields[name].get_prep_value(stored[name]) != fields[name].get_prep_value(getattr(self, name))
            for name in self.LOCKED_FIELDS
        ):
            raise ValidationError("A proposal can't be edited. Skip it and propose the change again.")

    def can_apply(self, user) -> bool:
        """Whether `user` may confirm: they, and the proposal's creator, may make
        the change. A proposal never does more than whoever filed it could."""
        return self._permits(user) and (self.created_by_id == user.pk or self._permits(self.created_by))

    def _permits(self, user) -> bool:
        if self.kind == self.Kind.CREATE:
            return has_model_permission(user, self.target_content_type.model_class(), "add")
        target = self.target
        return target is not None and has_object_permission(user, target, "change")

    def needs_approval(self) -> bool:
        """Whether an agent must leave this proposal for a person to decide."""
        model = self.target_content_type.model_class()
        if self.kind in (self.Kind.PATCH, self.Kind.CREATE):
            return requires_approval(model, fields=self.payload.get("fields"))
        if self.kind == self.Kind.ACTION:
            return requires_approval(model, action=self.payload.get("action"))
        if self.kind == self.Kind.REVERT:
            return revert_requires_approval(self.payload.get("change_set"))
        return False

    def _claim(self, user, status) -> bool:
        """Move PENDING to `status` atomically, so two Confirms (two tabs, the
        Inbox and the sidebar) can't both apply. False if already resolved."""
        now = timezone.now()
        claimed = (
            type(self)
            .objects.filter(pk=self.pk, status=self.Status.PENDING)
            .update(status=status, confirmed_at=now, confirmed_by=user, updated_by=user, updated_at=now)
        )
        self.refresh_from_db()
        return bool(claimed)

    def apply(self, user, request=None, change_set=None):
        """Execute the proposed mutation as its own change set (or `change_set`),
        attributed to where the proposal came from. Imported lazily to avoid
        app-loading cycles."""
        from crudkit_assistant.execution import execute_proposal

        if not self._claim(user, self.Status.CONFIRMED):
            return {"error": ALREADY_RESOLVED, "already_resolved": True}
        try:
            with audit(self.source, client=self.client, user=user, change_set=change_set or uuid4()) as context:
                outcome = execute_proposal(self, user, request=request)
            if context.logged and isinstance(outcome, dict):
                outcome = {**outcome, "change_set": str(context.change_set)}
            self.outcome = outcome
        except Exception as exc:
            logger.exception("AssistantProposal %s apply failed", self.pk)
            self.outcome = {"error": str(exc)}
            self.status = self.Status.FAILED
        self.save(update_fields=["outcome", "status", "updated_at"])
        return self.outcome

    def mark_skipped(self, user) -> bool:
        """Skip the proposal; False if it was already resolved."""
        if not self._claim(user, self.Status.SKIPPED):
            return False
        # _claim's queryset update sends no post_save; this does (realtime notifications).
        self.save(update_fields=["updated_at"])
        return True

    @crm_action("Confirm")
    def confirm(self, request):
        if not self.can_apply(request.user):
            raise PermissionDenied
        outcome = self.apply(request.user, request=request)
        if outcome.get("already_resolved"):
            return Response({"errors": [ALREADY_RESOLVED]}, status=409)
        if self.status == self.Status.FAILED:
            return Response({"errors": [outcome.get("error", "Failed")]}, status=400)
        return Response({"messages": [f"Confirmed: {self.label}"], "outcome": outcome})

    @crm_action("Skip")
    def skip(self, request):
        if not self.mark_skipped(request.user):
            return Response({"errors": [ALREADY_RESOLVED]}, status=409)
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


class Agent(BaseCrudKitModel):
    """
    Saved instructions the assistant carries out in the background, on a
    record of `model_type` that was just created or changed, on the records of
    `view` on a schedule, or when someone clicks Run now. What it would change
    is filed as proposals; in auto mode those that need no approval are applied
    right away, as `run_as`.
    """

    TYPE_ID = "AGT"

    class Trigger(models.TextChoices):
        RECORD_CREATED = "record_created", "Record created"
        RECORD_CHANGED = "record_changed", "Record changed"
        SCHEDULE = "schedule", "Schedule"
        MANUAL = "manual", "Manual"

    class Schedule(models.TextChoices):
        HOURLY = "hourly", "Hourly"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    class Mode(models.TextChoices):
        PROPOSE = "propose", "Propose changes"
        AUTO = "auto", "Apply changes"

    MAX_CONSECUTIVE_FAILURES = 3

    name = models.CharField(max_length=255)
    instructions = models.TextField(help_text="What the agent should do with each record, in plain language.")
    enabled = models.BooleanField(default=True)
    trigger = models.CharField(max_length=16, choices=Trigger.choices, default=Trigger.RECORD_CHANGED)
    model_type = ModelField(help_text="The record type (TYPE_ID) the agent works on.")
    view = models.ForeignKey(
        View,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Only records in this saved view are worked on.",
    )
    watch_fields = models.JSONField(
        default=list,
        blank=True,
        help_text='For "Record changed": run only when one of these fields changed. Empty means any field.',
    )
    schedule = models.CharField(max_length=16, choices=Schedule.choices, blank=True, default="")
    last_scheduled_at = models.DateTimeField(null=True, blank=True, editable=False)
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.PROPOSE)
    run_as = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        related_name="+",
        help_text="The user whose permissions the agent has. Defaults to its creator.",
    )
    max_records_per_run = models.PositiveIntegerField(default=25)
    max_runs_per_day = models.PositiveIntegerField(default=200)
    consecutive_failures = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["name"]
        owner_access = True
        ai_exposed = True
        approval_fields = [
            "instructions",
            "enabled",
            "trigger",
            "model_type",
            "view",
            "watch_fields",
            "schedule",
            "mode",
            "run_as",
            "max_records_per_run",
            "max_runs_per_day",
        ]
        default_inlines = [["AGR", ["status", "dry_run", "output", "finished_at"]]]

        @staticmethod
        def get_authorized_queryset(user, queryset, action):
            return queryset.filter(created_by=user)

    def get_model(self):
        return get_model_types().get(self.model_type)

    # What an agent does; only superusers change these while it runs as someone else.
    BEHAVIOUR_FIELDS = [
        "name",
        "instructions",
        "trigger",
        "model_type",
        "view_id",
        "watch_fields",
        "schedule",
        "mode",
        "max_records_per_run",
        "max_runs_per_day",
    ]

    def clean(self):
        model = self.get_model()
        if model is None:
            raise ValidationError({"model_type": f"Unknown record type {self.model_type!r}."})
        stored_type = Agent.objects.filter(pk=self.pk).values_list("model_type", flat=True).first() if self.pk else None
        if self.model_type != stored_type and model not in get_exposed_models(mcp_allowlist=False):
            # CrudKit's own bookkeeping (proposals, change log, notes, runs) is off limits.
            raise ValidationError({"model_type": f"Agents can't work on {model._meta.verbose_name_plural}."})
        if self.view_id and self.view.model != self.model_type:
            raise ValidationError({"view": f"Pick a saved view of {model._meta.verbose_name_plural}."})
        if not isinstance(self.watch_fields, list):
            raise ValidationError({"watch_fields": 'Format: ["field1", "field2"]'})
        unknown = sorted(set(self.watch_fields) - {f.name for f in model._meta.fields})
        if unknown:
            raise ValidationError({"watch_fields": f"Not fields of {model._meta.verbose_name}: {unknown}"})
        if (self.trigger == self.Trigger.SCHEDULE) != bool(self.schedule):
            raise ValidationError({"schedule": 'Set a schedule exactly when the trigger is "Schedule".'})
        self._check_run_as()

    def _check_run_as(self):
        """Only superusers may make an agent act as somebody else, or change what
        an agent that acts as somebody else does (else its owner could point a
        superuser-assigned `run_as` at anything)."""
        editor = self.updated_by if self.updated_by_id else None
        if not self.run_as_id or editor is None or editor.is_superuser or self.run_as_id == editor.pk:
            return
        stored = (
            Agent.objects.filter(pk=self.pk).values("run_as_id", *self.BEHAVIOUR_FIELDS).first() if self.pk else None
        )
        if stored is None or stored["run_as_id"] != self.run_as_id:
            raise ValidationError({"run_as": "Only superusers can make an agent run as another user."})
        changed = [name for name in self.BEHAVIOUR_FIELDS if stored[name] != getattr(self, name)]
        if changed:
            raise ValidationError(
                "Only superusers can change an agent that runs as another user "
                f"({', '.join(name.removesuffix('_id') for name in changed)})."
            )

    def save(self, *args, **kwargs):
        if not self.run_as_id:
            self.run_as_id = self.created_by_id
        # Re-enabling gives an agent disabled after failures a fresh start.
        if self.pk and self.enabled and Agent.objects.filter(pk=self.pk, enabled=False).exists():
            self.consecutive_failures = 0
        super().save(*args, **kwargs)

    # Starting runs is approval-required, so agents and MCP clients can't set
    # agents off (or themselves again); people click these directly.
    @crm_action("Dry run on latest matching record", requires_approval=True)
    def dry_run(self, request):
        from crudkit_assistant.background import start_dry_run  # background imports this module

        run = start_dry_run(self)
        if run is None:
            return Response({"errors": ["No record matches this agent."]}, status=400)
        return run

    @crm_action("Run now", requires_approval=True)
    def run_now(self, request):
        from crudkit_assistant.background import enqueue_runs  # background imports this module

        runs = enqueue_runs(self)
        return Response({"messages": [f"Started {len(runs)} run{'' if len(runs) == 1 else 's'} of {self}."]})


class AgentRun(BaseCrudKitModel):
    """One go of an Agent at one record: what it said, what it proposed (or,
    for a dry run, would have proposed) and the change set of what it applied."""

    TYPE_ID = "AGR"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="runs", editable=False)
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True, related_name="+", editable=False
    )
    target_object_id = CrudKitPositiveIntegerField(null=True, blank=True, editable=False)
    target = GenericForeignKey("target_content_type", "target_object_id")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, editable=False)
    dry_run = models.BooleanField(default=False, editable=False)
    trigger_info = models.JSONField(default=dict, blank=True, editable=False)
    change_set = models.UUIDField(default=uuid4, editable=False)
    output = models.TextField(blank=True, default="", editable=False)
    preview = models.JSONField(
        default=list, blank=True, editable=False, help_text="The proposals the run made, or would have made."
    )
    error = models.TextField(blank=True, default="", editable=False)
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    finished_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent} on {self.target or 'nothing'}" + (" (dry run)" if self.dry_run else "")

    @property
    def session_key(self) -> str:
        """Ties the run's proposals to it, as a conversation's do to the chat."""
        return f"agent-run:{self.pk}"

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        owner_access = True
        inline_create = False

        @staticmethod
        def get_authorized_queryset(user, queryset, action):
            return queryset.filter(agent__created_by=user)

    @crm_action("Revert this run", requires_approval=True)
    def revert(self, request):
        if not ChangeLog.objects.filter(change_set=self.change_set).exists():
            return Response({"errors": ["This run changed nothing."]}, status=400)
        try:
            result = revert_change_set(self.change_set, request.user)
        except ValueError as exc:
            return Response({"errors": [str(exc)]}, status=400)
        if "conflicts" in result:
            changed = ", ".join(f"{c['object']}.{c['field']}" for c in result["conflicts"])
            return Response({"errors": [f"Not reverted: changed since ({changed})"]}, status=400)
        return Response({"messages": [f"Reverted {result['reverted']} change(s) made by this run."]})
