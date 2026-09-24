"""
Object operations shared by the REST API, the assistant and the MCP server.
They route through the same serializers and permission checks as the REST
API so validation, FK coercion and ChangeLog behave identically everywhere.
"""

import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from rest_framework.exceptions import ValidationError as DRFValidationError

from crudkit.authorization import (
    get_authorized_queryset,
    has_model_permission,
    require_action_permission,
)
from crudkit.models import ChangeLog, FeedItem
from crudkit.utils import get_model_types
from crudkit_api.serializers import get_serializer

logger = logging.getLogger(__name__)


class RequestShim:
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


# ---------------------------------------------------------------------------
# Reads


def get_search_fields(model) -> list[str]:
    return list(getattr(getattr(model, "CrudKitSettings", None), "search_fields", None) or [])


def search_filter(model, query: str) -> Q:
    """Case-insensitive match of `query` against the model's `CrudKitSettings.search_fields`."""
    q = Q()
    for field in get_search_fields(model):
        q |= Q(**{f"{field}__icontains": query.strip()})
    return q


def search_objects(user, query: str, models_to_search=None, limit_per_model: int = 5) -> list[dict[str, Any]]:
    """`search_filter` across models, restricted to what `user` may view."""
    if models_to_search is None:
        models_to_search = get_model_types().values()
    results = []
    for mdl in models_to_search:
        if not get_search_fields(mdl) or not has_model_permission(user, mdl, "view"):
            continue
        serializer_cls = get_serializer(mdl, depth=0, fields=["id", "label", "object_images"])
        qs = get_authorized_queryset(user, mdl.objects.all(), "view").filter(search_filter(mdl, query))
        if "deleted" in [field.name for field in mdl._meta.fields]:
            qs = qs.filter(deleted=False)
        results += [serializer_cls(obj).data for obj in qs[0:limit_per_model]]
    return results


def get_feed(instance, limit: int = 20) -> list[dict[str, Any]]:
    """Recent FeedItems (notes, related-object events) on `instance`."""
    ct = ContentType.objects.get_for_model(instance.__class__)
    qs = FeedItem.objects.filter(parent_content_type=ct, parent_object_id=instance.pk, deleted=False).order_by(
        "-created_at"
    )[:limit]
    return [
        {
            "at": fei.created_at.isoformat(),
            "by": str(fei.created_by) if fei.created_by_id else None,
            "body": fei.body or "",
            "related_model": fei.related_content_type.model if fei.related_content_type_id else None,
            "related_id": str(fei.related_object_id) if fei.related_object_id else None,
        }
        for fei in qs
    ]


def get_changelog(instance, limit: int = 20) -> list[dict[str, Any]]:
    """Recent ChangeLog entries for `instance`: {at, by, field_changes: {field: [old, new]}}."""
    ct = ContentType.objects.get_for_model(instance.__class__)
    qs = ChangeLog.objects.filter(related_content_type=ct, related_object_id=instance.pk).order_by("-updated_at")[
        :limit
    ]
    return [
        {
            "at": cl.updated_at.isoformat(),
            "by": str(cl.updated_by) if cl.updated_by_id else None,
            "field_changes": cl.field_changes or {},
        }
        for cl in qs
    ]


# ---------------------------------------------------------------------------
# Writes


def run_action(instance, action_name: str, user, request=None) -> dict[str, Any]:
    """Mirror crudkit_api.views.GenericViewSet.call_action — invoke a
    @crm_action method bound to the instance."""
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
        request = RequestShim(user)
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


def _unwrap_fk_dict_values(model, fields: dict[str, Any]) -> dict[str, Any]:
    """Agents often echo the `describe_object` shape for FK fields,
    e.g. `{"stage": {"id": "OST1", "display": "Discovery"}}`. The DRF
    serializer's inline FK field expects a bare PK, not a dict — so we
    unwrap any value of that shape on a ForeignKey to just its `id` before
    handing it on. Other values are left untouched."""
    model_fields = {f.name: f for f in model._meta.fields}
    out: dict[str, Any] = {}
    for name, value in fields.items():
        field = model_fields.get(name)
        if field is not None and getattr(field, "many_to_one", False) and isinstance(value, dict) and "id" in value:
            unwrapped = value["id"]
            logger.info("Unwrapped FK dict for %s.%s: %s -> %r", model.__name__, name, value, unwrapped)
            out[name] = unwrapped
        else:
            out[name] = value
    return out


def _validated_serializer(model, instance, fields: dict[str, Any], user, request, partial: bool):
    """Build and validate the REST API serializer for `fields`. DRF silently
    drops fields not declared on the serializer; an agent mustn't get away
    with "I set X" when X never existed, so unknown fields are rejected."""
    fields = _unwrap_fk_dict_values(model, fields)
    serializer = get_serializer(model)(
        instance,
        data=fields,
        partial=partial,
        context={"request": request or RequestShim(user)},
    )
    unknown = [k for k in fields if k not in serializer.fields]
    if unknown:
        logger.warning("Rejected unknown field(s) %s on %s", unknown, model.__name__)
        raise ValueError(f"Field(s) not on {model.__name__}: {unknown}")
    try:
        serializer.is_valid(raise_exception=True)
    except DRFValidationError as exc:
        logger.warning("Validation failed on %s fields=%s errors=%s", model.__name__, list(fields), exc.detail)
        raise ValueError(f"Validation failed: {exc.detail}") from exc
    return serializer


def patch_fields(instance, fields: dict[str, Any], user, request=None) -> dict[str, Any]:
    """Apply a partial update through the same DRF serializer the REST API
    uses. The serializer turns FK PKs (ints or numeric strings) into model
    instances, runs `clean()`, and surfaces validation errors as ValueError."""
    if not isinstance(fields, dict) or not fields:
        raise ValueError("No fields to patch")
    serializer = _validated_serializer(instance.__class__, instance, fields, user, request, partial=True)

    # Mirror GenericViewSet.perform_update — snapshot the pre-save state for
    # ChangeLog, save, log the diff.
    old_instance = instance.__class__.objects.get(pk=instance.pk)
    with transaction.atomic():
        serializer.save()
        ChangeLog.objects.create_from_objects(old_instance, serializer.instance)

    logger.info("Patched %s.%s fields=%s", instance.__class__.__name__, instance.pk, list(fields))
    return {"kind": "patch", "applied": list(fields.keys())}


def create_object(model, fields: dict[str, Any], user, request=None):
    """Mirror GenericViewSet.create + perform_create."""
    serializer = _validated_serializer(model, None, fields, user, request, partial=False)
    serializer.initial_instance = model.from_query_params({}, {"created_by": user, "updated_by": user})
    with transaction.atomic():
        instance = serializer.save()
        ChangeLog.objects.create_from_objects(None, instance)
    logger.info("Created %s.%s", model.__name__, instance.pk)
    return instance


def create_note(instance, body: str, user) -> dict[str, Any]:
    """Create a FeedItem note on the target object."""
    body = (body or "").strip()
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
