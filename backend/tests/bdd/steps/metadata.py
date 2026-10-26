"""How record types and records are described to forms and to the assistant.

Phrases this area adds:

The description of a record type (what forms are built from)
- `When Alice looks up the description of customers`
- `Given customers also have a field "signature" made for {kind}` (see KINDS)
- `Given customer pages show the subject of their tickets inline by default`
- `Given the project also lists work logs on every record`
- `Then the description names the type "customer", or "customers" for several`
- `Then the description covers every field of customers`
- `Then the field "name" is required` / `is optional` / `cannot be edited`
- `Then the field "name" holds at most 255 characters` / `defaults to "active"`
- `Then the field "status" offers the choices "active" and "churned"` / `offers every record type as a choice`
- `Then the field "topic" links to topics`
- `Then the field "fields" is explained with "Format:"`
- `Then the field "body" is described as rich text` (see KINDS)
- `Then the description says new customers may be created` / `may not be created`
- `Then the description offers creating new ones from pickers`
- `Then the description lets new records be prefilled with name, email and topic`
- `Then the description says records are searched by name and email`
- `Then the description says tickets point at it through "customer"` / `does not say tickets point at it through "watchers"`
- `Then the description offers the action "Mark churned", which needs no approval`
- `Then the description shows the subject of tickets inline by default`

The description of one record (what the assistant reads)
- `When the assistant describes "Acme" for Alice`
- `Then the record description gives the status as "active"`
- `Then the record description leaves out id and created by`
- `Then the record description offers "Acme" and "Globex" as the choices for customer`
- `Then the record description says there are too many customers to list for customer`
- `Then the record description counts 2 tickets pointing at it`
- `Then the record description offers the action "mark_churned"`
"""

from parse import with_pattern
from pytest_bdd import given, then, when

from crudkit.fields import FieldChoiceField, ModelField
from crudkit.models import EmailWYSIWYGEditorField, WYSIWYGEditorField
from crudkit.utils import get_model_types
from crudkit_api.metadata import build_instance_metadata
from tests.bdd.steps.records import field_name
from tests.bdd.world import phrase as world_phrase

# How a field's kind reads in a feature, and the field class forms receive.
KINDS = {
    "rich text": WYSIWYGEditorField,
    "email bodies": EmailWYSIWYGEditorField,
    "choosing a record type": ModelField,
    "choosing a field": FieldChoiceField,
}


@with_pattern("|".join(KINDS))
def _kind(text):
    return KINDS[text]


def phrase(pattern: str):
    """The shared `phrase` plus `{x:Kind}`, a kind of field from KINDS."""
    return world_phrase(pattern, Kind=_kind)


def _description(world) -> dict:
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    return world.response.data


def _field(world, name: str) -> dict:
    return _description(world)["fields"][field_name(name)]


# The description of a record type


@when(phrase("{name:Actor} looks up the description of {model:Model}"))
def describe_type(world, name, model):
    world.remember(name, world.api(name).get(f"/api/v1/{model.TYPE_ID}/metadata/"))


@given(phrase('{model:Model} also have a field "{name:Q}" made for {kind:Kind}'))
def an_extra_field(monkeypatch, model, name, kind):
    """A project's own record type would declare it; here it is added to customers for the scenario."""
    extra = kind()
    extra.set_attributes_from_name(field_name(name))
    monkeypatch.setattr(model._meta, "fields", (*model._meta.fields, extra))


@given(phrase("{model:Model} pages show the {fields:List} of their {related:Model} inline by default"))
def default_inlines(monkeypatch, model, fields, related):
    inlines = [[related.TYPE_ID, [field_name(f) for f in fields]]]
    monkeypatch.setattr(model.CrudKitSettings, "default_inlines", inlines, raising=False)


@given(phrase("the project also lists work logs on every record"))
def extra_generic_relation(settings):
    settings.CRUDKIT_EXTRA_GENERIC_RELATIONS = [
        {"model": "crudkit.WorkLog", "field_name": "related_object", "name": "worklog"}
    ]


@then(phrase('the description names the type "{singular:Q}", or "{plural:Q}" for several'))
def names_the_type(world, singular, plural):
    data = _description(world)
    assert (data["verbose_name"], data["verbose_name_plural"]) == (singular, plural), data["verbose_name"]


@then(phrase("the description covers every field of {model:Model}"))
def covers_every_field(world, model):
    assert set(_description(world)["fields"]) == {f.name for f in model._meta.fields}
    assert _description(world)["type"] == model.TYPE_ID


@then(phrase('the field "{name:Q}" is required'))
def is_required(world, name):
    assert _field(world, name)["required"] is True, _field(world, name)


@then(phrase('the field "{name:Q}" is optional'))
def is_optional(world, name):
    assert _field(world, name)["required"] is False, _field(world, name)


@then(phrase('the field "{name:Q}" cannot be edited'))
def is_read_only(world, name):
    assert _field(world, name)["editable"] is False, _field(world, name)


@then(phrase('the field "{name:Q}" holds at most {length:d} characters'))
def max_length(world, name, length):
    assert _field(world, name)["max_length"] == length, _field(world, name)


