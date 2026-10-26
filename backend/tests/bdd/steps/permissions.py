"""Who may do what: model permissions, owner access, row rules and action rules.

Phrases this area adds:

- `Given people may view and change the customers they created without a permission` (owner access)
- `Given people may only get customers with status "active"` (a row rule, for every action)
- `Given people may only change the customers they are the owner of` (a row rule for writes only)
- `Given only superusers may run "Mark churned" on customers` (an action rule)
- `When someone who is not signed in looks at the list of customers` / `... looks at "Acme"`
- `When Bob looks at the list of customers` / `When Bob looks at the deleted customers`
- (`When Bob looks at "Acme"` comes from steps/history.py)
- `When Bob creates a customer "Globex"`
- `Then the list holds "Acme" and "Globex"` / `Then the list holds only "Acme"` / `Then the list holds nothing`

Shared with the other step modules of this area: `labels_phrase` (`phrase` plus `{x:Labels}`
for `"a", "b" and "c"`, converted to a list) and `patch_for_scenario`.
"""

from unittest.mock import patch

from pytest_bdd import given, then, when
from rest_framework.test import APIClient

from tests.bdd.world import phrase


def patch_for_scenario(request, target, attribute, value):
    """Patch `target.attribute` until the scenario ends."""
    patcher = patch.object(target, attribute, value, create=True)
    patcher.start()
    request.addfinalizer(patcher.stop)


# Rules a project configures on its record types


@given(phrase("people may view and change the {model:Model} they created without a permission"))
def owner_access(request, model):
    patch_for_scenario(request, model.CrudKitSettings, "owner_access", True)


@given(phrase('people may only get {model:Model} with {field:Words} "{value:Q}"'))
def a_row_rule(request, model, field, value):
    name = field.replace(" ", "_")

    def rule(user, queryset, action):
        return queryset.filter(**{name: value})

    patch_for_scenario(request, model.CrudKitSettings, "get_authorized_queryset", staticmethod(rule))


@given(phrase("people may only change the {model:Model} they are the owner of"))
def a_write_rule(request, model):
    def rule(user, queryset, action):
        return queryset if action == "view" else queryset.filter(owner=user)

    patch_for_scenario(request, model.CrudKitSettings, "get_authorized_queryset", staticmethod(rule))


@given(phrase('only superusers may run "{action:Q}" on {model:Model}'))
def an_action_rule(request, action, model):
    def rule(user, instance, action_name):
        verbose_name = getattr(getattr(instance, action_name), "verbose_name", None) or action_name
        return user.is_superuser or verbose_name != action

    patch_for_scenario(request, model.CrudKitSettings, "has_action_permission", staticmethod(rule))


# Reading and creating through the app


def _list_url(model):
    return f"/api/v1/{model.TYPE_ID}/"


@when(phrase("someone who is not signed in looks at the list of {model:Model}"))
def anonymous_lists(world, model):
    world.response = APIClient().get(_list_url(model))


@when(phrase('someone who is not signed in looks at "{label:Q}"'))
def anonymous_opens(world, label):
    world.response = APIClient().get(world.url(label))


@when(phrase("{name:Actor} looks at the list of {model:Model}"))
def lists(world, name, model):
    world.remember(name, world.api(name).get(_list_url(model)))


@when(phrase("{name:Actor} looks at the deleted {model:Model}"))
def lists_deleted(world, name, model):
    """The list of deleted records only, like a recycle bin."""
    world.remember(name, world.api(name).get(_list_url(model), {"deleted": "1"}))


@when(phrase('{name:Actor} creates a {model:Model} "{label:Q}"'))
def creates(world, name, model, label):
    world.remember(name, world.api(name).post(_list_url(model), {"name": label}, format="json"))


def _listed(world) -> list[str]:
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    return sorted(row["label"] for row in world.response.data["results"])


@then(phrase("the list holds {labels:Labels}"))
@then(phrase("the list holds only {labels:Labels}"))
def the_list_holds(world, labels):
    listed = _listed(world)
    assert listed == sorted(labels), listed


@then("the list holds nothing")
def the_list_holds_nothing(world):
    listed = _listed(world)
    assert listed == [], listed
