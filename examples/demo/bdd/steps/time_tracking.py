"""The time tracker in the header. A person has at most one clock running.

- `Given Alice is not tracking time`, `Given Alice is tracking time on "X"`
- `When Alice starts tracking time on "X"`, `When she stops tracking time`
- `Then she can|cannot start tracking time`, `Then a running clock is shown`,
  `Then the running clock is for "X"`
"""

import re

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.world import phrase


def start_button(world):
    return world.banner.get_by_role("button", name="Start")


def stop_button(world):
    return world.banner.get_by_role("button", name="Stop time tracking")


@given(phrase("{name:Actor} is not tracking time"))
def not_tracking(world):
    """A scenario that failed half-way may have left a clock running."""
    world.page.goto("/RDG")
    expect(stop_button(world).or_(start_button(world))).to_be_visible()
    if stop_button(world).is_visible():
        stops(world)
        expect(world.page.get_by_text("Time tracking stopped")).to_be_visible()


@given(phrase('{name:Actor} is tracking time on "{label:Q}"'))
@when(phrase('{name:Actor} starts tracking time on "{label:Q}"'))
def starts(world, label):
    world.open(label)
    start_button(world).click()
    expect(stop_button(world)).to_be_visible()


@when(phrase("{name:Actor} stops tracking time"))
def stops(world):
    stop_button(world).click()


@then(phrase("{name:Actor} cannot start tracking time"))
def cannot_start(world):
    expect(start_button(world)).to_be_disabled()


@then(phrase("{name:Actor} can start tracking time"))
def can_start(world):
    expect(start_button(world)).to_be_enabled()


@then("a running clock is shown")
def clock_shown(world):
    expect(stop_button(world)).to_be_visible()
    expect(world.banner.get_by_text(re.compile(r"^\d+:\d\d$"))).to_be_visible()


@then(phrase('the running clock is for "{label:Q}"'))
def clock_is_for(world, label):
    expect(world.banner.get_by_role("link", name=world.id(label), exact=True)).to_be_visible()
