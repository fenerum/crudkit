"""
The MCP tool set. Fixed in number and name — records are addressed by TYPE_ID
and CK-ID, so the same tools serve any CrudKit project:

    describe_types, search, list_records, aggregate_records, get_record

and, with the `write` scope and CRUDKIT_MCP_WRITE_ENABLED, or the `propose`
scope and crudkit_assistant installed:

    create_record, update_record, run_action, add_note, undo

With `propose` the write tools only file an AssistantProposal for the token's
user to confirm in their Inbox. With `write` they change records directly,
except for approval-required actions and fields
(crudkit.authorization.requires_approval), which are proposed as well.

`describe_types` is the schema tool: it reports each type's filters, writable
fields and actions, which `list_records`/`create_record`/… then take as a
`filters`/`fields` object. `describe_types` also lists a type's saved views;
`list_records` with a `view` returns that view's rows, filtered, ordered and
trimmed to its columns as in the UI. `aggregate_records` answers counts, sums
and trends server-side, so clients needn't page through rows, and the read
tools take a `fields` list so they return only the columns asked for. Every
call is filtered through the token user's model, row and action permissions.

Projects add or override tools with CRUDKIT_MCP_EXTRA_TOOLS: dotted paths to
`Tool` instances. Their handlers must do their own permission checks.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils.module_loading import import_string

from crudkit.audit import current as current_audit
from crudkit.authorization import has_model_permission, requires_approval
from crudkit_api import records, services
from crudkit_api.records import DEFAULT_GROUPS, DEFAULT_LIMIT, MAX_GROUP_BY, MAX_GROUPS, MAX_LIMIT, PERIODS
from crudkit_mcp.conf import proposals_enabled, write_mode

ID_DESCRIPTION = "Record ID, TYPE_ID-prefixed (e.g. CUS123)"
FIELDS_DESCRIPTION = (
    "Columns to return, from describe_types `columns`; id and label are always included. "
    "Ask only for the columns you need"
)
FILTERS_DESCRIPTION = (
    "Field filters, keys from describe_types `filters`: <field>_from/<field>_to for date and number "
    "ranges, <field>_isnull: true|false, and a list value on an exact-match field matches any of its values"
)
QUERY_DESCRIPTION = "Free-text search over the type's search fields, or a record ID"
VIEW_DESCRIPTION = "Saved view ID (e.g. VIW3), see describe_types. Applies the view's filters"


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
            "Search across all record types by text or record ID (e.g. CUS123). Returns matching records as {id, label}.",
            _search,
            _schema({"query": {"type": "string"}}, ["query"]),
        ),
        Tool(
            "list_records",
            "List records of one type, or of a saved view. Returns {total, results}. Give `type` "
            "or `view`. `filters` keys come from describe_types; unknown keys are rejected. Pass `fields` "
            "to get only the columns you need. For counts, totals or trends use aggregate_records "
            "instead of paging through rows.",
            _list_records,
            _schema(
                {
                    "type": types,
                    "view": {"type": "string", "description": f"{VIEW_DESCRIPTION}, ordering and columns"},
                    "filters": {"type": "object", "description": FILTERS_DESCRIPTION},
                    "query": {"type": "string", "description": QUERY_DESCRIPTION},
                    "fields": _names_schema(FIELDS_DESCRIPTION),
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
            "aggregate_records",
            "Count, sum, average, min or max records of one type or saved view, optionally grouped by "
            "fields or by date period, e.g. leads created per month: group_by ['created_at:month']. "
            "Returns {total, groups: [{<group keys>, count, sum_<field>, ...}], truncated}; foreign key "
            "groups also get <field>_label. Use this for any question about counts, totals or trends "
            "rather than listing records.",
            _aggregate_records,
            _schema(
                {
                    "type": types,
                    "view": {"type": "string", "description": VIEW_DESCRIPTION},
                    "filters": {"type": "object", "description": FILTERS_DESCRIPTION},
                    "query": {"type": "string", "description": QUERY_DESCRIPTION},
                    "group_by": _names_schema(
                        f"Up to {MAX_GROUP_BY} fields from describe_types `columns`; a date field takes a "
                        f"period, <field>:{'|'.join(PERIODS)}, grouped as <field>_<period>"
                    ),
                    "metrics": _names_schema(
                        "Default ['count']. Also sum:<field>, avg:<field> (fields in describe_types "
                        "`aggregatable`), min:<field>, max:<field> (numbers and dates)"
                    ),
                    "order_by": {
                        "type": "string",
                        "description": "A group key or metric (e.g. -count); prefix with '-' for descending. "
                        "Default: by group keys",
                    },
                    "limit": {
                        "type": "integer",
                        "description": f"Max groups (default {DEFAULT_GROUPS}, max {MAX_GROUPS})",
                    },
                },
            ),
        ),
        Tool(
            "get_record",
            "Get one record by ID, including its recent activity feed, change log and available actions. "
            "Pass `fields` to get only the columns you need.",
            _get_record,
            _schema(
                {
                    "id": {"type": "string", "description": ID_DESCRIPTION},
                    "fields": _names_schema(
                        f"{FIELDS_DESCRIPTION}. With `fields`, feed and changelog are only included if named"
                    ),
                },
                ["id"],
            ),
        ),
    ]
    mode = write_mode(scopes)
    if mode:
        tools += _write_tools(types, propose=mode == "propose")
    # Extra write tools write directly, so they need the `write` scope.
    extras = [
        tool
        for tool in map(import_string, getattr(settings, "CRUDKIT_MCP_EXTRA_TOOLS", []))
        if tool.scope != "write" or mode == "write"
    ]
    by_name = {tool.name: tool for tool in [*tools, *extras]}
    return {name: tool for name, tool in by_name.items() if tool.scope in scopes or (tool.scope == "write" and mode)}


PROPOSE_NOTE = (
    " Nothing changes yet: returns {status: pending_approval, proposal} and the user confirms or skips "
    "the proposal in their Inbox."
)
APPROVAL_NOTE = (
    " Changes to a type's approval_fields, and actions with requires_approval (see describe_types), "
    "are not made: they return {status: pending_approval, proposal} for the user to confirm in their Inbox."
)


def _write_tools(types: dict, propose: bool) -> list[Tool]:
    changing = {"readOnlyHint": False, "destructiveHint": not propose}
    adding = {"readOnlyHint": False, "destructiveHint": False}
    note = PROPOSE_NOTE if propose else ""
    approval_note = PROPOSE_NOTE if propose else APPROVAL_NOTE
    return [
        Tool(
            "create_record",
            "Create a record. `fields` keys come from describe_types. Returns the created record." + approval_note,
            partial(_create_record, propose=propose),
            _schema({"type": types, "fields": {"type": "object"}}, ["type", "fields"]),
            scope="write",
            annotations=adding,
        ),
        Tool(
            "update_record",
            "Update fields on a record. Only the given fields change. Returns the updated record." + approval_note,
            partial(_update_record, propose=propose),
            _schema(
                {"id": {"type": "string", "description": ID_DESCRIPTION}, "fields": {"type": "object"}},
                ["id", "fields"],
            ),
            scope="write",
            annotations={**changing, "idempotentHint": True},
        ),
        Tool(
            "run_action",
            "Run one of a record's actions, as listed by describe_types or get_record." + approval_note,
            partial(_run_action, propose=propose),
            _schema(
                {"id": {"type": "string", "description": ID_DESCRIPTION}, "action": {"type": "string"}},
                ["id", "action"],
            ),
            scope="write",
            annotations=changing,
        ),
        Tool(
            "add_note",
            "Add a note to a record's activity feed." + note,
            partial(_add_note, propose=propose),
            _schema(
                {"id": {"type": "string", "description": ID_DESCRIPTION}, "body": {"type": "string"}},
                ["id", "body"],
            ),
            scope="write",
            annotations=adding,
        ),
        Tool(
            "undo",
            "Revert a change set: every change one earlier write made, as returned in its `change_set` "
            "or listed in get_record's changelog. Returns `conflicts` and changes nothing if the records "
            "were changed since, unless `force` is true." + note,
            partial(_undo, propose=propose),
            _schema(
                {"change_set": {"type": "string", "description": "Change set UUID"}, "force": {"type": "boolean"}},
                ["change_set"],
            ),
            scope="write",
            annotations=changing,
        ),
    ]


def _type_schema(user) -> dict:
    return {
        "type": "string",
        "enum": [model.TYPE_ID for model in records.visible_models(user)],
        "description": "Record type (TYPE_ID), see describe_types",
    }


def _names_schema(description: str) -> dict:
    return {"type": "array", "items": {"type": "string"}, "description": description}


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
        fields=arguments.get("fields"),
    )


def _aggregate_records(user, arguments: dict) -> dict:
    return records.aggregate_records(
        user,
        type_id=arguments.get("type"),
        view=arguments.get("view"),
        filters=arguments.get("filters"),
        query=arguments.get("query"),
        group_by=arguments.get("group_by"),
        metrics=arguments.get("metrics"),
        order_by=arguments.get("order_by"),
        limit=arguments.get("limit"),
    )


def _get_record(user, arguments: dict) -> dict:
    return records.get_record(user, arguments.get("id"), fields=arguments.get("fields"))


def _create_record(user, arguments: dict, propose=False) -> dict:
    model = records.resolve_type(user, arguments.get("type"))
    if not has_model_permission(user, model, "add"):
        raise PermissionDenied
    fields = records.checked_fields(model, user, arguments.get("fields"))
    if propose or requires_approval(model, fields=fields):
        label = f"Create {model._meta.verbose_name}"
        return _propose(user, model, None, "create", {"type": model.TYPE_ID, "fields": fields}, label)
    instance = services.create_object(model, fields, user)
    return records.serialize(model, [instance], depth=0)[0]


def _update_record(user, arguments: dict, propose=False) -> dict:
    model, instance = records.get_instance(user, arguments.get("id"), "change")
    fields = records.checked_fields(model, user, arguments.get("fields"))
    if propose or requires_approval(model, fields=fields):
        return _propose(user, model, instance, "patch", {"fields": fields})
    services.patch_fields(instance, fields, user)
    instance.refresh_from_db()
    return records.serialize(model, [instance], depth=0)[0]


def _run_action(user, arguments: dict, propose=False) -> dict:
    model, instance = records.get_instance(user, arguments.get("id"), "change")
    action = arguments.get("action")
    if propose or requires_approval(model, action=action):
        services.check_action(instance, action, user)
        label = f"Run {records.action_names(model)[action]}"
        return _propose(user, model, instance, "action", {"action": action}, label)
    return services.run_action(instance, action, user)


def _add_note(user, arguments: dict, propose=False) -> dict:
    model, instance = records.get_instance(user, arguments.get("id"), "change")
    if propose:
        body = (arguments.get("body") or "").strip()
        if not body:
            raise ValueError("Note body is empty")
        return _propose(user, model, instance, "note", {"body": body}, f"Add note: {body.splitlines()[0][:80]}")
    return services.create_note(instance, arguments.get("body"), user)


def _undo(user, arguments: dict, propose=False) -> dict:
    change_set = uuid.UUID(str(arguments.get("change_set")))
    # Undoing a change to an approval field (or an approval-required action) is
    # itself that change, so it needs approval too.
    if propose or services.revert_requires_approval(change_set):
        newest = services.check_revertible(change_set)[0]
        type_id = newest.related_content_type.model_class().TYPE_ID
        model, instance = records.get_instance(user, f"{type_id}{newest.related_object_id}", "change")
        label = f"Undo change {str(change_set)[:8]}"
        return _propose(user, model, instance, "revert", {"change_set": str(change_set)}, label)
    return services.revert_change_set(change_set, user, force=bool(arguments.get("force")))


def _propose(user, model, instance, kind: str, payload: dict, label: str = "") -> dict:
    """File the change as an AssistantProposal for `user` to confirm, instead of making it."""
    if not proposals_enabled():
        raise ValueError("This change needs approval, and approvals need crudkit_assistant installed")
    # Importable only when crudkit_assistant is installed, which proposals_enabled() checked.
    from crudkit_assistant.proposals import create_proposal, patch_label

    proposal = create_proposal(
        user,
        model,
        instance,
        kind,
        label or patch_label(payload["fields"]),
        payload,
        source="mcp",
        client=current_audit().client,
    )
    return {
        "status": "pending_approval",
        "proposal": proposal.id,
        "label": proposal.label,
        "message": "Nothing has changed yet. The user confirms or skips this proposal in their Inbox.",
    }
