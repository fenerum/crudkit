"""
WebSocket consumer for the assistant sidebar. One socket per browser tab,
kept open while the user navigates; the SPA reports what is on screen.
`ws/assistant/<TYPE_ID>/<pk>/` still works and starts with that record on
screen. Inbound message types:

- {"type": "auth", "token": "..."}           — JWT clients, first frame
- {"type": "open_conversation", "id": "ASC12"|null}
                                              — resume a conversation, or start one
- {"type": "screen", "screen": {...}}         — what the user now has on screen
- {"type": "user_message", "text": "..."}     — kick off a turn
- {"type": "confirm", "id": <proposal_id>, "ok": true|false}
                                              — apply or skip a pending proposal

Outbound message types:

- {"type": "ready", "session": "..."}
- {"type": "conversation", id, title, transcript: [...]}
- {"type": "assistant_message", "text": "..."}
- {"type": "tool_call_pending", id, kind, label, payload, reasoning, target, target_label}
- {"type": "tool_outcome", id, ok, summary, status}
- {"type": "error", "message": "..."}
"""

import logging
from typing import Optional
from uuid import uuid4

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from pydantic import ValidationError
from pydantic_ai.messages import ModelMessagesTypeAdapter

from crudkit.authorization import has_object_permission
from crudkit.models import get_ck_id, parse_ck_id
from crudkit_api.ws_auth import AuthenticatedConsumer
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import AssistantConversation, AssistantProposal
from crudkit_assistant.runner import run_turn
from crudkit_assistant.screen import Screen, load_screen_record, parse_screen
from crudkit_assistant.tools import pending_envelope

logger = logging.getLogger(__name__)


class AssistantConsumer(AuthenticatedConsumer):
    """Assistant sidebar socket. One instance per browser tab."""

    async def connect(self):
        kwargs = self.scope["url_route"]["kwargs"]
        self.screen = (
            Screen(route="detail", record_id=get_ck_id(kwargs["type_id"], kwargs["pk"])) if kwargs else Screen()
        )
        self.conversation: Optional[AssistantConversation] = None
        self.session_key: str = uuid4().hex
        self.message_history: list = []
        await super().connect()

    async def on_authenticated(self, user) -> bool:
        if self.screen.record_id and await sync_to_async(load_screen_record)(user, self.screen) is None:
            await self.close(code=4403)
            return False
        await self.send_json({"type": "ready", "session": self.session_key})
        return True

    async def on_message(self, data: dict):
        msg_type = data.get("type")
        if msg_type == "open_conversation":
            await self._open_conversation(data.get("id"))
        elif msg_type == "screen":
            self.screen = parse_screen(data.get("screen"))
        elif msg_type == "user_message":
            await self._handle_user_message(data.get("text", ""))
        elif msg_type == "confirm":
            await self._handle_confirm(data.get("id"), bool(data.get("ok")))
        else:
            await self.send_json({"type": "error", "message": f"Unknown message type {msg_type!r}"})

    async def _open_conversation(self, conversation_id):
        user = await self._get_user()
        self.conversation = await database_sync_to_async(_load_or_create_conversation)(user, conversation_id)
        self.session_key = self.conversation.session_key
        self.message_history = _load_messages(self.conversation)
        await self.send_json(
            {
                "type": "conversation",
                "id": str(self.conversation.id),
                "title": self.conversation.title,
                "transcript": await database_sync_to_async(_expand_transcript)(self.conversation),
            }
        )

    async def _handle_user_message(self, text: str, synthetic: bool = False):
        """Run a turn. `synthetic` turns (proposal outcomes) are not shown as user bubbles."""
        text = (text or "").strip()
        if not text or self.user_id is None:
            return
        if self.conversation is None:
            await self._open_conversation(None)
        transcript = [] if synthetic else [{"role": "user", "text": text}]
        deps = AssistantDeps(user_id=self.user_id, session_key=self.session_key, screen=self.screen)
        try:
            result = await run_turn(text, deps=deps, message_history=self.message_history)
        except Exception:
            logger.exception("Assistant turn failed")
            await self.send_json({"type": "error", "message": "The assistant ran into an error."})
            transcript.append({"role": "system", "text": "Error: The assistant ran into an error."})
            await self._save(transcript)
            return

        self.message_history = (self.message_history or []) + (result.new_messages or [])

        for envelope in result.pending_events:
            await self.send_json(envelope)
            transcript.append({"role": "proposal", "id": envelope["id"]})
        if result.output_text:
            await self.send_json({"type": "assistant_message", "text": result.output_text})
            transcript.append({"role": "assistant", "text": result.output_text})
        await self._save(transcript)

    async def _save(self, new_items: list[dict]):
        await database_sync_to_async(_save_conversation)(self.conversation, self.message_history, new_items)

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
        await self._handle_user_message(synthetic, synthetic=True)

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


def _load_or_create_conversation(user, conversation_id) -> AssistantConversation:
    if isinstance(conversation_id, str):
        try:
            type_id, pk = parse_ck_id(conversation_id)
        except ValueError:
            type_id, pk = None, None
        if type_id == AssistantConversation.TYPE_ID:
            conversation = AssistantConversation.objects.filter(pk=pk, created_by=user, deleted=False).first()
            if conversation is not None:
                return conversation
    return AssistantConversation.objects.create(created_by=user, updated_by=user)


def _load_messages(conversation: AssistantConversation) -> list:
    try:
        return list(ModelMessagesTypeAdapter.validate_python(conversation.messages))
    except ValidationError:
        # Stored by an incompatible pydantic-ai version: keep the transcript, drop the model's memory.
        logger.warning("Dropping unreadable message history of %s", conversation.id)
        return []


def _save_conversation(conversation: AssistantConversation, messages: list, new_items: list[dict]):
    conversation.messages = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
    conversation.transcript = conversation.transcript + new_items
    if not conversation.title:
        first = next((item["text"] for item in conversation.transcript if item["role"] == "user"), "")
        conversation.title = first[: AssistantConversation.TITLE_LENGTH]
    conversation.save(update_fields=["messages", "transcript", "title", "updated_at"])


def _expand_transcript(conversation: AssistantConversation) -> list[dict]:
    """The stored transcript with proposal references replaced by their current state."""
    proposals = {
        proposal.id: proposal
        for proposal in AssistantProposal.objects.filter(session_key=conversation.session_key).prefetch_related(
            "target"
        )
    }
    out = []
    for item in conversation.transcript:
        if item.get("role") != "proposal":
            out.append(item)
        elif proposal := proposals.get(item["id"]):
            envelope = pending_envelope(proposal)
            out.append(
                {
                    **{key: value for key, value in envelope.items() if key != "type"},
                    "role": "proposal",
                    "status": proposal.status,
                    "summary": _summarize_outcome(proposal.outcome, proposal),
                }
            )
    return out


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
