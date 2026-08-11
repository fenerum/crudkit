"""Built-in AI backend for CrudKit using pydantic-ai.

The model comes from ``crudkit.llm.model_context()``, configured via the
``CRUDKIT_AI_MODEL_FACTORY`` / ``CRUDKIT_AI_MODEL`` settings. When neither is
set, AI-field processing is skipped.
"""

import asyncio
import json
import logging
from typing import Any

from pydantic import create_model as create_pydantic_model
from pydantic_ai import Agent

from crudkit import llm

logger = logging.getLogger(__name__)


def _build_pydantic_model(field_specs: dict[str, Any]) -> type:
    """Build a Pydantic model dynamically from the field specs dict."""
    field_definitions: dict[str, tuple] = {}
    for name, spec in field_specs.items():
        ftype = spec.get("type")
        if ftype == "string":
            field_definitions[name] = (str | None, None)
        elif ftype == "boolean":
            field_definitions[name] = (bool | None, None)
        elif ftype == "array":
            field_definitions[name] = (list[str] | None, None)
    return create_pydantic_model("AIFieldsOutput", **field_definitions)


def _build_prompt(context: str, field_specs: dict[str, Any]) -> str:
    schema = json.dumps(field_specs, indent=2)
    return (
        "Based on the context below, populate the requested fields.\n"
        "Return ONLY valid JSON matching the schema — no markdown, no explanation.\n\n"
        f"## Context\n{context}\n\n"
        f"## Required JSON schema\n{schema}\n\n"
        "Respond with JSON only."
    )


async def _run(prompt: str, output_type: type) -> Any:
    async with llm.model_context() as model:
        agent = Agent(model, output_type=output_type)
        return await agent.run(prompt)


def process(context: str, field_specs: dict[str, Any]) -> dict[str, Any]:
    """Process AI fields using pydantic-ai with the shared Mistral model.

    Args:
        context: Plain-text context from ``instance.get_ai_context()``.
        field_specs: ``{field_name: {type, description, ...}}`` JSON-Schema-like dict.

    Returns:
        ``{field_name: value}`` dict with the AI-generated values.
    """
    if not llm.is_configured():
        logger.info("Skipping AI field processing: no CrudKit AI model configured")
        return {}

    pydantic_model = _build_pydantic_model(field_specs)
    prompt = _build_prompt(context, field_specs)

    try:
        result = asyncio.run(_run(prompt, pydantic_model))
    except Exception:
        logger.exception("AI backend LLM call failed")
        return {}

    return result.output.model_dump()
