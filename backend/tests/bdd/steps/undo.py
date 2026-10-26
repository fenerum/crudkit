"""Undoing a change set.

- `Given Alice undid that change` / `When Alice undoes that change`: the latest change set anyone made
- `When Alice undoes her change` (`… anyway` to force it): Alice's latest change set
- `When Alice undoes that change from the script "cleanup"`
- `When someone who is not signed in undoes that change`
- `When Alice tries to undo the same change again` / `When Alice undoes a change that never happened`
- `Given Alice added a new customer "Fresh"` / `When Alice adds …`: created through the app, so the creation can be undone
- `Given only superusers may run "Mark churned"` / `Given the "Mark churned" action has since been renamed`
- `Given customers now refuse the name "Acme"`: the model's own rules reject the old value
- `Given "Acme" was removed for good afterwards` / `… was restored afterwards` / `… has since been deleted`
- `Given the change log of that change predates undo`
- `Then the undo conflicts on the status of "Acme"`
- `Then the undo conflicts because "Acme" no longer exists` / `… because "Acme" is no longer deleted`
- `Then it undid 2 changes`
"""

from django.core.exceptions import ValidationError
from pytest_bdd import given, then, when
from rest_framework.test import APIClient

from crudkit.models import ChangeLog
from tests.bdd.world import phrase
from tests.testapp.models import Customer


def _undo(world, name, change_set, force=False, client=None):
    world.undone = change_set
    client = client or world.api(name)
    response = client.post(f"/api/v1/changesets/{change_set}/revert/", {"force": force}, format="json")
    world.remember(name, response)


@given(phrase("{name:Actor} undid that change"))
@when(phrase("{name:Actor} undoes that change"))
def undo_latest(world, name):
    _undo(world, name, world.change_set)


@given(phrase("{name:Actor} undid {whose:Their} change"))
@when(phrase("{name:Actor} undoes {whose:Their} change"))
def undo_own_latest(world, name, whose):
    """`Alice undoes her change`: Alice's latest change, even if someone wrote after her."""
    _undo(world, name, world.change_sets[name])


@when(phrase("{name:Actor} undoes {whose:Their} change anyway"))
def undo_own_latest_forced(world, name, whose):
    _undo(world, name, world.change_sets[name], force=True)


@when(phrase("{name:Actor} undoes that change anyway"))
def undo_latest_forced(world, name):
    _undo(world, name, world.change_set, force=True)


@when(phrase('{name:Actor} undoes that change from the script "{script:Q}"'))
def undo_from_script(world, name, script):
    client = APIClient(headers={"Client-Id": script})
    client.force_authenticate(world.user(name))
    _undo(world, name, world.change_set, client=client)


@when("someone who is not signed in undoes that change")
def undo_anonymously(world):
    _undo(world, "Anonymous", world.change_set, client=APIClient())


@when(phrase("{name:Actor} tries to undo the same change again"))
def undo_again(world, name):
    _undo(world, name, world.undone)


@when(phrase("{name:Actor} undoes a change that never happened"))
def undo_unknown(world, name):
    _undo(world, name, "00000000-0000-0000-0000-000000000000")


@given(phrase('{name:Actor} added a new {model:Model} "{label:Q}"'))
@when(phrase('{name:Actor} adds a new {model:Model} "{label:Q}"'))
def add_through_the_app(world, name, model, label):
    response = world.api(name).post(f"/api/v1/{model.TYPE_ID}/", {"name": label}, format="json")
    assert response.status_code == 201, response.content
    world.remember(name, response)
    world.add(label, model._base_manager.get(pk=response.data["id"]))


@given(phrase('only superusers may run "{action:Q}"'))
def only_superusers_may_run(world, monkeypatch, action):
    allowed = staticmethod(lambda user, instance, action_name: user.is_superuser)
    monkeypatch.setattr(Customer.CrudKitSettings, "has_action_permission", allowed, raising=False)


@given(phrase('the "{action:Q}" action has since been renamed'))
def action_renamed(world, monkeypatch, action):
    func = next(f for f in vars(Customer).values() if getattr(f, "verbose_name", None) == action)
    monkeypatch.setattr(func, "verbose_name", f"{action} (renamed)")


@given(phrase('customers now refuse the name "{name:Q}"'))
def customers_refuse_a_name(world, monkeypatch, name):
    def clean(customer):
        if customer.name == name:
            raise ValidationError({"name": f"{name} is not allowed"})

    monkeypatch.setattr(Customer, "clean", clean)


@given(phrase('"{label:Q}" was removed for good afterwards'))
def removed_for_good(world, label):
    instance = world.record(label)
    type(instance)._base_manager.filter(pk=instance.pk).delete()


@given(phrase('"{label:Q}" has since been deleted'))
def deleted_since(world, label):
    instance = world.record(label)
    instance.soft_delete()


@given(phrase('"{label:Q}" was restored afterwards'))
def restored_afterwards(world, label):
    instance = world.record(label)
    instance.deleted = False
    instance.save()


@given("the change log of that change predates undo")
def predates_undo(world):
    ChangeLog.objects.filter(change_set=world.change_set).update(action="")


def _conflicts(world):
    assert world.response.status_code == 409, world.response.content
    return world.response.data["conflicts"]


@then(phrase('the undo conflicts on the {field:Words} of "{label:Q}"'))
def undo_conflicts_on(world, field, label):
    conflicts = {(c["label"], c["field"]) for c in _conflicts(world)}
    assert (label, field.replace(" ", "_")) in conflicts, conflicts


@then(phrase('the undo conflicts because "{label:Q}" no longer exists'))
def undo_conflicts_gone(world, label):
    conflicts = [(c["object"], c["reason"]) for c in _conflicts(world)]
    assert conflicts == [(world.ck_id(label), "The record no longer exists")], conflicts


@then(phrase('the undo conflicts because "{label:Q}" is no longer deleted'))
def undo_conflicts_undeleted(world, label):
    conflicts = [(c["label"], c["field"], c["current"]) for c in _conflicts(world)]
    assert conflicts == [(label, "deleted", False)], conflicts


@then(phrase("it undid {count:d} changes"))
@then(phrase("it undid {count:d} change"))
def undid_count(world, count):
    assert world.response.status_code == 200, world.response.content
    assert world.response.data["reverted"] == count, world.response.data
