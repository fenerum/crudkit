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
from django.db.models import Avg, Count, Max, Min, Sum
from django.db.models.functions import Trunc
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
NUMERIC_FIELDS = (models.IntegerField, models.DecimalField, models.FloatField)
RANGE_FIELDS = (models.DateField, *NUMERIC_FIELDS)
# get_record's `fields` may also name these, which are not columns.
RECORD_EXTRAS = ("feed", "changelog")
PERIODS = ("day", "week", "month", "quarter", "year")
AGGREGATES = {"sum": Sum, "avg": Avg, "min": Min, "max": Max}
MAX_GROUP_BY = 2
DEFAULT_GROUPS = 100
MAX_GROUPS = 500


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


def readable_fields(model) -> dict[str, models.Field]:
    """{name: field} of the columns a caller may ask for by name. Password
    fields stay out, as they do in the serializer."""
    return {f.name: f for f, _ in _schema_fields(model) if not f.name.lower().endswith("password")}


def _numeric(f) -> bool:
    return isinstance(f, NUMERIC_FIELDS) and not f.choices


def _filters(model) -> tuple[dict, dict[str, str]]:
    """The accepted `filters` keys and the ORM lookup each maps to."""
    described, lookups = {}, {}

    def add(key, lookup, schema):
        described[key], lookups[key] = schema, lookup

    for f, schema in _schema_fields(model):
        if isinstance(f, models.JSONField):
            continue
        if isinstance(f, models.DateField):
            pass  # Dates only filter by range.
        elif schema.get("type") == "string" and "enum" not in schema and not f.is_relation:
            add(
                f.name,
                f"{f.name}__icontains",
                {**schema, "description": f"{schema['description']} (contains, case-insensitive)"},
            )
        else:
            add(f.name, f.name, schema)
        if isinstance(f, RANGE_FIELDS) and not f.choices:
            for suffix, lookup, label in (("from", "gte", "on or after"), ("to", "lte", "on or before")):
                add(
                    f"{f.name}_{suffix}",
                    f"{f.name}__{lookup}",
                    {**schema, "description": f"{schema['description']} ({label})"},
                )
        if f.null:
            add(
                f"{f.name}_isnull",
                f"{f.name}__isnull",
                {"type": "boolean", "description": f"{schema['description']} is empty"},
            )
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
        "columns": list(readable_fields(model)),
        "aggregatable": [name for name, f in readable_fields(model).items() if _numeric(f)],
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
    fields: list[str] | None = None,
) -> dict:
    """Records of one type, or of a saved view (its filters, ordering and columns).
    `fields` picks the columns, overriding the view's."""
    model, view_obj, qs = _queryset(user, type_id, view, filters, query)
    if order_by and order_by.lstrip("-") not in {f.name for f in model._meta.concrete_fields}:
        raise ValueError(f"Cannot order by {order_by!r}")
    qs = order_queryset(qs, get_order_fields(view_obj, order_by))
    limit = min(max(int(limit or DEFAULT_LIMIT), 1), MAX_LIMIT)
    offset = max(int(offset or 0), 0)
    if fields:
        columns = _with_id_label(_checked_columns(model, fields))
    else:
        columns = _with_id_label(view_obj.fields) if view_obj else "__all__"
    return {"total": qs.count(), "results": serialize(model, qs[offset : offset + limit], depth=0, fields=columns)}


