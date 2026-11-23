"""Dependent fields: fields that apply, are required or narrow their choices
depending on other fields of the same record.

Phrases this area adds:

- `When Alice changes "Big deal" with:` followed by a `| field | value |` table, saved in one go
- `Given deals declare the field "colour" as depending on the stage` (or other mistakes, see below)
- `Then the field "lost reason" applies only when stage is "lost"`
- `Then the field "lost reason" is required while it applies`
- `Then the field "product" offers "laptop" and "phone" when category is "hardware"`
- `Then the field "ticket" only offers tickets that share the customer`
- `Then the client learns that "lost_reason" applies only when "stage" is "lost"` (MCP `describe_types`)
- `Then the client learns that "lost_reason" is required while it applies`
"""

from pytest_bdd import given, then, when

from crudkit.dependencies import DependentField
from tests.bdd.steps.records import field_name, table_payload
from tests.bdd.world import phrase


def _depends_on(world, name: str) -> dict:
    assert world.response.status_code == 200, world.response.content
    rule = world.response.data["fields"][field_name(name)]["depends_on"]
    assert rule, f"{name} depends on nothing"
    return rule


@when(phrase('{name:Actor} changes "{label:Q}" with:'))
def change_several(world, name, label, datatable):
    model = type(world.record(label))
    world.remember(
        name, world.api(name).patch(world.url(label), table_payload(world, model, datatable), format="json")
    )


def _declare(monkeypatch, model, field, rule):
    rules = {**model.CrudKitSettings.dependent_fields, field_name(field): rule}
    monkeypatch.setattr(model.CrudKitSettings, "dependent_fields", rules)


@given(phrase('{model:Model} declare the field "{field:Q}" as depending on the {other:Words}'))
def declare_unknown(monkeypatch, model, field, other):
    _declare(monkeypatch, model, field, DependentField(when={field_name(other): "x"}))


@given(phrase('{model:Model} declare the field "{field:Q}" as applying only when the {other:Words} is "{value:Q}"'))
def declare_when(monkeypatch, model, field, other, value):
    _declare(monkeypatch, model, field, DependentField(when={field_name(other): value}))


@given(phrase('{model:Model} declare the field "{field:Q}" as matching the {other:Words} of the record it links to'))
def declare_match(monkeypatch, model, field, other):
    _declare(monkeypatch, model, field, DependentField(match={field_name(other): field_name(other)}))


@then(phrase('the field "{name:Q}" applies only when {other:Words} is "{value:Q}"'))
def applies_only_when(world, name, other, value):
    assert _depends_on(world, name)["when"] == {field_name(other): [value]}


@then(phrase('the field "{name:Q}" is required while it applies'))
def required_while_applies(world, name):
    assert _depends_on(world, name)["required"] is True


@then(phrase('the field "{name:Q}" offers {values:Labels} when {other:Words} is "{value:Q}"'))
def offers_when(world, name, values, other, value):
    rule = _depends_on(world, name)
    assert rule["options_from"] == field_name(other), rule
    assert rule["options"][value] == list(values), rule


@then(phrase('the field "{name:Q}" only offers {model:Model} that share the {other:Words}'))
def offers_matching(world, name, model, other):
    assert _depends_on(world, name)["match"] == {field_name(other): field_name(other)}


@then(phrase('the field "{name:Q}" depends on no other field'))
def depends_on_nothing(world, name):
    assert world.response.data["fields"][field_name(name)]["depends_on"] is None



def _described(world, field: str) -> dict:
    assert world.mcp_error is None, world.mcp_error
    return world.mcp_result["dependent_fields"][field]


@then(phrase('the client learns that "{field:Q}" applies only when "{other:Q}" is "{value:Q}"'))
def client_learns_when(world, field, other, value):
    assert _described(world, field)["when"] == {other: [value]}


@then(phrase('the client learns that "{field:Q}" is required while it applies'))
def client_learns_required(world, field):
    assert _described(world, field)["required"] is True
