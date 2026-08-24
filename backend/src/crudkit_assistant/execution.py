"""
Carries out a confirmed AssistantProposal. Runs synchronously in the consumer
thread when the user clicks Confirm. Routes through the same code paths the
REST API uses so permissions, validation, FK PK coercion, and ChangeLog all
behave identically.
"""

import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.http import HttpResponseRedirect
from rest_framework.exceptions import ValidationError as DRFValidationError

from crudkit.authorization import require_action_permission, require_object_permission
from crudkit.models import ChangeLog
from crudkit_api.serializers import get_serializer

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

    if proposal.kind == proposal.Kind.ACTION:
        return _run_action(instance, proposal.payload, user, request)
    if proposal.kind == proposal.Kind.PATCH:
        return _patch_fields(instance, proposal.payload, user, request)
    if proposal.kind == proposal.Kind.NOTE:
        return _create_note(instance, proposal.payload, user)
    raise ValueError(f"Unknown proposal kind {proposal.kind!r}")


def _run_action(instance, payload: dict, user, request) -> dict[str, Any]:
    """Mirror crudkit_api.views.GenericViewSet.call_action — invoke a
    @crm_action method bound to the instance."""
    action_name = payload.get("action")
    if not action_name or action_name not in instance._actions:
        available = list(instance._actions.keys())
        logger.warning(
            "Action %r not available on %s; available=%s",
            action_name,
            instance.__class__.__name__,
            available,
        )
        raise ValueError(f"Action {action_name!r} not available on {instance}")
    require_action_permission(user, instance, action_name)
    if request is None:
        request = _RequestShim(user)
    logger.info("Running action %s on %s.%s", action_name, instance.__class__.__name__, instance.pk)
    response = instance._actions[action_name](request)
    return _serialize_action_response(response)


def _serialize_action_response(response) -> dict[str, Any]:
    """Normalise whatever a @crm_action returned into a JSON-safe outcome dict."""
    if isinstance(response, HttpResponseRedirect):
        return {"kind": "redirect", "url": response.url}
    if isinstance(response, models.Model):
        return {"kind": "object", "id": str(getattr(response, "id", response.pk))}
    if hasattr(response, "data"):
        try:
            return {"kind": "response", "data": response.data}
        except Exception:
            return {"kind": "response", "status": getattr(response, "status_code", None)}
    return {"kind": "value", "value": str(response) if response is not None else None}


def _unwrap_fk_dict_values(instance, fields: dict[str, Any]) -> dict[str, Any]:
    """The agent often echoes the `describe_object` shape for FK fields,
    e.g. `{"stage": {"id": "OST1", "display": "Discovery"}}`. The DRF
    serializer's inline FK field expects a bare PK, not a dict — so we
    unwrap any value of that shape on a ForeignKey to just its `id` before
    handing it on. Other values are left untouched."""
    model_fields = {f.name: f for f in instance._meta.fields}
    out: dict[str, Any] = {}
    for name, value in fields.items():
        field = model_fields.get(name)
        if field is not None and getattr(field, "many_to_one", False) and isinstance(value, dict) and "id" in value:
            unwrapped = value["id"]
            logger.info(
                "Unwrapped FK dict for %s.%s: %s -> %r",
                instance.__class__.__name__,
                name,
                value,
                unwrapped,
            )
            out[name] = unwrapped
        else:
            out[name] = value
    return out


def _patch_fields(instance, payload: dict, user, request) -> dict[str, Any]:
    """Apply a partial update through the same DRF serializer the REST API
    uses. The serializer turns FK PKs (ints or numeric strings) into model
    instances, runs `clean()`, and surfaces validation errors as DRF errors
    we can stringify for the user-visible failure message."""
    fields = payload.get("fields") or {}
    if not isinstance(fields, dict) or not fields:
        raise ValueError("No fields to patch")

    fields = _unwrap_fk_dict_values(instance, fields)

    serializer_cls = get_serializer(instance.__class__)
    if request is None:
        request = _RequestShim(user)
    serializer = serializer_cls(
        instance,
        data=fields,
        partial=True,
        context={"request": request},
    )
    # DRF silently drops fields not declared on the serializer. The agent
    # mustn't get away with "I patched X" when X never existed.
    unknown = [k for k in fields if k not in serializer.fields]
    if unknown:
        logger.warning(
            "Patch rejected: unknown field(s) %s on %s",
            unknown,
            instance.__class__.__name__,
        )
        raise ValueError(f"Field(s) not on {instance.__class__.__name__}: {unknown}")
    try:
        serializer.is_valid(raise_exception=True)
    except DRFValidationError as exc:
        logger.warning(
            "Patch validation failed on %s.%s fields=%s errors=%s",
            instance.__class__.__name__,
            instance.pk,
            list(fields),
            exc.detail,
        )
        raise ValueError(f"Validation failed: {exc.detail}") from exc

    # Mirror crudkit_api.views.GenericViewSet.perform_update — snapshot the
    # pre-save state for ChangeLog, save, log the diff.
    old_instance = instance.__class__.objects.get(pk=instance.pk)
    with transaction.atomic():
        serializer.save()
        ChangeLog.objects.create_from_objects(old_instance, serializer.instance)

    logger.info(
        "Patched %s.%s fields=%s",
        instance.__class__.__name__,
        instance.pk,
        list(fields),
    )
    return {"kind": "patch", "applied": list(fields.keys())}


def _create_note(instance, payload: dict, user) -> dict[str, Any]:
    """Create a FeedItem note on the target object."""
    from crudkit.models import FeedItem

    body = (payload.get("body") or "").strip()
    if not body:
        raise ValueError("Note body is empty")
    fei = FeedItem.objects.create(
        parent_content_type=ContentType.objects.get_for_model(instance.__class__),
        parent_object_id=instance.pk,
        body=body,
        created_by=user,
        updated_by=user,
    )
    logger.info("Created FeedItem %s on %s.%s", fei.pk, instance.__class__.__name__, instance.pk)
    return {"kind": "note", "feeditem_id": fei.id}


class _RequestShim:
    """Minimal request-like object for @crm_action methods and the DRF
    serializer's request-aware `_fields` filtering."""

    def __init__(self, user):
        self.user = user
        self.data: dict = {}

    class _EmptyGet:
        def get(self, *args, **kwargs):
            return None

        def __contains__(self, key):
            return False

    GET = _EmptyGet()
