"""Importing records from a spreadsheet.

Phrases (a sheet is a table whose first row names the columns; record labels
in it become this scenario's names, other cells are typed as they are):
- `When Alice uploads a books sheet:`
- `Then the column "Title" goes into the name`
- `When she imports it, confirming "Create 2 books?"`
- `Then she cannot import yet`
- `Then the books list holds "Dawn" and "Imago"` / `Then the books list holds nothing of hers`
"""

import csv
import io

from playwright.sync_api import expect
from pytest_bdd import then, when

from bdd.steps.lists import open_own_records
from bdd.world import phrase


def _cell(world, column: str, text: str) -> str:
    """Titles are this scenario's own records; anything else (an author) is typed as is."""
    return world.new_name(text) if column in ("Title", "Name") else text


@when(phrase("{name:Actor} uploads a {model:Model} sheet:"))
def uploads_sheet(world, model, datatable):
    header, *rows = datatable
    content = io.StringIO()
    csv.writer(content).writerows([header] + [[_cell(world, h, v) for h, v in zip(header, row)] for row in rows])
    world.page.goto(f"/{model}/import")
    world.page.get_by_label("Spreadsheet to import").set_input_files(
        files=[{"name": "sheet.csv", "mimeType": "text/csv", "buffer": content.getvalue().encode()}]
    )


@then(phrase('the column "{column:Q}" goes into the {field:Words}'))
def column_goes_into(world, column, field):
    expect(world.main.get_by_label(f"Field for {column}")).to_have_value(world.api.field("BOK", field)["name"])


@when(phrase('{name:Actor} imports it, confirming "{question:Q}"'))
def imports_it(world, question):
    asked = []

    def answer(dialog):
        asked.append(dialog.message)
        dialog.accept()

    world.page.once("dialog", answer)
    world.main.get_by_role("button", name="Import", exact=True).click()
    expect(world.page.get_by_role("alert").get_by_text("imported successfully")).to_be_visible()
    assert asked == [question], asked


@then(phrase("{name:Actor} cannot import yet"))
def cannot_import(world):
    expect(world.main.get_by_role("button", name="Import", exact=True)).to_be_disabled()


@then(phrase("the {model:Model} list holds {labels:QList}"))
def list_holds(world, model, labels):
    open_own_records(world, model)
    for label in labels:
        expect(world.main.get_by_text(world.text(label), exact=True)).to_be_visible()


@then(phrase("the {model:Model} list holds nothing of {their:Words}"))
def list_holds_nothing(world, model, their):
    expect(world.page.get_by_role("alert").get_by_text("Undone:")).to_be_visible()
    open_own_records(world, model)
    expect(world.main.get_by_text("Nothing here yet")).to_be_visible()
