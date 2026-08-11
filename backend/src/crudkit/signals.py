import logging

from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save

from crudkit.models import BaseCrudKitModel

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


def _handle_post_save(sender, instance, update_fields=None, **kwargs):
    if not issubclass(sender, BaseCrudKitModel):
        return

    if sender.get_ai_fields() and not _is_ai_only_save(sender, update_fields):
        _dispatch_ai_processing(sender, instance.pk)

    for parent_model, fk_field_name in _get_parent_triggers(sender):
        parent_pk = getattr(instance, f"{fk_field_name}_id", None)
        if parent_pk is not None:
            _dispatch_ai_processing(parent_model, parent_pk)


def _handle_post_delete(sender, instance, **kwargs):
    if not issubclass(sender, BaseCrudKitModel):
        return

    for parent_model, fk_field_name in _get_parent_triggers(sender):
        parent_pk = getattr(instance, f"{fk_field_name}_id", None)
        if parent_pk is not None:
            _dispatch_ai_processing(parent_model, parent_pk)


post_save.connect(_handle_post_save, dispatch_uid="crudkit_ai_post_save")
post_delete.connect(_handle_post_delete, dispatch_uid="crudkit_ai_post_delete")
