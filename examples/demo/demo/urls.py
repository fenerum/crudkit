from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("crudkit_api.urls")),
    # Catch-all for the bundled SPA — must stay last.
    path("", include("crudkit_frontend.urls")),
]
