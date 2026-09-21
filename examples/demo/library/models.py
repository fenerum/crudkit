from django.db import models
from rest_framework.response import Response

from crudkit.decorators import crm_action
from crudkit.models import BaseCrudKitModel


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

    def __str__(self):
        return self.name

    @crm_action(verbose_name="Mark finished")
    def mark_finished(self, request):
        self.status = self.Status.FINISHED
        self.save(update_fields=["status", "updated_at"])
        return Response({"messages": [f"{self} marked finished"]})

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["name"]
