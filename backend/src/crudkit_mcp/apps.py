from django.apps import AppConfig

from crudkit_mcp import checks  # noqa: F401  (registers the system checks)


class CrudkitMcpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crudkit_mcp"
    verbose_name = "CrudKit MCP"
