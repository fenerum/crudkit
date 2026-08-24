"""Builders for the model metadata payload returned by `GenericViewSet.metadata`.

Extracted so the assistant agent can hand the same structure to the LLM as a
tool result, plus instance-level enrichments (current values, FK choices).
"""

from collections import OrderedDict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from django.apps import apps
from django.conf import settings
from django.db.models import Model

from crudkit.authorization import get_authorized_queryset
from crudkit.fields import ModelField
from crudkit.models import ExternalObject, FeedItem
from crudkit.utils import get_model_types

# Fields that are housekeeping/audit — never useful patch targets and not
# worth showing the LLM.
NON_PATCHABLE_FIELDS = frozenset({"id", "created_at", "updated_at", "created_by", "updated_by", "deleted"})

# Natural-key field names on related models we treat as a human-readable
# display value (in priority order).
FK_DISPLAY_FIELDS = ("name", "slug", "code", "title", "label")

# Soft cap for FK row enumeration in `build_instance_metadata`. Wider FK
# targets (e.g. Person, Company) are summarised rather than dumped.
FK_CHOICES_LIMIT = 50


def _model_field_choices() -> tuple[tuple[str, str], ...]:
    return tuple(sorted((m.TYPE_ID, m._meta.verbose_name.title()) for m in get_model_types().values()))


def _field_metadata(field, model_field_choices) -> dict[str, Any]:
    return {
        "name": field.name,
        "verbose_name": field.verbose_name.title(),
        "type": str(field.__class__.__name__),
        "choices": (
            tuple(field.choices) if field.choices else model_field_choices if isinstance(field, ModelField) else None
        ),
        "null": field.null,
        "blank": field.blank,
        "required": not field.blank,
        "editable": field.editable,
        "unique": field.unique,
        "max_length": field.max_length,
        "default": field.get_default(),
        "help_text": field.help_text,
        "auto_created": field.auto_created,
        "related_model": field.related_model.__name__ if field.related_model else None,
        "related_model_type": (
            field.related_model.TYPE_ID if field.related_model and hasattr(field.related_model, "TYPE_ID") else None
        ),
    }


def _relation_metadata(relation) -> dict[str, Any]:
    return {
        "name": relation.name,
        "verbose_name": relation.related_model._meta.verbose_name,
        "type": str(relation.__class__.__name__),
        "related_model": relation.related_model.__name__,
        "related_model_type": (relation.related_model.TYPE_ID if hasattr(relation.related_model, "TYPE_ID") else None),
        "field_name": relation.field.name,
    }


_CORE_GENERIC_RELATIONS = (
    {
        "name": "feeditem",
        "verbose_name": "Feed Item",
        "type": "",
        "related_model_cls": FeedItem,
        "field_name": "parent_object",
    },
    {
        "name": "externalobject",
        "verbose_name": "External Object",
        "type": "",
        "related_model_cls": ExternalObject,
        "field_name": "related_object",
    },
)


def _generic_relations() -> list[dict[str, Any]]:
    """Core generic relations plus project-supplied ones from
    CRUDKIT_EXTRA_GENERIC_RELATIONS, a list of dicts like
    ``{"model": "crm.Task", "field_name": "related_object", "name": "task"}``."""
    relations = list(_CORE_GENERIC_RELATIONS)
    for extra in getattr(settings, "CRUDKIT_EXTRA_GENERIC_RELATIONS", []):
        model_cls = apps.get_model(extra["model"])
        relations.append(
            {
                "name": extra["name"],
                "verbose_name": extra.get("verbose_name", model_cls._meta.verbose_name.title()),
                "type": extra.get("type", ""),
                "related_model_cls": model_cls,
                "field_name": extra["field_name"],
            }
        )
    return relations


