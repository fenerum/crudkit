"""Working with records through the app: listing, opening, creating, editing
and starting new ones.

Phrases this area adds (record types are named by their verbose name):

Setup
- `Given 3 customers named "Acme" followed by a number`: "Acme 1", "Acme 2", "Acme 3"
- `Given an urgent comment "Server down" on the ticket "Outage"`

Listing (also see `Alice looks at the list of customers` in steps/permissions.py)
- `When Alice lists the customers 2 per page` / `When Alice opens page 2 of the customers, 2 per page`
- `When Alice lists the customers whose status is "churned"` / `... whose owner is herself`
- `When Alice lists the customers that have no topic` / `... that have a topic`
- `When Alice lists the customers sorted by status then name descending`
- `When Alice lists the customers showing only name and status`
- `When Alice opens the list of record types`
- `Then the list shows 2 of 3 customers, on page 1 of 2`
- `Then the list is ordered "Alpha", "beta" and "Cobalt"`
- `Then the list holds up to 50 records per page`
- `Then every row of the list shows only name and status`
- `Then the record types offered include customers and tickets` / `... leave out topics and comments`

Opening (`When Alice looks at "Acme"` is in steps/history.py)
- `When Alice opens "Acme" by its number` / `When Alice opens the deleted "Acme"`
- `When Alice opens the ID of "Billing" as a customer`
- `Then the record shown is "Acme"`
- `Then "Acme" is shown with the ID "CUS" followed by its number`
- `Then the topic is shown with the ID of "Billing"`
- `Then the topic is shown as "Billing"`
- `Then the people on the record are shown without their passwords`
- `Then the record does not include the watchers`

Creating and editing
- `When Alice creates a customer "Acme" with:` / `When Alice creates an exchange rate with:` (a field/value table)
- `When Alice creates a customer "Acme" prefilled with topic "Billing"`
- `When Alice creates a reminder "Read up" with the target written as "XYZ1"` (sent exactly as typed)
- `When Alice replaces "Acme" with:` (every field the form sends)
- `When Alice points the topic of "Acme" at a topic that does not exist`
- `Then Alice is recorded as the creator of "Acme"` / `... as the last editor of "Acme"`

Starting a new record (the values a new form opens with)
- `When Alice starts a new customer prefilled with name "Acme"` / `When Alice starts a new customer`
- `When Alice starts a new layout for customers`
- `Then the new form is prefilled with name "Acme"` / `leaves email empty` / `does not prefill status`
- `Then the new layout is for customers` / `Then the new layout places the fields two per row:` (a table, one row per form row)

Layouts
- `When Alice saves a layout for customers with the rows:` / `Then the layout for customers has the rows:`

Shared with the other modules of this area: `phrase` (adds `{x:Model}`, a record type that
fails to match instead of erroring, `{x:Labels}` for `"a", "b" and "c"`, `{x:Article}` for
a/an and `{x:Self}` for herself/himself/themselves), `list_url`.
"""

from pytest_bdd import given, then, when

from crudkit.models import Layout, parse_ck_id
from crudkit.utils import get_model_types
from tests.bdd.world import missing_id, model_named, phrase
from tests.testapp.models import UrgentComment


def field_name(words: str) -> str:
    return words.replace(" ", "_")


def table_payload(world, model, datatable) -> dict:
    return {field_name(row[0]): world.api_value(model, field_name(row[0]), row[1]) for row in datatable}


def list_url(model) -> str:
    return f"/api/v1/{model.TYPE_ID}/"


def results(world) -> list[dict]:
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    return world.response.data["results"]


def label_field_of(model) -> str:
    return next(f.name for f in model._meta.fields if f.name in ("name", "subject", "title", "note", "body"))


# Setup


@given(phrase('{count:d} {model:Model} named "{prefix:Q}" followed by a number'))
def numbered_records(world, count, model, prefix):
    for number in range(1, count + 1):
        world.create(model, f"{prefix} {number}")


@given(phrase('an urgent comment "{label:Q}" on the ticket "{ticket:Q}"'))
def an_urgent_comment(world, label, ticket):
    world.create(UrgentComment, label, {"ticket": ticket})


# Listing


def _get_list(world, name, model, params=None):
    world.remember(name, world.api(name).get(list_url(model), params or {}))


@when(phrase("{name:Actor} lists the {model:Model} {size:d} per page"))
def list_per_page(world, name, model, size):
    _get_list(world, name, model, {"page_size": size})


@when(phrase("{name:Actor} opens page {page:d} of the {model:Model}, {size:d} per page"))
def list_a_page(world, name, page, model, size):
    _get_list(world, name, model, {"page": page, "page_size": size})


@when(phrase('{name:Actor} lists the {model:Model} whose {field:Words} is "{value:Q}"'))
def list_filtered(world, name, model, field, value):
    _get_list(world, name, model, {field_name(field): world.api_value(model, field_name(field), value)})


@when(phrase("{name:Actor} lists the {model:Model} whose {field:Words} is {who:Self}"))
def list_filtered_by_self(world, name, model, field, who):
    _get_list(world, name, model, {field_name(field): "${user}"})


