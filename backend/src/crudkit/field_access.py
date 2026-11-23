"""Field permissions: who may see and change one field of a record type.

Built on Django's own permissions, so roles are ordinary Groups. A model
declares its sensitive fields:

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        field_permissions = {"special_terms": "change", "margin": "view"}

- `"change"`: everyone who may see the record sees the field; changing it
  needs `<app>.change_<model>_<field>`.
- `"view"`: seeing it also needs `<app>.view_<model>_<field>` (or the change
  permission), and it is hidden from everyone else.

The permissions are created on `migrate` (see `create_field_permissions`) and
handed out to groups or people like any other. Checks go through
`user.has_perm`, so superusers, inactive users and custom auth backends behave
as everywhere else in Django. Code running without a person (no user) is
never limited.

Every reader and writer of records (the REST API, the metadata endpoint, MCP,
the assistant, imports, bulk edits and undo) asks this module, so a field is
hidden or read-only the same way everywhere.
"""

from django.core.exceptions import PermissionDenied

VIEW = "view"
EDIT = "edit"
CHANGE = "change"
LEVELS = (VIEW, CHANGE)


def declared(model) -> dict[str, str]:
    """`{field: "view" | "change"}`: the model's `CrudKitSettings.field_permissions`."""
    return dict(getattr(getattr(model, "CrudKitSettings", None), "field_permissions", None) or {})


def codename(model, field: str, action: str) -> str:
    return f"{action}_{model._meta.model_name}_{field}"


def permission_name(model, field: str, action: str) -> str:
    """The full permission, as `user.has_perm` takes it: `crm.change_opportunity_special_terms`."""
    return f"{model._meta.app_label}.{codename(model, field, action)}"


def field_access(user, model) -> dict[str, str | None]:
    """`{field: "view" | "edit" | None}` for the fields of `model` with field
    permissions; None means hidden. Fields left out are open."""
    rules = declared(model)
    if not rules or user is None:
        return {}
    access: dict[str, str | None] = {}
    for field, level in rules.items():
        if user.has_perm(permission_name(model, field, CHANGE)):
            access[field] = EDIT
        elif level == CHANGE or user.has_perm(permission_name(model, field, VIEW)):
            access[field] = VIEW
        else:
            access[field] = None
    return access


def hidden_fields(user, model) -> set[str]:
    """Fields of `model` that `user` may not see."""
    return {name for name, level in field_access(user, model).items() if level is None}


def read_only_fields(user, model) -> set[str]:
    """Fields of `model` that `user` may not change: the hidden ones too."""
    return {name for name, level in field_access(user, model).items() if level != EDIT}


def require_editable_fields(user, model, names) -> None:
    """Raise PermissionDenied naming the fields of `names` that `user` may not change."""
    blocked = sorted(set(names) & read_only_fields(user, model))
    if blocked:
        raise PermissionDenied(f"You may not change {', '.join(blocked)}")


def permissions_for(model) -> list[tuple[str, str]]:
    """`(codename, name)` of the permissions the model's field permissions need."""
    out = []
    for field, level in declared(model).items():
        try:
            label = str(model._meta.get_field(field).verbose_name)
        except Exception:
            label = field
        out.append((codename(model, field, CHANGE), f"Can change {label} of {model._meta.verbose_name}"))
        if level == VIEW:
            out.append((codename(model, field, VIEW), f"Can view {label} of {model._meta.verbose_name}"))
    return out


def create_field_permissions(**kwargs) -> None:
    """Create the Permission rows every model's field permissions need, as
    Django creates model permissions after `migrate`."""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    from crudkit.utils import get_model_types

    for model in get_model_types().values():
        wanted = permissions_for(model)
        if not wanted:
            continue
        content_type = ContentType.objects.get_for_model(model, for_concrete_model=False)
        for code, name in wanted:
            Permission.objects.get_or_create(content_type=content_type, codename=code, defaults={"name": name[:255]})
