from django.conf import settings
from django.urls import reverse


def write_enabled() -> bool:
    return getattr(settings, "CRUDKIT_MCP_WRITE_ENABLED", False)


def supported_scopes() -> list[str]:
    return ["read", "write"] if write_enabled() else ["read"]


def base_url(request) -> str:
    """The public origin. CRUDKIT_MCP_BASE_URL overrides the request's, e.g.
    behind a proxy that rewrites Host/scheme."""
    base = getattr(settings, "CRUDKIT_MCP_BASE_URL", None) or request.build_absolute_uri("/")
    return base.rstrip("/")


def absolute_url(request, url_name: str) -> str:
    return base_url(request) + reverse(url_name)
