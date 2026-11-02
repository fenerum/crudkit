"""Importing records from a spreadsheet.

Phrases this area adds (a sheet is a table whose first row holds the column names):

- `When Alice imports a customers sheet:` (an Excel workbook called "customers.xlsx"; a cell
  reading `the ID of Acme` holds the ID of the record "Acme")
- `When Alice imports a customers sheet saved as CSV:`
- `When Alice previews importing a customers sheet:` (nothing is saved)
- `When Alice imports a customers sheet, updating those that match on email:` (creating the rest)
- `When Alice imports a customers sheet, only updating those that match on email:` (skipping the rest)
- `When Alice imports a customers sheet, skipping those that match on email:` (creating the rest)
- `When Alice imports a customers sheet of 6 rows`
- `When Alice imports a file "customers.txt"`
- `Given Alice puts the column "Company" into the name` (otherwise columns go where they are suggested)
- `Given sheets may hold at most 5 rows`
- `Then the import created 2, updated 1, left 0 unchanged and skipped 0`
- `Then row 3 of the sheet is rejected with "No topic is called"`
- `Then nothing was imported`
- `Then the column "Company" is suggested for the name` / `Then the column "Notes" is not suggested for anything`
- `Given customers can also be matched on email`
- `Then the description says customers can be matched on their ID and email`
"""

import csv
import io
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from pytest_bdd import given, then, when

from crudkit.models import ChangeLog
from crudkit_api import imports
from tests.bdd.steps.permissions import patch_for_scenario
from tests.bdd.steps.records import field_name
from tests.bdd.world import label_field, phrase

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# How a sheet's rows are matched to existing records: (mode, phrase).
MATCHING = {"updating": "upsert", "only updating": "update", "skipping": "create"}


def _table(world, datatable) -> list[list[str]]:
    return [[_id_of(world, text) for text in line] for line in datatable]


def _id_of(world, text: str) -> str:
    return world.ck_id(text.removeprefix("the ID of ")) if text.startswith("the ID of ") else text


def _xlsx(name, table) -> SimpleUploadedFile:
    workbook = Workbook()
    for line in table:
        workbook.active.append([_cell(value) for value in line])
    content = io.BytesIO()
    workbook.save(content)
    return SimpleUploadedFile(name, content.getvalue(), content_type=XLSX)


def _cell(text):
    """Whole numbers are typed into a sheet as numbers, the rest as text."""
    return int(text) if text.isdigit() else text or None


def _csv(name, table) -> SimpleUploadedFile:
    content = io.StringIO()
    csv.writer(content).writerows(table)
    return SimpleUploadedFile(name, content.getvalue().encode(), content_type="text/csv")


def _import(world, name, model, upload, headers=(), dry_run=False, mode="create", match_on=None):
    world.import_model = model
    world.records_before = model._base_manager.count()
    world.changes_before = ChangeLog.objects.count()
    payload = {"file": upload, "mode": mode, "dry_run": "1" if dry_run else ""}
    if match_on:
        payload["match_on"] = field_name(match_on)
    chosen = getattr(world, "import_columns", {})
    if chosen:
        payload["mapping"] = json.dumps(imports.suggest_mapping(model, list(headers)) | chosen)
    response = world.remember(name, world.api(name).post(f"/api/v1/{model.TYPE_ID}/import/", payload))
    # Imported records can be named in later steps, like those given as setup.
    for row in response.data.get("rows", []) if isinstance(response.data, dict) else []:
        instance = model._base_manager.filter(pk=row["id"]).first() if row["id"] else None
        if instance is not None:
            world.add(str(getattr(instance, label_field(model))), instance)


@given(phrase("{name:Actor} imported a {model:Model} sheet:"))
@when(phrase("{name:Actor} imports a {model:Model} sheet:"))
def imports_sheet(world, name, model, datatable):
    table = _table(world, datatable)
    _import(world, name, model, _xlsx(f"{model._meta.verbose_name_plural}.xlsx", table), table[0])


@when(phrase("{name:Actor} imports a {model:Model} sheet saved as CSV:"))
def imports_csv(world, name, model, datatable):
    table = _table(world, datatable)
    _import(world, name, model, _csv(f"{model._meta.verbose_name_plural}.csv", table), table[0])


@when(phrase("{name:Actor} previews importing a {model:Model} sheet:"))
def previews_sheet(world, name, model, datatable):
    table = _table(world, datatable)
    _import(world, name, model, _xlsx(f"{model._meta.verbose_name_plural}.xlsx", table), table[0], dry_run=True)


@when(phrase("{name:Actor} imports a {model:Model} sheet, {matching} those that match on {field:Words}:"))
def imports_matching(world, name, model, matching, field, datatable):
    table = _table(world, datatable)
    upload = _xlsx(f"{model._meta.verbose_name_plural}.xlsx", table)
    _import(world, name, model, upload, table[0], mode=MATCHING[matching], match_on=field)


@when(phrase("{name:Actor} imports a {model:Model} sheet of {count:d} rows"))
def imports_rows(world, name, model, count):
    table = [["name"]] + [[f"Customer {n}"] for n in range(1, count + 1)]
    _import(world, name, model, _xlsx(f"{model._meta.verbose_name_plural}.xlsx", table), table[0])


@when(phrase('{name:Actor} imports a file "{filename:Q}"'))
def imports_file(world, name, filename):
    upload = SimpleUploadedFile(filename, b"name\nGlobex\n", content_type="text/plain")
    world.remember(name, world.api(name).post("/api/v1/CUS/import/", {"file": upload}))


@given(phrase('{name:Actor} puts the column "{header:Q}" into the {field:Words}'))
def puts_column(world, name, header, field):
    world.import_columns = getattr(world, "import_columns", {}) | {header: field_name(field)}


@given(phrase("sheets may hold at most {count:d} rows"))
def at_most_rows(settings, count):
    settings.CRUDKIT_IMPORT_MAX_ROWS = count


@then(
    phrase("the import created {created:d}, updated {updated:d}, left {unchanged:d} unchanged and skipped {skipped:d}")
)
def import_counts(world, created, updated, unchanged, skipped):
    counts = world.response.data["counts"]
    expected = {"created": created, "updated": updated, "unchanged": unchanged, "skipped": skipped}
    assert {status: counts[status] for status in expected} == expected, world.response.data


@then(phrase('row {number:d} of the sheet is rejected with "{message:Q}"'))
def row_rejected(world, number, message):
    row = next(row for row in world.response.data["rows"] if row["row"] == number)
    assert row["status"] == "error", row
    assert any(message in error for error in row["errors"].values()), row


@then("nothing was imported")
def nothing_imported(world):
    assert world.import_model._base_manager.count() == world.records_before
    assert ChangeLog.objects.count() == world.changes_before


@then(phrase('the column "{header:Q}" is suggested for the {field:Words}'))
def suggested(world, header, field):
    assert world.response.data["mapping"].get(header) == field_name(field), world.response.data["mapping"]


@then(phrase('the column "{header:Q}" is not suggested for anything'))
def not_suggested(world, header):
    assert header not in world.response.data["mapping"], world.response.data["mapping"]


@given(phrase("{model:Model} can also be matched on {field:Words}"))
def also_matched_on(request, model, field):
    patch_for_scenario(request, model.CrudKitSettings, "import_match_fields", [field_name(field)])


@then(phrase("the description says {model:Model} can be matched on their ID and {fields:List}"))
def matched_on(world, model, fields):
    keys = world.response.data["import_match_fields"]
    assert keys == ["id", *map(field_name, fields)], keys
