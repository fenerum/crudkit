"""Celebrating a record reaching a milestone, such as a deal being won.

Phrases this area adds:

- `Given customers celebrate reaching status "churned"`
- `Then the app celebrates` / `Then the app does not celebrate`
"""

from pytest_bdd import given, then

from tests.bdd.world import phrase

CELEBRATE_HEADER = "X-CrudKit-Celebrate"


@given(phrase('{model:Model} celebrate reaching {field:Words} "{value:Q}"'))
def celebrates_reaching(monkeypatch, model, field, value):
    monkeypatch.setattr(model.CrudKitSettings, "celebrate", {field.replace(" ", "_"): [value]})


@then("the app celebrates")
def the_app_celebrates(world):
    assert world.response.headers.get(CELEBRATE_HEADER) == "1", dict(world.response.headers)


@then("the app does not celebrate")
def the_app_does_not_celebrate(world):
    assert CELEBRATE_HEADER not in world.response.headers, dict(world.response.headers)
