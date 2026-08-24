from django.core.exceptions import PermissionDenied
from django.db.models import Model, QuerySet


def get_permission_action(method: str, view_action: str | None = None) -> str:
    if view_action in {"create", "initial_data"}:
        return "add"
    if view_action in {"update", "partial_update", "merge", "call_action"}:
        return "change"
    if view_action == "destroy":
        return "delete"
    return "view"


def has_model_permission(user, model: type[Model], action: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    permission = f"{model._meta.app_label}.{action}_{model._meta.model_name}"
    return user.has_perm(permission)


def get_authorized_queryset(user, queryset: QuerySet, action: str = "view") -> QuerySet:
    model = queryset.model
    if not has_model_permission(user, model, action):
        return queryset.none()
    if getattr(user, "is_superuser", False):
        return queryset

    settings = getattr(model, "CrudKitSettings", None)
    authorize = getattr(settings, "get_authorized_queryset", None)
    return authorize(user, queryset, action) if authorize else queryset


def has_object_permission(user, instance: Model, action: str = "view") -> bool:
    queryset = get_authorized_queryset(user, instance.__class__._default_manager.all(), action)
    return queryset.filter(pk=instance.pk).exists()


def require_object_permission(user, instance: Model, action: str = "view") -> None:
    if not has_object_permission(user, instance, action):
        raise PermissionDenied


def has_action_permission(user, instance: Model, action_name: str) -> bool:
    if not has_object_permission(user, instance, "change"):
        return False
    settings = getattr(instance.__class__, "CrudKitSettings", None)
    authorize = getattr(settings, "has_action_permission", None)
    return authorize(user, instance, action_name) if authorize else True


def require_action_permission(user, instance: Model, action_name: str) -> None:
    if not has_action_permission(user, instance, action_name):
        raise PermissionDenied
