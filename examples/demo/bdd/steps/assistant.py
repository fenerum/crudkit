"""The assistant sidebar. The demo runs pydantic-ai's offline test model, which answers with canned text.

- `When she toggles the assistant with the keyboard`, `Given the assistant is open`
- `Then the assistant is ready|closed|answers`
- `When she asks the assistant "Q"`, `Then the assistant still shows "Q"`
- `Then the assistant is looking at the books list with 1 selected`, `Then the assistant is looking at "X"`
"""

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.world import phrase


def sidebar(world):
    return world.page.get_by_role("complementary", name="Assistant chat")


def composer(world):
    return sidebar(world).get_by_placeholder("Ask Assistant…")


@when(phrase("{name:Actor} toggles the assistant with the keyboard"))
def toggles(world):
    expect(world.page.get_by_role("button", name="Toggle assistant")).to_be_visible()
    world.page.keyboard.press("ControlOrMeta+j")


@given("the assistant is open")
def is_open(world):
    toggles(world)
    is_ready(world)


@then("the assistant is ready")
def is_ready(world):
    expect(sidebar(world).get_by_text("Ready")).to_be_visible()


@then("the assistant is closed")
def is_closed(world):
    expect(sidebar(world)).to_be_hidden()


@when(phrase('{name:Actor} asks the assistant "{question:Q}"'))
def asks(world, question):
    composer(world).fill(question)
    composer(world).press("Enter")


@then("the assistant answers")
def answers(world):
    is_ready(world)
    expect(sidebar(world).locator(".ck-bubble-in")).not_to_have_count(0)


@then(phrase('the assistant still shows "{text:Q}"'))
def still_shows(world, text):
    expect(sidebar(world).get_by_text(text)).to_be_visible()


@then(phrase("the assistant is looking at the {model:Model} list with {count:d} selected"))
def looking_at_list(world, model, count):
    expect(sidebar(world).get_by_test_id("assistant-screen")).to_have_text(f"{model} list · {count} selected")


@then(phrase('the assistant is looking at "{label:Q}"'))
def looking_at_record(world, label):
    expect(sidebar(world).get_by_test_id("assistant-screen")).to_have_text(world.id(label))
