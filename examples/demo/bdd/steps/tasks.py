"""Task progress: the tray and the record's progress bar.

Phrases:
- `Then she sees the task "Count pages" working on "Long read"`
- `Then she sees the task "Count pages" finish`
"""

from playwright.sync_api import expect
from pytest_bdd import then

from bdd.world import phrase


def tray(world):
    return world.page.get_by_role("region", name="Tasks")


@then(phrase('{name:Actor} sees the task "{label:Q}" working on "{record:Q}"'))
def sees_task_working(world, label, record):
    expect(tray(world).get_by_text(record)).to_be_visible()
    expect(tray(world).get_by_role("progressbar", name=label)).to_be_visible()
    expect(world.page.get_by_role("main").get_by_role("progressbar", name=label)).to_be_visible()


@then(phrase('{name:Actor} sees the task "{label:Q}" finish'))
def sees_task_finish(world, label):
    expect(tray(world).get_by_text("Done")).to_be_visible(timeout=15_000)
    expect(world.page.get_by_role("main").get_by_role("progressbar", name=label)).to_be_hidden()
