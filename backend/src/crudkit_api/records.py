"""
Record reads shared by the MCP server and the assistant: type descriptions,
filtered listing, saved views and single-record lookups, addressed by TYPE_ID
and CK-ID. Every call is filtered through the user's model, row and action
permissions. Invalid input raises ValueError, missing permissions
PermissionDenied; callers turn those into tool errors.
"""

from typing import Any

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import translation

from crudkit.authorization import (
    get_authorized_queryset,
    has_action_permission,
    has_model_permission,
    requires_approval,
)
from crudkit.models import ChangeLog, View, ck_id_regex, parse_ck_id
from crudkit.utils import get_model_types
from crudkit_api import services
from crudkit_api.filters import get_order_fields, order_queryset
from crudkit_api.serializers import get_serializer

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
FEED_LIMIT = 20
CHANGELOG_LIMIT = 10
# CrudKit's own bookkeeping models, and Django's (User carries a TYPE_ID so it
# can be addressed by CK-ID, but is not project data).
SKIPPED_APP_LABELS = {"admin", "auth", "contenttypes", "sessions"}
SKIPPED_FIELDS = {"deleted", "merged_into"}
AUDIT_FIELDS = {"created_by", "updated_by", "created_at", "updated_at"}


def get_exposed_models(mcp_allowlist: bool = True) -> list[type[models.Model]]:
    """Project models, minus CrudKit's and Django's own (unless they set
    `CrudKitSettings.ai_exposed`). CRUDKIT_MCP_MODELS (a list of TYPE_IDs)
    narrows this to an explicit allowlist, unless `mcp_allowlist` is False
    (the in-app assistant and agents aren't MCP clients)."""
    allowlist = getattr(settings, "CRUDKIT_MCP_MODELS", None) if mcp_allowlist else None
    return [
        model
        for type_id, model in get_model_types().items()
        if (type_id in allowlist if allowlist else True)
        and (not model._meta.app_label.startswith("crudkit") or _crudkit_settings(model, "ai_exposed"))
        and model._meta.app_label not in SKIPPED_APP_LABELS
        and not _crudkit_settings(model, "mcp_exclude")
    ]


def _crudkit_settings(model, name: str):
    return getattr(getattr(model, "CrudKitSettings", None), name, False)


def visible_models(user) -> list[type[models.Model]]:
    return [model for model in get_exposed_models() if has_model_permission(user, model, "view")]


def _verbose_names(model) -> tuple[str, str]:
    # Untranslated, so the description reads the same whatever language the request is in.
    with translation.override(None):
        return str(model._meta.verbose_name), str(model._meta.verbose_name_plural)


# ---------------------------------------------------------------------------
# Field descriptions


def _field_schema(f) -> dict | None:
    description = str(f.verbose_name) + (f" — {f.help_text}" if f.help_text else "")
    if f.choices:
        values = [value for value, _ in f.flatchoices]
        value_type = "integer" if all(isinstance(v, int) for v in values) else "string"
        return {"type": value_type, "enum": values, "description": description}
    if f.is_relation:
        related = f.related_model
        type_id = getattr(related, "TYPE_ID", None)
        if type_id:
            return {"type": "string", "description": f"{description}: {related._meta.verbose_name} ID ({type_id}123)"}
        return {"type": "integer", "description": f"{description}: {related._meta.verbose_name} ID"}
    for field_class, schema in (
        (models.BooleanField, {"type": "boolean"}),
        (models.DateTimeField, {"type": "string", "format": "date-time"}),
        (models.DateField, {"type": "string", "format": "date"}),
        (models.IntegerField, {"type": "integer"}),
        ((models.DecimalField, models.FloatField), {"type": "number"}),
        ((models.CharField, models.TextField, models.UUIDField), {"type": "string"}),
        (models.JSONField, {}),
    ):
        if isinstance(f, field_class):
            return {**schema, "description": description}
    return None


def _schema_fields(model) -> list[tuple[models.Field, dict]]:
    """Concrete fields that can be expressed as JSON-schema arguments."""
    generic_parts = set()
    for private in model._meta.private_fields:
        if isinstance(private, GenericForeignKey):
            generic_parts |= {private.ct_field, private.fk_field}
    out = []
    for f in model._meta.concrete_fields:
        if (
            f.primary_key
            or f.name in SKIPPED_FIELDS
            or f.name in generic_parts
            or getattr(f.remote_field, "parent_link", False)
            or isinstance(f, models.FileField)
        ):
            continue
        schema = _field_schema(f)
        if schema is not None:
            out.append((f, schema))
    return out


