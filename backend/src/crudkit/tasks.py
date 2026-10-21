"""Generic Celery task for populating AI fields on any CrudKit model."""

import logging
from typing import Any

from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.db import close_old_connections

from crudkit.ai_backend import process
from crudkit.fields import AIBooleanField, AICategoryField, AIForeignKeyField, AISummaryField, AITagsField

logger = logging.getLogger(__name__)


def _build_field_specs(ai_fields: list, instance=None) -> dict[str, dict[str, Any]]:
    """Build a dict of {field_name: JSON-Schema-like spec} for the backend."""
    specs: dict[str, dict[str, Any]] = {}
    for field in ai_fields:
        desc = getattr(field, "ai_prompt", "") or field.verbose_name
        if isinstance(field, AISummaryField):
            specs[field.name] = {"type": "string", "description": desc}
        elif isinstance(field, AICategoryField):
            choices = [c[0] for c in (field.choices or [])]
            specs[field.name] = {"type": "string", "description": desc, "enum": choices}
        elif isinstance(field, AIBooleanField):
            specs[field.name] = {"type": "boolean", "description": desc}
        elif isinstance(field, AIForeignKeyField):
            related_model = field.related_model
            qs = related_model.objects.filter(deleted=False)
            authorize = getattr(getattr(related_model, "CrudKitSettings", None), "get_authorized_queryset", None)
            if instance is not None and authorize:
                qs = authorize(instance.updated_by, qs, "view")
            scope_candidates = getattr(
                getattr(instance.__class__, "CrudKitSettings", None),
                "get_ai_foreign_key_queryset",
                None,
            )
            if scope_candidates:
                qs = scope_candidates(instance, field, qs)
            limit = max(1, int(getattr(settings, "CRUDKIT_AI_FOREIGN_KEY_CHOICES_LIMIT", 50)))
            options = []
            for obj in qs[:limit]:
                option = {"pk": str(obj.pk), "name": str(obj)}
                if hasattr(obj, "get_ai_context"):
                    option["context"] = obj.get_ai_context()
                options.append(option)
            if not options:
                continue
            specs[field.name] = {
                "type": "string",
                "description": desc,
                "enum": [o["pk"] for o in options],
                "options": options,
            }
        elif isinstance(field, AITagsField):
            max_tags = getattr(field, "max_tags", 10)
            specs[field.name] = {
                "type": "array",
                "items": {"type": "string"},
                "description": f"{desc} (max {max_tags} tags)",
            }
    return specs


@shared_task
def process_ai_fields(app_label: str, model_name: str, pk: int) -> None:
    """Populate all AI fields on a model instance."""
    close_old_connections()

    model_cls = apps.get_model(app_label, model_name)
    ai_fields = model_cls.get_ai_fields()
    if not ai_fields:
        logger.info(f"No AI fields on {app_label}.{model_name}")
        return

    try:
        instance = model_cls.objects.get(pk=pk)
    except model_cls.DoesNotExist:
        logger.warning(f"{app_label}.{model_name} pk={pk} not found")
        return

    context = instance.get_ai_context()
    if not context.strip():
        logger.info(f"Empty AI context for {instance}, skipping")
        return

    field_specs = _build_field_specs(ai_fields, instance=instance)

    try:
        result = process(context, field_specs)
    except Exception:
        logger.exception(f"AI backend call failed for {instance}")
        return

    if not result:
        return

    update_fields = []
    field_map = {f.name: f for f in ai_fields}
    for name, value in result.items():
        if value is None:
            continue
        field = field_map.get(name)
        if not field:
            continue
        if isinstance(field, AICategoryField) and field.choices:
            valid = {c[0] for c in field.choices}
            if value not in valid:
                logger.warning(f"Invalid choice '{value}' for {name}, skipping")
                continue
        if isinstance(field, AIForeignKeyField):
            allowed = {str(pk) for pk in field_specs.get(name, {}).get("enum", [])}
            if str(value) not in allowed:
                logger.warning(f"Related object pk={value} is not an allowed candidate for {name}, skipping")
                continue
            try:
                related_obj = field.related_model.objects.get(pk=value)
            except field.related_model.DoesNotExist:
                logger.warning(f"Related object pk={value} not found for {name}, skipping")
                continue
            setattr(instance, name, related_obj)
            update_fields.append(f"{name}_id")
            continue
        if isinstance(field, AITagsField):
            value = value[: getattr(field, "max_tags", 10)]
        setattr(instance, name, value)
        update_fields.append(name)

    if update_fields:
        instance.save(update_fields=update_fields)
        logger.info(f"Updated AI fields {update_fields} on {instance}")
