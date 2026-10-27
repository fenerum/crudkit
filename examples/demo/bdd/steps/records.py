"""A record's page and forms: creating, editing, deleting, related records,
actions, history, notes and live updates.

- `When she starts a new book` (the New button of the list on screen),
  `Given Alice is filling in a new reading`, `When Alice edits "X"`,
  `When Alice deletes "X"`, `When Alice is about to delete "X"`
- `When she opens "Kindred" from the list`, `Then she is on the page of a new reading`,
  `Then she sees the link "X"`, `Then its status is "Finished"`, `Then the page is about "X"`
- `When Alice opens the books tab of "X"`, `When she adds a new one from the tab`
- `When she creates the book "X" on the spot`, `Then only the form for the book is still open`
- `When Alice runs "Mark finished" on "X" and confirms|but declines "<question>"`,
  `When Alice opens the actions menu of "X"|of the readings list`,
  `Then the menu offers|does not offer "X"`, `Then "X" in the menu says "<hint>"`
- `Given Alice renamed "X" to "Y"`, `When she reverts her latest change in the history of "X"`,
  `Then the history shows the revert`, `When she undoes it from the notification`,
  `When she restores "X" from its page`, `Then "X" is not marked as deleted`
- `When Alice posts the note "N" on "X"`, `Then the feed shows "N"`
- `Given Alice has "X" open`, `Given Alice is editing "X"`,
  `Then she is told the record changed elsewhere`, `When she loads the other change`
"""

import re

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.steps.common import field_input, fills_in, saves_it, searchable_select
from bdd.world import goto_with_change_stream, phrase

# Creating, editing and deleting


@when(phrase("{name:Actor} starts a new {model:Model}"))
def starts_a_new_record(world):
    world.banner.get_by_role("link", name=re.compile(r"^New")).click()


@given(phrase("{name:Actor} is filling in a new {model:Model}"))
def filling_in_a_new_record(world, model):
    world.page.goto(f"/{model}/create")


@when(phrase('{name:Actor} edits "{label:Q}"'))
def edits(world, label):
    world.open(label)
    world.banner.get_by_role("link", name=re.compile(r"^Edit")).click()


@when(phrase('{name:Actor} is about to delete "{label:Q}"'))
def about_to_delete(world, label):
    world.open(label, "delete")


@when(phrase('{name:Actor} deletes "{label:Q}"'))
def deletes(world, label):
    about_to_delete(world, label)
    world.page.get_by_role("button", name="Delete").click()
    expect(world.page).not_to_have_url(re.compile(r"/delete$"))


# A record's page


@when(phrase('{name:Actor} opens "{label:Q}" from the list'))
def opens_from_the_list(world, label):
    world.main.get_by_role("link", name=world.id(label), exact=True).click()


@then(phrase("{name:Actor} is on the page of a new {model:Model}"))
def on_a_new_record(world, model):
    expect(world.page).to_have_url(re.compile(rf"/{model}\d+$"))


@then(phrase('{name:Actor} sees the link "{text:Q}"'))
def sees_a_link(world, text):
    expect(world.main.get_by_role("link", name=world.text(text))).to_be_visible()


@then(phrase('its {field:Words} is "{value:Q}"'))
def its_value_is(world, value):
    expect(world.main.get_by_text(world.text(value), exact=True)).to_be_visible()


@then(phrase('the page is about "{text:Q}"'))
def page_is_about(world, text):
    expect(world.visible_text(text, world.banner).first).to_be_visible()


# Related records


@when(phrase('{name:Actor} opens the {model:Model} tab of "{label:Q}"'))
def opens_a_related_tab(world, model, label):
    world.open(label)
    plural = world.api.metadata(model)["verbose_name_plural"]
    world.main.get_by_role("tab", name=re.compile(rf"^{plural}")).click()


@when(phrase("{name:Actor} adds a new one from the tab"))
def adds_from_the_tab(world):
    world.main.get_by_role("link", name="New").click()


@when(phrase('{name:Actor} creates the {field:Words} "{label:Q}" on the spot'))
def creates_on_the_spot(world, field, label):
    """Type a name that does not exist yet into a related field and pick "+ Create …", which opens its form."""
    name = world.name_for(label)
    searchable_select(world, field).fill(name)
    world.page.get_by_role("option", name=f'+ Create {field} "{name}"').click()
    expect(field_input(world, world.page.get_by_role("dialog").last, "name")).to_have_value(name)


@then(phrase("only the form for the {model:Model} is still open"))
def only_form_open(world, model):
    dialogs = world.page.get_by_role("dialog")
    expect(dialogs).to_have_count(1)
    label_field = world.api.label_field(model)
    expect(dialogs.locator(f'input[name="{label_field}"]')).to_be_visible()


# Actions


def actions_menu(world):
    world.page.get_by_role("button", name=re.compile(r"^Actions")).click()


@when(phrase('{name:Actor} opens the actions menu of "{label:Q}"'))
def opens_record_actions(world, label):
    world.open(label)
    actions_menu(world)


