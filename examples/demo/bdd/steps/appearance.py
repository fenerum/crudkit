"""Light and dark theme.

- `When Alice switches to the light|dark theme`
- `Then the app is light|dark`
"""

from playwright.sync_api import expect
from pytest_bdd import then, when

from bdd.world import phrase


@when(phrase("{name:Actor} switches to the {theme:Words} theme"))
def switches_theme(world, theme):
    world.page.get_by_role("tab", name=f"{theme.capitalize()} theme").click()


@then(phrase("the app is {theme:Words}"))
def app_is(world, theme):
    expect(world.page.locator("html")).to_have_attribute("data-theme", theme)
