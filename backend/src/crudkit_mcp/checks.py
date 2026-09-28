from django.conf import settings
from django.core import checks
from django.core.exceptions import ImproperlyConfigured

from crudkit_mcp.conf import write_enabled, write_rate

PER_PROCESS_CACHES = ("django.core.cache.backends.locmem.LocMemCache", "django.core.cache.backends.dummy.DummyCache")


@checks.register()
def check_write_rate(app_configs, **kwargs):
    """CRUDKIT_MCP_WRITE_RATE is parsed on the first MCP write; report a typo at startup instead."""
    try:
        rate = write_rate()
    except (ImproperlyConfigured, ValueError) as exc:
        return [checks.Error(f"CRUDKIT_MCP_WRITE_RATE is invalid: {exc}", hint='e.g. "60/min"', id="crudkit_mcp.E001")]
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if rate is not None and write_enabled() and backend in PER_PROCESS_CACHES:
        return [
            checks.Warning(
                "CRUDKIT_MCP_WRITE_RATE is counted in the default cache, which is per process "
                f"({backend.rsplit('.', 1)[-1]}): each worker allows the full rate, or none are counted.",
                hint="Use a shared cache (Redis, Memcached or the database cache) in production.",
                id="crudkit_mcp.W001",
            )
        ]
    return []
