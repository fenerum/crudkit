"""Per-role field access: who may see and change each field of a record type.

Rules are `FieldAccess` rows. A field without rules is open to everyone who may
see the record. Once a field has rules, a person gets the best access among
the rules for the roles they hold (`RoleMember`) and the rule for everyone
else (a rule without a role). A person no rule covers doesn't see the field.
Superusers, and code running without a person (no user), are never limited.

Every reader and writer of records (the REST API, the metadata endpoint, MCP,
the assistant, imports, bulk edits and undo) asks this module, so a field is
hidden or read-only the same way everywhere.
"""

from django.core.exceptions import PermissionDenied

VIEW = "view"
EDIT = "edit"
_RANK = {None: 0, VIEW: 1, EDIT: 2}


def _type_ids(model) -> list[str]:
    """The model's TYPE_ID and those of the types it extends: a rule on a
    parent type's field holds for the extending type too."""
    ids = [getattr(model, "TYPE_ID", None)]
    ids += [getattr(parent, "TYPE_ID", None) for parent in model._meta.get_parent_list()]
    return [type_id for type_id in ids if type_id]


def _unrestricted(user) -> bool:
    return user is None or getattr(user, "is_superuser", False)


def field_access(user, model) -> dict[str, str | None]:
    """`{field: "view" | "edit" | None}` for the fields of `model` that have
    rules; None means hidden. Fields left out are open."""
    if _unrestricted(user) or not getattr(user, "is_authenticated", False):
        return {} if _unrestricted(user) else _anonymous(model)
    from crudkit.models import FieldAccess, RoleMember

    rules = list(
        FieldAccess.objects.filter(model__in=_type_ids(model), deleted=False).values_list("field", "role_id", "access")
    )
    if not rules:
        return {}
    roles = set(
        RoleMember.objects.filter(user=user, deleted=False, role__deleted=False).values_list("role_id", flat=True)
    )
    access: dict[str, str | None] = {}
    for field, role_id, level in rules:
        granted = level if role_id is None or role_id in roles else None
        if _RANK[granted] >= _RANK[access.get(field)]:
            access[field] = granted
    return access


def _anonymous(model) -> dict[str, str | None]:
    """Someone not signed in: every restricted field is hidden."""
    from crudkit.models import FieldAccess

    fields = FieldAccess.objects.filter(model__in=_type_ids(model), deleted=False).values_list("field", flat=True)
    return dict.fromkeys(fields)


def hidden_fields(user, model) -> set[str]:
    """Fields of `model` that `user` may not see."""
    return {name for name, level in field_access(user, model).items() if level is None}


def read_only_fields(user, model) -> set[str]:
    """Fields of `model` that `user` may not change: the hidden ones too."""
    return {name for name, level in field_access(user, model).items() if level != EDIT}


def can_view_field(user, model, name: str) -> bool:
    return name not in hidden_fields(user, model)


def can_edit_field(user, model, name: str) -> bool:
    return name not in read_only_fields(user, model)


def require_editable_fields(user, model, names) -> None:
    """Raise PermissionDenied naming the first of `names` that `user` may not change."""
    blocked = sorted(set(names) & read_only_fields(user, model))
    if blocked:
        raise PermissionDenied(f"You may not change {', '.join(blocked)}")
