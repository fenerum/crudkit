"""
Bulk import of records from a spreadsheet (.xlsx or .csv).

Every row goes through the same services as a REST create or PATCH, so
validation, permissions and ChangeLog behave as for any other write. The whole
import runs in one transaction: a preview (`dry_run`) or an import with any
failing row is rolled back, so the preview reports exactly what the import
would do and an import either saves every row or none.
"""

import csv
import datetime
import io
import zipfile
from collections import Counter
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, models, transaction
from django.db.models import UniqueConstraint
from django.utils.text import capfirst
from openpyxl import load_workbook

from crudkit import jobs
from crudkit.authorization import get_authorized_queryset, has_model_permission
from crudkit.models import ck_id_regex, get_accepted_type_ids
from crudkit_api import services
from crudkit_api.records import fk_display_field, viewable_queryset, writable_fields

MAX_BYTES = 10 * 1024 * 1024
MODES = ("create", "update", "upsert")
SAMPLES = 3
STATUSES = ("created", "updated", "unchanged", "skipped", "error")
CREATING_MODES = ("create", "upsert")
UPDATING_MODES = ("update", "upsert")
# The mapping target for a column of this type's own IDs; it only matches.
ID = "id"
TRUE = {"true", "yes", "y", "1", "x"}
FALSE = {"false", "no", "n", "0"}


def max_rows() -> int:
    return getattr(settings, "CRUDKIT_IMPORT_MAX_ROWS", 5000)


# ---------------------------------------------------------------------------
# Reading the file