@then(phrase('the field "{name:Q}" defaults to "{value:Q}"'))
def defaults_to(world, name, value):
    assert _field(world, name)["default"] == value, _field(world, name)


@then(phrase('the field "{name:Q}" offers the choices {labels:Labels}'))
def offers_choices(world, name, labels):
    assert [choice[0] for choice in _field(world, name)["choices"]] == labels, _field(world, name)


@then(phrase('the field "{name:Q}" offers every record type as a choice'))
def offers_record_types(world, name):
    assert [choice[0] for choice in _field(world, name)["choices"]] == sorted(get_model_types())


@then(phrase('the field "{name:Q}" links to {model:Model}'))
def links_to(world, name, model):
    assert _field(world, name)["related_model_type"] == model.TYPE_ID, _field(world, name)


@then(phrase('the field "{name:Q}" is explained with "{text:Q}"'))
def explained_with(world, name, text):
    assert text in _field(world, name)["help_text"], _field(world, name)


@then(phrase('the field "{name:Q}" is described as {kind:Kind}'))
def described_as(world, name, kind):
    assert _field(world, name)["type"] == kind.__name__, _field(world, name)


@then(phrase("the description says new {model:Model} may be created"))
def may_create(world, model):
    assert _description(world)["type"] == model.TYPE_ID
    assert _description(world)["can_create"] is True


@then(phrase("the description says new {model:Model} may not be created"))
def may_not_create(world, model):
    assert _description(world)["type"] == model.TYPE_ID
    assert _description(world)["can_create"] is False


@then(phrase("the description offers creating new ones from pickers"))
def inline_create(world):
    assert _description(world)["inline_create"] is True


@then(phrase("the description lets new records be prefilled with {fields:List}"))
def prefills(world, fields):
    assert _description(world)["allowed_prefills"] == [field_name(f) for f in fields]


@then(phrase("the description says records are searched by {fields:List}"))
def searched_by(world, fields):
    assert _description(world)["search_fields"] == [field_name(f) for f in fields]


def _relations(world) -> set[tuple[str, str]]:
    """(type, field) of each record type the description says points at it."""
    return {(r["related_model_type"], r["field_name"]) for r in _description(world)["relations"]}


@then(phrase('the description says {model:Model} point at it through "{field:Q}"'))
def pointed_at_by(world, model, field):
    relations = _relations(world)
    assert (model.TYPE_ID, field_name(field)) in relations, relations


@then(phrase('the description does not say {model:Model} point at it through "{field:Q}"'))
def not_pointed_at_by(world, model, field):
    relations = _relations(world)
    assert (model.TYPE_ID, field_name(field)) not in relations, relations


@then(phrase('the description offers the action "{verbose_name:Q}", which needs no approval'))
def offers_action(world, verbose_name):
    actions = {a["verbose_name"]: a["requires_approval"] for a in _description(world)["actions"]}
    assert actions.get(verbose_name) is False, actions


@then(phrase("the description shows the {fields:List} of {related:Model} inline by default"))
def shows_inline(world, fields, related):
    assert _description(world)["default_inlines"] == [[related.TYPE_ID, [field_name(f) for f in fields]]]


# The description of one record, as the assistant reads it


@when(phrase('the assistant describes "{label:Q}" for {name:Actor}'))
def describe_record(world, label, name):
    world.record_description = build_instance_metadata(world.record(label), world.user(name))


def _described(world, field: str) -> dict:
    return world.record_description["fields"][field_name(field)]


@then(phrase('the record description gives the {field:Words} as "{value:Q}"'))
def current_value(world, field, value):
    current = _described(world, field)["current"]
    assert (current["display"] if isinstance(current, dict) else current) == value, current


@then(phrase("the record description leaves out {fields:List}"))
def leaves_out(world, fields):
    described = world.record_description["fields"]
    assert not {field_name(f) for f in fields} & set(described), list(described)


@then(phrase("the record description offers {labels:Labels} as the choices for {field:Words}"))
def offers_record_choices(world, labels, field):
    described = _described(world, field)
    if "fk_choices" in described:
        offered = [option["display"] for option in described["fk_choices"]["options"]]
    else:
        offered = described["choices"]
    assert sorted(offered) == sorted(labels), described


@then(phrase("the record description offers no choices for {field:Words}"))
def offers_no_choices(world, field):
    assert _described(world, field)["fk_choices"]["options"] == [], _described(world, field)


@then(phrase("the record description says there are too many {model:Model} to list for {field:Words}"))
def too_many(world, model, field):
    choices = _described(world, field)["fk_choices"]
    assert choices["options"] is None, choices
    assert f"{model.__name__} has" in choices["reason"] and "too many to list" in choices["reason"], choices


@then(phrase("the record description counts {count:d} {model:Model} pointing at it"))
def counts_related(world, count, model):
    related = {r["type"]: r["count"] for r in world.record_description["related"]}
    assert related.get(model.TYPE_ID) == count, related


@then(phrase('the record description offers the action "{action:Q}"'))
def offers_named_action(world, action):
    assert action in world.record_description["actions"], world.record_description["actions"]
