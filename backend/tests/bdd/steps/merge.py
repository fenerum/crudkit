"""Merging duplicates, restoring deleted records and reordering.

Phrases this area adds:

- `When Alice merges "Acme dup" and "Acme copy" into "Acme"`
- `When Alice merges "Acme dup" into "Acme", taking:` with `| field | record |` rows
- `When Alice merges nothing into "Acme"` (no duplicates chosen)
- `When Alice, on the page of "Acme dup", merges "Acme dup" into "Acme"`
- `Given customers refuse to be saved with "Customers are frozen"` (the type's own validation fails)
- `Given "Acme old" was merged into "Acme dup"` / `Then "Acme dup" is merged into "Acme"`
- `When Alice restores "Acme"` / `Given Alice restored "Acme"`
- `When Alice reorders the topics by sort order as "Sales", "Bugs" and "Billing"` / `Given Alice reordered …`
- `When Alice reorders the topics by name` (every topic, in the order they were introduced)
- `Then that change touched only "Bugs" and "Billing"`
"""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from pytest_bdd import given, then, when

from crudkit.models import ChangeLog
from tests.bdd.steps.permissions import patch_for_scenario
from tests.bdd.world import phrase

# Merging


def _merge(world, name, labels, keep, page=None, taking=None):
    payload = {"id": world.ck_id(keep), "merge": [world.ck_id(label) for label in [keep, *labels]]}
    payload |= {field: world.ck_id(source) for field, source in (taking or {}).items()}
    world.remember(name, world.api(name).post(world.url(page or keep, "merge"), payload, format="json"))


@when(phrase('{name:Actor} merges {labels:Labels} into "{keep:Q}"'))
def merges(world, name, labels, keep):
    _merge(world, name, labels, keep)


@when(phrase('{name:Actor} merges nothing into "{keep:Q}"'))
def merges_nothing(world, name, keep):
    _merge(world, name, [], keep)


@when(phrase('{name:Actor} merges {labels:Labels} into "{keep:Q}", taking:'))
def merges_taking(world, name, labels, keep, datatable):
    """A table of `| field | record |` rows: which record each field's value is taken from."""
    taking = {row[0].replace(" ", "_"): row[1] for row in datatable}
    _merge(world, name, labels, keep, taking=taking)


@when(phrase('{name:Actor}, on the page of "{page:Q}", merges {labels:Labels} into "{keep:Q}"'))
def merges_from_page(world, name, page, labels, keep):
    _merge(world, name, labels, keep, page=page)


@given(phrase('{model:Model} refuse to be saved with "{message:Q}"'))
def refuse_to_save(request, model, message):
    """The record type's own validation rejects every save."""

    def clean(self):
        raise ValidationError(message)

    patch_for_scenario(request, model, "clean", clean)


@given(phrase('"{label:Q}" was merged into "{keep:Q}"'))
def was_merged(world, label, keep):
    world.record(label).delete_and_merge_with(world.record(keep))


@then(phrase('"{label:Q}" is merged into "{keep:Q}"'))
def is_merged(world, label, keep):
    merged = world.record(label)
    assert merged.deleted
    assert merged.merged_into_id == world.record(keep).pk


# Restoring


@given(phrase('{name:Actor} restored "{label:Q}"'))
@when(phrase('{name:Actor} restores "{label:Q}"'))
def restores(world, name, label):
    world.remember(name, world.api(name).post(world.url(label, "restore")))


# Reordering


def _reorder(world, name, model, field, labels):
    payload = {"field": field.replace(" ", "_"), "ids": [world.ck_id(label) for label in labels]}
    world.remember(name, world.api(name).post(f"/api/v1/{model.TYPE_ID}/reorder/", payload, format="json"))


@given(phrase("{name:Actor} reordered the {model:Model} by {field:Words} as {labels:Labels}"))
@when(phrase("{name:Actor} reorders the {model:Model} by {field:Words} as {labels:Labels}"))
def reorders(world, name, model, field, labels):
    _reorder(world, name, model, field, labels)


@when(phrase("{name:Actor} reorders the {model:Model} by {field:Words}"))
def reorders_all(world, name, model, field):
    labels = [label for label, instance in world.records.items() if isinstance(instance, model)]
    _reorder(world, name, model, field, labels)


# What the change log recorded


def _address(world, label) -> tuple[int, int]:
    """The (content type, pk) a change log entry stores for the record called `label`."""
    instance = world.records[label]
    return ContentType.objects.get_for_model(type(instance)).pk, world.number(label)


@then(phrase("that change touched only {labels:Labels}"))
def change_touched_only(world, labels):
    entries = ChangeLog.objects.filter(change_set=world.change_set)
    touched = set(entries.values_list("related_content_type", "related_object_id"))
    expected = {_address(world, label) for label in labels}
    assert touched == expected, (touched, expected)
