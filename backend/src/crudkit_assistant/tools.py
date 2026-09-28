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

from crudkit.authorization import get_authorized_instance, get_authorized_queryset, has_action_permission
from crudkit.models import parse_ck_id
from crudkit_api import records, services
from crudkit_api.metadata import build_instance_metadata
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
        return services.get_changelog(instance, limit) if instance is not None else f"ERROR: {error}"

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
    """Walk a reverse FK relation on a record (default: the one open on screen),
    e.g. 'activity_set', 'opportunityproduct_set', 'message_set'. Returns up
    to `limit` rows summarised via get_ai_context()."""

    def _run():
        instance, error = _load_instance(ctx.deps, id)
        if instance is None:
            return f"ERROR: {error}"
        manager = getattr(instance, relation_name, None)
        if manager is None or not hasattr(manager, "all"):
            return f"ERROR: Unknown relation {relation_name!r}"
        out = []
        queryset = get_authorized_queryset(_load_user(ctx.deps), manager.all(), "view")
        for obj in queryset[:limit]:
            ctx_text = obj.get_ai_context() if hasattr(obj, "get_ai_context") else str(obj)
            out.append({"id": str(getattr(obj, "id", obj.pk)), "context": ctx_text})
        return out

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
    """Search all record types by text. Returns matching records as {id, label}."""
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


def _make_proposal(
    deps: AssistantDeps,
    object_id: str | None,
    kind: str,
    label: str,
    payload: dict,
    reasoning: str,
) -> AssistantProposal:
    instance, error = _load_instance(deps, object_id, "change")
    if instance is None:
        raise PermissionError(error)
    return create_proposal(
        _load_user(deps),
        instance.__class__,
        instance,
        kind,
        label,
        payload,
        reasoning=reasoning,
        session_key=deps.session_key,
    )


def pending_envelope(proposal: AssistantProposal) -> dict:
    target = proposal.target
    return {
        "type": "tool_call_pending",
        "id": proposal.id,
        "kind": proposal.kind,
        "label": proposal.label,
        "payload": proposal.payload,
        "reasoning": proposal.reasoning,
        "target": str(target.id) if target is not None else None,
        "target_label": str(target) if target is not None else None,
    }


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
        proposal = await sync_to_async(_make_proposal)(ctx.deps, object_id, kind, label, payload, reasoning)
    except PermissionError as exc:
        return f"ERROR: {exc}"
    await _emit(ctx, await sync_to_async(pending_envelope)(proposal))
    return (
        f"Proposal {proposal.id} ({kind}: {label}) is awaiting user confirmation. "
        "The action has NOT run yet. You will be told the outcome in a later turn."
    )


def _field_errors(model, fields: dict) -> str | None:
    """Why `fields` can't be proposed on `model`: unknown field names, or
    choice values the model invented."""
    field_map = {f.name: f for f in model._meta.fields}
    unknown = [k for k in fields if k not in field_map]
    if unknown:
        return (
            f"field(s) {unknown} do not exist on {model.__name__}. Valid fields: {sorted(field_map)}. "
            "Call describe_types or describe_object first."
        )
    choice_errors = []
    for name, value in fields.items():
        field = field_map[name]
        if field.choices and value not in (None, "") and not isinstance(value, (int, bool)):
            valid_values = [choice for choice, _ in field.flatchoices]
            if value not in valid_values:
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

    instance, error = await sync_to_async(_load_instance)(ctx.deps, id)
    if instance is None:
        return f"ERROR: {error}"
    if error := _field_errors(instance.__class__, fields):
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
            instance, error = _load_instance(ctx.deps, object_id, "change") if object_id else (None, "Empty id.")
            if instance is None:
                refused.append(error)
            else:
                instances.append(instance)
        for model in {instance.__class__ for instance in instances}:
            if error := _field_errors(model, fields):
                raise ValueError(error)
        user = _load_user(ctx.deps)
        envelopes, unchanged = [], []
        for instance in instances:
            if all(
                instance._meta.get_field(name).value_from_object(instance) == value for name, value in fields.items()
            ):
                unchanged.append(str(instance.id))
                continue
            proposal = create_proposal(
                user,
                instance.__class__,
                instance,
                AssistantProposal.Kind.PATCH,
                label,
                {"fields": fields},
                reasoning=reasoning,
                session_key=ctx.deps.session_key,
            )
            envelopes.append(pending_envelope(proposal))
        return envelopes, refused, unchanged

    try:
        envelopes, refused, unchanged = await sync_to_async(_run)()
    except ValueError as exc:
        return f"ERROR: {exc}"
    for envelope in envelopes:
        await _emit(ctx, envelope)

    lines = []
    if envelopes:
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
