"""
Carries out a confirmed AssistantProposal. Runs synchronously in the consumer
thread when the user clicks Confirm. Routes through crudkit_api.services so
permissions, validation, FK PK coercion, and ChangeLog behave identically to
the REST API.
"""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied

from crudkit.authorization import has_model_permission, require_object_permission
from crudkit_api import records
from crudkit_api.services import create_note, create_object, patch_fields, revert_change_set, run_action

logger = logging.getLogger(__name__)


def execute_proposal(proposal, user, request=None) -> dict[str, Any]:
    """Dispatch a confirmed proposal to the right executor. Raises on failure;
    `AssistantProposal.apply()` converts that to status=FAILED."""
    if proposal.kind == proposal.Kind.CREATE:
        return _create(proposal, user, request)
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
    if proposal.kind == proposal.Kind.REVERT:
        result = revert_change_set(payload.get("change_set"), user)
        if "conflicts" in result:
            changed = ", ".join(f"{c['object']}.{c['field']}" for c in result["conflicts"])
            raise ValueError(f"Not reverted: changed since ({changed})")
        return {"kind": "revert", **result}
    raise ValueError(f"Unknown proposal kind {proposal.kind!r}")


def _create(proposal, user, request) -> dict[str, Any]:
    model = proposal.target_content_type.model_class()
    if not has_model_permission(user, model, "add"):
        raise PermissionDenied
    fields = records.checked_fields(model, user, proposal.payload.get("fields"))
    instance = create_object(model, fields, user, request)
    logger.info("execute_proposal id=%s kind=create created %s", proposal.pk, instance.id)
    proposal.target_object_id = instance.pk
    proposal.save(update_fields=["target_object_id"])
    return {"kind": "create", "id": str(instance.id)}