def writable_fields(model) -> list[tuple[models.Field, dict]]:
    return [
        (f, schema)
        for f, schema in _schema_fields(model)
        if f.editable and f.name not in AUDIT_FIELDS and not getattr(f, "ai_field", False)
    ]


def _filters(model) -> tuple[dict, dict[str, str]]:
    """The accepted `filters` keys and the ORM lookup each maps to."""
    described, lookups = {}, {}
    for f, schema in _schema_fields(model):
        if isinstance(f, models.JSONField):
            continue
        if isinstance(f, models.DateField):
            for suffix, lookup, label in (("from", "gte", "on or after"), ("to", "lte", "on or before")):
                described[f"{f.name}_{suffix}"] = {**schema, "description": f"{schema['description']} ({label})"}
                lookups[f"{f.name}_{suffix}"] = f"{f.name}__{lookup}"
        elif schema.get("type") == "string" and "enum" not in schema and not f.is_relation:
            described[f.name] = {**schema, "description": f"{schema['description']} (contains, case-insensitive)"}
            lookups[f.name] = f"{f.name}__icontains"
        else:
            described[f.name] = schema
            lookups[f.name] = f.name
    return described, lookups


def action_names(model) -> dict[str, str]:
    """{name: verbose name} of the model's @crm_actions, as BaseCrudKitModel._actions sees them."""
    return {
        name: func.verbose_name or name for name, func in model.__dict__.items() if getattr(func, "_crm_action", False)
    }


# ---------------------------------------------------------------------------
# Reads


def describe_types(user, type_id: str | None = None):
    """Without `type_id`, a short list of the visible types; with it, that
    type's filters, writable fields, actions and saved views."""
    if type_id:
        model = resolve_type(user, type_id)
        return {**_type_summary(model), **_type_detail(user, model)}
    return [_type_summary(model) for model in visible_models(user)]


def _type_summary(model) -> dict:
    verbose, plural = _verbose_names(model)
    return {"type": model.TYPE_ID, "name": verbose, "name_plural": plural}


def _type_detail(user, model) -> dict:
    filters, _ = _filters(model)
    can_change = has_model_permission(user, model, "change")
    return {
        "filters": filters,
        "searchable": bool(services.get_search_fields(model)),
        "fields": {f.name: schema for f, schema in writable_fields(model)},
        "required_on_create": [f.name for f, _ in writable_fields(model) if not f.blank and not f.has_default()],
        "actions": {
            name: {"label": label, "requires_approval": requires_approval(model, action=name)}
            for name, label in action_names(model).items()
        }
        if can_change
        else {},
        "approval_fields": list(getattr(model.CrudKitSettings, "approval_fields", [])),
        "can_create": has_model_permission(user, model, "add"),
        "can_update": can_change,
        "views": {view.id: view.name for view in _views(user).filter(model=model.TYPE_ID)},
    }


def search(user, query: str) -> list[dict[str, Any]]:
    return services.search_objects(user, query, get_exposed_models())