def read_table(upload) -> tuple[list[str], list[tuple[int, dict[str, Any]]]]:
    """The header row and the non-empty rows below it, each as (spreadsheet row
    number, {header: cell})."""
    if upload is None:
        raise ValueError("Choose a file to import")
    if upload.size > MAX_BYTES:
        raise ValueError(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    name = upload.name.lower()
    if name.endswith(".xlsx"):
        lines = _xlsx_lines(upload)
    elif name.endswith(".csv"):
        lines = _csv_lines(upload)
    else:
        raise ValueError("Upload an Excel workbook (.xlsx) or a CSV file")

    header = next(lines, None)
    if not header:
        raise ValueError("The file is empty")
    headers = [_text(cell) for cell in header]
    duplicates = sorted({h for h in headers if h and headers.count(h) > 1})
    if duplicates:
        raise ValueError(f"Columns appear more than once: {', '.join(duplicates)}")

    rows = []
    for number, line in enumerate(lines, start=2):
        values = {h: cell for h, cell in zip(headers, line, strict=False) if h}
        if all(_blank(cell) for cell in values.values()):
            continue
        if len(rows) == max_rows():
            raise ValueError(f"The file has more than {max_rows()} rows")
        rows.append((number, values))
    if not rows:
        raise ValueError("The file has no rows below its header")
    return [h for h in headers if h], rows


def _xlsx_lines(upload):
    try:
        # read_only streams the sheet; data_only reads formulas' cached values.
        workbook = load_workbook(upload, read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ValueError("The file could not be read as an Excel workbook") from exc
    try:
        yield from workbook.worksheets[0].iter_rows(values_only=True)
    finally:
        workbook.close()


def _csv_lines(upload):
    raw = upload.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel on Windows saves CSV in the ANSI code page.
        text = raw.decode("cp1252", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return iter(csv.reader(io.StringIO(text), dialect))


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


# ---------------------------------------------------------------------------
# Columns and keys


def importable_fields(model) -> dict[str, models.Field]:
    return {f.name: f for f, _ in writable_fields(model)}


def match_fields(model) -> list[str]:
    """Fields an import can find existing records by: the type's own IDs, unique
    fields, and those listed in `CrudKitSettings.import_match_fields`."""
    fields = importable_fields(model)
    declared = list(getattr(model.CrudKitSettings, "import_match_fields", []))
    unique = [f.name for f in model._meta.fields if f.unique] + [
        c.fields[0] for c in model._meta.constraints if isinstance(c, UniqueConstraint) and len(c.fields) == 1
    ]
    keys = [ID]
    for name in declared + unique:
        if name in fields and name not in keys:
            keys.append(name)
    return keys


def suggest_mapping(model, headers: list[str]) -> dict[str, str]:
    """{header: field} for headers that name a field (or its label), ignoring case,
    spaces and underscores."""

    def normal(text) -> str:
        return str(text).lower().replace("_", " ").strip()

    targets = {normal(ID): ID}
    for name, field in importable_fields(model).items():
        targets.setdefault(normal(field.verbose_name), name)
        targets[normal(name)] = name
    mapping = {}
    for header in headers:
        field = targets.get(normal(header))
        if field and field not in mapping.values():
            mapping[header] = field
    return mapping


def _check_mapping(model, headers, mapping) -> None:
    if not isinstance(mapping, dict):
        raise ValueError("The mapping must map columns to fields")
    fields = importable_fields(model)
    for header, field in mapping.items():
        if header not in headers:
            raise ValueError(f"The file has no column {header!r}")
        if field != ID and field not in fields:
            raise ValueError(f"{model._meta.verbose_name} has no field {field!r} that can be imported")
    used = list(mapping.values())
    twice = sorted({f for f in used if used.count(f) > 1})
    if twice:
        raise ValueError(f"More than one column is mapped to {', '.join(twice)}")


# ---------------------------------------------------------------------------
# Cells


def coerce(field, value, user):
    """The cell `value` as the REST API expects it for `field`, or None for an
    empty cell. Raises ValueError with a message for the person importing."""
    if isinstance(value, str):
        value = value.strip()
    if _blank(value):
        return None
    if field.is_relation:
        return _related_id(field.related_model, value, user)
    if field.choices:
        return _choice(field, value)
    if isinstance(field, models.BooleanField):
        return _boolean(value)
    if isinstance(field, models.DateTimeField):
        return value
    if isinstance(field, models.DateField):
        return value.date() if isinstance(value, datetime.datetime) else value
    if isinstance(field, models.IntegerField) and isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(field, (models.DecimalField, models.FloatField)):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        # A phone number or code typed into a number cell.
        return str(int(value))
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    return value if isinstance(value, str) else str(value)


def _related_id(related, value, user):
    """A related record given by its ID (`CUS12`) or, when the type has a name
    field, by its name."""
    text = _text(value)
    type_id = getattr(related, "TYPE_ID", None)
    verbose_name = related._meta.verbose_name
    if ck_id_regex.fullmatch(text.upper()):
        if type_id and text[:3].upper() not in get_accepted_type_ids(related):
            raise ValueError(f"{text} is not the ID of a {verbose_name}")
        return text.upper()
    name_field = fk_display_field(related)
    if name_field is None:
        raise ValueError(f"Give the {verbose_name} by its ID, like {type_id or ''}123")
    queryset = viewable_queryset(user, related).filter(**{f"{name_field}__iexact": text})
    if hasattr(related, "deleted"):
        queryset = queryset.filter(deleted=False)
    pks = list(queryset.values_list("pk", flat=True)[:2])
    if not pks:
        raise ValueError(f"No {verbose_name} is called {text!r}")
    if len(pks) > 1:
        raise ValueError(f"More than one {verbose_name} is called {text!r}; give its ID instead")
    return pks[0]


def _choice(field, value):
    text = _text(value).lower()
    for choice, label in field.flatchoices:
        if text in (str(choice).lower(), str(label).lower()):
            return choice
    labels = ", ".join(str(label) for _, label in field.flatchoices)
    raise ValueError(f"{_text(value)!r} is not one of: {labels}")


def _boolean(value) -> bool:
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text.endswith(".0"):
        text = text[:-2]
    if text in TRUE:
        return True
    if text in FALSE:
        return False
    raise ValueError(f"{_text(value)!r} is not yes or no")


# ---------------------------------------------------------------------------
# Importing


def run_import(model, user, upload, mapping=None, match_on=None, mode="create", dry_run=True):
    """Read `upload` and import its rows into `model` as `user`.

    Returns {columns, samples, fields, mapping, match_fields, counts, rows,
    saved} (and `job` when not a dry run). Without a `mapping`, the suggested one is used.
    Importing needs the add permission, updating existing records the change
    permission too. Raises ValueError for a request that can't be imported at all."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}; use one of {', '.join(MODES)}")
    if not has_model_permission(user, model, "add") or (
        mode in UPDATING_MODES and not has_model_permission(user, model, "change")
    ):
        raise PermissionDenied
    keys = match_fields(model)
    if match_on and match_on not in keys:
        raise ValueError(f"Records can't be matched on {match_on!r}; use one of {', '.join(keys)}")
    if mode in UPDATING_MODES and not match_on:
        raise ValueError("Choose a column to match existing records on")

    headers, rows = read_table(upload)
    if mapping is None:
        mapping = suggest_mapping(model, headers)
    _check_mapping(model, headers, mapping)
    if match_on and match_on not in mapping.values():
        label = "ID" if match_on == ID else importable_fields(model)[match_on].verbose_name
        raise ValueError(f"Choose the column that holds the {label} to match records on it")

    importer = _Importer(model, user, mapping, match_on, mode, label=f"Imported from {upload.name}"[:255])
    if dry_run:
        report = importer.run(rows, dry_run=True)
    else:
        with jobs.track(f"Import {upload.name}"[:255], user) as tracker:
            # Created before the import's transaction, which may be rolled back.
            tracker.get_job(total=len(rows))
            report = importer.run(rows, dry_run=False)
            if not report["saved"]:
                failed = report["counts"]["error"]
                tracker.finish(RuntimeError(f"{failed} of {len(rows)} rows have errors; nothing was imported"))
        report["job"] = tracker.job.pk
    return {
        "columns": headers,
        "samples": _samples(headers, rows),
        "fields": [{"name": ID, "label": "ID"}]
        + [{"name": name, "label": capfirst(f.verbose_name)} for name, f in importable_fields(model).items()],
        "mapping": mapping,
        "match_fields": keys,
        **report,
    }


def _samples(headers, rows) -> dict[str, list[str]]:
    """The first few values of each column, to show next to it."""
    samples = {header: [] for header in headers}
    for _, values in rows:
        for header, value in values.items():
            if not _blank(value) and len(samples[header]) < SAMPLES:
                samples[header].append(_text(value))
    return samples


class _Importer:
    def __init__(self, model, user, mapping, match_on, mode, label):
        self.model = model
        self.user = user
        self.mapping = mapping
        self.match_on = match_on
        self.mode = mode
        self.label = label
        self.fields = importable_fields(model)

    def run(self, rows, dry_run: bool) -> dict:
        results = []
        with transaction.atomic():
            for done, (number, values) in enumerate(rows, start=1):
                results.append({"row": number, **self.row(values)})
                jobs.progress(done, total=len(rows), message=f"Row {number}")
            saved = not dry_run and not any(result["errors"] for result in results)
            if not saved:
                transaction.set_rollback(True)
        counts = {status: 0 for status in STATUSES} | Counter(result["status"] for result in results)
        return {"counts": counts, "rows": results, "saved": saved}

    def row(self, values) -> dict:
        fields, errors = {}, {}
        for header, name in self.mapping.items():
            cell = values.get(header)
            if name == ID:
                fields[ID] = _text(cell) or None
                continue
            try:
                value = coerce(self.fields[name], cell, self.user)
            except ValueError as exc:
                errors[header] = str(exc)
                continue
            if value is not None:
                fields[name] = value
        if errors:
            return _result("error", errors=errors)

        key = fields.pop(ID, None)
        if self.match_on and self.match_on != ID:
            key = fields.get(self.match_on)
        try:
            existing = self.find(key) if self.match_on and key is not None else None
            if existing is None:
                if self.mode not in CREATING_MODES:
                    return _result("skipped")
                if self.match_on == ID and key is not None:
                    raise ValueError(f"No {self.model._meta.verbose_name} has the ID {key}")
                instance = services.create_object(self.model, fields, self.user, label=self.label)
                return _result("created", instance.pk)
            if self.mode not in UPDATING_MODES:
                return _result("skipped", existing.pk)
            if not fields:
                return _result("unchanged", existing.pk)
            outcome = services.patch_fields(existing, fields, self.user, label=self.label, skip_unchanged=True)
            return _result("updated" if outcome["applied"] else "unchanged", existing.pk)
        except (ValueError, PermissionDenied, IntegrityError) as exc:
            return _result("error", errors=self.errors(exc))

    def errors(self, exc) -> dict[str, str]:
        """{column: message}, "" for the row as a whole."""
        detail = getattr(exc.__cause__, "detail", None)
        if not isinstance(detail, dict):
            return {"": str(exc) or "You may not make this change"}
        columns = {name: header for header, name in self.mapping.items()}
        return {
            columns.get(name, ""): " ".join(map(str, messages if isinstance(messages, list) else [messages]))
            for name, messages in detail.items()
        }

    def find(self, key):
        """The record `key` names in the match column, if any."""
        queryset = get_authorized_queryset(self.user, self.model.objects.all(), "view")
        if hasattr(self.model, "deleted"):
            queryset = queryset.filter(deleted=False)
        if self.match_on == ID:
            if not ck_id_regex.fullmatch(key.upper()) or key[:3].upper() not in get_accepted_type_ids(self.model):
                raise ValueError(f"{key} is not the ID of a {self.model._meta.verbose_name}")
            queryset = queryset.filter(pk=key.upper())
        elif isinstance(self.fields[self.match_on], (models.CharField, models.TextField)):
            queryset = queryset.filter(**{f"{self.match_on}__iexact": key})
        else:
            queryset = queryset.filter(**{self.match_on: key})
        matches = list(queryset[:2])
        if len(matches) > 1:
            raise ValueError(f"More than one {self.model._meta.verbose_name} has {self.match_on} {key!r}")
        if not matches:
            return None
        if not get_authorized_queryset(self.user, queryset, "change").filter(pk=matches[0].pk).exists():
            raise PermissionDenied(f"You may not change {matches[0]}")
        return matches[0]


def _result(status, pk=None, errors=None) -> dict:
    return {"status": status, "id": pk, "errors": errors or {}}
