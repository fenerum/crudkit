import logging

from django.apps import apps
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save

from crudkit.models import BaseCrudKitModel, ChangeLog, m2m_value
from crudkit.realtime import broadcast_change

logger = logging.getLogger(__name__)


def _is_ai_only_save(model_cls, update_fields):
    """Return True when save() touched only AI field columns (called by process_ai_fields)."""
    if update_fields is None:
        return False
    ai_attnames = {
        f.attname for f in model_cls._meta.get_fields() if getattr(f, "ai_field", False) and hasattr(f, "attname")
    }
    return bool(update_fields) and set(update_fields).issubset(ai_attnames)


def _get_parent_triggers(sender):
    """Find parent models whose AI fields should refresh when sender is saved/deleted."""
    triggers = []
    for model_cls in apps.get_models():
        if not issubclass(model_cls, BaseCrudKitModel) or not model_cls.get_ai_fields():
            continue
        children = getattr(getattr(model_cls, "CrudKitSettings", None), "ai_trigger_children", [])
        for child_model_name, fk_field_name in children:
            if apps.get_model(model_cls._meta.app_label, child_model_name) is sender:
                triggers.append((model_cls, fk_field_name))
    return triggers


def _dispatch_ai_processing(model_cls, pk):
    app_label = model_cls._meta.app_label
    model_name = model_cls.__name__

    def _dispatch():
        from crudkit.tasks import process_ai_fields  # avoid circular import

        try:
            process_ai_fields.delay(app_label, model_name, pk)
        except Exception:
            # A broken/missing Celery broker (common in dev workspaces) must
            # not retroactively fail the save that just committed. The data
            # is already on disk; surface the enqueue failure as a log line
            # so we don't silently lose AI-field refreshes in production.
            logger.exception(
                "Failed to enqueue process_ai_fields for %s.%s pk=%s",
                app_label,
                model_name,
                pk,
            )

    transaction.on_commit(_dispatch)


def _broadcast_on_commit(sender, instance, action):
    type_id = getattr(sender, "TYPE_ID", None)
    if not type_id:
        return
    pk = instance.pk
    by = getattr(instance, "updated_by_id", None)
    transaction.on_commit(lambda: broadcast_change(type_id, pk, action, by))


def _handle_post_save(sender, instance, update_fields=None, **kwargs):
    _broadcast_on_commit(sender, instance, "saved")
    if not issubclass(sender, BaseCrudKitModel):
        return

    if sender.get_ai_fields() and not _is_ai_only_save(sender, update_fields):
        _dispatch_ai_processing(sender, instance.pk)

    for parent_model, fk_field_name in _get_parent_triggers(sender):
        parent_pk = getattr(instance, f"{fk_field_name}_id", None)
        if parent_pk is not None:
            _dispatch_ai_processing(parent_model, parent_pk)


def _handle_post_delete(sender, instance, **kwargs):
    _broadcast_on_commit(sender, instance, "deleted")
    if not issubclass(sender, BaseCrudKitModel):
        return

    for parent_model, fk_field_name in _get_parent_triggers(sender):
        parent_pk = getattr(instance, f"{fk_field_name}_id", None)
        if parent_pk is not None:
            _dispatch_ai_processing(parent_model, parent_pk)


def _handle_m2m_changed(sender, instance, action, reverse, **kwargs):
    """Log a change to a many-to-many field as an update of the record that
    declares it, with the related ids before and after. The reverse side
    (`topic.ticket_set.add(...)`) isn't logged."""
    if reverse or not isinstance(instance, BaseCrudKitModel) or instance.pk is None:
        return
    field = next((f for f in instance._meta.many_to_many if f.remote_field.through is sender), None)
    if field is None:
        return
    before = instance.__dict__.setdefault("_crudkit_m2m_before", {})
    if action in ("pre_add", "pre_remove", "pre_clear"):
        before[field.name] = m2m_value(instance, field)
    elif action in ("post_add", "post_remove", "post_clear") and field.name in before:
        old, new = before.pop(field.name), m2m_value(instance, field)
        if old != new:
            ChangeLog.objects.create_for_m2m(instance, field, old, new)


post_save.connect(_handle_post_save, dispatch_uid="crudkit_ai_post_save")
m2m_changed.connect(_handle_m2m_changed, dispatch_uid="crudkit_changelog_m2m")
post_delete.connect(_handle_post_delete, dispatch_uid="crudkit_ai_post_delete")
