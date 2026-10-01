"""
Tools the assistant agent can call.

Split into two physically-separate groups:

- Read tools: run inline, return data. Record tools take an optional `id`
  (CK-ID) and default to the record open on the user's screen; the
  cross-record tools (search, list_records, …) share their logic with MCP
  via crudkit_api.records.
- Proposal tools: do NOT mutate. They persist an AssistantProposal row,
  emit a tool_call_pending WS event, and return a "pending" string. The
  actual mutation only runs in AssistantConsumer.confirm_proposal() when
  the staff user clicks Confirm.

The proposal tools talk to the consumer via an asyncio.Queue exposed on
the RunContext.deps shim attached by the runner.
"""

import logging
import uuid
from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from pydantic_ai import RunContext

from crudkit.authorization import (
    get_authorized_instance,
    has_action_permission,
    has_model_permission,
)
from crudkit.models import ChangeLog, parse_ck_id
from crudkit_api import records, services
from crudkit_api.metadata import build_instance_metadata, related_queryset, reverse_relations
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import AssistantProposal
from crudkit_assistant.proposals import create_proposal, patch_label

logger = logging.getLogger(__name__)

MAX_BULK_IDS = 100


def describe_call(tool_name: str, args: dict) -> str:
    """A short, human description of a tool call for the sidebar's activity list."""
    target = args.get("id") or "the open record"
    count = len(args.get("ids") or []) if isinstance(args.get("ids"), list) else 0
    labels = {
        "get_object": f"Reading {target}",
        "describe_object": f"Checking the fields of {target}",
        "get_changelog": f"Reading the history of {target}",
        "get_feed": f"Reading the activity on {target}",
        "get_related": f"Reading {args.get('relation_name')} of {target}",
        "search": f"Searching for “{args.get('query')}”",
        "describe_types": f"Looking up {args.get('type') or 'the record types'}",
        "list_records": f"Listing {args.get('view') or args.get('type') or 'records'}",
        "get_record": f"Reading {args.get('id')}",
        "get_screen_rows": f"Reading the {args.get('which') or 'selected'} rows",
        "propose_patch": f"Drafting a change to {target}",
        "propose_bulk_patch": f"Drafting changes to {count} record{'' if count == 1 else 's'}",
        "propose_action": f"Drafting {args.get('action_name')} on {target}",
        "propose_create_note": f"Drafting a note on {target}",
        "propose_create": f"Drafting a new {args.get('type') or 'record'}",
        "propose_revert": "Drafting an undo",
    }
    return labels.get(tool_name, f"Running {tool_name}")


# ---------------------------------------------------------------------------
# Read tools


def _load_user(deps: AssistantDeps):
    return get_user_model().objects.get(pk=deps.user_id)


def _load_instance(deps: AssistantDeps, object_id: str | None, action: str = "view"):
    """`(instance, error)` for `object_id`, else the record open on screen."""
    object_id = object_id or deps.screen.record_id
    if not object_id:
        return None, "No record is open; pass `id` (e.g. CUS123)."
    try:
        type_id, pk = parse_ck_id(object_id)
    except ValueError:
        return None, f"Invalid id {object_id!r}; expected e.g. CUS123."
    instance = get_authorized_instance(_load_user(deps), type_id, pk, action)
    if instance is None:
        return None, f"{object_id} not found, or not available for {action}."
    return instance, None


async def get_object(ctx: RunContext[AssistantDeps], id: str | None = None) -> str:
    """Return a textual summary of a record (default: the one open on screen)."""

    def _run():
        instance, error = _load_instance(ctx.deps, id)
        if instance is None:
            return f"ERROR: {error}"
        return f"{instance.__class__._meta.verbose_name} {instance.id}\n{instance.get_ai_context()}"

    return await sync_to_async(_run)()


async def describe_object(ctx: RunContext[AssistantDeps], id: str | None = None) -> dict[str, Any]:
    """Return the schema of a record (default: the one open on screen): every writable field with its
    type, current value, valid choices (for choice fields), and — for
    foreign keys — the list of related rows the model is allowed to pick
    from. Also lists the available @crm_actions.

    Call this BEFORE any `propose_patch` or `propose_action`. Never invent
    field values, choice strings, or action names — they must appear in
    this payload."""

    def _run():
        instance, error = _load_instance(ctx.deps, id)
        if instance is None:
            return {"error": error}
        return build_instance_metadata(instance, user=_load_user(ctx.deps))

    return await sync_to_async(_run)()


