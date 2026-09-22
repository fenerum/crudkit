"""
The MCP tool set. Fixed in number and name — records are addressed by TYPE_ID
and CK-ID, so the same tools serve any CrudKit project:

    describe_types, search, list_records, get_record

and, with the `write` scope and CRUDKIT_MCP_WRITE_ENABLED:

    create_record, update_record, run_action, add_note

`describe_types` is the schema tool: it reports each type's filters, writable
fields and actions, which `list_records`/`create_record`/… then take as a
`filters`/`fields` object. Every call is filtered through the token user's
model, row and action permissions.

Projects add or override tools with CRUDKIT_MCP_EXTRA_TOOLS: dotted paths to
`Tool` instances. Their handlers must do their own permission checks.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import translation
from django.utils.module_loading import import_string

from crudkit.authorization import get_authorized_queryset, has_action_permission, has_model_permission
from crudkit.models import ck_id_regex, get_accepted_type_ids, parse_ck_id
from crudkit.utils import get_model_types
from crudkit_api import services
from crudkit_api.serializers import get_serializer
from crudkit_mcp.conf import write_enabled

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
FEED_LIMIT = 20
CHANGELOG_LIMIT = 10
# CrudKit's own bookkeeping models, and Django's (User carries a TYPE_ID so it
# can be addressed by CK-ID, but is not project data).
SKIPPED_APP_LABELS = {"admin", "auth", "contenttypes", "sessions"}
SKIPPED_FIELDS = {"deleted", "merged_into"}
AUDIT_FIELDS = {"created_by", "updated_by", "created_at", "updated_at"}

ID_DESCRIPTION = "Record ID, TYPE_ID-prefixed (e.g. CUS123)"


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[[Any, dict], Any]
    input_schema: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    scope: str = "read"
    annotations: dict | None = None

    def definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": self.annotations or {"readOnlyHint": self.scope == "read"},
        }


def get_tools(user, scopes: list[str]) -> dict[str, Tool]:
    """The tools `user` may call with a token granting `scopes`."""
    types = _type_schema(user)
    tools = [
        Tool(
            "describe_types",
            "List the record types, and for one type its filters, writable fields and actions. "
            "Call this before list_records or any write tool.",
            _describe_types,
            _schema({"type": types}),
        ),
        Tool(
            "search",
            "Search across all record types by text. Returns matching records as {id, label}.",
            _search,
            _schema({"query": {"type": "string"}}, ["query"]),
        ),
        Tool(
            "list_records",
            "List records of one type. Returns {total, results}. `filters` keys come from "
            "describe_types; unknown keys are rejected.",
            _list_records,
            _schema(
                {
                    "type": types,
                    "filters": {"type": "object", "description": "Field filters, see describe_types"},
                    "query": {"type": "string", "description": "Free-text search over the type's search fields"},
                    "order_by": {"type": "string", "description": "Field to sort by; prefix with '-' for descending"},
                    "limit": {
                        "type": "integer",
                        "description": f"Max results (default {DEFAULT_LIMIT}, max {MAX_LIMIT})",
                    },
                    "offset": {"type": "integer", "description": "Number of results to skip"},
                },
                ["type"],
            ),
        ),
        Tool(
            "get_record",
            "Get one record by ID, including its recent activity feed, change log and available actions.",
            _get_record,
            _schema({"id": {"type": "string", "description": ID_DESCRIPTION}}, ["id"]),
        ),
    ]
    if write_enabled() and "write" in scopes:
        tools += _write_tools(types)
    by_name = {tool.name: tool for tool in tools}
    by_name.update({tool.name: tool for tool in map(import_string, getattr(settings, "CRUDKIT_MCP_EXTRA_TOOLS", []))})
    return {
        name: tool
        for name, tool in by_name.items()
        if tool.scope in scopes and (tool.scope != "write" or write_enabled())
    }


def _write_tools(types: dict) -> list[Tool]:
    changing = {"readOnlyHint": False, "destructiveHint": True}
    return [
        Tool(
            "create_record",
            "Create a record. `fields` keys come from describe_types. Returns the created record.",
            _create_record,
            _schema({"type": types, "fields": {"type": "object"}}, ["type", "fields"]),
            scope="write",
            annotations={"readOnlyHint": False, "destructiveHint": False},
        ),
        Tool(
            "update_record",
            "Update fields on a record. Only the given fields change. Returns the updated record.",
            _update_record,
            _schema(
                {"id": {"type": "string", "description": ID_DESCRIPTION}, "fields": {"type": "object"}},
                ["id", "fields"],
            ),
            scope="write",
            annotations={**changing, "idempotentHint": True},
        ),
        Tool(
            "run_action",
            "Run one of a record's actions, as listed by describe_types or get_record.",
            _run_action,
            _schema(
                {"id": {"type": "string", "description": ID_DESCRIPTION}, "action": {"type": "string"}},
                ["id", "action"],
            ),
            scope="write",
            annotations=changing,
        ),
        Tool(
            "add_note",
            "Add a note to a record's activity feed.",
            _add_note,
            _schema(
                {"id": {"type": "string", "description": ID_DESCRIPTION}, "body": {"type": "string"}},
                ["id", "body"],
            ),
            scope="write",
            annotations={"readOnlyHint": False, "destructiveHint": False},
        ),
    ]


def get_exposed_models() -> list[type[models.Model]]:
    """Project models, minus CrudKit's and Django's own. CRUDKIT_MCP_MODELS
    (a list of TYPE_IDs) narrows this to an explicit allowlist."""
    allowlist = getattr(settings, "CRUDKIT_MCP_MODELS", None)
    return [
        model
        for type_id, model in get_model_types().items()
        if (type_id in allowlist if allowlist else True)
        and not model._meta.app_label.startswith("crudkit")
        and model._meta.app_label not in SKIPPED_APP_LABELS
        and not getattr(getattr(model, "CrudKitSettings", None), "mcp_exclude", False)
    ]


def _visible_models(user) -> list[type[models.Model]]:
    return [model for model in get_exposed_models() if has_model_permission(user, model, "view")]


def _type_schema(user) -> dict:
    return {
        "type": "string",
        "enum": [model.TYPE_ID for model in _visible_models(user)],
        "description": "Record type (TYPE_ID), see describe_types",
    }


def _verbose_names(model) -> tuple[str, str]:
    # Untranslated, so the description reads the same whatever language the request is in.
    with translation.override(None):
        return str(model._meta.verbose_name), str(model._meta.verbose_name_plural)


# ---------------------------------------------------------------------------
# Field descriptions


def _schema(properties: dict, required: list[str] | None = None) -> dict:
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


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


def _writable_fields(model) -> list[tuple[models.Field, dict]]:
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


def _action_names(model) -> dict[str, str]:
    """{name: verbose name} of the model's @crm_actions, as BaseCrudKitModel._actions sees them."""
    return {
        name: func.verbose_name or name for name, func in model.__dict__.items() if getattr(func, "_crm_action", False)
    }


