"""Catch-all URLconf for the SPA shell.

Include this LAST in the project urlconf so real routes (admin, API, ...)
win; every other path serves the SPA and client-side routing takes over.
"""

from django.urls import re_path

from crudkit_frontend import views

urlpatterns = [
    re_path(r"^.*$", views.spa, name="crudkit_spa"),
]