@when(phrase("{name:Actor} opens the actions menu of the {model:Model} list"))
def opens_list_actions(world, model):
    world.page.goto(f"/{model}")
    actions_menu(world)


def menu_item(world, text):
    return world.page.get_by_role("menuitem", name=re.compile(rf"^{re.escape(text)}"))


@then(phrase('the menu offers "{text:Q}"'))
def menu_offers(world, text):
    expect(menu_item(world, text)).to_be_visible()


@then(phrase('the menu does not offer "{text:Q}"'))
def menu_does_not_offer(world, text):
    expect(menu_item(world, text)).to_be_hidden()


@then(phrase('"{text:Q}" in the menu says "{hint:Q}"'))
def menu_hint(world, text, hint):
    expect(menu_item(world, text)).to_have_attribute("title", hint)


def run_action(world, label, action, question, accept):
    asked = []

    def answer(dialog):
        asked.append(dialog.message)
        if accept:
            dialog.accept()
        else:
            dialog.dismiss()

    opens_record_actions(world, label)
    world.page.once("dialog", answer)
    menu_item(world, action).click()
    assert asked == [question], asked


@when(phrase('{name:Actor} runs "{action:Q}" on "{label:Q}" and confirms "{question:Q}"'))
def runs_and_confirms(world, action, label, question):
    run_action(world, label, action, question, accept=True)


@when(phrase('{name:Actor} runs "{action:Q}" on "{label:Q}" but declines "{question:Q}"'))
def runs_and_declines(world, action, label, question):
    run_action(world, label, action, question, accept=False)


# History


@given(phrase('{name:Actor} renamed "{label:Q}" to "{text:Q}"'))
def renamed(world, label, text):
    """Through the edit form, so the history shows the change as hers."""
    edits(world, label)
    fills_in(world, "name", text)
    saves_it(world)
    world.expect_on_page_of(label)


@when(phrase('{name:Actor} reverts {their:Words} latest change in the history of "{label:Q}"'))
def reverts_latest_change(world, label):
    world.open(label)
    world.page.get_by_role("tab", name="History").click()
    latest = world.page.get_by_test_id("history-batch").first
    expect(latest.get_by_text("You")).to_be_visible()
    latest.get_by_role("button", name="Revert").click()


@then("the history shows the revert")
def history_shows_revert(world):
    expect(world.page.get_by_test_id("history-batch").first.get_by_text("Undo")).to_be_visible()


@when(phrase("{name:Actor} undoes it from the notification"))
def undoes_from_notification(world):
    world.page.get_by_role("alert").get_by_role("button", name="Undo", exact=True).click()


def deleted_banner(world):
    return world.page.get_by_role("status").filter(has_text="This record was deleted.")


@when(phrase('{name:Actor} restores "{label:Q}" from its page'))
def restores(world, label):
    world.open(label)
    deleted_banner(world).get_by_role("button", name="Restore").click()


@then(phrase('"{label:Q}" is not marked as deleted'))
def not_marked_deleted(world, label):
    world.expect_on_page_of(label)
    # Wait for the record before checking the banner is absent.
    expect(world.visible_text(label).first).to_be_visible()
    expect(world.page.get_by_role("status").filter(has_text="was deleted")).to_have_count(0)


# Notes


@when(phrase('{name:Actor} posts the note "{note:Q}" on "{label:Q}"'))
def posts_a_note(world, note, label):
    world.open(label)
    expect(world.main.get_by_role("heading", name="feed items")).to_be_visible()
    world.main.locator('[contenteditable="true"]').first.click()
    world.page.keyboard.type(world.text(note))
    world.main.get_by_role("button", name="Post note").click()


@then(phrase('the feed shows "{note:Q}"'))
def feed_shows(world, note):
    expect(world.main.locator(".ck-note-body").filter(has_text=world.text(note))).to_be_visible()


# Live updates


@given(phrase('{name:Actor} has "{label:Q}" open'))
def has_open(world, label):
    goto_with_change_stream(world.page, f"/{world.id(label)}")
    expect(world.visible_text(label).first).to_be_visible()


@given(phrase('{name:Actor} is editing "{label:Q}"'))
def is_editing(world, label):
    record_id = world.id(label)
    goto_with_change_stream(world.page, f"/{record_id}/edit")
    label_field = world.api.label_field(record_id[:3])
    expect(world.main.locator(f'input[name="{label_field}"]')).to_have_value(world.text(label))


def changed_elsewhere_notice(world):
    return world.page.get_by_role("status").filter(has_text="changed elsewhere")


@then(phrase("{name:Actor} is told the record changed elsewhere"))
def told_changed_elsewhere(world):
    expect(changed_elsewhere_notice(world)).to_be_visible()


@when(phrase("{name:Actor} loads the other change"))
def loads_the_other_change(world):
    notice = changed_elsewhere_notice(world)
    notice.get_by_role("button", name="Reload").click()
    expect(notice).to_be_hidden()
