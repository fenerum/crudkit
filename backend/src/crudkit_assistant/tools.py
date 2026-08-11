"""
Tools the assistant agent can call.

Split into two physically-separate groups:

- Read tools: run inline, return data.
- Proposal tools: do NOT mutate. They persist an AssistantProposal row,
  emit a tool_call_pending WS event, and return a "pending" string. The
  actual mutation only runs in AssistantConsumer.confirm_proposal() when
  the staff user clicks Confirm.

The proposal tools talk to the consumer via an asyncio.Queue exposed on
the RunContext.deps shim attached by the runner.
"""

import json
import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.contenttypes.models import ContentType
from pydantic_ai import RunContext

from crudkit.models import ChangeLog, FeedItem
from crudkit_api.metadata import build_instance_metadata
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import AssistantProposal
from crudkit_assistant.utils import get_instance

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Read tools


def _load_instance(deps: AssistantDeps):
    return get_instance(deps.object_type_id, deps.object_pk)


async def get_object(ctx: RunContext[AssistantDeps]) -> str:
    """Return a textual summary of the currently-open CrudKit object."""

    def _run():
        instance = _load_instance(ctx.deps)
        if instance is None:
            return "Object not found."
        return f"{instance.__class__._meta.verbose_name} {instance.id}\n{instance.get_ai_context()}"

    return await sync_to_async(_run)()


async def describe_object(ctx: RunContext[AssistantDeps]) -> dict[str, Any]:
    """Return the schema of the open object: every writable field with its
    type, current value, valid choices (for choice fields), and — for
    foreign keys — the list of related rows the model is allowed to pick
    from. Also lists the available @crm_actions.

    Call this BEFORE any `propose_patch` or `propose_action`. Never invent
    field values, choice strings, or action names — they must appear in
    this payload."""

    def _run():
        instance = _load_instance(ctx.deps)
        if instance is None:
            return {"error": "Object not found."}
        return build_instance_metadata(instance)

    return await sync_to_async(_run)()


async def get_changelog(ctx: RunContext[AssistantDeps], limit: int = 20) -> list[dict[str, Any]]:
    """Return up to `limit` recent ChangeLog entries for the open object.

    Each entry has {at, by, field_changes: {field: [old, new]}}.
    """

    def _run():
        instance = _load_instance(ctx.deps)
        if instance is None:
            return []
        ct = ContentType.objects.get_for_model(instance.__class__)
        qs = ChangeLog.objects.filter(related_content_type=ct, related_object_id=instance.pk).order_by("-updated_at")[
            :limit
        ]
        return [
            {
                "at": cl.updated_at.isoformat(),
                "by": str(cl.updated_by) if cl.updated_by_id else None,
                "field_changes": cl.field_changes or {},
            }
            for cl in qs
        ]

    return await sync_to_async(_run)()


async def get_feed(ctx: RunContext[AssistantDeps], limit: int = 20) -> list[dict[str, Any]]:
    """Return up to `limit` recent FeedItems (notes, related-object events) on the open object."""

    def _run():
        instance = _load_instance(ctx.deps)
        if instance is None:
            return []
        ct = ContentType.objects.get_for_model(instance.__class__)
        qs = FeedItem.objects.filter(parent_content_type=ct, parent_object_id=instance.pk, deleted=False).order_by(
            "-created_at"
        )[:limit]
        results = []
        for fei in qs:
            results.append(
                {
                    "at": fei.created_at.isoformat(),
                    "by": str(fei.created_by) if fei.created_by_id else None,
                    "body": fei.body or "",
                    "related_model": fei.related_content_type.model if fei.related_content_type_id else None,
                    "related_id": str(fei.related_object_id) if fei.related_object_id else None,
                }
            )
        return results

    return await sync_to_async(_run)()


async def get_related(ctx: RunContext[AssistantDeps], relation_name: str, limit: int = 20) -> list[dict[str, Any]]:
    """Walk a reverse FK relation on the open object (e.g. 'activity_set',
    'opportunityproduct_set', 'message_set'). Returns up to `limit` rows
    summarised via get_ai_context()."""

    def _run():
        instance = _load_instance(ctx.deps)
        if instance is None:
            return []
        manager = getattr(instance, relation_name, None)
        if manager is None or not hasattr(manager, "all"):
            return [{"error": f"Unknown relation {relation_name!r}"}]
        out = []
        for obj in manager.all()[:limit]:
            ctx_text = obj.get_ai_context() if hasattr(obj, "get_ai_context") else str(obj)
            out.append({"id": str(getattr(obj, "id", obj.pk)), "context": ctx_text})
        return out

    return await sync_to_async(_run)()


# ---------------------------------------------------------------------------
# Proposal tools (no mutation — only persist + emit)


