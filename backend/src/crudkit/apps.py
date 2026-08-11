from django.apps import AppConfig


class CrudKitConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crudkit"

    def ready(self):
        import crudkit.signals  # noqa