def build_model_metadata(model) -> dict[str, Any]:
    """Return the model-level metadata payload served at /api/v1/<type>/metadata/."""
    mfc = _model_field_choices()
    fields = OrderedDict((field.name, _field_metadata(field, mfc)) for field in model._meta.fields)
    relations = [_relation_metadata(rel) for rel in model._meta.related_objects]
    for gen in _generic_relations():
        rm = gen["related_model_cls"]
        relations.append(
            {
                "name": gen["name"],
                "verbose_name": gen["verbose_name"],
                "type": gen["type"],
                "related_model": rm.__name__,
                "related_model_type": rm.TYPE_ID,
                "field_name": gen["field_name"],
            }
        )
    return {
        "verbose_name": model._meta.verbose_name,
        "verbose_name_plural": model._meta.verbose_name_plural,
        "type": model.TYPE_ID,
        "allowed_prefills": list(
            getattr(model.CrudKitSettings, "allowed_prefills", []),
        ),
        "fields": fields,
        "relations": relations,
        "actions": [{"verbose_name": func.verbose_name, "action": action} for action, func in model()._actions.items()],
    }


def _fk_display_field(related_model) -> Optional[str]:
    names = {f.name for f in related_model._meta.fields}
    for cand in FK_DISPLAY_FIELDS:
        if cand in names:
            return cand
    return None


def _fk_choices(field, user=None) -> dict[str, Any]:
    """List the rows the LLM can refer to for a ForeignKey. Returns
    `{"options": [...], "truncated": bool}` or `{"options": None, "reason": str}`
    when the table is too wide to enumerate."""
    related_model = field.related_model
    display = _fk_display_field(related_model)
    qs = related_model._default_manager.all()
    if user is not None:
        qs = get_authorized_queryset(user, qs, "view")
    if "deleted" in {f.name for f in related_model._meta.fields}:
        qs = qs.filter(deleted=False)
    total = qs.count()
    if total > FK_CHOICES_LIMIT:
        return {
            "options": None,
            "reason": (
                f"{related_model.__name__} has {total} rows — too many to list. "
                "Ask the user which one, or pass a primary key."
            ),
        }
    rows = []
    for obj in qs[:FK_CHOICES_LIMIT]:
        rows.append(
            {
                "id": getattr(obj, "pk", None),
                "display": getattr(obj, display) if display else str(obj),
            }
        )
    return {"options": rows, "truncated": False}


_JSON_PRIMITIVES = (str, int, float, bool)


def _coerce_current_value(value: Any) -> Any:
    """Project a raw field value into a JSON-safe shape for the LLM.
    pydantic-ai dumps tool returns through pydantic_core which doesn't know
    about Django-specific types like django_countries.Country, so anything
    exotic gets stringified."""
    if value is None or isinstance(value, _JSON_PRIMITIVES):
        return value
    if isinstance(value, Model):
        display = _fk_display_field(type(value))
        return {
            "id": value.pk,
            "display": getattr(value, display) if display else str(value),
        }
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return [_coerce_current_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _coerce_current_value(v) for k, v in value.items()}
    return str(value)


def build_instance_metadata(instance: Model, user=None) -> dict[str, Any]:
    """Return a slim, LLM-friendly projection of the writable fields on an
    instance: name, type, current value, valid choices, FK options, plus
    the available @crm_action names. Skips audit/housekeeping fields."""
    base = build_model_metadata(instance.__class__)
    fields_out: dict[str, Any] = {}
    for name, meta in base["fields"].items():
        if name in NON_PATCHABLE_FIELDS or meta.get("auto_created"):
            continue
        if not meta.get("editable", True):
            continue
        field = instance._meta.get_field(name)
        current = _coerce_current_value(getattr(instance, name, None))
        entry: dict[str, Any] = {
            "type": meta["type"],
            "current": current,
        }
        if meta.get("help_text"):
            entry["help_text"] = meta["help_text"]
        if meta.get("required"):
            entry["required"] = True
        choices = meta.get("choices")
        if choices:
            entry["choices"] = [c[0] for c in choices]
        if field.related_model is not None and field.many_to_one:
            entry["fk_choices"] = _fk_choices(field, user=user)
        fields_out[name] = entry
    return {
        "type": base["type"],
        "fields": fields_out,
        "actions": [a["action"] for a in base["actions"]],
    }
