"""
Object operations shared by the REST API, the assistant and the MCP server.
They route through the same serializers and permission checks as the REST
API so validation, FK coercion and ChangeLog behave identically everywhere.
"""

import copy
import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from rest_framework.exceptions import ValidationError as DRFValidationError

from crudkit.audit import audit
from crudkit.authorization import (
    get_authorized_queryset,
    has_model_permission,
    has_object_permission,
    require_action_permission,
    require_object_permission,
    requires_approval,
)
from crudkit.models import ChangeLog, FeedItem, field_value, same_value
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
    """Recent ChangeLog entries for `instance`: {at, by, action, source, client,
    label, change_set, field_changes: {field: [old, new]}}."""
    ct = ContentType.objects.get_for_model(instance.__class__)
    qs = ChangeLog.objects.filter(related_content_type=ct, related_object_id=instance.pk).order_by("-updated_at")[
        :limit
    ]
    return [
        {
            "at": cl.updated_at.isoformat(),
            "by": str(cl.updated_by) if cl.updated_by_id else None,
            "action": cl.action,
            "source": cl.source,
            "client": cl.client,
            "label": cl.label,
            "change_set": str(cl.change_set) if cl.change_set else None,
            "field_changes": cl.field_changes or {},
        }
        for cl in qs
    ]


def get_history(instance, limit: int = 200) -> list[dict[str, Any]]:
    """ChangeLog entries for `instance`, newest first, grouped into the change
    sets that produced them, each flagged with whether it can be reverted."""
    ct = ContentType.objects.get_for_model(instance.__class__)
    entries = list(
        ChangeLog.objects.filter(related_content_type=ct, related_object_id=instance.pk)
        .select_related("updated_by")
        .order_by("-created_at", "-id")[:limit]
    )
    change_sets = {entry.change_set for entry in entries if entry.change_set}
    totals = {
        row["change_set"]: row
        for row in ChangeLog.objects.filter(change_set__in=change_sets)
        .values("change_set")
        .annotate(
            total=Count("id"),
            unrevertible=Count("id", filter=~Q(action__in=REVERTIBLE_ACTIONS)),
        )
    }
    reverted = set(ChangeLog.objects.filter(revert_of__in=change_sets).values_list("revert_of", flat=True))

    groups: dict[Any, dict[str, Any]] = {}
    for entry in entries:
        key = entry.change_set or entry.id
        group = groups.get(key)
        if group is None:
            user = entry.updated_by
            stats = totals.get(entry.change_set, {})
            group = groups[key] = {
                "change_set": str(entry.change_set) if entry.change_set else None,
                "at": entry.created_at.isoformat(),
                "by": {"id": user.pk, "label": user.get_full_name() or user.get_username()} if user else None,
                "source": entry.source,
                "client": entry.client,
                "label": entry.label,
                "actions": [],
                "entries": [],
                "total_entries": stats.get("total", 1),
                "reverted": entry.change_set in reverted,
                "revertible": bool(stats) and not stats["unrevertible"] and entry.change_set not in reverted,
            }
        if entry.action not in group["actions"]:
            group["actions"].append(entry.action)
        group["label"] = group["label"] or entry.label
        group["entries"].append({"id": entry.id, "action": entry.action, "field_changes": entry.field_changes or {}})
    for group in groups.values():
        group["other_records"] = group.pop("total_entries") - len(group["entries"])
    return list(groups.values())


# ---------------------------------------------------------------------------
# Writes


def check_action(instance, action_name: str, user) -> None:
    """Raise unless `action_name` is one of the instance's @crm_actions and `user` may run it."""
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


def perform_action(instance, action_name: str, user, request=None):
    """Invoke a @crm_action method bound to the instance, log what it changed,
    and return whatever the action returned."""
    check_action(instance, action_name, user)
    if request is None:
        request = RequestShim(user)
    logger.info("Running action %s on %s.%s", action_name, instance.__class__.__name__, instance.pk)
    action = instance._actions[action_name]
    before = _refetch(instance)
    response = action(request)
    # An action may delete its own record; log that as a delete.
    after = instance.__class__._base_manager.filter(pk=instance.pk).first()
    ChangeLog.objects.create_from_objects(
        before,
        after,
        user=user,
        action=ChangeLog.Action.ACTION if after is not None else ChangeLog.Action.DELETE,
        label=getattr(action, "verbose_name", None) or action_name,
    )
    return response


def run_action(instance, action_name: str, user, request=None) -> dict[str, Any]:
    """Like perform_action, with the result normalised to a JSON-safe outcome."""
    return _serialize_action_response(perform_action(instance, action_name, user, request))


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
    old_instance = _refetch(instance)
    with transaction.atomic():
        serializer.save()
        ChangeLog.objects.create_from_objects(old_instance, serializer.instance, user=user)

    logger.info("Patched %s.%s fields=%s", instance.__class__.__name__, instance.pk, list(fields))
    return {"kind": "patch", "applied": list(fields.keys())}


