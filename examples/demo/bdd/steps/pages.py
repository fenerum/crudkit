"""The app's own pages: profile, the overview of record types, and pages that do not exist.

- `When Alice opens her profile`, `When she logs out`
- `When Alice opens the overview of all record types`
- `When Alice opens a page that does not exist`
"""

from pytest_bdd import when

from bdd.world import phrase


@when(phrase("{name:Actor} opens her profile"))
@when(phrase("{name:Actor} opens his profile"))
@when(phrase("{name:Actor} opens their profile"))
def opens_profile(world):
    world.page.goto("/profile")


@when(phrase("{name:Actor} logs out"))
def logs_out(world):
    world.main.get_by_role("button", name="Log out").click()


@when(phrase("{name:Actor} opens the overview of all record types"))
def opens_overview(world):
    world.page.goto("/all-objects")


@when(phrase("{name:Actor} opens a page that does not exist"))
def opens_missing_page(world):
    world.page.goto(f"/no/such/page/{world.token}")
