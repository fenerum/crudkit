"""Dependent fields: fields whose visibility, requiredness or allowed values
follow the values of other fields on the same record.

A model declares them on `CrudKitSettings.dependent_fields`:

    from crudkit.dependencies import DependentField

    class Deal(BaseCrudKitModel):
        class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
            dependent_fields = {
                "lost_reason": DependentField(when={"stage": ["lost"]}, required=True),
                "subcategory": DependentField(
                    options_from="category",
                    options={"hardware": ["laptop", "phone"], "software": ["saas"]},
                ),
                "ticket": DependentField(match={"customer": "customer"}),
            }

The metadata endpoint describes each rule as the field's `depends_on`, so the SPA
hides, requires and narrows fields while a form is filled in. Every write through
the app (REST, bulk edit, import, MCP, the assistant, undo) enforces the same rules
in `apply()`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import models


@dataclass(frozen=True)
class DependentField:
    """How one field depends on others.

    - `when`: `{field: [values]}`. The field only applies while every listed field
      holds one of its values; otherwise it is hidden and cleared on save. A single
      value may stand in for a one-item list.
    - `required`: the field must be filled in while it applies.
    - `options_from` + `options`: a choice field whose allowed values follow another
      field, `{that field's value: [allowed values]}`. A value of `options_from` that
      `options` doesn't list leaves every choice allowed.
    - `match`: `{field on the linked record: field on this record}`. For a foreign key:
      the linked record must share that value with this one (a contact of the deal's
      company). Nothing is enforced while this record's field is empty.
    """

    when: Mapping[str, Any] = field(default_factory=dict)
    required: bool = False
    options_from: str = ""
    options: Mapping[Any, Sequence[Any]] = field(default_factory=dict)
    match: Mapping[str, str] = field(default_factory=dict)

    def conditions(self) -> dict[str, list]:
        return {
            name: list(values) if isinstance(values, (list, tuple, set, frozenset)) else [values]
            for name, values in self.when.items()
        }

    def as_metadata(self) -> dict[str, Any]:
        return {
            "when": {name: [key(v) for v in values] for name, values in self.conditions().items()},
            "required": self.required,
            "options_from": self.options_from or None,
            "options": {key(k): [key(v) for v in vs] for k, vs in self.options.items()} or None,
            "match": dict(self.match) or None,
        }


def get_dependent_fields(model) -> dict[str, DependentField]:
    return dict(getattr(getattr(model, "CrudKitSettings", None), "dependent_fields", None) or {})


def key(value: Any) -> str | None:
    """A value as rules compare it: records by ID, booleans as true/false, the rest as text."""
    if value is None or value == "":
        return None
    if isinstance(value, models.Model):
        value = value.pk
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _current(instance, name: str) -> Any:
    model_field = instance._meta.get_field(name)
    if model_field.many_to_one:
        return getattr(instance, model_field.attname)
    return getattr(instance, name)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def applies(instance, rule: DependentField) -> bool:
    """Whether the field `rule` governs applies to `instance` as it stands."""
    return all(key(_current(instance, name)) in {key(v) for v in values} for name, values in rule.conditions().items())


def _label(model, name: str) -> str:
    return str(model._meta.get_field(name).verbose_name)


def _value_label(model, name: str, value: Any) -> str:
    model_field = model._meta.get_field(name)
    for choice, label in model_field.flatchoices or ():
        if key(choice) == key(value):
            return str(label)
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _condition_text(model, rule: DependentField) -> str:
    parts = []
    for name, values in rule.conditions().items():
        shown = " or ".join(_value_label(model, name, v) for v in values)
        parts.append(f"{_label(model, name)} is {shown}")
    return " and ".join(parts)


def _empty_value(model_field):
    if model_field.null:
        return None
    if model_field.has_default():
        return model_field.get_default()
    if isinstance(model_field, models.BooleanField):
        return False
    return ""


def apply(instance) -> list[str]:
    """Clear the fields that don't apply to `instance`, then check the rest: the ones
    required in its situation are filled in, choices are among those allowed, linked
    records match. Raises a ValidationError keyed by field. Returns the attnames it
    cleared, for a save with `update_fields`."""
    model = type(instance)
    rules = get_dependent_fields(model)
    cleared: list[str] = []
    if not rules:
        return cleared
    errors: dict[str, list[str]] = {}
    for name, rule in rules.items():
        model_field = model._meta.get_field(name)
        if not applies(instance, rule):
            if not _is_empty(_current(instance, name)):
                setattr(instance, model_field.attname, _empty_value(model_field))
                cleared.append(model_field.attname)
            continue
        value = _current(instance, name)
        if rule.required and _is_empty(value):
            when = _condition_text(model, rule)
            errors.setdefault(name, []).append(
                f"{_label(model, name).capitalize()} is required when {when}."
                if when
                else f"{_label(model, name).capitalize()} is required."
            )
            continue
        if _is_empty(value):
            continue
        if rule.options_from:
            controlling = _current(instance, rule.options_from)
            allowed = next((vs for k, vs in rule.options.items() if key(k) == key(controlling)), None)
            if allowed is not None and key(value) not in {key(v) for v in allowed}:
                errors.setdefault(name, []).append(
                    f"{_value_label(model, name, value)!s} is not allowed when "
                    f"{_label(model, rule.options_from)} is {_value_label(model, rule.options_from, controlling)}."
                )
        if rule.match:
            linked = getattr(instance, name)
            for linked_field, own_field in rule.match.items():
                own = _current(instance, own_field)
                if _is_empty(own):
                    continue
                theirs = _current(linked, linked_field)
                if key(theirs) != key(own):
                    errors.setdefault(name, []).append(
                        f"{linked} does not belong to the {_label(model, own_field)} of this "
                        f"{model._meta.verbose_name}."
                    )
    if errors:
        raise ValidationError(errors)
    return cleared


def problems(model) -> list[str]:
    """What is wrong with `model`'s `dependent_fields`, for the system check."""
    out = []
    for name, rule in get_dependent_fields(model).items():
        if not isinstance(rule, DependentField):
            out.append(f"{name!r} must be a crudkit.dependencies.DependentField")
            continue
        try:
            model_field = model._meta.get_field(name)
        except FieldDoesNotExist:
            out.append(f"names the unknown field {name!r}")
            continue
        named = [*rule.when, *([rule.options_from] if rule.options_from else []), *rule.match.values()]
        for other in named:
            try:
                model._meta.get_field(other)
            except FieldDoesNotExist:
                out.append(f"{name!r} depends on the unknown field {other!r}")
        if name in rule.when or name == rule.options_from:
            out.append(f"{name!r} depends on itself")
        if rule.when and not model_field.blank:
            out.append(f"{name!r} can be hidden, so it must allow blank (blank=True)")
        if bool(rule.options_from) != bool(rule.options):
            out.append(f"{name!r} needs both options_from and options")
        elif rule.options and not model_field.choices:
            out.append(f"{name!r} has options but no choices")
        if rule.match:
            if not model_field.many_to_one:
                out.append(f"{name!r} has match but is not a foreign key")
            else:
                for linked_field in rule.match:
                    try:
                        model_field.related_model._meta.get_field(linked_field)
                    except FieldDoesNotExist:
                        out.append(
                            f"{name!r} matches on {linked_field!r}, which "
                            f"{model_field.related_model.__name__} does not have"
                        )
    return out
