"""
The single shared assistant Agent. The per-model `assistant_prompt` is
injected dynamically by the runner via @agent.system_prompt so we don't
need a separate Agent per model.
"""

import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from pydantic_ai import Agent, RunContext
from pydantic_ai.settings import ModelSettings

from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.tools import (
    describe_object,
    get_changelog,
    get_feed,
    get_object,
    get_related,
    propose_action,
    propose_create_note,
    propose_patch,
)
from crudkit_assistant.utils import get_assistant_prompt, get_instance

logger = logging.getLogger(__name__)


_BASE_SYSTEM_PROMPT = """
You are an AI assistant helping a CRM staff user reason about a single object
they have open in the application.

The ONLY tools you may call are exactly these — never invent another name:
  Read tools:    get_object, describe_object, get_changelog, get_feed, get_related
  Propose tools: propose_patch, propose_action, propose_create_note

Proposals do NOT take effect immediately — they pop up as a Confirm/Skip
card in the user's chat. You will be told the outcome in a later turn
before you can propose anything that depends on it. Never claim an action
has run unless a confirmation outcome has been delivered to you.

Before proposing anything, call `get_object`, `get_feed`, AND
`describe_object`. `describe_object` returns the writable fields with
their current values, the exact list of valid choices for choice fields,
the available rows for foreign-key fields, and the names of the
@crm_actions you may propose. Every field name, choice value, FK target,
and action name you put in a proposal MUST appear verbatim in that
payload. If the right value isn't listed, ask the user instead of
guessing.

When choosing between proposal types, prefer in this order:
1. `propose_patch` — if the information belongs in a structured field on
   the object (status, stage, owner, dates, amounts, contact details,
   etc.), update the field. Structured data is searchable and reportable;
   notes are not.
2. `propose_action` — if there is a named `@crm_action` that captures the
   intent better than a freeform note.
3. `propose_create_note` — only as a last resort, for information that
   genuinely has no home in a field or action: meeting summaries,
   qualitative observations, decisions and their rationale. Never propose
   a note whose substance duplicates or paraphrases an existing feed item
   — quote the existing item's date in your reasoning and skip the
   proposal instead.

Style:
- Be concise. Short paragraphs and bullet lists, not essays.
- Lead with the observation or recommendation. Cite the specific fields
  or changelog entries that support it.
- When you propose an action, explain in one sentence why it is the
  right next move. Then call the proposal tool.
- Do not list multiple proposals in a single message unless the user asks
  for options; pick the best one and propose it.
""".strip()


assistant_agent = Agent(
    deps_type=AssistantDeps,
    model_settings=ModelSettings(temperature=0.2),
    system_prompt=_BASE_SYSTEM_PROMPT,
)


# Register the read + propose tools on the shared agent.
for _tool in (
    get_object,
    describe_object,
    get_changelog,
    get_feed,
    get_related,
    propose_action,
    propose_patch,
    propose_create_note,
):
    assistant_agent.tool(_tool)


@assistant_agent.system_prompt
async def _model_specific_prompt(ctx: RunContext[AssistantDeps]) -> str:
    """Inject the per-model `CrudKitSettings.assistant_prompt` plus a short
    framing of the currently-open object."""

    def _build():
        instance = get_instance(ctx.deps.object_type_id, ctx.deps.object_pk)
        if instance is None:
            return None, ""
        return instance, get_assistant_prompt(instance)

    instance, prompt = await sync_to_async(_build)()
    if instance is None:
        return "The object the user opened could not be loaded. Tell them so."

    project_prefix = getattr(settings, "CRUDKIT_ASSISTANT_SYSTEM_PROMPT", "") or ""
    name = getattr(settings, "CRUDKIT_ASSISTANT_NAME", "Assistant")

    lines = []
    if project_prefix:
        lines.append(project_prefix)
    lines.append(f"Your name is {name}.")
    lines.append(
        f"The user is currently viewing the {instance.__class__._meta.verbose_name} "
        f"{instance.id}. Always reason in the context of this specific object."
    )
    if prompt:
        lines.append("Playbook for this model:")
        lines.append(prompt)
    else:
        lines.append(
            "No model-specific playbook is configured for this model. Help the user "
            "understand the object, what changed recently, and what reasonable next "
            "steps might be."
        )
    return "\n\n".join(lines)