@when(phrase("{name:Actor} lists the {model:Model} that have no {field:Words}"))
def list_without(world, name, model, field):
    _get_list(world, name, model, {f"{field_name(field)}__isnull": "True"})


@when(phrase("{name:Actor} lists the {model:Model} that have a {field:Words}"))
def list_with(world, name, model, field):
    _get_list(world, name, model, {f"{field_name(field)}__isnull": "False"})


@when(phrase("{name:Actor} lists the {model:Model} sorted by {order:Words}"))
def list_sorted(world, name, model, order):
    """`sorted by status then name descending`"""
    fields = []
    for part in order.split(" then "):
        words = part.strip()
        if words.endswith(" descending"):
            fields.append("-" + field_name(words.removesuffix(" descending")))
        else:
            fields.append(field_name(words))
    _get_list(world, name, model, {"_order_by": ",".join(fields)})


@when(phrase("{name:Actor} lists the {model:Model} showing only {fields:List}"))
def list_some_fields(world, name, model, fields):
    _get_list(world, name, model, {"_fields": ",".join(field_name(f) for f in fields)})


@when(phrase("{name:Actor} opens the list of record types"))
def list_record_types(world, name):
    world.remember(name, world.api(name).get("/api/v1/"))


@then(phrase("the list shows {count:d} of {total:d} {model:Model}, on page {page:d} of {pages:d}"))
def a_page_of(world, count, total, model, page, pages):
    data = world.response.data
    shown = (len(results(world)), data["count"], data["current_page"], data["total_pages"])
    assert shown == (count, total, page, pages), shown
    assert all(row["id"].startswith(model.TYPE_ID) for row in data["results"])


@then(phrase("the list offers a next page"))
def has_next_page(world):
    assert world.response.data["next"], world.response.data


@then(phrase("the list offers no next page"))
def has_no_next_page(world):
    assert world.response.data["next"] is None, world.response.data["next"]


@then(phrase("the list offers a previous page"))
def has_previous_page(world):
    assert world.response.data["previous"], world.response.data


@then(phrase("the list is ordered {labels:Labels}"))
def ordered(world, labels):
    assert [row["label"] for row in results(world)] == labels, [row["label"] for row in results(world)]


@then(phrase("the list holds up to {size:d} records per page"))
def page_size(world, size):
    assert world.response.data["page_size"] == size, world.response.data["page_size"]


@then(phrase("every row of the list shows only {fields:List}"))
def rows_show_only(world, fields):
    rows = results(world)
    assert rows
    assert all(set(row) == {field_name(f) for f in fields} for row in rows), rows


def _types_offered(world) -> set[str]:
    assert world.response.status_code == 200, world.response.status_code
    return set(world.response.data)


@then(phrase("the record types offered include {types:List}"))
def record_types_offered(world, types):
    assert {model_named(words).TYPE_ID for words in types} <= _types_offered(world), _types_offered(world)


@then(phrase("the record types offered leave out {types:List}"))
def record_types_left_out(world, types):
    assert not {model_named(words).TYPE_ID for words in types} & _types_offered(world), _types_offered(world)


# Opening one record


@when(phrase('{name:Actor} opens "{label:Q}" by its number'))
def open_by_number(world, name, label):
    type_id = world.records[label].TYPE_ID
    world.remember(name, world.api(name).get(f"/api/v1/{type_id}/{world.number(label)}/"))


@when(phrase('{name:Actor} opens the deleted "{label:Q}"'))
def open_deleted(world, name, label):
    world.remember(name, world.api(name).get(world.url(label), {"deleted": "1"}))


@when(phrase('{name:Actor} opens the ID of "{label:Q}" as {a:Article} {model:Model}'))
def open_as(world, name, label, a, model):
    world.remember(name, world.api(name).get(f"/api/v1/{model.TYPE_ID}/{world.ck_id(label)}/"))


@then(phrase('the record shown is "{label:Q}"'))
def record_shown(world, label):
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    data = world.response.data
    assert data["label"] == label, data["label"]
    assert parse_ck_id(data["id"])[1] == world.number(label), data["id"]


@then(phrase('"{label:Q}" is shown with the ID "{letters:Q}" followed by its number'))
def shown_with_id(world, label, letters):
    data = world.response.data
    assert data["id"] == f"{letters}{world.number(label)}", data["id"]


@then(phrase('the {field:Words} is shown with the ID of "{label:Q}"'))
def linked_id(world, field, label):
    value = world.response.data[field_name(field)]
    shown = value["id"] if isinstance(value, dict) else value
    assert shown == world.ck_id(label), shown


@then(phrase('the {field:Words} is shown as "{label:Q}"'))
def linked_label(world, field, label):
    value = world.response.data[field_name(field)]
    assert value["label"] == label, value


@then(phrase("the people on the record are shown without their passwords"))
def no_passwords(world):
    data = world.response.data
    for field in ("created_by", "updated_by"):
        assert data[field]["username"], data[field]
        assert not any("password" in key for key in data[field]), data[field]


