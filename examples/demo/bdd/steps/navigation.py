"""The rail of workspaces and the sidebar of views next to it.

- `Given a workspace "W" with the view "V"`
- `When Alice chooses the workspace "W"`, `When she goes back to Home`
- `When she collapses the sidebar`, `When she brings back the sidebar`
- `Then the sidebar is hidden`
"""

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.world import phrase


@given(phrase('a workspace "{label:Q}" with the view "{view:Q}"'))
def a_workspace(world, label, view):
    data = {"name": world.new_name(label), "views": [world.ids[view]], "public": True}
    world.ids[label] = world.api.create("WSP", data)["id"]


@when(phrase('{name:Actor} chooses the workspace "{label:Q}"'))
def chooses_workspace(world, label):
    rail = world.page.get_by_role("navigation", name="Workspaces")
    rail.get_by_role("button", name=world.text(label), exact=True).click()


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
