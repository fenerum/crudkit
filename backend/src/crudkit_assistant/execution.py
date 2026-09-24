"""
Carries out a confirmed AssistantProposal. Runs synchronously in the consumer
thread when the user clicks Confirm. Routes through crudkit_api.services so
permissions, validation, FK PK coercion, and ChangeLog behave identically to
the REST API.
"""

import logging
from typing import Any

from crudkit.authorization import require_object_permission
from crudkit_api.services import create_note, patch_fields, run_action

logger = logging.getLogger(__name__)


def execute_proposal(proposal, user, request=None) -> dict[str, Any]:
    """Dispatch a confirmed proposal to the right executor. Raises on failure;
    `AssistantProposal.apply()` converts that to status=FAILED."""
    instance = proposal.target
    if instance is None:
        raise ValueError("Target object no longer exists")
    require_object_permission(user, instance, "change")

    logger.info(
        "execute_proposal id=%s kind=%s target=%s.%s",
        proposal.pk,
        proposal.kind,
        instance.__class__.__name__,
        instance.pk,
    )

    payload = proposal.payload
    if proposal.kind == proposal.Kind.ACTION:
        return run_action(instance, payload.get("action"), user, request)
    if proposal.kind == proposal.Kind.PATCH:
        return patch_fields(instance, payload.get("fields") or {}, user, request)
    if proposal.kind == proposal.Kind.NOTE:
        return create_note(instance, payload.get("body"), user)
    raise ValueError(f"Unknown proposal kind {proposal.kind!r}")