async def get_changelog(
    ctx: RunContext[AssistantDeps], id: str | None = None, limit: int = 20
) -> list[dict[str, Any]] | str:
    """Return up to `limit` recent ChangeLog entries for a record (default: the one open on screen).

    Each entry has {at, by, action, source, client, label, change_set,
    field_changes: {field: [old, new]}}. Entries sharing a change_set were made
    together and can be undone together with propose_revert.
    """

    def _run():
        instance, error = _load_instance(ctx.deps, id)
        if instance is None:
            return f"ERROR: {error}"
        if not has_model_permission(_load_user(ctx.deps), ChangeLog, "view"):
            return "ERROR: this user may not view change history."
        return services.get_changelog(instance, limit)

    return await sync_to_async(_run)()


async def get_feed(
    ctx: RunContext[AssistantDeps], id: str | None = None, limit: int = 20
) -> list[dict[str, Any]] | str:
    """Return up to `limit` recent FeedItems (notes, related-object events) on a record
    (default: the one open on screen)."""

    def _run():
        instance, error = _load_instance(ctx.deps, id)
        return services.get_feed(instance, limit) if instance is not None else f"ERROR: {error}"

    return await sync_to_async(_run)()


async def get_related(
    ctx: RunContext[AssistantDeps], relation_name: str, id: str | None = None, limit: int = 20
) -> list[dict[str, Any]] | str:
    """List the records pointing at a record (default: the one open on screen)
    through one of the relations in describe_object's `related`, e.g.
    'ticket_set' (or its TYPE_ID, 'TIC'). Returns up to `limit` rows
    summarised via get_ai_context()."""

    def _run():
        instance, error = _load_instance(ctx.deps, id)
        if instance is None:
            return f"ERROR: {error}"
        user = _load_user(ctx.deps)
        relations = reverse_relations(instance.__class__, user)
        relation = next(
            (
                rel
                for rel in relations
                if relation_name in (rel.get_accessor_name(), rel.name, rel.related_model.TYPE_ID)
            ),
            None,
        )
        if relation is None:
            valid = [f"{rel.get_accessor_name()} ({rel.related_model.TYPE_ID})" for rel in relations]
            return f"ERROR: Unknown relation {relation_name!r}. Valid: {valid}"
        return [
            {"id": str(obj.pk), "context": obj.get_ai_context()}
            for obj in related_queryset(instance, relation, user)[:limit]
        ]

    return await sync_to_async(_run)()


async def _records_call(ctx: RunContext[AssistantDeps], fn, *args, **kwargs):
    def _run():
        try:
            return fn(_load_user(ctx.deps), *args, **kwargs)
        except PermissionDenied:
            return {"error": "Permission denied."}
        except ValueError as exc:
            return {"error": str(exc)}

    return await sync_to_async(_run)()


async def search(ctx: RunContext[AssistantDeps], query: str) -> list[dict[str, Any]] | dict:
    """Search all record types by text or record ID (e.g. CUS123). Returns matching records as {id, label}."""
    return await _records_call(ctx, records.search, query)


async def describe_types(ctx: RunContext[AssistantDeps], type: str | None = None) -> list | dict:
    """Without `type`, list the record types (TYPE_IDs). With a TYPE_ID, that type's
    filters, writable fields, actions and saved views (view ids like VIW3)."""
    return await _records_call(ctx, records.describe_types, type)