def _make_proposal(
    deps: AssistantDeps,
    kind: str,
    label: str,
    payload: dict,
    reasoning: str,
) -> AssistantProposal:
    instance = get_instance(deps.object_type_id, deps.object_pk)
    if instance is None:
        raise ValueError(f"Object {deps.object_type_id}{deps.object_pk} not found")
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.get(pk=deps.user_id)
    return AssistantProposal.objects.create(
        target_content_type=ContentType.objects.get_for_model(instance.__class__),
        target_object_id=instance.pk,
        session_key=deps.session_key,
        kind=kind,
        label=label[:255],
        payload=payload,
        reasoning=reasoning or "",
        created_by=user,
        updated_by=user,
    )


def _pending_envelope(proposal: AssistantProposal) -> dict:
    return {
        "type": "tool_call_pending",
        "id": proposal.id,
        "kind": proposal.kind,
        "label": proposal.label,
        "payload": proposal.payload,
        "reasoning": proposal.reasoning,
    }


async def _propose(
    ctx: RunContext[AssistantDeps],
    kind: str,
    label: str,
    payload: dict,
    reasoning: str,
) -> str:
    """Shared helper: persist a proposal, push the pending envelope to the
    consumer's outbox, and return a string the model treats as the tool result."""
    proposal = await sync_to_async(_make_proposal)(ctx.deps, kind, label, payload, reasoning)
    outbox = getattr(ctx.deps, "_outbox", None)
    if outbox is not None:
        await outbox.put(_pending_envelope(proposal))
    return (
        f"Proposal {proposal.id} ({kind}: {label}) is awaiting user confirmation. "
        "The action has NOT run yet. You will be told the outcome in a later turn."
    )


async def propose_action(
    ctx: RunContext[AssistantDeps],
    action_name: str,
    reasoning: str = "",
) -> str:
    """Propose running a @crm_action on the open object. The action is NOT
    executed until the user confirms. `action_name` must be one of the names
    returned by describe_object().actions."""

    def _validate():
        instance = _load_instance(ctx.deps)
        if instance is None:
            return ["object not found"], []
        valid = list(getattr(instance, "_actions", {}).keys())
        return ([] if action_name in valid else [action_name]), valid

    invalid, valid_actions = await sync_to_async(_validate)()
    if invalid:
        return (
            f"ERROR: action {action_name!r} does not exist on this object. "
            f"Valid actions: {valid_actions}. Pick one of these or do not propose an action."
        )
    label = f"Run {action_name}"
    return await _propose(ctx, AssistantProposal.Kind.ACTION, label, {"action": action_name}, reasoning)


async def propose_patch(
    ctx: RunContext[AssistantDeps],
    fields: dict[str, Any],
    reasoning: str = "",
) -> str:
    """Propose updating one or more fields on the open object via PATCH. The
    edit is NOT applied until the user confirms. `fields` is a {field_name: new_value} dict."""
    if not isinstance(fields, dict) or not fields:
        return "ERROR: `fields` must be a non-empty {field_name: new_value} dict."

    def _validate():
        instance = _load_instance(ctx.deps)
        if instance is None:
            return None
        return instance

    instance = await sync_to_async(_validate)()
    if instance is None:
        return "ERROR: object not found."

    field_map = {f.name: f for f in instance._meta.fields}
    unknown = [k for k in fields if k not in field_map]
    if unknown:
        valid = sorted(field_map)
        return (
            f"ERROR: field(s) {unknown} do not exist on "
            f"{instance.__class__.__name__}. Valid fields: {valid}. "
            "Call describe_object first."
        )
    # Reject choice values the model invented.
    choice_errors: list[str] = []
    for name, value in fields.items():
        field = field_map[name]
        if field.choices and value not in (None, "") and not isinstance(value, (int, bool)):
            valid_values = [c[0] for c in field.choices]
            if value not in valid_values:
                choice_errors.append(f"{name}={value!r} is not a valid choice; valid: {valid_values}")
    if choice_errors:
        return "ERROR: " + "; ".join(choice_errors)

    try:
        preview = ", ".join(f"{k}={json.dumps(v, default=str)}" for k, v in fields.items())
    except (TypeError, ValueError):
        preview = ", ".join(fields)
    label = f"Update {preview}"
    return await _propose(ctx, AssistantProposal.Kind.PATCH, label, {"fields": fields}, reasoning)


async def propose_create_note(
    ctx: RunContext[AssistantDeps],
    body: str,
    reasoning: str = "",
) -> str:
    """Propose adding a note (FeedItem) to the open object. The note is NOT
    created until the user confirms."""
    snippet = (body or "").strip().splitlines()[0] if body else ""
    label = f"Add note: {snippet[:80]}"
    return await _propose(ctx, AssistantProposal.Kind.NOTE, label, {"body": body}, reasoning)