# ---------------------------------------------------------------------------
# Handlers


def _describe_types(user, arguments: dict):
    if type_id := arguments.get("type"):
        model = _resolve_type(user, type_id)
        return {**_type_summary(model), **_type_detail(user, model)}
    # The overview stays short; ask for one type to get its fields.
    return [_type_summary(model) for model in _visible_models(user)]


def _type_summary(model) -> dict:
    verbose, plural = _verbose_names(model)
    return {"type": model.TYPE_ID, "name": verbose, "name_plural": plural}


def _type_detail(user, model) -> dict:
    filters, _ = _filters(model)
    can_change = has_model_permission(user, model, "change")
    return {
        "filters": filters,
        "searchable": bool(services.get_search_fields(model)),
        "fields": {f.name: schema for f, schema in _writable_fields(model)},
        "required_on_create": [f.name for f, _ in _writable_fields(model) if not f.blank and not f.has_default()],
        "actions": _action_names(model) if can_change else {},
        "can_create": has_model_permission(user, model, "add"),
        "can_update": can_change,
    }


def _search(user, arguments: dict):
    query = (arguments.get("query") or "").strip()
    if not query:
        return "No query provided"
    return services.search_objects(user, query, get_exposed_models()) or "No results found"


def _list_records(user, arguments: dict) -> dict:
    model = _resolve_type(user, arguments.get("type"))
    _, lookups = _filters(model)
    filters = arguments.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("`filters` must be an object of {field: value}")
    unknown = sorted(set(filters) - set(lookups))
    if unknown:
        raise ValueError(f"Unknown filter(s): {unknown}. Valid: {sorted(lookups)}")

    qs = _visible(model, user, "view")
    for name, value in filters.items():
        if value not in (None, ""):
            qs = qs.filter(**{lookups[name]: value})
    if query := arguments.get("query"):
        qs = qs.filter(services.search_filter(model, query))
    if order_by := arguments.get("order_by"):
        if order_by.lstrip("-") not in {f.name for f in model._meta.concrete_fields}:
            raise ValueError(f"Cannot order by {order_by!r}")
        qs = qs.order_by(order_by)
    limit = min(max(int(arguments.get("limit") or DEFAULT_LIMIT), 1), MAX_LIMIT)
    offset = max(int(arguments.get("offset") or 0), 0)
    return {"total": qs.count(), "results": _serialize(model, qs[offset : offset + limit], depth=0)}


