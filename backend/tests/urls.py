from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("crudkit_mcp.urls")),
    path("api/v1/", include("crudkit_api.urls")),
    path("", include("crudkit_mcp.well_known_urls")),
]
