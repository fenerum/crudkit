"""LLM model factory indirection for CrudKit AI features.

Consumers configure one of (checked in this order):
- ``CRUDKIT_AI_MODEL_FACTORY``: dotted path to an async context manager that
  yields a pydantic-ai ``Model`` (and may own client lifecycle, e.g. closing
  its httpx client on exit).
- ``CRUDKIT_AI_MODEL``: a pydantic-ai model string such as
  ``"mistral:mistral-large-latest"``, resolved via ``infer_model``.

With neither set, AI features are disabled: callers should check
``is_configured()`` and skip gracefully; ``model_context()`` raises
``ImproperlyConfigured``.

``ai_context()`` renders the user-maintained AI context documents (AIC) that
every LLM feature adds to its prompt.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from pydantic_ai.models import Model, infer_model

from crudkit.models import AIContext


def is_configured() -> bool:
    return bool(getattr(settings, "CRUDKIT_AI_MODEL_FACTORY", None) or getattr(settings, "CRUDKIT_AI_MODEL", None))


@asynccontextmanager
async def model_context() -> AsyncGenerator[Model]:
    factory_path = getattr(settings, "CRUDKIT_AI_MODEL_FACTORY", None)
    if factory_path:
        factory = import_string(factory_path)
        async with factory() as model:
            yield model
        return

    model_name = getattr(settings, "CRUDKIT_AI_MODEL", None)
    if model_name:
        yield infer_model(model_name)
        return

    raise ImproperlyConfigured(
        "CrudKit AI features require either CRUDKIT_AI_MODEL_FACTORY (dotted path to an "
        "async context manager yielding a pydantic-ai Model) or CRUDKIT_AI_MODEL "
        '(a pydantic-ai model string, e.g. "mistral:mistral-large-latest").'
    )


def ai_context(type_id: str | None = None, *, include_global: bool = True, with_ids: bool = False) -> str:
    """Active AI context documents as markdown, each under a ``## <name>`` heading:
    the global ones (no ``model_types``) plus those scoped to ``type_id``.
    ``with_ids`` adds each document's id to its heading so the assistant can
    propose edits to it."""
    docs = [
        doc
        for doc in AIContext.objects.filter(deleted=False, active=True).order_by("order", "name")
        # Filtered in Python: JSON containment lookups differ between SQLite and Postgres.
        if (include_global and not doc.model_types) or (type_id and type_id in (doc.model_types or []))
    ]
    return "\n\n".join(f"## {doc.name}{f' ({doc.pk})' if with_ids else ''}\n{doc.body.strip()}" for doc in docs)
