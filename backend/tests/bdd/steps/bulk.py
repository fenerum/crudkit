"""Changing many records at once from a list's selection.

Phrases this area adds:

- `When Alice sets the status of "Acme", "Beta" and "Gamma" to "churned" at once` / `Given Alice set …`
- `When Alice deletes "Acme" and "Beta" at once`
- `When Alice uses the "Mark churned" action on "Acme" and "Beta" at once`
- `When Alice sets the status of 501 customers to "churned" at once`
- `When Alice tries to "archive" "Acme" and "Beta" at once` (something the app doesn't offer)
- `Then 2 records were changed`
- `Then "Beta" was skipped because "You may not change it"`
- `Then Alice has only the task "Mark churned"`
"""

from pytest_bdd import given, then, when

from crudkit.models import Job
from tests.bdd.world import phrase


def _bulk(world, name, model, ids, payload):
    payload["ids"] = ids
    world.remember(name, world.api(name).post(f"/api/v1/{model.TYPE_ID}/bulk/", payload, format="json"))


def _bulk_on(world, name, labels, payload):
    model = type(world.records[labels[0]])
    _bulk(world, name, model, [world.ck_id(label) for label in labels], payload)


@given(phrase('{name:Actor} set the {field:Words} of {labels:Labels} to "{value:Q}" at once'))
@when(phrase('{name:Actor} sets the {field:Words} of {labels:Labels} to "{value:Q}" at once'))
def sets_at_once(world, name, field, labels, value):
    field = field.replace(" ", "_")
    model = type(world.records[labels[0]])
    _bulk_on(world, name, labels, {"operation": "update", "fields": {field: world.api_value(model, field, value)}})


@when(phrase('{name:Actor} sets the {field:Words} of {count:d} {model:Model} to "{value:Q}" at once'))
def sets_many_at_once(world, name, field, count, model, value):
    ids = [f"{model.TYPE_ID}{number}" for number in range(1, count + 1)]
    _bulk(world, name, model, ids, {"operation": "update", "fields": {field.replace(" ", "_"): value}})


@when(phrase("{name:Actor} deletes {labels:Labels} at once"))
def deletes_at_once(world, name, labels):
    _bulk_on(world, name, labels, {"operation": "delete"})


@when(phrase('{name:Actor} uses the "{action:Q}" action on {labels:Labels} at once'))
def action_at_once(world, name, action, labels):
    _bulk_on(world, name, labels, {"operation": "action", "action": action.lower().replace(" ", "_")})


@when(phrase('{name:Actor} tries to "{operation:Q}" {labels:Labels} at once'))
def unknown_at_once(world, name, operation, labels):
    _bulk_on(world, name, labels, {"operation": operation})


@then(phrase("{count:d} records were changed"))
@then(phrase("{count:d} record was changed"))
def records_changed(world, count):
    assert world.response.status_code == 200, world.response.content
    assert world.response.data["done"] == count, world.response.data


@then(phrase('"{label:Q}" was skipped because "{reason:Q}"'))
def was_skipped(world, label, reason):
    skipped = {row["label"]: row["reason"] for row in world.response.data["skipped"]}
    assert skipped.get(label, "").startswith(reason), skipped


@then(phrase('{name:Actor} has only the task "{label:Q}"'))
def only_task(world, name, label):
    labels = list(Job.objects.filter(created_by=world.user(name)).values_list("label", flat=True))
    assert labels == [label], labels
    assert world.response.data["job"] is not None, world.response.data
