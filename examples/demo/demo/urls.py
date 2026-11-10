from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("crudkit_mcp.urls")),
    path("api/v1/", include("crudkit_api.urls")),
    path("", include("crudkit_mcp.well_known_urls")),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
    # Catch-all for the bundled SPA — must stay last.
    path("", include("crudkit_frontend.urls")),
]
