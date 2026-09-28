"""Writing AssistantProposal rows: the one place the assistant, MCP clients
and agents record a change for a person to Confirm or Skip."""

import json

from django.contrib.contenttypes.models import ContentType

from crudkit_assistant.models import AssistantProposal


def create_proposal(
    user,
    model,
    instance,
    kind: str,
    label: str,
    payload: dict,
    *,
    source: str = "assistant",
    client: str = "",
    reasoning: str = "",
    session_key: str = "",
) -> AssistantProposal:
    """`instance` is the record to change, or None for a create of `model`."""
    return AssistantProposal.objects.create(
        target_content_type=ContentType.objects.get_for_model(model),
        target_object_id=instance.pk if instance is not None else None,
        session_key=session_key,
        source=source,
        client=client[:255],
        kind=kind,
        label=label[:255],
        payload=payload,
        reasoning=reasoning or "",
        created_by=user,
        updated_by=user,
    )


def patch_label(fields: dict) -> str:
    try:
        preview = ", ".join(f"{k}={json.dumps(v, default=str)}" for k, v in fields.items())
    except (TypeError, ValueError):
        preview = ", ".join(fields)
    return f"Update {preview}"
