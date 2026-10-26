"""The search box in the header (the command palette) and the search page.

- `When Alice searches everywhere for "X"`, `When she opens the search with the keyboard`,
  `When she types "X" into the search`
- `Then the search results include "X"`, `Then the search results show 5 readings`,
  `When she picks "X" from the search results`
- `Then the search is ready to type in`, `Then the search is closed`
- `When Alice searches the search page for "X"`
- `Given 6 readings whose names start with "X"`
"""

import re

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.world import phrase


def palette(world):
    return world.page.get_by_role("textbox", name="Search objects, navigate, or run actions…")


def results(world):
    return world.page.locator(".ck-cmd-item")


@given(phrase('{count:d} {model:Model} whose names start with "{prefix:Q}"'))
def records_with_a_prefix(world, count, model, prefix):
    name = world.new_name(prefix)
    label_field = world.api.label_field(model)
    for number in range(count):
        world.api.create(model, {label_field: f"{name} {number}"})


@when(phrase('{name:Actor} searches everywhere for "{text:Q}"'))
def searches_everywhere(world, text):
    world.page.goto("/")
    world.page.get_by_role("button", name=re.compile(r"^Search")).click()
    types_into_search(world, text)


@when(phrase("{name:Actor} opens the search with the keyboard"))
def opens_with_keyboard(world):
    world.page.keyboard.press("ControlOrMeta+k")


@when(phrase('{name:Actor} types "{text:Q}" into the search'))
def types_into_search(world, text):
    palette(world).fill(world.text(text))


@then(phrase('the search results include "{text:Q}"'))
def results_include(world, text):
    expect(results(world).filter(has_text=world.text(text))).to_be_visible()


@then(phrase("the search results show {count:d} {model:Model}"))
def results_show(world, count, model):
    plural = world.api.metadata(model)["verbose_name_plural"]
    heading = world.page.locator(".ck-cmd .eyebrow", has_text=f"{plural} ({model})")
    expect(heading).to_be_visible()
    expect(results(world).filter(has_text=world.token)).to_have_count(count)


@when(phrase('{name:Actor} picks "{text:Q}" from the search results'))
def picks_a_result(world, text):
    results(world).filter(has_text=world.text(text)).first.click()


@then("the search is ready to type in")
def ready_to_type(world):
    expect(palette(world)).to_be_focused()


@then("the search is closed")
def search_closed(world):
    expect(palette(world)).to_be_hidden()


@when(phrase('{name:Actor} searches the search page for "{text:Q}"'))
def searches_the_search_page(world, text):
    world.page.goto("/search")
    world.main.get_by_placeholder("Search anything…").fill(world.text(text))
