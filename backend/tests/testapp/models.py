"""Fixture models for the django-crudkit test suite.

These stand in for a consuming project's domain models (the package's tests
were originally written against a CRM).
"""

from typing import ClassVar

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from crudkit.decorators import crm_action
from crudkit.fields import AIBooleanField, AIForeignKeyField, AISummaryField, AITagsField, MoneyField
from crudkit.models import BaseCrudKitModel, CrudKitPositiveIntegerField, WYSIWYGEditorField


class Topic(BaseCrudKitModel):
    TYPE_ID = "TOP"
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class Customer(BaseCrudKitModel):
    TYPE_ID = "CUS"

    class StatusChoices(models.TextChoices):
        ACTIVE = "active"
        CHURNED = "churned"

    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=StatusChoices.choices, default=StatusChoices.ACTIVE)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    balance = MoneyField(null=True, blank=True)

    def __str__(self):
        return self.name

    @crm_action(verbose_name="Mark churned")
    def mark_churned(self, request):
        self.status = self.StatusChoices.CHURNED
        self.save(update_fields=["status", "updated_at"])
        return self

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        allowed_prefills: ClassVar[list] = ["name", "email", "topic"]
        search_fields: ClassVar[list] = ["name", "email"]


class Ticket(BaseCrudKitModel):
    TYPE_ID = "TIC"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    subject = models.CharField(max_length=512, null=True)
    body = WYSIWYGEditorField(null=True, blank=True)

    topic = AIForeignKeyField(Topic, prompt="Identify the most relevant topic for this ticket.")
    summary = AISummaryField(prompt="Concise 2-3 sentence summary of this ticket.")
    is_urgent = AIBooleanField(prompt="Is this ticket urgent?")
    tags = AITagsField(prompt="Short lowercase tags describing this ticket.")

    def get_ai_context(self) -> str:
        parts = [f"Subject: {self.subject}"]
        if self.customer:
            parts.append(f"Customer: {self.customer.name}")
        for comment in self.comment_set.filter(deleted=False).order_by("created_at"):
            parts.append(f"Comment: {comment.body}")
        return "\n".join(parts)

    def __str__(self):
        return self.subject or f"Ticket {self.pk}"

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        allowed_prefills: ClassVar[list] = ["subject", "customer"]
        search_fields: ClassVar[list] = ["subject"]
        ai_trigger_children: ClassVar[list] = [("Comment", "ticket")]


class Comment(BaseCrudKitModel):
    TYPE_ID = "COM"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    body = models.TextField()

    def __str__(self):
        return self.body[:50]


class Reminder(BaseCrudKitModel):
    """Fixture model with a generic FK to any CrudKit object, used to test
    CK-ID (TYPE_ID-prefixed) serialization of generic object-id columns."""

    TYPE_ID = "REM"

    related_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, editable=False)
    related_object_id = CrudKitPositiveIntegerField(editable=False)
    target = GenericForeignKey("related_content_type", "related_object_id")

    note = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return self.note or f"Reminder {self.pk}"


class UrgentComment(Comment):
    """Multi-table-inheritance child of Comment with its own TYPE_ID, used to
    test that serialization uses the subclass prefix (URG) rather than the
    parent's (COM)."""

    TYPE_ID = "URG"

    escalation_reason = models.CharField(max_length=255, blank=True, default="")
