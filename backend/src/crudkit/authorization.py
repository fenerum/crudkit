from django.core.exceptions import PermissionDenied
from django.db.models import Model, QuerySet

from crudkit.utils import get_model_types


def get_permission_action(method: str, view_action: str | None = None) -> str:
    if view_action in {"create", "initial_data"}:
        return "add"
    if view_action in {"update", "partial_update", "merge", "call_action", "restore"}:
        return "change"
    if view_action == "destroy":
        return "delete"
    return "view"


OWNER_ACTIONS = {"view", "change"}


def _has_django_permission(user, model: type[Model], action: str) -> bool:
    return user.has_perm(f"{model._meta.app_label}.{action}_{model._meta.model_name}")


def _owner_access(model: type[Model], action: str) -> bool:
    return action in OWNER_ACTIONS and getattr(getattr(model, "CrudKitSettings", None), "owner_access", False)


def has_model_permission(user, model: type[Model], action: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return _has_django_permission(user, model, action) or _owner_access(model, action)


def get_authorized_queryset(user, queryset: QuerySet, action: str = "view") -> QuerySet:
    model = queryset.model
    if not has_model_permission(user, model, action):
        return queryset.none()
    if getattr(user, "is_superuser", False):
        return queryset
    if _owner_access(model, action) and not _has_django_permission(user, model, action):
        queryset = queryset.filter(created_by=user)

    settings = getattr(model, "CrudKitSettings", None)
    authorize = getattr(settings, "get_authorized_queryset", None)
    return authorize(user, queryset, action) if authorize else queryset


def get_authorized_instance(user, type_id: str, pk: int, action: str = "view"):
    model = get_model_types().get(type_id)
    if model is None:
        return None
    queryset = get_authorized_queryset(user, model.objects.all(), action)
    if hasattr(model, "deleted"):
        queryset = queryset.filter(deleted=False)
    return queryset.filter(pk=pk).first()


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


def requires_approval(model: type[Model], action: str | None = None, fields=None) -> bool:
    """Whether MCP clients and agents may only propose running `action` or
    writing `fields` on `model`: the action is a `@crm_action(requires_approval=True)`
    or a field is in `CrudKitSettings.approval_fields`."""
    if action and getattr(getattr(model, action, None), "requires_approval", False):
        return True
    approval_fields = getattr(getattr(model, "CrudKitSettings", None), "approval_fields", [])
    return bool(fields and set(approval_fields) & set(fields))
