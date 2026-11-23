from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CrudKitConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crudkit"

    def ready(self):
        import crudkit.checks  # noqa: F401  # App registry must load model classes first.
        import crudkit.signals  # noqa
        from crudkit.field_access import create_field_permissions

        # After every app's migrations, like Django's own model permissions.
        post_migrate.connect(create_field_permissions, dispatch_uid="crudkit.create_field_permissions")
