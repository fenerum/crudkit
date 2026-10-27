"""Helpers shared by the unittest suite and the BDD behaviour suite."""

from django.contrib.auth.models import Permission


def grant(user, model, *actions):
    """Give ``user`` the ``<action>_<model>`` permissions, e.g. ``grant(alice, Customer, "view")``."""
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label=model._meta.app_label,
            codename__in=[f"{action}_{model._meta.model_name}" for action in actions],
        )
    )
