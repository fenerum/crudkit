"""Saved views and their layouts: board (kanban), gallery, chart (quadrant),
lanes (swimlane) and conversation inbox.

- `When Alice creates the view "V" of the readings, showing only:` + `| field | choice |` rows
- `Given Alice's private view "V" of the readings`,
  `Given a view "V" of the readings that is not in the sidebar`,
  `Given a conversation view "V" of the readings` (any layout; newest records first)
- `When Alice opens the view "Board" of the readings`, `When she switches to the view "V"`
- `Then the view "V" is offered|is not offered above the list|in the sidebar`
- Board: `Then the "To read" column holds "X"`, `Then the card "X" shows its priority "High"`,
  `When she drags "X" to the "Finished" column`, `When she drags "X" above "Y"`,
  `Then "X" comes before "Y" in the "Reading" column`, `When she adds a card to the "Finished" column`
- Gallery: `Then the card "X" is labelled "To read"`, `When she narrows the gallery to "Finished"`,
  `Then she sees|does not see the card "X"`
- Chart: `Then the chart plots pages against rating`, `When she picks "X" from the chart's table`
- Lanes: `Then the lanes are split by priority`, `Then the "High" lane holds|does not hold "X"`
- Conversations: `Then the conversations include "A" and "B"`,
  `When she picks the conversation "A"`, `Then the conversation "A" is open`
"""

import re

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.world import phrase


def create_view(world, model, label, **options):
    """Shows the record's label field; `options` are the view's other settings."""
    data = {"model": model, "name": world.new_name(label), "fields": [world.api.label_field(model)], **options}
    world.ids[label] = world.api.create("VIW", data)["id"]


def choose(select, text):
    """Pick an option of a searchable select by typing it and pressing Enter."""
    select.press_sequentially(text)
    select.press("Enter")


@when(phrase('{name:Actor} creates the view "{label:Q}" of the {model:Model}, showing only:'))
def creates_a_filtered_view(world, label, model, datatable):
    world.page.goto(f"/VIW/create?model={model}&next=/{model}")
    world.page.locator('input[name="name"]').fill(world.new_name(label))
    # The form also has a badge filters editor below this one.
    filters = world.page.get_by_test_id("filters-editor").first
    rows = filters.get_by_test_id("filter-row")
    for field, value in datatable:
        choose(filters.get_by_label("Filter field").last, world.api.field(model, field)["verbose_name"])
        choose(rows.last.get_by_label("Filter value"), value)
    expect(rows).to_have_count(len(datatable))
    world.main.get_by_role("button", name="Create", exact=True).click()


@given(phrase('{name:Actor}\'s private view "{label:Q}" of the {model:Model}'))
def a_private_view(world, label, model):
    create_view(world, model, label, public=False)


@given(phrase('a view "{label:Q}" of the {model:Model} that is not in the sidebar'))
def a_view_outside_the_sidebar(world, label, model):
    create_view(world, model, label, show_in_menu=False)


@given(phrase('a {layout:Words} view "{label:Q}" of the {model:Model}'))
def a_view_with_layout(world, layout, label, model):
    create_view(world, model, label, layout=layout, order_by="-created_at")


def view_tab(world, label):
    return world.banner.get_by_role("button", name=world.text(label), exact=True)


def sidebar_link(world, label):
    return world.page.get_by_role("navigation", name="Sidebar").get_by_role("link", name=world.text(label), exact=True)


@when(phrase('{name:Actor} opens the view "{label:Q}" of the {model:Model}'))
def opens_a_view(world, label, model):
    world.page.goto(f"/{model}")
    switches_to(world, label)


@when(phrase('{name:Actor} switches to the view "{label:Q}"'))
def switches_to(world, label):
    view_tab(world, label).click()
    expect(world.page).to_have_url(re.compile(r"/VIW/VIW\d+$"))


@then(phrase('the view "{label:Q}" is offered above the list'))
def offered_above(world, label):
    expect(view_tab(world, label)).to_be_visible()


@then(phrase('the view "{label:Q}" is not offered above the list'))
def not_offered_above(world, label):
    expect(view_tab(world, label)).to_have_count(0)


@then(phrase('the view "{label:Q}" is offered in the sidebar'))
def offered_in_sidebar(world, label):
    expect(sidebar_link(world, label)).to_be_visible()


@then(phrase('the view "{label:Q}" is not offered in the sidebar'))
def not_offered_in_sidebar(world, label):
    expect(sidebar_link(world, label)).to_have_count(0)


# Board


def column(world, name):
    title = world.page.locator(".ck-pipe-name", has_text=re.compile(rf"^{re.escape(name)}$"))
    return world.page.locator(".ck-pipe-col").filter(has=title)


def card(world, text):
    return world.page.locator(".ck-deal-card").filter(has_text=world.text(text))


@then(phrase('the "{column_name:Q}" column holds "{text:Q}"'))
def column_holds(world, column_name, text):
    expect(column(world, column_name)).to_contain_text(world.text(text))


