"""Proposals waiting for approval in the inbox.

- `Given a pending proposal to change the name of "X" to "Y"`
- `When Alice opens the proposals in her inbox`
- `When Alice confirms|skips the proposal for "X" in her inbox`
- `Then the proposal for "X" would set name to "Y"`, `Then the proposal for "X" leaves the inbox`
"""

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.world import phrase


def proposal(world, label):
    target = world.page.get_by_role("link", name=world.id(label), exact=True)
    return world.page.get_by_test_id("proposal").filter(has=target)


@given(phrase('a pending proposal to change the {field:Words} of "{label:Q}" to "{value:Q}"'))
def a_pending_proposal(world, field, label, value):
    """Filed as the signed-in user, as an MCP client acting for them would."""
    record_id = world.id(label)
    spec = world.api.field(record_id[:3], field)
    payload = {"fields": {spec["name"]: world.api_value(spec, value)}}
    world.api.create("ASP", {"target": record_id, "kind": "patch", "payload": payload})


@when(phrase("{name:Actor} opens the proposals in {their:Words} inbox"))
def opens_proposals(world):
    world.page.goto("/inbox?tab=proposals")


@when(phrase('{name:Actor} confirms the proposal for "{label:Q}" in {their:Words} inbox'))
def confirms(world, label):
    opens_proposals(world)
    proposal(world, label).get_by_role("button", name="Confirm").click()


@when(phrase('{name:Actor} skips the proposal for "{label:Q}" in {their:Words} inbox'))
def skips(world, label):
    opens_proposals(world)
    proposal(world, label).get_by_role("button", name="Skip").click()


@then(phrase('the proposal for "{label:Q}" would set {field:Words} to "{value:Q}"'))
def would_set(world, label, field, value):
    expect(proposal(world, label).get_by_text(f'{field} = "{world.text(value)}"')).to_be_visible()


@then(phrase('the proposal for "{label:Q}" leaves the inbox'))
def leaves_the_inbox(world, label):
    expect(proposal(world, label)).to_have_count(0)
