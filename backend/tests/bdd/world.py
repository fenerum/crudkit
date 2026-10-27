"""The shared state of one scenario, and the vocabulary steps are written in.

Steps never talk about primary keys or URLs: records are named by their label
("Acme"), people by their first name ("Alice"), and record types by their
verbose name ("customer", "saved views"). `World` translates between the two.
"""

import json
import re
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.db import models
from parse import with_pattern
from pytest_bdd import parsers
from rest_framework.test import APIClient

from crudkit.models import get_ck_id, parse_ck_id
from crudkit.utils import get_model_types, get_system_user
from crudkit_api.views import SPA_CLIENT_ID

User = get_user_model()

# The field a record's human label lives in, in order of preference.
LABEL_FIELDS = ("name", "subject", "title", "note", "body")


def _model_names() -> dict:
    names = {}
    for model in get_model_types().values():
        names[str(model._meta.verbose_name).lower()] = model
        names[str(model._meta.verbose_name_plural).lower()] = model
    return names


def model_named(words: str) -> type[models.Model]:
    """The CrudKit model whose verbose name (singular or plural) is `words`."""
    names = _model_names()
    try:
        return names[words.lower()]
    except KeyError:
        raise LookupError(f"No record type is called {words!r}. Known: {', '.join(sorted(names))}") from None


@with_pattern(r'[^"]*')
def _quoted(text):
    return text


@with_pattern(r"[A-Z][a-z]+")
def _actor(text):
    return text


# Only real type names match, longest first, so `{x:Model}` never swallows neighbouring words.
@with_pattern("|".join(re.escape(name) for name in sorted(_model_names(), key=len, reverse=True)))
def _model(text):
    return model_named(text)


@with_pattern(r"[a-z][a-z_ ]*[a-z]")
def _words(text):
    return text


@with_pattern(r"her|his|their")
def _their(text):
    return text


@with_pattern(r"herself|himself|themselves")
def _self(text):
    return text


@with_pattern(r"an?")
def _article(text):
    return text


@with_pattern(r"[a-z][a-z_, ]*[a-z]")
def _list(text):
    return split_list(text)


_PERMISSION = r"(?:view|add|change|delete)"


@with_pattern(rf"{_PERMISSION}(?:(?:,| and|, and) {_PERMISSION})*")
def _permissions(text):
    return split_list(text)


# `"Acme", "Beta" and "Gamma"` (or `"a" or "b"`): only quoted labels, so it never swallows other words.
LABELS = r'"[^"]*"(?:(?:, | and | or )"[^"]*")*'


@with_pattern(LABELS)
def _labels(text):
    return re.findall(r'"([^"]*)"', text)


@with_pattern(r"[A-Z]{3}")
def _currency(text):
    return text


VOCABULARY = {
    "Q": _quoted,
    "Actor": _actor,
    "Model": _model,
    "Words": _words,
    "List": _list,
    "Perms": _permissions,
    "Labels": _labels,
    "Their": _their,
    "Self": _self,
    "Article": _article,
    "Currency": _currency,
}


def phrase(pattern: str, **extra_types):
    """A step parser with the suite's vocabulary (see README.md, "Writing steps").

    A step module may add its own placeholder types as keyword arguments.
    """
    return parsers.parse(pattern, extra_types=VOCABULARY | extra_types)


def split_list(text: str) -> list[str]:
    """ "view, change and delete" -> ["view", "change", "delete"]"""
    return [part.strip() for part in text.replace(" and ", ",").split(",") if part.strip()]


def label_field(model) -> str:
    names = {f.name for f in model._meta.get_fields()}
    return next(name for name in LABEL_FIELDS if name in names)


def missing_id(model) -> str:
    """The ID the next `model` would get, so no record has it yet."""
    last = model._base_manager.order_by("-pk").first()
    return get_ck_id(model.TYPE_ID, parse_ck_id(last.pk)[1] + 1 if last else 1)


@dataclass
class World:
    users: dict = field(default_factory=dict)
    records: dict = field(default_factory=dict)
    response: object = None
    # The change set of the latest write, and of each actor's latest write.
    change_set: str | None = None
    change_sets: dict = field(default_factory=dict)
    # The change set most recently undone.
    undone: str | None = None

    # People

    def add_user(self, name: str, superuser: bool = False):
        create = User.objects.create_superuser if superuser else User.objects.create_user
        self.users[name] = create(username=name.lower(), password="password", email=f"{name.lower()}@example.com")
        return self.users[name]

    def user(self, name: str):
        """`name` as a fresh instance, so permission caches never go stale."""
        if name not in self.users:
            raise LookupError(f"{name} has not been introduced in a Given step")
        return User.objects.get(pk=self.users[name].pk)

    def api(self, name: str) -> APIClient:
        """A REST client acting as `name` through the app (attributed to the UI)."""
        client = APIClient(headers={"Client-Id": SPA_CLIENT_ID})
        client.force_authenticate(self.user(name))
        return client

    def remember(self, name: str, response):
        """Keep `response` as the outcome of the latest attempt by `name`."""
        self.response = response
        change_set = response.headers.get("X-CrudKit-Change-Set")
        if change_set:
            self.change_set = self.change_sets[name] = change_set
        return response

    # Records

    def add(self, label: str, instance):
        self.records[label] = instance
        return instance

    def record(self, label: str):
        """The record called `label`, re-read from the database."""
        if label not in self.records:
            raise LookupError(f'No record called "{label}" has been introduced in a Given step')
        instance = self.records[label]
        return type(instance)._base_manager.get(pk=instance.pk)

    def ck_id(self, label: str) -> str:
        return get_ck_id(self.records[label].TYPE_ID, self.number(label))

    def number(self, label: str) -> int:
        """The database id of `label`. A fresh instance holds it as an int, a re-read one as a CK-ID."""
        pk = self.records[label].pk
        return parse_ck_id(pk)[1] if isinstance(pk, str) else pk

    def url(self, label: str, action: str = "") -> str:
        """The REST URL of the record called `label`, optionally of one of its actions."""
        instance = self.records[label]
        return f"/api/v1/{instance.TYPE_ID}/{self.number(label)}/" + (f"{action}/" if action else "")

    def create(self, model, label: str, values: dict | None = None, by=None):
        """Create a `model` called `label` directly, as setup (not through the API)."""
        by = by or get_system_user()
        fields = {label_field(model): label} | {k: self.value(model, k, v) for k, v in (values or {}).items()}
        return self.add(label, model.objects.create(created_by=by, updated_by=by, **fields))

    def value(self, model, field_name: str, text: str):
        """The Python value for `text` typed into `field_name` of `model`."""
        model_field = model._meta.get_field(field_name)
        if model_field.is_relation:
            if model_field.related_model is User:
                return self.user(text)
            return self.record(text)
        if isinstance(model_field, models.JSONField):
            return json.loads(text)
        return model_field.to_python(text)

    def api_value(self, model, field_name: str, text: str):
        """`text` as the REST API expects it for `field_name` of `model`."""
        model_field = model._meta.get_field(field_name)
        if model_field.is_relation:
            if model_field.related_model is User:
                return self.user(text).pk
            return self.ck_id(text)
        if isinstance(model_field, models.JSONField):
            return json.loads(text)
        return text

    @staticmethod
    def shown(instance, field_name: str) -> str:
        """How `field_name` of `instance` reads in a step: labels for relations."""
        value = getattr(instance, field_name)
        if value is None:
            return ""
        return str(value)
