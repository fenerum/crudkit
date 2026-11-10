import time

from django.core.mail import EmailMessage
from django.db import models
from django.utils import timezone
from rest_framework.response import Response

from crudkit import jobs
from crudkit.decorators import crm_action
from crudkit.models import BaseCrudKitModel, EmailWYSIWYGEditorField, FeedEntry, WYSIWYGEditorField
from library.tasks import fetch_reviews


class Author(BaseCrudKitModel):
    TYPE_ID = "AUT"
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["name"]


class Book(BaseCrudKitModel):
    TYPE_ID = "BOK"
    title = models.CharField(max_length=255, verbose_name="name")
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    published_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["title"]
        allowed_prefills = ["title", "author"]


class Reading(BaseCrudKitModel):
    """A book on someone's reading list; exercises the board-style views."""

    TYPE_ID = "RDG"

    class Status(models.TextChoices):
        TO_READ = "to_read", "To read"
        READING = "reading", "Reading"
        FINISHED = "finished", "Finished"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        HIGH = "high", "High"

    name = models.CharField(max_length=255)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TO_READ)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.LOW)
    pages = models.PositiveIntegerField(null=True, blank=True)
    rating = models.PositiveIntegerField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    @crm_action(verbose_name="Mark finished", requires_approval=True)
    def mark_finished(self, request):
        self.status = self.Status.FINISHED
        self.save(update_fields=["status", "updated_at"])
        return Response({"messages": [f"{self} marked finished"]})

    # Show off task progress: one runs during the click, one in the background.
    @crm_action(verbose_name="Count pages")
    def count_pages(self, request):
        steps = 8
        for step in range(1, steps + 1):
            time.sleep(0.4)
            jobs.progress(step, total=steps, message=f"Chapter {step}")
        self.pages = steps * 40
        self.save(update_fields=["pages", "updated_at"])

    @crm_action(verbose_name="Look up reviews")
    def look_up_reviews(self, request):
        fetch_reviews.delay(jobs.hand_off().pk)

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["name"]
        celebrate = {"status": ["finished"]}


class Call(BaseCrudKitModel):
    """A phone call with an author, logged from the author's feed."""

    TYPE_ID = "CAL"

    author = models.ForeignKey(Author, on_delete=models.CASCADE, null=True, blank=True)
    summary = models.CharField(max_length=255)
    minutes = models.PositiveIntegerField(null=True, blank=True)
    notes = WYSIWYGEditorField(null=True, blank=True)

    def __str__(self):
        return self.summary

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["summary"]
        allowed_prefills = ["author"]
        feed_entry = FeedEntry(fields=["summary", "minutes", "notes"], icon="phone", verb="logged a call", on=["AUT"])


class Email(BaseCrudKitModel):
    """An email to an author, written and sent from the author's feed, with files attached."""

    TYPE_ID = "EML"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"

    author = models.ForeignKey(Author, on_delete=models.CASCADE, null=True, blank=True)
    to = models.EmailField()
    cc = models.CharField(max_length=255, blank=True, help_text="Addresses separated by commas")
    subject = models.CharField(max_length=255)
    body = EmailWYSIWYGEditorField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, editable=False)
    sent_at = models.DateTimeField(null=True, blank=True, editable=False)

    def __str__(self):
        return self.subject

    @classmethod
    def from_query_params(cls, params, kwargs=None):
        email = super().from_query_params(params, kwargs)
        if "reply_to" in params:
            original = cls.objects.get(pk=params["reply_to"])
            email.author = original.author
            email.to = original.to
            email.subject = original.subject if original.subject.startswith("Re: ") else f"Re: {original.subject}"
            email.body = f"<p></p><blockquote>{original.body or ''}</blockquote>"
        return email

    @crm_action(verbose_name="Send")
    def send(self, request):
        if self.status == self.Status.SENT:
            return Response({"messages": ["This email was already sent"]}, status=400)
        cc = [address.strip() for address in self.cc.split(",") if address.strip()]
        message = EmailMessage(self.subject, self.body or "", to=[self.to], cc=cc)
        message.content_subtype = "html"
        for attachment in self.emailattachment_set.filter(deleted=False):
            message.attach(attachment.filename, attachment.file.read(), attachment.content_type or None)
        message.send()
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at", "updated_at"])
        return Response({"messages": [f"Email sent to {self.to}"]})

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["subject", "to"]
        allowed_prefills = ["author", "to", "subject", "body"]
        feed_entry = FeedEntry(
            fields=["to", "cc", "subject", "status", "body"],
            icon="mail",
            verb="emailed",
            action="send",
            reply=True,
            attachments="EMA",
            on=["AUT"],
        )


class EmailAttachment(BaseCrudKitModel):
    TYPE_ID = "EMA"

    email = models.ForeignKey(Email, on_delete=models.CASCADE)
    file = models.FileField(upload_to="email-attachments/")
    filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return self.filename or self.file.name
