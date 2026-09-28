from django.apps import AppConfig


class CrudkitAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crudkit_assistant"
    verbose_name = "CrudKit Assistant"

    def ready(self):
        from crudkit_assistant import signals  # noqa: F401 -- connects the receivers
