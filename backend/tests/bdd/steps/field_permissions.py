"""Field permissions: fields only some people may see or change.

Roles are Django groups, and each guarded field has its own Django permission.

Phrases this area adds:

- `Given only some people may change the email of customers` (or `may see`): the field gets its permissions
- `Given the group "Legal" may change the email of customers` (or `may see`)
- `Given Alice is in the group "Legal"` / `Given Alice is no longer in the group "Legal"`
- `Given Alice may change the email of customers` (a permission of her own, without a group)
- `Given customers guard the field "colour"` / `... guard the email at the level "edit"` (wrong declarations)
- `When the database is set up` / `Then the permission "Can change email of customer" exists`
- `When Bob saves "Acme" with its email unchanged and the status "churned"` (what the edit form sends)
- `Then the record shown has the email "legal@acme.test"` / `Then the record shown leaves out the email`
- `Then the description leaves out the field "email"`
- `Then the history leaves out the email`
- `Then the client is not shown the email` (an MCP client's latest answer)
"""

from django.contrib.auth.models import Group, Permission
from parse import with_pattern
from pytest_bdd import given, then, when

from crudkit.field_access import codename, create_field_permissions, declared
from tests.bdd.steps.mcp import _rows
from tests.bdd.steps.permissions import patch_for_scenario
from tests.bdd.world import phrase as world_phrase


def phrase(pattern: str):
    return world_phrase(pattern, Action=_action)


@with_pattern(r"change|see")
def _action(text):
    return "view" if text == "see" else "change"


def _guard(request, model, field, level):
    patch_for_scenario(request, model.CrudKitSettings, "field_permissions", {**declared(model), field: level})
    create_field_permissions()


def _permission(model, field, action) -> Permission:
    return Permission.objects.get(content_type__app_label=model._meta.app_label, codename=codename(model, field, action))


# What a project declares


@given(phrase("only some people may {action:Action} the {field:Words} of {model:Model}"))
def guarded(request, action, field, model):
    _guard(request, model, field.replace(" ", "_"), action)


@given(phrase('{model:Model} guard the field "{field:Q}"'))
def guard_unknown_field(request, model, field):
    patch_for_scenario(request, model.CrudKitSettings, "field_permissions", {field: "change"})


@given(phrase('{model:Model} guard the {field:Words} at the level "{level:Q}"'))
def guard_wrong_level(request, model, field, level):
    patch_for_scenario(request, model.CrudKitSettings, "field_permissions", {field.replace(" ", "_"): level})


# Who gets the permissions, as set up by an administrator


@given(phrase('{name:Actor} is in the group "{group:Q}"'))
def in_group(world, name, group):
    world.user(name).groups.add(Group.objects.get_or_create(name=group)[0])


@given(phrase('{name:Actor} is no longer in the group "{group:Q}"'))
def left_group(world, name, group):
    world.user(name).groups.remove(Group.objects.get(name=group))


@given(phrase('the group "{group:Q}" may {action:Action} the {field:Words} of {model:Model}'))
def group_may(group, action, field, model):
    Group.objects.get_or_create(name=group)[0].permissions.add(_permission(model, field.replace(" ", "_"), action))


@given(phrase("{name:Actor} may {action:Action} the {field:Words} of {model:Model}"))
def user_may(world, name, action, field, model):
    world.user(name).user_permissions.add(_permission(model, field.replace(" ", "_"), action))


@when("the database is set up")
def database_set_up():
    create_field_permissions()


@then(phrase('the permission "{name:Q}" exists'))
def permission_exists(name):
    assert Permission.objects.filter(name=name).exists(), list(Permission.objects.values_list("name", flat=True))


# Writing as the edit form does


@when(phrase('{name:Actor} saves "{label:Q}" with its {field:Words} unchanged and the {other:Words} "{value:Q}"'))
def save_form(world, name, label, field, other, value):
    client = world.api(name)
    shown = client.get(world.url(label)).data
    field, other = field.replace(" ", "_"), other.replace(" ", "_")
    payload = {field: shown[field], other: world.api_value(type(world.records[label]), other, value)}
    world.remember(name, client.patch(world.url(label), payload, format="json"))


# What people are shown


def _record(world) -> dict:
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    return world.response.data


@then(phrase('the record shown has the {field:Words} "{value:Q}"'))
def shown_with(world, field, value):
    assert _record(world)[field.replace(" ", "_")] == value, _record(world)


@then(phrase("the record shown leaves out the {field:Words}"))
def shown_without(world, field):
    assert field.replace(" ", "_") not in _record(world), _record(world)


@then(phrase('the description leaves out the field "{name:Q}"'))
def description_without(world, name):
    data = _record(world)
    assert name.replace(" ", "_") not in data["fields"], list(data["fields"])
    assert name.replace(" ", "_") not in data["search_fields"], data["search_fields"]


@then(phrase("the history leaves out the {field:Words}"))
def history_without(world, field):
    changes = [entry["field_changes"] for group in _record(world) for entry in group["entries"]]
    assert changes, "The history is empty"
    assert all(field.replace(" ", "_") not in change for change in changes), changes


@then(phrase("the client is not shown the {field:Words}"))
def client_not_shown(world, field):
    rows = _rows(world)
    assert rows, "The client got no records"
    for row in rows:
        assert field.replace(" ", "_") not in row, row


@then(phrase('the field "{name:Q}" can be edited'))
def is_editable(world, name):
    field = _record(world)["fields"][name.replace(" ", "_")]
    assert field["editable"] is True, field


@when(phrase('{name:Actor} opens the view "{label:Q}" as the app does'))
def open_view_like_the_app(world, name, label):
    """The list page asks for the view's columns and its order, as well as the view."""
    view = world.records[label]
    params = {"_view": world.ck_id(label), "_fields": ",".join(["id", "label", *view.fields])}
    if view.order_by:
        params["_order_by"] = view.order_by
    world.remember(name, world.api(name).get(f"/api/v1/{view.model}/", params))
