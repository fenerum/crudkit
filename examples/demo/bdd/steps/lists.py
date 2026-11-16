"""Lists: searching, paging, page size, selecting rows and merging.

- `When Alice searches the books list for "Kindred"` / `When she searches the list for "Kindred"`
- `Then the list has 1 record` / `Then the list is empty`
- `Given Alice pages through the authors one at a time`, then
  `When she goes to the next page|the previous page|page 3|the last page`,
  `Then the list is on page 2`, `Then there is no previous page|next page`
- `When she shows 10 records per page` / `Then the list shows 10 records per page`
- `When Alice selects "A", "B" and "C" in the books list` (this scenario's
  records) / `When she selects "Kindred" in the list` (the list on screen)
- `When she selects everything on the page`
- `When she unselects "C"`, `Then the bulk bar shows 2 selected`, `Then no bulk bar is shown`,
  `Then the bulk bar offers to merge "A" and "B"`, `Then the bulk bar does not offer to merge`
- `Then the pages of "X" read "1,234", lined up on the right`
- `When she edits the status of the selection` then `When she sets it on the selection`,
  `When she deletes the selection`
- `When Alice merges "A" and "B" from the books list`, `When she keeps "B" as the name`,
  `When she completes the merge`, `Then the merge keeps "A" by default`,
  `Then "B" is gone from the books list`
"""

import re
from urllib.parse import parse_qs, quote, urlparse

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.world import phrase


def search_box(world):
    return world.page.get_by_role("searchbox", name="Search this view")


def showing(world, text: str):
    return world.main.get_by_text(re.compile(rf"^Showing {text}$"))


def searched_for(url: str) -> str | None:
    return parse_qs(urlparse(url).query).get("q", [None])[0]


def pagination(world):
    return world.main.get_by_role("navigation", name="Pagination")


def checkbox(world, label: str):
    return world.main.get_by_role("checkbox", name=f"Select {world.id(label)}", exact=True)


def open_own_records(world, model: str):
    """The list of `model`, narrowed to this scenario's records."""
    world.page.goto(f"/{model}?q={quote(world.token)}")


# Searching


@when(phrase('{name:Actor} searches the {model:Model} list for "{text:Q}"'))
def searches_a_list(world, model, text):
    world.page.goto(f"/{model}")
    searches_the_list(world, text)


@when(phrase('{name:Actor} searches the list for "{text:Q}"'))
def searches_the_list(world, text):
    search_box(world).fill(world.text(text))
    world.page.wait_for_url(lambda url: searched_for(url) == world.text(text))


@then(phrase("the list has {count:d} record"))
@then(phrase("the list has {count:d} records"))
def list_has(world, count):
    expect(showing(world, f"1–{count} of {count}")).to_be_visible()


@then("the list is empty")
def list_is_empty(world):
    expect(world.main.get_by_text("Nothing here yet")).to_be_visible()
    expect(showing(world, "0 of 0")).to_be_visible()


@then(phrase('{name:Actor} is on the {model:Model} list, searched for "{text:Q}"'))
def is_on_a_searched_list(world, model, text):
    expect(world.page).to_have_url(re.compile(rf"/{model}\?"))
    assert searched_for(world.page.url) == world.text(text), world.page.url


# Paging


@given(phrase("{name:Actor} pages through the {model:Model} one at a time"))
def pages_one_at_a_time(world, model):
    """Other scenarios add records to the shared database, so the total is read, not assumed."""
    world.page.goto(f"/{model}?page_size=1")
    first = showing(world, r"1–1 of \d+")
    expect(first).to_be_visible()
    world.total = int(re.search(r"of (\d+)", first.text_content()).group(1))
    assert world.total >= 3, "paging needs at least three records"


@when(phrase("{name:Actor} goes to the next page"))
def next_page(world):
    world.main.get_by_role("button", name="Next").click()


@when(phrase("{name:Actor} goes to the previous page"))
def previous_page(world):
    world.main.get_by_role("button", name="Previous").click()


@when(phrase("{name:Actor} goes to page {number:d}"))
def goes_to_page(world, number):
    world.main.get_by_role("button", name=str(number), exact=True).click()


@when(phrase("{name:Actor} goes to the last page"))
def last_page(world):
    world.page.goto(f"{world.page.url}&page={world.total}")


@then(phrase("the list is on page {number:d}"))
def on_page(world, number):
    expect(showing(world, f"{number}–{number} of {world.total}")).to_be_visible()
    current = world.main.get_by_role("button", name=str(number), exact=True)
    expect(current).to_have_attribute("aria-current", "page")


@then("there is no previous page")
def no_previous_page(world):
    expect(world.main.get_by_role("button", name="Previous")).to_be_disabled()


@then("there is no next page")
def no_next_page(world):
    expect(showing(world, f"{world.total}–{world.total} of {world.total}")).to_be_visible()
    expect(world.main.get_by_role("button", name="Next")).to_be_disabled()