def _get_record(user, arguments: dict) -> dict:
    model, instance = _get_instance(user, arguments.get("id"), "view")
    data = _serialize(model, [instance], depth=1)[0]
    data["feed"] = services.get_feed(instance, FEED_LIMIT)
    data["changelog"] = services.get_changelog(instance, CHANGELOG_LIMIT)
    data["actions"] = [name for name in _action_names(model) if has_action_permission(user, instance, name)]
    return data


def _create_record(user, arguments: dict) -> dict:
    model = _resolve_type(user, arguments.get("type"))
    if not has_model_permission(user, model, "add"):
        raise PermissionDenied
    fields = _checked_fields(model, user, arguments.get("fields"))
    instance = services.create_object(model, fields, user)
    return _serialize(model, [instance], depth=0)[0]


def _update_record(user, arguments: dict) -> dict:
    model, instance = _get_instance(user, arguments.get("id"), "change")
    fields = _checked_fields(model, user, arguments.get("fields"))
    services.patch_fields(instance, fields, user)
    instance.refresh_from_db()
    return _serialize(model, [instance], depth=0)[0]


def _run_action(user, arguments: dict) -> dict:
    _, instance = _get_instance(user, arguments.get("id"), "change")
    return services.run_action(instance, arguments.get("action"), user)


def _add_note(user, arguments: dict) -> dict:
    _, instance = _get_instance(user, arguments.get("id"), "change")
    return services.create_note(instance, arguments.get("body"), user)


# ---------------------------------------------------------------------------
# Helpers


def _resolve_type(user, type_id):
    model = get_model_types().get(type_id) if isinstance(type_id, str) else None
    if model is None or model not in get_exposed_models():
        raise ValueError(f"Unknown type {type_id!r}. Call describe_types for the available types.")
    if not has_model_permission(user, model, "view"):
        raise PermissionDenied
    return model


def _visible(model, user, action: str):
    qs = get_authorized_queryset(user, model.objects.all(), action)
    if any(f.name == "deleted" for f in model._meta.concrete_fields):
        qs = qs.filter(deleted=False)
    return qs


def _get_instance(user, object_id, action: str):
    if not isinstance(object_id, str) or not ck_id_regex.fullmatch(object_id):
        raise ValueError(f"Invalid ID {object_id!r}; expected e.g. CUS123")
    type_id, pk = parse_ck_id(object_id)
    model = _resolve_type(user, type_id)
    # An MTI child shares its parent's pk column, so address it by its own TYPE_ID.
    if type_id not in get_accepted_type_ids(model):
        raise ValueError(f"{object_id!r} is not a {model._meta.verbose_name} ID")
    instance = _visible(model, user, action).filter(pk=pk).first()
    if instance is None:
        raise ValueError(f"{object_id} not found, or not available for {action}")
    return model, instance


def _checked_fields(model, user, fields) -> dict:
    """Reject unknown fields and FK targets the user can't see. The REST
    serializer silently turns an unknown FK id into None, so check first."""
    if not isinstance(fields, dict) or not fields:
        raise ValueError("`fields` must be a non-empty object of {field: value}")
    writable = {f.name: f for f, _ in _writable_fields(model)}
    unknown = sorted(set(fields) - set(writable))
    if unknown:
        raise ValueError(f"Unknown or read-only field(s): {unknown}. Writable: {sorted(writable)}")
    for name, value in fields.items():
        f = writable[name]
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


def _serialize(model, rows, depth: int) -> list[dict]:
    # One serializer for all rows, re-pointed per row: MoneyField reads the
    # currency from `parent.instance`.
    serializer = get_serializer(model, depth=depth)()
    data = []
    for obj in rows:
        serializer.instance = obj
        data.append(serializer.to_representation(obj))
    return data
