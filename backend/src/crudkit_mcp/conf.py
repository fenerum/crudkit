from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse


def write_enabled() -> bool:
    return getattr(settings, "CRUDKIT_MCP_WRITE_ENABLED", False)


RATE_PERIODS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def write_rate() -> tuple[int, str] | None:
    """CRUDKIT_MCP_WRITE_RATE ("60/min", "1000/day", ...) as (count, period
    name); None when unlimited."""
    rate = getattr(settings, "CRUDKIT_MCP_WRITE_RATE", "60/min")
    if not rate:
        return None
    count, unit = rate.split("/")
    period = next((name for name in RATE_PERIODS if name.startswith(unit.strip())), None)
    if period is None:
        raise ImproperlyConfigured(f"CRUDKIT_MCP_WRITE_RATE: unknown period {unit!r}")
    return int(count), period


def supported_scopes() -> list[str]:
    return ["read", "write"] if write_enabled() else ["read"]


def base_url(request) -> str:
    """The public origin. CRUDKIT_MCP_BASE_URL overrides the request's, e.g.
    behind a proxy that rewrites Host/scheme."""
    base = getattr(settings, "CRUDKIT_MCP_BASE_URL", None) or request.build_absolute_uri("/")
    return base.rstrip("/")


def absolute_url(request, url_name: str) -> str:
    return base_url(request) + reverse(url_name)