@when(phrase("{name:Actor} shows {count:d} records per page"))
def shows_per_page(world, count):
    pagination(world).get_by_text(re.compile(r"^\d+ / page$")).click()
    world.page.get_by_role("option", name=f"{count} / page", exact=True).click()


@then(phrase("the list shows {count:d} records per page"))
def shows_records_per_page(world, count):
    expect(showing(world, rf"1–{count} of \d+")).to_be_visible()


# Selecting and merging


@when(phrase("{name:Actor} selects {labels:QList} in the {model:Model} list"))
def selects_own_records(world, labels, model):
    open_own_records(world, model)
    expect(showing(world, r"1–\d+ of \d+")).to_be_visible()
    for label in labels:
        checkbox(world, label).check()


@when(phrase('{name:Actor} selects "{label:Q}" in the list'))
def selects_on_screen(world, label):
    checkbox(world, label).check()


@when(phrase("{name:Actor} selects everything on the page"))
def selects_page(world):
    world.main.get_by_role("checkbox", name="Select all on this page").check()


@when(phrase('{name:Actor} unselects "{label:Q}"'))
def unselects(world, label):
    checkbox(world, label).uncheck()


@then(phrase("the bulk bar shows {count:d} selected"))
def bulk_bar_counts(world, count):
    expect(world.main.get_by_text(f"{count} selected", exact=True)).to_be_visible()


@then("no bulk bar is shown")
def no_bulk_bar(world):
    expect(world.main.get_by_text(re.compile(r"^\d+ selected$"))).to_have_count(0)


@then(phrase("the bulk bar offers to merge {labels:QList}"))
def offers_to_merge(world, labels):
    ids = [world.id(label) for label in labels]
    query = "&".join(f"object_id={record_id}" for record_id in ids)
    merge = world.main.get_by_role("link", name="Merge")
    expect(merge).to_have_attribute("href", f"/{ids[0][:3]}/merge?{query}")


@then("the bulk bar does not offer to merge")
def does_not_offer_merge(world):
    expect(world.main.get_by_role("link", name="Merge")).to_have_count(0)


def bulk_bar(world):
    return world.main.get_by_role("toolbar", name="Selection")


@when(phrase("{name:Actor} edits the {field:Words} of the selection"))
def edits_selection(world, field):
    bulk_bar(world).get_by_role("button", name="Edit field").click()
    world.page.get_by_role("dialog").get_by_label("Field").select_option(label=field.title())


@when(phrase("{name:Actor} sets it on the selection"))
def sets_on_selection(world):
    dialog = world.page.get_by_role("dialog")
    dialog.get_by_role("button", name=re.compile(r"^Set on \d+$")).click()
    expect(dialog).to_have_count(0)


@when(phrase("{name:Actor} deletes the selection"))
def deletes_selection(world):
    bulk_bar(world).get_by_role("button", name="Delete").click()
    dialog = world.page.get_by_role("dialog")
    dialog.get_by_role("button", name=re.compile(r"^Delete \d+$")).click()
    expect(dialog).to_have_count(0)


@when(phrase("{name:Actor} merges {labels:QList} from the {model:Model} list"))
def merges(world, labels, model):
    selects_own_records(world, labels, model)
    world.main.get_by_role("link", name="Merge").click()
    expect(world.page.get_by_role("heading", name=f"Merge {len(labels)} records")).to_be_visible()


@then(phrase('the merge keeps "{label:Q}" by default'))
def merge_default(world, label):
    expect(world.page.get_by_role("radio", name=world.id(label), exact=True)).to_be_checked()


@when(phrase('{name:Actor} keeps "{text:Q}" as the {field:Words}'))
def keeps_value(world, text):
    world.page.get_by_role("radio", name=world.text(text), exact=True).check()


@when(phrase("{name:Actor} completes the merge"))
def completes_the_merge(world):
    world.page.get_by_role("button", name="Merge records").click()


@then(phrase('"{label:Q}" is gone from the {model:Model} list'))
def gone_from_list(world, label, model):
    open_own_records(world, model)
    expect(showing(world, r"1–\d+ of \d+")).to_be_visible()
    expect(world.main.get_by_role("link", name=world.id(label), exact=True)).to_have_count(0)


# Numbers


@then(phrase('the {field:Words} of "{label:Q}" read "{value:Q}", lined up on the right'))
def number_lined_up(world, field, label, value):
    row = world.main.locator(".ck-lrow").filter(has_text=world.text(label))
    cell = row.locator(".ck-lh-c", has_text=re.compile(rf"^{re.escape(value)}$"))
    expect(cell).to_be_visible()
    gap = cell.evaluate("c => c.getBoundingClientRect().right - c.firstElementChild.getBoundingClientRect().right")
    padding = cell.evaluate("c => parseFloat(getComputedStyle(c).paddingRight)")
    assert gap <= padding + 1, f"The {field} sit {gap}px from the right edge of their cell"
