"""
Runs one turn of the assistant against what the user has on screen. Owns the lifecycle
of the per-turn LLM client and threads an asyncio.Queue (the "outbox") onto
RunContext.deps so proposal tools can emit `tool_call_pending` events as
they fire.

`run_turn` drives the agent via `agent.iter()` (rather than `agent.run()`)
so we can log each model response, tool call, tool return, and retry prompt.
This is what makes `UnexpectedModelBehavior: Exceeded maximum retries` actually
diagnosable — without the per-step trail, we only ever see the final failure.

With an `on_event` callback the turn is streamed: model requests stream their
reasoning and text as they are generated, and each tool call is reported as it
starts and ends, so the user can follow along while a slow model works.
"""

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from pydantic_ai import Agent
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolReturnPart,
)
from pydantic_ai.toolsets import FunctionToolset

from crudkit import llm
from crudkit_assistant.agent import assistant_agent
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.screen import describe_screen, screen_model
from crudkit_assistant.tools import describe_call
from crudkit_assistant.utils import get_assistant_tools

logger = logging.getLogger(__name__)

# Cap any single payload we put in a log line — tool args / returns can be
# big and we don't want to flood the console.
_LOG_VALUE_LIMIT = 400

# Mistral occasionally emits tool calls whose `tool_name` carries invisible
# "Tag" characters from the Unicode Supplementary Private Use Plane (U+E0000
# – U+E007F) and the literal args dict appended after them, e.g.
# `get_object\U000e006a{}`. pydantic-ai then can't match the name to any
# registered tool, retries once, and aborts with
# `UnexpectedModelBehavior: Exceeded maximum retries (1) for output validation`.
# We sanitise the tool name on the way out of the model so pydantic-ai sees
# the clean `get_object` and dispatch succeeds.
_TAG_CHAR_RE = re.compile(r"[\U000E0000-\U000E007F]")
_NAME_TERMINATOR_RE = re.compile(r"[\s{(\[]")


class TurnResult:
    def __init__(self, output_text: str, new_messages: list, pending_events: list[dict[str, Any]]):
        self.output_text = output_text
        self.new_messages = new_messages
        self.pending_events = pending_events


EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


async def run_turn(
    user_prompt: str,
    deps: AssistantDeps,
    message_history: Optional[list] = None,
    on_event: Optional[EventCallback] = None,
) -> TurnResult:
    """Run one agent turn. Returns the assistant's text, any tool_call_pending
    envelopes the proposal tools emitted during the run (with `on_event`, those
    are sent as they happen instead), and the new message history segment to
    keep for the next turn.

    `on_event` receives, in order: `thinking_delta` / `text_delta` {text},
    `tool_start` {id, tool, label}, `tool_end` {id, ok} and `tool_call_pending`
    envelopes."""

    if not llm.is_configured():
        logger.warning("Assistant turn skipped: no CrudKit AI model configured")
        return TurnResult(
            output_text="The assistant is not available: no AI model is configured for this installation.",
            new_messages=[],
            pending_events=[],
        )

    outbox: asyncio.Queue = asyncio.Queue()
    # Stash the outbox onto deps so proposal tools can reach it via RunContext.
    deps._outbox = outbox  # type: ignore[attr-defined]

    extra_tools: list = await sync_to_async(_load_extra_tools)(deps)
    screen_block = await sync_to_async(_describe_screen)(deps)

    logger.info(
        "Assistant turn start: screen=%s prompt=%r history_len=%d extra_tools=%d",
        deps.screen.record_id or deps.screen.path,
        _truncate(user_prompt),
        len(message_history or []),
        len(extra_tools),
    )

    output_text = ""
    new_messages: list = []
    steps = 0
    try:
        async with llm.model_context() as model:
            async with assistant_agent.iter(
                f"{screen_block}\n\n{user_prompt}",
                deps=deps,
                model=model,
                message_history=message_history or [],
                **({"toolsets": [FunctionToolset(extra_tools)]} if extra_tools else {}),
            ) as agent_run:
                async for node in agent_run:
                    if Agent.is_call_tools_node(node):
                        _sanitise_tool_names(node.model_response)
                    _log_node(node)
                    steps += 1
                    if on_event is not None and Agent.is_model_request_node(node):
                        async with node.stream(agent_run.ctx) as stream:
                            async for event in stream:
                                await _forward_model_event(event, on_event)
                    elif on_event is not None and Agent.is_call_tools_node(node):
                        async with node.stream(agent_run.ctx) as stream:
                            async for event in stream:
                                await _forward_tool_event(event, on_event, outbox)
                result = agent_run.result
        output_text = _coerce_text(result.output if result is not None else None)
        new_messages = list(result.new_messages()) if result is not None and hasattr(result, "new_messages") else []
    except Exception:
        logger.exception(
            "Assistant turn FAILED after %d step(s): screen=%s prompt=%r",
            steps,
            deps.screen.record_id or deps.screen.path,
            _truncate(user_prompt),
        )
        raise

    pending: list[dict[str, Any]] = []
    while not outbox.empty():
        pending.append(outbox.get_nowait())

    logger.info(
        "Assistant turn done: screen=%s steps=%d pending_proposals=%d output=%r",
        deps.screen.record_id or deps.screen.path,
        steps,
        len(pending),
        _truncate(output_text),
    )
    return TurnResult(output_text=output_text, new_messages=new_messages, pending_events=pending)


