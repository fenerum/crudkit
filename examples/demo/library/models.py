from django.db import models

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
