"""Test-only urlconf: the crudkit_frontend catch-all on its own."""

from django.urls import include, path

urlpatterns = [
    path("", include("crudkit_frontend.urls")),
]