def _load_extra_tools(deps: AssistantDeps) -> list:
    # Background agents get only CrudKit's own tools: a project's tools don't
    # know about dry runs or agent-sourced proposals, so an agent could write
    # through them unnoticed (and retrigger itself).
    model = screen_model(deps.screen)
    return get_assistant_tools(model) if model is not None and deps.source != "agent" else []


def _describe_screen(deps: AssistantDeps) -> str:
    return describe_screen(get_user_model().objects.get(pk=deps.user_id), deps.screen)


def _sanitise_tool_name(name: str) -> str:
    """Strip Unicode tag characters and any args literal that the model
    accidentally appended to the tool name."""
    if not name:
        return name
    cleaned = _TAG_CHAR_RE.sub("", name)
    # If the model glued `{...}` / `(...)` / whitespace onto the name,
    # keep just the prefix up to the first such terminator.
    match = _NAME_TERMINATOR_RE.search(cleaned)
    if match:
        cleaned = cleaned[: match.start()]
    return cleaned.strip()


def _sanitise_tool_names(response) -> None:
    """Fix garbled `ToolCallPart.tool_name`s in a model response before
    pydantic-ai dispatches its tool calls. Done on the CallToolsNode, so it
    covers streamed and non-streamed requests alike."""
    for part in getattr(response, "parts", []) or []:
        if getattr(part, "part_kind", None) != "tool-call":
            continue
        raw = getattr(part, "tool_name", "") or ""
        cleaned = _sanitise_tool_name(raw)
        if cleaned and cleaned != raw:
            logger.warning("Sanitised garbled tool name from model: %r -> %r", raw, cleaned)
            part.tool_name = cleaned


async def _forward_model_event(event, on_event: EventCallback) -> None:
    """Reasoning and reply text as the model generates them."""
    if isinstance(event, PartStartEvent):
        part, text = event.part, getattr(event.part, "content", "")
        kind = (
            "thinking_delta" if isinstance(part, ThinkingPart) else "text_delta" if isinstance(part, TextPart) else ""
        )
    elif isinstance(event, PartDeltaEvent):
        delta, text = event.delta, getattr(event.delta, "content_delta", "")
        kind = (
            "thinking_delta"
            if isinstance(delta, ThinkingPartDelta)
            else "text_delta"
            if isinstance(delta, TextPartDelta)
            else ""
        )
    else:
        return
    if kind and text:
        await on_event({"type": kind, "text": text})


async def _forward_tool_event(event, on_event: EventCallback, outbox: asyncio.Queue) -> None:
    """Tool calls as they start and end; proposals as soon as they exist."""
    if isinstance(event, FunctionToolCallEvent):
        part = event.part
        await on_event(
            {
                "type": "tool_start",
                "id": part.tool_call_id,
                "tool": part.tool_name,
                "label": describe_call(part.tool_name, _args(part)),
            }
        )
    elif isinstance(event, FunctionToolResultEvent):
        await on_event({"type": "tool_end", "id": event.tool_call_id, "ok": _succeeded(event.part)})
        while not outbox.empty():
            await on_event(outbox.get_nowait())


def _args(part) -> dict:
    try:
        return part.args_as_dict()
    except (ValueError, TypeError):
        return {}


def _succeeded(part) -> bool:
    """Tools report failures as "ERROR: …" strings or {"error": …} dicts."""
    if not isinstance(part, ToolReturnPart):
        return False
    content = part.content
    if isinstance(content, str):
        return not content.startswith("ERROR")
    return not (isinstance(content, dict) and "error" in content)


def _log_node(node) -> None:
    """Pull the diagnostic-worthy bits out of each pydantic-ai graph node.

    `CallToolsNode` carries the model's latest response (tool calls and/or
    text). `ModelRequestNode` carries what we're about to send back (tool
    returns + any retry prompts the framework injected). We log both so a
    failure mid-stream is fully reconstructable."""
    cls = type(node).__name__
    if cls == "CallToolsNode":
        model_response = getattr(node, "model_response", None)
        for part in getattr(model_response, "parts", []) or []:
            kind = getattr(part, "part_kind", "")
            if kind == "tool-call":
                logger.info(
                    "  model→call %s(%s)",
                    getattr(part, "tool_name", "?"),
                    _truncate(_stringify(getattr(part, "args", None))),
                )
            elif kind == "text":
                content = getattr(part, "content", "") or ""
                if content.strip():
                    logger.info("  model→text %r", _truncate(content))
            elif kind == "thinking":
                logger.debug("  model→thinking %r", _truncate(getattr(part, "content", "") or ""))
    elif cls == "ModelRequestNode":
        request = getattr(node, "request", None)
        for part in getattr(request, "parts", []) or []:
            kind = getattr(part, "part_kind", "")
            if kind == "tool-return":
                logger.info(
                    "  tool→model %s -> %s",
                    getattr(part, "tool_name", "?"),
                    _truncate(_stringify(getattr(part, "content", None))),
                )
            elif kind == "retry-prompt":
                # This is the smoking gun for `Exceeded maximum retries`.
                logger.warning(
                    "  framework→model RETRY for %s: %s",
                    getattr(part, "tool_name", None) or "<output>",
                    _truncate(_stringify(getattr(part, "content", None))),
                )


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)


def _truncate(s: str) -> str:
    if not isinstance(s, str):
        s = str(s)
    if len(s) <= _LOG_VALUE_LIMIT:
        return s
    return s[:_LOG_VALUE_LIMIT] + f"…[+{len(s) - _LOG_VALUE_LIMIT}]"


def _coerce_text(output: Any) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    return str(output)
