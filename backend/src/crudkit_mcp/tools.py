"""
The MCP tool set. Fixed in number and name — records are addressed by TYPE_ID
and CK-ID, so the same tools serve any CrudKit project:

    describe_types, search, list_records, get_record

and, with the `write` scope and CRUDKIT_MCP_WRITE_ENABLED:

    create_record, update_record, run_action, add_note

`describe_types` is the schema tool: it reports each type's filters, writable
fields and actions, which `list_records`/`create_record`/… then take as a
`filters`/`fields` object. `describe_types` also lists a type's saved views;
`list_records` with a `view` returns that view's rows, filtered, ordered and
trimmed to its columns as in the UI. Every call is filtered through the token user's
model, row and action permissions.

Projects add or override tools with CRUDKIT_MCP_EXTRA_TOOLS: dotted paths to
`Tool` instances. Their handlers must do their own permission checks.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils.module_loading import import_string

from crudkit.authorization import has_model_permission
from crudkit_api import records, services
from crudkit_api.records import DEFAULT_LIMIT, MAX_LIMIT
from crudkit_mcp.conf import write_enabled

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
            "List the record types, and for one type its filters, writable fields, actions and saved views. "
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
            "List records of one type, or of a saved view. Returns {total, results}. Give `type` "
            "or `view`. `filters` keys come from describe_types; unknown keys are rejected.",
            _list_records,
            _schema(
                {
                    "type": types,
                    "view": {
                        "type": "string",
                        "description": "Saved view ID (e.g. VIW3), see describe_types. Applies the view's "
                        "filters, ordering and columns",
                    },
                    "filters": {"type": "object", "description": "Field filters, see describe_types"},
                    "query": {"type": "string", "description": "Free-text search over the type's search fields"},
                    "order_by": {"type": "string", "description": "Field to sort by; prefix with '-' for descending"},
                    "limit": {
                        "type": "integer",
                        "description": f"Max results (default {DEFAULT_LIMIT}, max {MAX_LIMIT})",
                    },
                    "offset": {"type": "integer", "description": "Number of results to skip"},
                },
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


def _type_schema(user) -> dict:
    return {
        "type": "string",
        "enum": [model.TYPE_ID for model in records.visible_models(user)],
        "description": "Record type (TYPE_ID), see describe_types",
    }


def _schema(properties: dict, required: list[str] | None = None) -> dict:
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


# ---------------------------------------------------------------------------
# Handlers


def _describe_types(user, arguments: dict):
    return records.describe_types(user, arguments.get("type"))


def _search(user, arguments: dict):
    query = (arguments.get("query") or "").strip()
    if not query:
        return "No query provided"
    return records.search(user, query) or "No results found"


def _list_records(user, arguments: dict) -> dict:
    return records.list_records(
        user,
        type_id=arguments.get("type"),
        view=arguments.get("view"),
        filters=arguments.get("filters"),
        query=arguments.get("query"),
        order_by=arguments.get("order_by"),
        limit=arguments.get("limit"),
        offset=arguments.get("offset"),
    )


def _get_record(user, arguments: dict) -> dict:
    return records.get_record(user, arguments.get("id"))


def _create_record(user, arguments: dict) -> dict:
    model = records.resolve_type(user, arguments.get("type"))
    if not has_model_permission(user, model, "add"):
        raise PermissionDenied
    fields = records.checked_fields(model, user, arguments.get("fields"))
    instance = services.create_object(model, fields, user)
    return records.serialize(model, [instance], depth=0)[0]


def _update_record(user, arguments: dict) -> dict:
    model, instance = records.get_instance(user, arguments.get("id"), "change")
    fields = records.checked_fields(model, user, arguments.get("fields"))
    services.patch_fields(instance, fields, user)
    instance.refresh_from_db()
    return records.serialize(model, [instance], depth=0)[0]


def _run_action(user, arguments: dict) -> dict:
    _, instance = records.get_instance(user, arguments.get("id"), "change")
    return services.run_action(instance, arguments.get("action"), user)


def _add_note(user, arguments: dict) -> dict:
    _, instance = records.get_instance(user, arguments.get("id"), "change")
    return services.create_note(instance, arguments.get("body"), user)