def aggregate_records(
    user,
    type_id: str | None = None,
    view: str | None = None,
    filters: dict | None = None,
    query: str | None = None,
    group_by: list[str] | None = None,
    metrics: list[str] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> dict:
    """Count, sum, average, min or max over the records list_records would
    return, grouped by up to MAX_GROUP_BY fields or date periods
    (`created_at:month`)."""
    model, _, qs = _queryset(user, type_id, view, filters, query)
    columns = readable_fields(model)
    plain, truncated = [], {}
    for entry in _names(group_by, "group_by"):
        name, _, period = entry.partition(":")
        f = columns.get(name)
        if f is None or isinstance(f, models.JSONField):
            raise ValueError(f"Cannot group by {name!r}. Valid: {list(columns)}")
        if not period:
            plain.append(name)
        elif isinstance(f, models.DateField) and period in PERIODS:
            truncated[f"{name}_{period}"] = Trunc(name, period, output_field=models.DateField())
        else:
            raise ValueError(f"Cannot group by {entry!r}: date fields take :{'|:'.join(PERIODS)}")
    keys = [*plain, *truncated]
    if len(keys) > MAX_GROUP_BY:
        raise ValueError(f"Group by at most {MAX_GROUP_BY} fields")

    annotations = {}
    for entry in _names(metrics, "metrics") or ["count"]:
        func, _, name = entry.partition(":")
        f = columns.get(name)
        if entry == "count":
            annotations["count"] = Count("pk")
        elif func not in AGGREGATES or f is None:
            raise ValueError(f"Unknown metric {entry!r}: use count, or sum|avg|min|max:<field>")
        elif not (_numeric(f) if func in ("sum", "avg") else isinstance(f, RANGE_FIELDS)):
            raise ValueError(
                f"Cannot {func} {name!r}: needs a {'numeric' if func in ('sum', 'avg') else 'numeric or date'} field"
            )
        else:
            annotations[f"{func}_{name}"] = AGGREGATES[func](name)

    qs = qs.order_by()
    total = qs.count()
    if not keys:
        return {"total": total, "groups": [_jsonable(qs.aggregate(**annotations))], "truncated": False}
    if order_by and order_by.lstrip("-") not in [*keys, *annotations]:
        raise ValueError(f"Cannot order by {order_by!r}. Valid: {[*keys, *annotations]}")
    rows = qs.values(*plain, **truncated).annotate(**annotations).order_by(*([order_by] if order_by else []), *keys)
    limit = min(max(int(limit or DEFAULT_GROUPS), 1), MAX_GROUPS)
    rows = list(rows[: limit + 1])
    groups = [_jsonable(row) for row in rows[:limit]]
    for name in plain:
        if columns[name].is_relation:
            labels = _labels(user, columns[name].related_model, {group[name] for group in groups})
            for group in groups:
                group[f"{name}_label"] = labels.get(group[name])
    return {"total": total, "groups": groups, "truncated": len(rows) > limit}


def get_record(user, object_id: str, fields: list[str] | None = None) -> dict:
    """One record with its recent feed, change log and the actions `user` may
    run. `fields` picks the columns, and `feed`/`changelog` only if named."""
    model, instance = get_instance(user, object_id, "view")
    if fields:
        wanted = _checked_columns(model, fields, RECORD_EXTRAS)
        columns = _with_id_label([name for name in wanted if name not in RECORD_EXTRAS])
    else:
        wanted, columns = RECORD_EXTRAS, "__all__"
    data = serialize(model, [instance], depth=1, fields=columns)[0]
    if "feed" in wanted:
        data["feed"] = services.get_feed(instance, FEED_LIMIT)
    if "changelog" in wanted and has_model_permission(user, ChangeLog, "view"):
        data["changelog"] = services.get_changelog(instance, CHANGELOG_LIMIT)
    data["actions"] = [name for name in action_names(model) if has_action_permission(user, instance, name)]
    return data


# ---------------------------------------------------------------------------
# Helpers


def _queryset(user, type_id, view, filters, query):
    """`(model, view, queryset)`: the visible records of `type_id` or of the
    saved `view`, narrowed by `filters` and the free-text `query`."""
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
        if value in (None, ""):
            continue
        lookup = lookups[name]
        if isinstance(value, list):
            if "__" in lookup:
                raise ValueError(f"Filter {name!r} takes one value, not a list")
            lookup += "__in"
        qs = qs.filter(**{lookup: value})
    if query:
        qs = qs.filter(services.search_filter(model, query))
    if view_obj:
        qs = view_obj.filter(qs, request=services.RequestShim(user))
    return model, view_obj, qs


def _names(value, argument: str) -> list[str]:
    """A list of names; a lone string counts as a list of one."""
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or not all(isinstance(name, str) for name in value):
        raise ValueError(f"`{argument}` must be a list of names")
    return value


def _checked_columns(model, fields, extras=()) -> list[str]:
    names = _names(fields, "fields")
    valid = ["id", "label", *readable_fields(model), *extras]
    unknown = sorted(set(names) - set(valid))
    if unknown:
        raise ValueError(f"Unknown field(s): {unknown}. Valid: {valid}")
    return names


def _with_id_label(columns) -> list[str]:
    return list(dict.fromkeys(["id", "label", *columns]))


def _jsonable(row: dict) -> dict:
    return {key: value.isoformat() if hasattr(value, "isoformat") else value for key, value in row.items()}


def _related_queryset(user, related):
    if getattr(related, "TYPE_ID", None):
        return get_authorized_queryset(user, related.objects.all(), "view")
    return related._default_manager.all()


def _labels(user, related, pks) -> dict:
    """{pk: label} of the `related` rows among `pks` that `user` may see."""
    return {obj.pk: str(obj) for obj in _related_queryset(user, related).filter(pk__in=pks - {None})}


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
            if not _related_queryset(user, related).filter(pk=value).exists():
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