async def list_records(
    ctx: RunContext[AssistantDeps],
    type: str | None = None,
    view: str | None = None,
    filters: dict[str, Any] | None = None,
    query: str | None = None,
    order_by: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """List records of one type, or of a saved view (e.g. the view on screen).
    Returns {total, results}. `filters` keys come from describe_types."""
    return await _records_call(
        ctx,
        records.list_records,
        type_id=type,
        view=view,
        filters=filters,
        query=query,
        order_by=order_by,
        limit=limit,
        offset=offset,
    )


async def get_record(ctx: RunContext[AssistantDeps], id: str) -> dict:
    """One record by id, with its recent feed, change log and available actions."""
    return await _records_call(ctx, records.get_record, id)


async def get_screen_rows(ctx: RunContext[AssistantDeps], which: str = "selected") -> list[dict[str, Any]]:
    """The rows on the user's screen, summarised: `which` is "selected" (falls
    back to the visible rows when nothing is selected) or "visible"."""
    screen = ctx.deps.screen
    ids = screen.selected_ids if which == "selected" and screen.selected_ids else screen.visible_ids

    def _run():
        user = _load_user(ctx.deps)
        out = []
        for object_id in ids:
            try:
                _, instance = records.get_instance(user, object_id, "view")
            except (ValueError, PermissionDenied):
                continue
            out.append({"id": object_id, "context": instance.get_ai_context()})
        return out

    return await sync_to_async(_run)()


# ---------------------------------------------------------------------------
# Proposal tools (no mutation — only persist + emit)


def _file_proposal(deps: AssistantDeps, user, model, instance, kind: str, label: str, payload: dict, reasoning: str):
    """Persist a proposal and return its pending envelope. On a dry run
    nothing is saved: the envelope (with no id) is all there is."""
    if deps.dry_run:
        return _envelope(None, kind, label[:255], payload, reasoning or "", instance) | {"dry_run": True}
    proposal = create_proposal(
        user,
        model,
        instance,
        kind,
        label,
        payload,
        source=deps.source,
        client=deps.client,
        reasoning=reasoning,
        session_key=deps.session_key,
    )
    return pending_envelope(proposal)


def _load_changeable(deps: AssistantDeps, object_id: str | None):
    """`(instance, error)` for a record the assistant may propose changes to:
    one the user may change, of a type exposed to the assistant (not CrudKit's
    own bookkeeping such as proposals, runs or the change log)."""
    instance, error = _load_instance(deps, object_id, "change")
    if instance is not None and instance.__class__ not in records.get_exposed_models(mcp_allowlist=False):
        return None, f"{instance.id} can't be changed by the assistant."
    return instance, error


def _make_proposal(
    deps: AssistantDeps,
    object_id: str | None,
    kind: str,
    label: str,
    payload: dict,
    reasoning: str,
) -> dict:
    if kind == AssistantProposal.Kind.REVERT:
        # An undo's target is only where it is shown; revert_change_set checks every record it touches.
        instance, error = _load_instance(deps, object_id, "change")
    else:
        instance, error = _load_changeable(deps, object_id)
    if instance is None:
        raise PermissionError(error)
    return _file_proposal(deps, _load_user(deps), instance.__class__, instance, kind, label, payload, reasoning)


def _envelope(proposal_id, kind: str, label: str, payload: dict, reasoning: str, target) -> dict:
    return {
        "type": "tool_call_pending",
        "id": proposal_id,
        "kind": kind,
        "label": label,
        "payload": payload,
        "reasoning": reasoning,
        "target": str(target.id) if target is not None else None,
        "target_label": str(target) if target is not None else None,
    }


def pending_envelope(proposal: AssistantProposal) -> dict:
    return _envelope(proposal.id, proposal.kind, proposal.label, proposal.payload, proposal.reasoning, proposal.target)


def _pending_text(envelope: dict) -> str:
    what = f"({envelope['kind']}: {envelope['label']})"
    if envelope.get("dry_run"):
        return f"Dry run: proposal {what} recorded; nothing was saved."
    return (
        f"Proposal {envelope['id']} {what} is awaiting user confirmation. "
        "The action has NOT run yet. You will be told the outcome in a later turn."
    )


async def _emit(ctx: RunContext[AssistantDeps], envelope: dict) -> None:
    outbox = getattr(ctx.deps, "_outbox", None)
    if outbox is not None:
        await outbox.put(envelope)


async def _propose(
    ctx: RunContext[AssistantDeps],
    object_id: str | None,
    kind: str,
    label: str,
    payload: dict,
    reasoning: str,
) -> str:
    """Shared helper: persist a proposal, push the pending envelope to the
    consumer's outbox, and return a string the model treats as the tool result."""
    try:
        envelope = await sync_to_async(_make_proposal)(ctx.deps, object_id, kind, label, payload, reasoning)
    except PermissionError as exc:
        return f"ERROR: {exc}"
    await _emit(ctx, envelope)
    return _pending_text(envelope)


def _field_errors(model, fields: dict, user) -> str | None:
    """Why `fields` can't be proposed on `model`: unknown or read-only field
    names, FK targets that don't exist or `user` can't see (the serializer
    would silently store None), or choice values the model invented."""
    writable = {
        f.name: f
        for f in model._meta.fields
        if f.editable
        and not f.primary_key
        and f.name not in records.AUDIT_FIELDS | records.SKIPPED_FIELDS
        and not getattr(f, "ai_field", False)
    }
    try:
        records.check_values(user, writable, fields)
    except ValueError as exc:
        return f"{exc}. Call describe_types or describe_object first."
    field_map = {f.name: f for f in model._meta.fields}
    choice_errors = []
    for name, value in fields.items():
        field = field_map[name]
        if field.choices and value not in (None, "") and not isinstance(value, bool):
            valid_values = [choice for choice, _ in field.flatchoices]
            if value not in valid_values and str(value) not in map(str, valid_values):
                choice_errors.append(f"{name}={value!r} is not a valid choice; valid: {valid_values}")
    return "; ".join(choice_errors) or None


async def propose_action(
    ctx: RunContext[AssistantDeps],
    action_name: str,
    reasoning: str = "",
    id: str | None = None,
) -> str:
    """Propose running a @crm_action on a record (default: the one open on
    screen). The action is NOT executed until the user confirms.
    `action_name` must be one of the names returned by describe_object().actions."""

    def _validate():
        instance, error = _load_instance(ctx.deps, id)
        if instance is None:
            return error, []
        valid = list(getattr(instance, "_actions", {}).keys())
        return None, [name for name in valid if has_action_permission(_load_user(ctx.deps), instance, name)]

    error, valid_actions = await sync_to_async(_validate)()
    if error:
        return f"ERROR: {error}"
    if action_name not in valid_actions:
        return (
            f"ERROR: action {action_name!r} does not exist on this object. "
            f"Valid actions: {valid_actions}. Pick one of these or do not propose an action."
        )
    label = f"Run {action_name}"
    return await _propose(ctx, id, AssistantProposal.Kind.ACTION, label, {"action": action_name}, reasoning)


async def propose_patch(
    ctx: RunContext[AssistantDeps],
    fields: dict[str, Any],
    reasoning: str = "",
    id: str | None = None,
) -> str:
    """Propose updating one or more fields on a record (default: the one open
    on screen) via PATCH. The edit is NOT applied until the user confirms.
    `fields` is a {field_name: new_value} dict."""
    if not isinstance(fields, dict) or not fields:
        return "ERROR: `fields` must be a non-empty {field_name: new_value} dict."

    def _check():
        instance, error = _load_changeable(ctx.deps, id)
        if instance is None:
            return error
        return _field_errors(instance.__class__, fields, _load_user(ctx.deps))

    if error := await sync_to_async(_check)():
        return f"ERROR: {error}"
    return await _propose(ctx, id, AssistantProposal.Kind.PATCH, patch_label(fields), {"fields": fields}, reasoning)


async def propose_bulk_patch(
    ctx: RunContext[AssistantDeps],
    ids: list[str],
    fields: dict[str, Any],
    reasoning: str = "",
) -> str:
    """Propose the same field update on several records at once (e.g. the
    rows on screen): one Confirm/Skip card per record, nothing applied until
    the user confirms. `ids` are record ids (at most 100); `fields` is a
    {field_name: new_value} dict whose names and choice values come from
    describe_types(type). Records that already have these values are skipped."""
    if not isinstance(fields, dict) or not fields:
        return "ERROR: `fields` must be a non-empty {field_name: new_value} dict."
    if not isinstance(ids, list) or not ids:
        return 'ERROR: `ids` must be a non-empty list of record ids, e.g. ["CUS1", "CUS2"].'
    ids = list(dict.fromkeys(ids))
    if len(ids) > MAX_BULK_IDS:
        return f"ERROR: at most {MAX_BULK_IDS} ids per call; split the records into batches."
    label = patch_label(fields)

    def _run():
        instances, refused = [], []
        for object_id in ids:
            # An empty id would fall back to the record open on screen.
            instance, error = _load_changeable(ctx.deps, object_id) if object_id else (None, "Empty id.")
            if instance is None:
                refused.append(error)
            else:
                instances.append(instance)
        user = _load_user(ctx.deps)
        for model in {instance.__class__ for instance in instances}:
            if error := _field_errors(model, fields, user):
                raise ValueError(error)
        envelopes, unchanged = [], []
        for instance in instances:
            if all(
                instance._meta.get_field(name).value_from_object(instance) == value for name, value in fields.items()
            ):
                unchanged.append(str(instance.id))
                continue
            envelopes.append(
                _file_proposal(
                    ctx.deps,
                    user,
                    instance.__class__,
                    instance,
                    AssistantProposal.Kind.PATCH,
                    label,
                    {"fields": fields},
                    reasoning,
                )
            )
        return envelopes, refused, unchanged

    try:
        envelopes, refused, unchanged = await sync_to_async(_run)()
    except ValueError as exc:
        return f"ERROR: {exc}"
    for envelope in envelopes:
        await _emit(ctx, envelope)

    lines = []
    if envelopes and ctx.deps.dry_run:
        lines.append(f"Dry run: {len(envelopes)} proposal(s) ({label}) recorded; nothing was saved.")
    elif envelopes:
        drafted = ", ".join(f"{e['target']} (proposal {e['id']})" for e in envelopes)
        lines.append(
            f"{len(envelopes)} proposal(s) ({label}) are awaiting user confirmation, one per record: {drafted}. "
            "Nothing has run yet. You will be told the outcomes in a later turn."
        )
    if unchanged:
        lines.append(f"Already set, not proposed: {', '.join(unchanged)}.")
    if refused:
        lines.append("Not proposed: " + " ".join(refused))
    if not envelopes and refused:
        lines.insert(0, "ERROR: no proposals made.")
    return "\n".join(lines)


async def propose_create_note(
    ctx: RunContext[AssistantDeps],
    body: str,
    reasoning: str = "",
    id: str | None = None,
) -> str:
    """Propose adding a note (FeedItem) to a record (default: the one open on
    screen). The note is NOT created until the user confirms."""
    snippet = (body or "").strip().splitlines()[0] if body else ""
    label = f"Add note: {snippet[:80]}"
    return await _propose(ctx, id, AssistantProposal.Kind.NOTE, label, {"body": body}, reasoning)


async def propose_create(
    ctx: RunContext[AssistantDeps],
    type: str,
    fields: dict[str, Any],
    reasoning: str = "",
) -> str:
    """Propose creating a new record of `type` (a TYPE_ID, e.g. AGT for an
    agent) with `fields`, a {field_name: value} dict whose names and choice
    values come from describe_types(type). Nothing is created until the user
    confirms."""
    if not isinstance(fields, dict) or not fields:
        return "ERROR: `fields` must be a non-empty {field_name: value} dict."

    def _run():
        user = _load_user(ctx.deps)
        model = records.resolve_type(user, type)
        if not has_model_permission(user, model, "add"):
            raise PermissionDenied
        checked = records.checked_fields(model, user, fields)
        if error := _field_errors(model, checked, user):
            raise ValueError(error)
        services.check_create(model, checked, user)
        label = f"Create {model._meta.verbose_name}"
        payload = {"type": model.TYPE_ID, "fields": checked}
        return _file_proposal(ctx.deps, user, model, None, AssistantProposal.Kind.CREATE, label, payload, reasoning)

    try:
        envelope = await sync_to_async(_run)()
    except PermissionDenied:
        return f"ERROR: you may not create {type} records."
    except ValueError as exc:
        return f"ERROR: {exc}"
    await _emit(ctx, envelope)
    return _pending_text(envelope)


async def propose_revert(ctx: RunContext[AssistantDeps], change_set: str, reasoning: str = "") -> str:
    """Propose undoing a change set: every change one earlier edit made, as
    listed by get_changelog's `change_set`. Nothing is reverted until the user
    confirms."""

    def _target():
        try:
            entries = services.check_revertible(uuid.UUID(str(change_set)))
        except ValueError as exc:
            return None, str(exc)
        newest = entries[0]
        return f"{newest.related_content_type.model_class().TYPE_ID}{newest.related_object_id}", None

    target, error = await sync_to_async(_target)()
    if error:
        return f"ERROR: {error}"
    label = f"Undo change {str(change_set)[:8]}"
    return await _propose(ctx, target, AssistantProposal.Kind.REVERT, label, {"change_set": str(change_set)}, reasoning)
