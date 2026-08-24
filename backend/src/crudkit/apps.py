from django.apps import AppConfig


class CrudKitConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crudkit"

    def ready(self):
        import crudkit.checks  # noqa: F401  # App registry must load model classes first.
        import crudkit.signals  # noqa