@then(phrase("the record does not include the {field:Words}"))
def not_included(world, field):
    assert field_name(field) not in world.response.data, list(world.response.data)


# Creating and editing


def _create(world, name, model, payload, params=""):
    response = world.api(name).post(list_url(model) + params, payload, format="json")
    world.remember(name, response)
    if response.status_code == 201:
        world.add(str(response.data["label"]), model._base_manager.get(pk=response.data["id"]))


@when(phrase('{name:Actor} creates {a:Article} {model:Model} "{label:Q}" with:'))
def create_with(world, name, a, model, label, datatable):
    _create(world, name, model, {label_field_of(model): label} | table_payload(world, model, datatable))


@when(phrase("{name:Actor} creates {a:Article} {model:Model} with:"))
def create_unlabelled(world, name, a, model, datatable):
    _create(world, name, model, table_payload(world, model, datatable))


@when(phrase('{name:Actor} creates {a:Article} {model:Model} "{label:Q}" prefilled with {field:Words} "{value:Q}"'))
def create_prefilled(world, name, a, model, label, field, value):
    prefill = world.api_value(model, field_name(field), value)
    _create(world, name, model, {label_field_of(model): label}, f"?{field_name(field)}={prefill}")


@when(phrase('{name:Actor} creates {a:Article} {model:Model} "{label:Q}" with the {field:Words} written as "{text:Q}"'))
def create_with_raw_value(world, name, a, model, label, field, text):
    """The value is sent exactly as typed, e.g. something that is not a record ID."""
    _create(world, name, model, {label_field_of(model): label, field_name(field): text})


@when(phrase('{name:Actor} replaces "{label:Q}" with:'))
def replace(world, name, label, datatable):
    model = type(world.record(label))
    world.remember(name, world.api(name).put(world.url(label), table_payload(world, model, datatable), format="json"))


@when(phrase('{name:Actor} points the {field:Words} of "{label:Q}" at {a:Article} {model:Model} that does not exist'))
def point_at_missing(world, name, field, label, a, model):
    payload = {field_name(field): missing_id(model)}
    world.remember(name, world.api(name).patch(world.url(label), payload, format="json"))


def _record_called(world, label):
    """The record called `label`: introduced in a Given, or just created through the app."""
    if label not in world.records:
        data = world.response.data
        assert data.get("label") == label, data
        model = get_model_types()[parse_ck_id(data["id"])[0]]
        world.add(label, model._base_manager.get(pk=data["id"]))
    return world.record(label)


@then(phrase('{name:Actor} is recorded as the creator of "{label:Q}"'))
def recorded_creator(world, name, label):
    assert _record_called(world, label).created_by == world.user(name)


@then(phrase('{name:Actor} is recorded as the last editor of "{label:Q}"'))
def recorded_editor(world, name, label):
    assert _record_called(world, label).updated_by == world.user(name)


# Starting a new record


def _start(world, name, model, params=None):
    world.remember(name, world.api(name).get(list_url(model) + "initial/", params or {}))


@when(phrase("{name:Actor} starts a new {model:Model}"))
def start_new(world, name, model):
    _start(world, name, model)


@when(phrase('{name:Actor} starts a new {model:Model} prefilled with {field:Words} "{value:Q}"'))
def start_prefilled(world, name, model, field, value):
    _start(world, name, model, {field_name(field): world.api_value(model, field_name(field), value)})


@when(phrase("{name:Actor} starts a new layout for {model:Model}"))
def start_layout(world, name, model):
    _start(world, name, Layout, {"model": model.TYPE_ID})


def _prefilled(world):
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    return world.response.data["fields"]


@then(phrase('the new form is prefilled with {field:Words} "{value:Q}"'))
def prefilled_with(world, field, value):
    shown = _prefilled(world)[field_name(field)]
    assert (shown["label"] if isinstance(shown, dict) else shown) == value, shown


@then(phrase("the new form leaves {field:Words} empty"))
def prefilled_empty(world, field):
    assert _prefilled(world)[field_name(field)] is None, _prefilled(world)


@then(phrase("the new form does not prefill {field:Words}"))
def not_prefilled(world, field):
    assert field_name(field) not in _prefilled(world), _prefilled(world)


@then(phrase("the new layout is for {model:Model}"))
def layout_for(world, model):
    assert _prefilled(world)["model"] == model.TYPE_ID, _prefilled(world)


@then(phrase("the new layout places the fields two per row:"))
def layout_rows(world, datatable):
    assert _prefilled(world)["fields"] == _rows(datatable), _prefilled(world)


# Layouts of a record type's page


def _rows(datatable) -> list[list[str]]:
    return [[cell for cell in row if cell] for row in datatable]


@when(phrase("{name:Actor} saves a layout for {model:Model} with the rows:"))
def save_layout(world, name, model, datatable):
    payload = {"model": model.TYPE_ID, "fields": _rows(datatable)}
    world.remember(name, world.api(name).post(list_url(Layout), payload, format="json"))


@then(phrase("the layout for {model:Model} has the rows:"))
def saved_layout(world, model, datatable):
    assert Layout.objects.get(model=model.TYPE_ID).fields == _rows(datatable)
