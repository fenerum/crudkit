"""Roles and per-role field access: who may see and change each field.

Phrases this area adds:

- `Given Alice has the role "Legal"` / `Given Alice no longer has the role "Legal"`
- `Given people with the role "Legal" can edit the email of customers` (or `can view`)
- `Given everyone else can view the email of customers` (a rule without a role)
- `When Bob saves "Acme" with its email unchanged and the status "churned"` (what the edit form sends)
- `When Alice adds a rule letting "Legal" edit the "email" of customers` (also `letting everyone else view ...`)
- `When Alice adds Bob to the role "Legal"`
- `Then the record shown has the email "legal@acme.test"` / `Then the record shown leaves out the email`
- `Then the description leaves out the field "email"`
- `Then the history leaves out the email`
- `Then the client is not shown the email` (an MCP client's latest answer)
"""

from parse import with_pattern
from pytest_bdd import given, then, when

from crudkit.models import FieldAccess, Role, RoleMember, get_ck_id
from crudkit.utils import get_system_user
from tests.bdd.steps.mcp import _rows
from tests.bdd.world import phrase as world_phrase


def phrase(pattern: str):
    return world_phrase(pattern, Level=_level)


@with_pattern(r"edit|view")
def _level(text):
    return FieldAccess.Access(text)


def _role_id(name: str) -> str:
    pk = _role(name).pk
    return pk if isinstance(pk, str) else get_ck_id(Role.TYPE_ID, pk)


def _role(name: str) -> Role:
    system = get_system_user()
    return Role.objects.get_or_create(name=name, defaults={"created_by": system, "updated_by": system})[0]


def _rule(model, field: str, role, level):
    system = get_system_user()
    FieldAccess.objects.create(
        model=model.TYPE_ID,
        field=field.replace(" ", "_"),
        role=role,
        access=level,
        created_by=system,
        updated_by=system,
    )


# Roles and rules, as set up by an administrator


@given(phrase('{name:Actor} has the role "{role:Q}"'))
def has_role(world, name, role):
    system = get_system_user()
    RoleMember.objects.create(role=_role(role), user=world.user(name), created_by=system, updated_by=system)


@given(phrase('{name:Actor} no longer has the role "{role:Q}"'))
def lost_role(world, name, role):
    RoleMember.objects.filter(role__name=role, user=world.user(name)).update(deleted=True)


@given(phrase('people with the role "{role:Q}" can {level:Level} the {field:Words} of {model:Model}'))
def role_rule(role, level, field, model):
    _rule(model, field, _role(role), level)


@given(phrase("everyone else can {level:Level} the {field:Words} of {model:Model}"))
def everyone_rule(level, field, model):
    _rule(model, field, None, level)


# Rules and roles, managed through the app


def _add_rule(world, name, role, level, field, model):
    payload = {"model": model.TYPE_ID, "field": field, "access": str(level), "role": None}
    if role is not None:
        payload["role"] = _role_id(role)
    world.remember(name, world.api(name).post(f"/api/v1/{FieldAccess.TYPE_ID}/", payload, format="json"))


@when(phrase('{name:Actor} adds a rule letting "{role:Q}" {level:Level} the "{field:Q}" of {model:Model}'))
def add_role_rule(world, name, role, level, field, model):
    _add_rule(world, name, role, level, field, model)


@when(phrase('{name:Actor} adds a rule letting everyone else {level:Level} the "{field:Q}" of {model:Model}'))
def add_everyone_rule(world, name, level, field, model):
    _add_rule(world, name, None, level, field, model)


@when(phrase('{name:Actor} adds {member:Actor} to the role "{role:Q}"'))
def add_member(world, name, member, role):
    payload = {"role": _role_id(role), "user": world.user(member).pk}
    world.remember(name, world.api(name).post(f"/api/v1/{RoleMember.TYPE_ID}/", payload, format="json"))


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
