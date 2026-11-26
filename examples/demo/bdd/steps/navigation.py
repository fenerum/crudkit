"""The rail of workspaces and the sidebar of views next to it.

- `Given a workspace "W" with the view "V"`, `Given a workspace "W" with the view "V" and the star icon`
- `Then the workspace "W" is shown as "WC" in the rail`, `Then the workspace "W" has the star icon in the rail`
- `When Alice chooses the workspace "W"`, `When she goes back to Home`
- `When she collapses the sidebar`, `When she brings back the sidebar`
- `Then the sidebar is hidden`
"""

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.steps.views import shows_icon
from bdd.world import phrase


@given(phrase('a workspace "{label:Q}" with the view "{view:Q}"'))
def a_workspace(world, label, view):
    data = {"name": world.new_name(label), "views": [world.ids[view]], "public": True}
    world.ids[label] = world.api.create("WSP", data)["id"]


@given(phrase('a workspace "{label:Q}" with the view "{view:Q}" and the {icon:Words} icon'))
def a_workspace_with_icon(world, label, view, icon):
    data = {"name": world.new_name(label), "views": [world.ids[view]], "icon": icon.replace(" ", "-"), "public": True}
    world.ids[label] = world.api.create("WSP", data)["id"]


def rail_item(world, label):
    rail = world.page.get_by_role("navigation", name="Workspaces")
    return rail.get_by_role("button", name=world.text(label), exact=True)


@then(phrase('the workspace "{label:Q}" is shown as "{initials:Q}" in the rail'))
def shown_by_initials(world, label, initials):
    expect(rail_item(world, label)).to_contain_text(initials)
    expect(rail_item(world, label).locator("svg")).to_have_count(0)


@then(phrase('the workspace "{label:Q}" has the {icon:Words} icon in the rail'))
def workspace_icon_in_rail(world, label, icon):
    shows_icon(rail_item(world, label), icon)


@when(phrase('{name:Actor} chooses the workspace "{label:Q}"'))
def chooses_workspace(world, label):
    rail_item(world, label).click()


@when(phrase("{name:Actor} goes back to Home"))
def goes_home(world):
    world.page.get_by_role("navigation", name="Workspaces").get_by_role("link", name="Home", exact=True).click()


@when(phrase("{name:Actor} collapses the sidebar"))
def collapses_sidebar(world):
    world.page.get_by_role("button", name="Collapse sidebar").click()


@when(phrase("{name:Actor} brings back the sidebar"))
def brings_back_sidebar(world):
    world.page.get_by_role("button", name="Show sidebar").click()


@then(phrase("the sidebar is hidden"))
def sidebar_hidden(world):
    expect(world.page.get_by_role("navigation", name="Sidebar")).to_be_hidden()