def create_object(model, fields: dict[str, Any], user, request=None):
    """Mirror GenericViewSet.create + perform_create."""
    serializer = _validated_serializer(model, None, fields, user, request, partial=False)
    serializer.initial_instance = model.from_query_params({}, {"created_by": user, "updated_by": user})
    with transaction.atomic():
        instance = serializer.save()
        ChangeLog.objects.create_from_objects(None, instance, user=user)
    logger.info("Created %s.%s", model.__name__, instance.pk)
    return instance


def check_create(model, fields: dict[str, Any], user) -> None:
    """Validate a create as create_object would, model `clean()` included,
    without saving. Raises ValueError."""
    serializer = _validated_serializer(model, None, fields, user, None, partial=False)
    instance = model.from_query_params({}, {"created_by": user, "updated_by": user})
    for field, value in serializer.validated_data.items():
        setattr(instance, field, value)
    try:
        serializer._validate_model(instance)
    except DRFValidationError as exc:
        raise ValueError(f"Validation failed: {exc.detail}") from exc


def create_note(instance, body: str, user) -> dict[str, Any]:
    """Create a FeedItem note on the target object."""
    body = (body or "").strip()
    if not body:
        raise ValueError("Note body is empty")
    with transaction.atomic():
        fei = FeedItem.objects.create(
            parent_content_type=ContentType.objects.get_for_model(instance.__class__),
            parent_object_id=instance.pk,
            body=body,
            created_by=user,
            updated_by=user,
        )
        # Logged (as stored, ids normalised) so the change set that added the note can be undone.
        ChangeLog.objects.create_from_objects(None, _refetch(fei), user=user)
    logger.info("Created FeedItem %s on %s.%s", fei.pk, instance.__class__.__name__, instance.pk)
    return {"kind": "note", "feeditem_id": fei.id}


def _refetch(instance):
    return instance.__class__._base_manager.get(pk=instance.pk)


# ---------------------------------------------------------------------------
# Undo

REVERTIBLE_ACTIONS = [
    ChangeLog.Action.CREATE,
    ChangeLog.Action.UPDATE,
    ChangeLog.Action.DELETE,
    ChangeLog.Action.RESTORE,
    ChangeLog.Action.ACTION,
    ChangeLog.Action.REVERT,
]


def check_revertible(change_set) -> list[ChangeLog]:
    """The change set's entries, newest first. Raises ValueError if it cannot
    be reverted."""
    entries = list(
        ChangeLog.objects.filter(change_set=change_set)
        .select_related("related_content_type")
        .order_by("-created_at", "-id")
    )
    if not entries:
        raise ValueError(f"Unknown change set {change_set}")
    if any(entry.action == ChangeLog.Action.MERGE for entry in entries):
        raise ValueError("Merges cannot be reverted")
    if any(entry.action not in REVERTIBLE_ACTIONS for entry in entries):
        raise ValueError("This change was recorded before undo was available and cannot be reverted")
    if ChangeLog.objects.filter(revert_of=change_set).exists():
        raise ValueError("This change has already been reverted")
    return entries


def revert_change_set(change_set, user, force: bool = False) -> dict[str, Any]:
    """Undo every entry of a change set, newest first, in one transaction.

    Returns {"change_set", "reverted"} for the new change set, or
    {"conflicts": [...]} (and changes nothing) when a record has changed since,
    unless `force`."""
    entries = check_revertible(change_set)
    conflicts = []
    reverted = 0
    with audit("revert", user=user, revert_of=change_set) as context, transaction.atomic():
        # Locks the change set's entries, so two reverts of it can't both pass
        # the "already reverted" check (a no-op on SQLite).
        list(ChangeLog.objects.select_for_update().filter(change_set=change_set).values_list("pk", flat=True))
        if ChangeLog.objects.filter(revert_of=change_set).exists():
            raise ValueError("This change has already been reverted")
        for entry in entries:
            model = entry.related_content_type.model_class()
            instance = model._base_manager.filter(pk=entry.related_object_id).first()
            if instance is None:
                conflicts.append(_conflict(entry, model, reason="The record no longer exists"))
                continue
            _require_revert_permission(user, entry, instance)
            conflicts += _entry_conflicts(entry, instance)
            _revert_entry(entry, instance, user)
            reverted += 1
        if conflicts and not force:
            transaction.set_rollback(True)
            return {"conflicts": conflicts}
    logger.info("Reverted change set %s as %s", change_set, context.change_set)
    return {"change_set": str(context.change_set), "reverted": reverted}


