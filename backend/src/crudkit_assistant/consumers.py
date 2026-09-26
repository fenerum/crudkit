"""
WebSocket consumer for the per-object assistant. Each client opens a socket
scoped to one (TYPE_ID, pk) pair. Inbound message types:

- {"type": "user_message", "text": "..."}     — kick off a turn
- {"type": "confirm", "id": <proposal_id>, "ok": true|false}
                                              — apply or skip a pending proposal

Outbound message types:

- {"type": "assistant_message", "text": "..."}
- {"type": "tool_call_pending", id, kind, label, payload, reasoning}
- {"type": "tool_outcome", id, ok, summary, status}
- {"type": "error", "message": "..."}
"""

import asyncio
import logging
from typing import Optional
from uuid import uuid4

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

from crudkit.authorization import get_authorized_instance, has_object_permission
from crudkit_api.ws_auth import AuthenticatedConsumer
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import AssistantProposal
from crudkit_assistant.runner import run_turn

logger = logging.getLogger(__name__)

# Synthetic first-turn prompt. The assistant treats this as the user's
# opening request and produces a proactive briefing/proposal — but the prompt
# itself is never rendered to the user as a chat bubble.
INITIAL_BRIEFING_PROMPT = (
    "Take a quick look at this record. If there is a clear recommended next "
    "action or a notable observation, state it in one short paragraph and "
    "propose an action when appropriate. If nothing stands out, say so in a "
    "single sentence."
)


class AssistantConsumer(AuthenticatedConsumer):
    """Per-detail-page assistant socket. One instance per browser tab."""

    async def connect(self):
        self.type_id: str = self.scope["url_route"]["kwargs"]["type_id"]
        self.object_pk: int = int(self.scope["url_route"]["kwargs"]["pk"])
        self.session_key: str = uuid4().hex
        self.message_history: list = []
        self._briefing_task: Optional[asyncio.Task] = None
        await super().connect()

    async def disconnect(self, close_code):
        await super().disconnect(close_code)
        if self._briefing_task is not None:
            self._briefing_task.cancel()
            self._briefing_task = None

    async def on_authenticated(self, user) -> bool:
        instance = await sync_to_async(get_authorized_instance)(user, self.type_id, self.object_pk)
        if instance is None:
            await self.close(code=4403)
            return False
        await self.send_json({"type": "ready", "session": self.session_key})
        # Kick off a proactive first turn so the user sees an observation /
        # recommended action instead of a static greeting. Detached so we
        # don't block the receive loop, but tracked so disconnect can cancel
        # it (e.g. user closes the window before the LLM responds).
        self._briefing_task = asyncio.create_task(self._handle_user_message(INITIAL_BRIEFING_PROMPT, is_briefing=True))
        return True

    async def on_message(self, data: dict):
        msg_type = data.get("type")
        if msg_type == "user_message":
            await self._handle_user_message(data.get("text", ""))
        elif msg_type == "confirm":
            await self._handle_confirm(data.get("id"), bool(data.get("ok")))
        else:
            await self.send_json({"type": "error", "message": f"Unknown message type {msg_type!r}"})

    async def _handle_user_message(self, text: str, is_briefing: bool = False):
        text = (text or "").strip()
        if not text or self.user_id is None:
            return
        deps = AssistantDeps(
            user_id=self.user_id,
            object_type_id=self.type_id,
            object_pk=self.object_pk,
            session_key=self.session_key,
        )
        try:
            result = await run_turn(text, deps=deps, message_history=self.message_history)
        except Exception:
            logger.exception("Assistant turn failed")
            if is_briefing:
                # The proactive first turn is best-effort. Don't surface a
                # scary error to the user — invite them to drive instead.
                await self.send_json(
                    {
                        "type": "assistant_message",
                        "text": (
                            "I had trouble reading this record automatically. "
                            "Ask me anything about it below and I'll dig in."
                        ),
                    }
                )
            else:
                await self.send_json({"type": "error", "message": "The assistant ran into an error."})
            return

        self.message_history = (self.message_history or []) + (result.new_messages or [])

        for envelope in result.pending_events:
            await self.send_json(envelope)
        if result.output_text:
            await self.send_json({"type": "assistant_message", "text": result.output_text})

    async def _handle_confirm(self, proposal_id, ok: bool):
        proposal = await self._load_proposal(proposal_id)
        if proposal is None:
            await self.send_json({"type": "error", "message": "Proposal not found."})
            return
        if proposal.status != AssistantProposal.Status.PENDING:
            await self.send_json(
                {
                    "type": "tool_outcome",
                    "id": proposal.id,
                    "ok": proposal.status == AssistantProposal.Status.CONFIRMED,
                    "status": proposal.status,
                    "summary": "Already resolved.",
                }
            )
            return

        user = await self._get_user()
        if not await self._can_change_proposal_target(proposal, user):
            await self.send_json({"type": "error", "message": "Proposal not found."})
            return
        if ok:
            outcome = await sync_to_async(proposal.apply)(user)
            applied = proposal.status == AssistantProposal.Status.CONFIRMED
            await self.send_json(
                {
                    "type": "tool_outcome",
                    "id": proposal.id,
                    "ok": applied,
                    "status": proposal.status,
                    "summary": _summarize_outcome(outcome, proposal),
                    "outcome": outcome,
                }
            )
            synthetic = f"[system] Outcome of proposal {proposal.id}: " + (
                f"{proposal.label} succeeded. {_summarize_outcome(outcome, proposal)}"
                if applied
                else f"{proposal.label} FAILED: {outcome.get('error', 'unknown error') if outcome else 'unknown error'}"
            )
        else:
            await sync_to_async(proposal.skip)(user)
            await self.send_json(
                {
                    "type": "tool_outcome",
                    "id": proposal.id,
                    "ok": False,
                    "status": proposal.status,
                    "summary": "Skipped by user.",
                }
            )
            synthetic = f"[system] User skipped proposal {proposal.id} ({proposal.label})."

        # Re-run the agent so it can acknowledge the outcome in chat.
        await self._handle_user_message(synthetic)

    @database_sync_to_async
    def _load_proposal(self, proposal_id) -> Optional[AssistantProposal]:
        if proposal_id is None:
            return None
        try:
            return AssistantProposal.objects.get(pk=proposal_id, session_key=self.session_key)
        except AssistantProposal.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_user(self):
        return get_user_model().objects.get(pk=self.user_id)

    @database_sync_to_async
    def _can_change_proposal_target(self, proposal, user):
        target = proposal.target
        return target is not None and has_object_permission(user, target, "change")


def _summarize_outcome(outcome: Optional[dict], proposal: AssistantProposal) -> str:
    if not outcome:
        return ""
    if "error" in outcome and proposal.status == AssistantProposal.Status.FAILED:
        return f"Failed: {outcome['error']}"
    kind = outcome.get("kind")
    if kind == "redirect":
        return f"Redirect to {outcome.get('url')}"
    if kind == "object":
        return f"Returned object {outcome.get('id')}"
    if kind == "patch":
        return f"Applied fields: {', '.join(outcome.get('applied') or [])}"
    if kind == "note":
        return f"Note {outcome.get('feeditem_id')} added"
    if kind == "response":
        return "Action returned a response"
    return outcome.get("value") or ""