@then(phrase('the card "{text:Q}" shows its {field:Words} "{value:Q}"'))
def card_shows(world, text, field, value):
    expect(card(world, text).get_by_role("img", name=f"{field}: {value}")).to_be_visible()


def drag(world, source, target, y_offset, method, path):
    """Drag with real mouse moves (the board needs several pointer events) and
    wait for the board to save the move with a `method` request to `path`."""
    start = source.bounding_box()
    end = target.bounding_box()

    def saves_the_move(response):
        return response.request.method == method and path in response.url

    with world.page.expect_response(saves_the_move) as saved:
        world.page.mouse.move(start["x"] + start["width"] / 2, start["y"] + start["height"] / 2)
        world.page.mouse.down()
        world.page.mouse.move(end["x"] + end["width"] / 2, end["y"] + y_offset, steps=20)
        world.page.mouse.up()
    assert saved.value.ok


@when(phrase('{name:Actor} drags "{text:Q}" to the "{column_name:Q}" column'))
def drags_to_column(world, text, column_name):
    record_id = world.id(text)
    expect(card(world, text)).to_be_visible()
    target = column(world, column_name)
    drag(world, card(world, text), target, 120, "PATCH", f"/api/v1/{record_id[:3]}/{record_id}/")


@when(phrase('{name:Actor} drags "{text:Q}" above "{other:Q}"'))
def drags_above(world, text, other):
    card(world, text).scroll_into_view_if_needed()
    model = world.id(text)[:3]
    drag(world, card(world, text), card(world, other), 5, "POST", f"/api/v1/{model}/reorder/")


@then(phrase('"{text:Q}" comes before "{other:Q}" in the "{column_name:Q}" column'))
def comes_before(world, text, other, column_name):
    expect(card(world, text)).to_be_visible()
    texts = column(world, column_name).locator(".ck-deal-card").all_text_contents()

    def position(label):
        return next(index for index, content in enumerate(texts) if world.text(label) in content)

    assert position(text) < position(other), texts


@when(phrase('{name:Actor} adds a card to the "{column_name:Q}" column'))
def adds_a_card(world, column_name):
    column(world, column_name).get_by_role("button", name="Add item").click()


# Gallery


def gallery_card(world, text):
    return world.main.get_by_role("link", name=re.compile(re.escape(world.text(text))))


@then(phrase('the card "{text:Q}" is labelled "{value:Q}"'))
def card_labelled(world, text, value):
    expect(gallery_card(world, text).locator(".ck-gal-cat")).to_have_text(value)


@when(phrase('{name:Actor} narrows the gallery to "{value:Q}"'))
def narrows_the_gallery(world, value):
    world.main.get_by_role("button", name=value, exact=True).click()


@then(phrase('{name:Actor} sees the card "{text:Q}"'))
def sees_card(world, text):
    expect(gallery_card(world, text)).to_be_visible()


@then(phrase('{name:Actor} does not see the card "{text:Q}"'))
def does_not_see_card(world, text):
    expect(gallery_card(world, text)).to_have_count(0)


# Chart


@then(phrase("the chart plots {x:Words} against {y:Words}"))
def chart_plots(world, x, y):
    expect(world.main.get_by_text(re.compile(rf"items · {x.capitalize()} × {y.capitalize()}"))).to_be_visible()


@when(phrase('{name:Actor} picks "{text:Q}" from the chart\'s table'))
def picks_from_chart(world, text):
    world.page.locator(".ck-qt-row").filter(has_text=world.text(text)).click()


# Lanes


def lane(world, name):
    title = world.page.locator(".ck-srh-label", has_text=name)
    return world.page.locator(".ck-swim-row").filter(has=title)


@then(phrase("the lanes are split by {field:Words}"))
def lanes_split_by(world, field):
    expect(world.page.locator(".ck-swim-head")).to_contain_text(field.capitalize())


@then(phrase('the "{lane_name:Q}" lane holds "{text:Q}"'))
def lane_holds(world, lane_name, text):
    expect(lane(world, lane_name)).to_contain_text(world.text(text))


@then(phrase('the "{lane_name:Q}" lane does not hold "{text:Q}"'))
def lane_does_not_hold(world, lane_name, text):
    expect(lane(world, lane_name)).not_to_contain_text(world.text(text))


# Conversations


def conversation_row(world, text):
    return world.page.locator(".ck-conv-row").filter(has_text=world.text(text))


@then(phrase("the conversations include {texts:QList}"))
def conversations_include(world, texts):
    for text in texts:
        expect(conversation_row(world, text)).to_be_visible()


@when(phrase('{name:Actor} picks the conversation "{text:Q}"'))
def picks_conversation(world, text):
    conversation_row(world, text).click()


@then(phrase('the conversation "{text:Q}" is open'))
def conversation_open(world, text):
    expect(world.page.locator(".ck-cth-who")).to_have_text(world.text(text))