def restore_object(instance, user):
    """Bring back a soft-deleted record."""
    require_object_permission(user, instance, "change")
    if not getattr(instance, "deleted", False):
        raise ValueError(f"{instance} is not deleted")
    if instance.merged_into_id:
        raise ValueError(f"{instance} was merged into {instance.merged_into_id} and cannot be restored")
    with transaction.atomic():
        _undelete(instance, user, ChangeLog.Action.RESTORE)
    return instance


def _undelete(instance, user, action):
    before = copy.copy(instance)
    instance.deleted = False
    instance.updated_by = user
    instance.save(update_fields=["deleted", "updated_by", "updated_at"])
    ChangeLog.objects.create_from_objects(before, instance, user=user, action=action)


def _require_revert_permission(user, entry, instance):
    permission = "delete" if entry.action == ChangeLog.Action.CREATE else "change"
    if not has_object_permission(user, instance, permission):
        raise PermissionDenied(f"You may not {permission} {instance}")
    if entry.action == ChangeLog.Action.ACTION:
        # Undoing an action needs the same permission as running it. Entries
        # name the action by its label; an action that no longer exists can't
        # be checked, so it can't be undone.
        name = action_for_label(instance.__class__, entry.label)
        if name is None:
            raise PermissionDenied(f"The action {entry.label!r} no longer exists on {instance}; it can't be undone")
        require_action_permission(user, instance, name)


def action_for_label(model, label: str) -> str | None:
    """The @crm_action a ChangeLog entry's label names, if it still exists."""
    for name, func in model.__dict__.items():
        if getattr(func, "_crm_action", False) and (getattr(func, "verbose_name", None) or name) == label:
            return name
    return None


def revert_requires_approval(change_set) -> bool:
    """Whether undoing `change_set` touches what MCP clients and agents may only
    propose: an approval field, or the effects of an approval-required action
    (or of an action that no longer exists, which can't be checked)."""
    for entry in ChangeLog.objects.filter(change_set=change_set).select_related("related_content_type"):
        model = entry.related_content_type.model_class() if entry.related_content_type_id else None
        if model is None:
            continue
        if requires_approval(model, fields=list(entry.field_changes or {})):
            return True
        if entry.action == ChangeLog.Action.ACTION:
            name = action_for_label(model, entry.label)
            if name is None or requires_approval(model, action=name):
                return True
    return False


def _entry_fields(entry, model):
    for name, (old, new) in (entry.field_changes or {}).items():
        try:
            yield model._meta.get_field(name), old, new
        except FieldDoesNotExist:
            continue


def _entry_conflicts(entry, instance) -> list[dict[str, Any]]:
    model = instance.__class__
    if entry.action == ChangeLog.Action.DELETE:
        if instance.deleted:
            return []
        return [_conflict(entry, model, instance, "deleted", True, False)]
    return [
        _conflict(entry, model, instance, field.name, new, current)
        for field, _old, new in _entry_fields(entry, model)
        if not isinstance(field, models.FileField)
        and not same_value(field, current := field_value(instance, field), new)
    ]


def _conflict(entry, model, instance=None, field=None, expected=None, current=None, reason="") -> dict[str, Any]:
    return {
        "object": f"{model.TYPE_ID}{entry.related_object_id}" if model else None,
        "label": str(instance) if instance is not None else None,
        "field": field,
        "expected": expected,
        "current": current,
        "reason": reason,
    }


def _revert_entry(entry, instance, user):
    if entry.action == ChangeLog.Action.DELETE:
        _undelete(instance, user, ChangeLog.Action.REVERT)
        return
    before = copy.copy(instance)
    if entry.action == ChangeLog.Action.CREATE:
        instance.updated_by = user
        instance.soft_delete()
    else:
        update_fields = ["updated_by", "updated_at"]
        m2m = {}
        for field, old, _new in _entry_fields(entry, instance.__class__):
            if isinstance(field, models.FileField):
                continue
            if field.many_to_many:
                m2m[field] = old or []
                continue
            setattr(instance, field.attname, None if old is None else field.to_python(old))
            update_fields.append(field.attname)
        instance.updated_by = user
        try:
            # The same model validation a PATCH gets (e.g. who an agent may run as).
            instance.clean()
            with transaction.atomic():
                instance.save(update_fields=update_fields)
                # Logged by the m2m_changed handler, as part of this revert.
                for field, ids in m2m.items():
                    getattr(instance, field.name).set([field.related_model._meta.pk.to_python(i) for i in ids])
        except (ValidationError, IntegrityError) as exc:
            raise ValueError(f"Could not revert {instance}: {exc}") from exc
        if m2m and len(update_fields) == 2:
            return
    ChangeLog.objects.create_from_objects(before, instance, user=user, action=ChangeLog.Action.REVERT)