def list_records(
    user,
    type_id: str | None = None,
    view: str | None = None,
    filters: dict | None = None,
    query: str | None = None,
    order_by: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    """Records of one type, or of a saved view (its filters, ordering and columns)."""
    view_obj = get_view(user, view) if view else None
    model = resolve_type(user, view_obj.model if view_obj else type_id)
    if view_obj and type_id not in (None, view_obj.model):
        raise ValueError(f"{view_obj.id} is a view of {view_obj.model}, not {type_id}")
    _, lookups = _filters(model)
    filters = filters or {}
    if not isinstance(filters, dict):
        raise ValueError("`filters` must be an object of {field: value}")
    unknown = sorted(set(filters) - set(lookups))
    if unknown:
        raise ValueError(f"Unknown filter(s): {unknown}. Valid: {sorted(lookups)}")

    qs = visible(model, user, "view")
    for name, value in filters.items():
        if value not in (None, ""):
            qs = qs.filter(**{lookups[name]: value})
    if query:
        qs = qs.filter(services.search_filter(model, query))
    if view_obj:
        qs = view_obj.filter(qs, request=services.RequestShim(user))
    if order_by and order_by.lstrip("-") not in {f.name for f in model._meta.concrete_fields}:
        raise ValueError(f"Cannot order by {order_by!r}")
    qs = order_queryset(qs, get_order_fields(view_obj, order_by))
    limit = min(max(int(limit or DEFAULT_LIMIT), 1), MAX_LIMIT)
    offset = max(int(offset or 0), 0)
    fields = ["id", "label", *view_obj.fields] if view_obj else "__all__"
    return {"total": qs.count(), "results": serialize(model, qs[offset : offset + limit], depth=0, fields=fields)}


def get_record(user, object_id: str) -> dict:
    """One record with its recent feed, change log and the actions `user` may run."""
    model, instance = get_instance(user, object_id, "view")
    data = serialize(model, [instance], depth=1)[0]
    data["feed"] = services.get_feed(instance, FEED_LIMIT)
    if has_model_permission(user, ChangeLog, "view"):
        data["changelog"] = services.get_changelog(instance, CHANGELOG_LIMIT)
    data["actions"] = [name for name in action_names(model) if has_action_permission(user, instance, name)]
    return data


# ---------------------------------------------------------------------------
# Helpers


def resolve_type(user, type_id):
    model = get_model_types().get(type_id) if isinstance(type_id, str) else None
    if model is None or model not in get_exposed_models():
        raise ValueError(f"Unknown type {type_id!r}. Call describe_types for the available types.")
    if not has_model_permission(user, model, "view"):
        raise PermissionDenied
    return model


def visible(model, user, action: str):
    qs = get_authorized_queryset(user, model.objects.all(), action)
    if any(f.name == "deleted" for f in model._meta.concrete_fields):
        qs = qs.filter(deleted=False)
    return qs


def _views(user):
    return get_authorized_queryset(user, View.objects.all(), "view").filter(deleted=False)


def get_view(user, view_id) -> View:
    if not isinstance(view_id, str) or not ck_id_regex.fullmatch(view_id) or parse_ck_id(view_id)[0] != View.TYPE_ID:
        raise ValueError(f"Invalid view ID {view_id!r}; expected e.g. VIW3")
    view = _views(user).filter(pk=view_id).first()
    if view is None:
        raise ValueError(f"{view_id} not found")
    return view


def get_instance(user, object_id, action: str):
    if not isinstance(object_id, str) or not ck_id_regex.fullmatch(object_id):
        raise ValueError(f"Invalid ID {object_id!r}; expected e.g. CUS123")
    type_id, pk = parse_ck_id(object_id)
    model = resolve_type(user, type_id)
    instance = visible(model, user, action).filter(pk=pk).first()
    if instance is None:
        raise ValueError(f"{object_id} not found, or not available for {action}")
    return model, instance


def checked_fields(model, user, fields) -> dict:
    """Reject unknown fields and FK targets the user can't see. The REST
    serializer silently turns an unknown FK id into None, so check first."""
    if not isinstance(fields, dict) or not fields:
        raise ValueError("`fields` must be a non-empty object of {field: value}")
    return check_values(user, {f.name: f for f, _ in writable_fields(model)}, fields)


def check_values(user, writable: dict, fields: dict) -> dict:
    """`fields` only names fields in `writable` ({name: field}), and its FK
    values are rows that exist and `user` can see."""
    unknown = sorted(set(fields) - set(writable))
    if unknown:
        raise ValueError(f"Unknown or read-only field(s): {unknown}. Writable: {sorted(writable)}")
    for name, value in fields.items():
        f = writable[name]
        if f.is_relation and isinstance(value, dict):
            # The describe_object shape, {"id": ..., "display": ...}.
            value = value.get("id")
        if f.is_relation and value not in (None, ""):
            related = f.related_model
            qs = (
                get_authorized_queryset(user, related.objects.all(), "view")
                if getattr(related, "TYPE_ID", None)
                else related._default_manager.all()
            )
            if not qs.filter(pk=value).exists():
                raise ValueError(f"{name}: {related._meta.verbose_name} {value!r} not found")
    return fields


def serialize(model, rows, depth: int, fields="__all__") -> list[dict]:
    # One serializer for all rows, re-pointed per row: MoneyField reads the
    # currency from `parent.instance`.
    serializer = get_serializer(model, depth=depth, fields=fields)()
    data = []
    for obj in rows:
        serializer.instance = obj
        data.append(serializer.to_representation(obj))
    return data
