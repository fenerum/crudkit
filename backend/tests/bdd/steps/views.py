"""Saved views, their menu badges, and workspaces.

A view's settings are written as `| setting | value |` rows (no header row, like the shared record tables):
- `fields`: "name, status"; `layout`: "kanban"; `order by`: "-balance"; `group by`, `pivot by`, `aggregate by`
- `aggregate type`: "sum" or "count"; `public` / `badge in menu`: "yes" or "no"
- `filter` and `badge filter`: "status = churned", one row per filter. A linked record is named by its
  label ("topic = Billing"); `${user}` is whoever opens the view.

Views
- `Given Alice saved a view "Churned" of customers` (`… with:` a settings table; `a private view`)
- `When Alice saves a view "Churned" of customers` (`… with:`) / `… for a record type that does not exist`
- `When Alice opens the view "Churned"` (`… sorted by "name"`, `… on the ticket list`)
- `When Alice opens a view that does not exist`
- `When Bob lists the saved views` / `Then the saved views listed are "Team" and "Mine"`
- `Then the view shows "Acme" and "Globex"` / `… "Globex", "Acme" in that order` / `Then the view shows nothing`
- `Then the view is not found` / `Then there is no saved view "Broken"`
- `Then the menu badge of "Churned" shows 2 for Alice`

Workspaces
- `Given Alice saved a workspace "Sales" with the views "Churned" and "Active"` (`a private workspace`)
- `When Alice saves a workspace "Sales" with the views "Churned" and "Active"` (`… without any views`)
- `When Alice saves a workspace "Sales" holding a customer` (or a view that does not exist, something that
  is not an id, something other than a list)
- `When Bob lists the workspaces` / `When Bob searches the workspaces for "Sal"`
- `Then the workspaces listed are "Sales"` / `Then the workspace "Sales" has the tabs "Churned" and "Active" in order` (`… has no tabs`)
"""

from pytest_bdd import given, parsers, then, when

from crudkit.models import View, Workspace
from tests.bdd.world import LABELS, phrase, split_list

FLAGS = {"yes": True, "no": False}
AGGREGATE_TYPES = {"sum": View.AggregationTypes.SUM, "count": View.AggregationTypes.COUNT}
SINGLE_SETTINGS = {
    "layout": "layout",
    "order by": "order_by",
    "group by": "group_by",
    "pivot by": "pivot_by",
    "aggregate by": "aggregate_by",
}
NOT_A_VIEW = {
    "a customer": ["CUS1"],
    "a view that does not exist": ["VIW999999"],
    "something that is not an id": ["not-an-id"],
    "something other than a list": "VIW1",
}


# Several labels: `"Acme"`, `"Acme" and "Globex"`, `"Acme", "Globex" and "Initech"`.
def labels_in(text: str) -> list[str]:
    return [label.strip('"') for label in split_list(text)]


def _filter(world, model, text):
    """ "status = churned" -> ["status", "=", "churned"], with linked records named by label."""
    parts = text.split(" ", 2)
    if len(parts) == 3:
        field, _comparator, value = parts
        is_relation = "__" not in field and field in {f.name for f in model._meta.fields if f.is_relation}
        if is_relation and value in world.records:
            parts[2] = world.ck_id(value)
    return parts


def view_settings(world, model, rows) -> dict:
    """The fields of a View of `model` from `| setting | value |` rows."""
    values = {"model": model.TYPE_ID, "fields": ["name"], "filters": [], "badge_filters": []}
    for setting, value in rows:
        if setting == "fields":
            values["fields"] = split_list(value)
        elif setting == "filter":
            values["filters"].append(_filter(world, model, value))
        elif setting == "badge filter":
            values["badge_filters"].append(_filter(world, model, value))
        elif setting == "aggregate type":
            values["aggregate_type"] = AGGREGATE_TYPES[value]
        elif setting == "public":
            values["public"] = FLAGS[value]
        elif setting == "badge in menu":
            values["show_badge_in_menu"] = FLAGS[value]
        else:
            values[SINGLE_SETTINGS[setting]] = value
    return values


def _names(response, key="label") -> list[str]:
    assert response.status_code == 200, (response.status_code, response.content)
    return [row[key] for row in response.data["results"]]


# Views


def _save_view(world, name, label, values):
    by = world.user(name)
    view = View(name=label, created_by=by, updated_by=by, **values)
    view.clean()
    view.save()
    world.add(label, view)


@given(phrase('{name:Actor} saved a view "{label:Q}" of {model:Model}'))
def saved_a_view(world, name, label, model):
    _save_view(world, name, label, view_settings(world, model, []))


@given(phrase('{name:Actor} saved a private view "{label:Q}" of {model:Model}'))
def saved_a_private_view(world, name, label, model):
    _save_view(world, name, label, view_settings(world, model, [("public", "no")]))


@given(phrase('{name:Actor} saved a view "{label:Q}" of {model:Model} with:'))
def saved_a_view_with(world, name, label, model, datatable):
    _save_view(world, name, label, view_settings(world, model, datatable))


def _post_view(world, name, label, values):
    response = world.api(name).post("/api/v1/VIW/", {"name": label, **values}, format="json")
    world.remember(name, response)
    if response.status_code == 201:
        world.add(label, View.objects.get(pk=response.data["id"]))


@when(phrase('{name:Actor} saves a view "{label:Q}" of {model:Model}'))
def save_a_view(world, name, label, model):
    _post_view(world, name, label, view_settings(world, model, []))


@when(phrase('{name:Actor} saves a view "{label:Q}" of {model:Model} with:'))
def save_a_view_with(world, name, label, model, datatable):
    _post_view(world, name, label, view_settings(world, model, datatable))


@when(phrase('{name:Actor} saves a view "{label:Q}" for a record type that does not exist'))
def save_a_view_of_nothing(world, name, label):
    _post_view(world, name, label, {"model": "ZZZ", "fields": ["name"]})


def _open(world, name, type_id, params):
    world.remember(name, world.api(name).get(f"/api/v1/{type_id}/", params))


@when(phrase('{name:Actor} opens the view "{label:Q}"'))
def open_a_view(world, name, label):
    view = world.records[label]
    _open(world, name, view.model, {"_view": world.ck_id(label)})


@when(phrase('{name:Actor} opens the view "{label:Q}" sorted by "{order:Q}"'))
def open_a_view_sorted(world, name, label, order):
    view = world.records[label]
    _open(world, name, view.model, {"_view": world.ck_id(label), "_order_by": order})


@when(phrase('{name:Actor} opens the view "{label:Q}" on the {model:Model} list'))
def open_a_view_elsewhere(world, name, label, model):
    _open(world, name, model.TYPE_ID, {"_view": world.ck_id(label)})


@when(phrase("{name:Actor} opens a view that does not exist"))
def open_a_missing_view(world, name):
    _open(world, name, "CUS", {"_view": "VIW999999"})


@when(phrase("{name:Actor} lists the saved views"))
def list_views(world, name):
    world.remember(name, world.api(name).get("/api/v1/VIW/"))


@then(parsers.re(rf"the view shows (?P<labels>{LABELS})"))
def view_shows(world, labels):
    assert sorted(_names(world.response)) == sorted(labels_in(labels)), _names(world.response)


@then(parsers.re(rf"the view shows (?P<labels>{LABELS}) in that order"))
def view_shows_in_order(world, labels):
    assert _names(world.response) == labels_in(labels), _names(world.response)


@then("the view shows nothing")
def view_shows_nothing(world):
    assert _names(world.response) == [], _names(world.response)


@then("the view is not found")
def view_not_found(world):
    assert world.response.status_code == 404, world.response.status_code
    assert "Saved view not found" in world.response.content.decode(), world.response.content


@then(phrase('there is no saved view "{label:Q}"'))
def no_such_view(world, label):
    assert not View.objects.filter(name=label).exists()


@then(parsers.re(rf"the saved views listed are (?P<labels>{LABELS})"))
def views_listed(world, labels):
    names = _names(world.response, key="name")
    assert names == labels_in(labels), names


@then(phrase('the menu badge of "{label:Q}" shows {count:d} for {name:Actor}'))
def badge_shows(world, label, count, name):
    """What the menu shows: the count of the view's list with its badge filters applied."""
    view = world.records[label]
    response = world.api(name).get(
        f"/api/v1/{view.model}/", {"_view": world.ck_id(label), "_badge": "1", "page_size": 1}
    )
    assert response.status_code == 200, response.content
    assert response.data["count"] == count, response.data["count"]


# Workspaces


def _view_ids(world, labels):
    return [world.ck_id(label) for label in labels_in(labels)]


def _save_workspace(world, name, label, views, public=True):
    by = world.user(name)
    workspace = Workspace(name=label, views=views, public=public, created_by=by, updated_by=by)
    workspace.clean()
    workspace.save()
    world.add(label, workspace)


def _post_workspace(world, name, label, views):
    response = world.api(name).post("/api/v1/WSP/", {"name": label, "views": views}, format="json")
    world.remember(name, response)
    if response.status_code == 201:
        world.add(label, Workspace.objects.get(pk=response.data["id"]))


@given(parsers.re(rf'(?P<name>[A-Z][a-z]+) saved a workspace "(?P<label>[^"]*)" with the views? (?P<views>{LABELS})'))
def saved_a_workspace(world, name, label, views):
    _save_workspace(world, name, label, _view_ids(world, views))


@given(phrase('{name:Actor} saved a private workspace "{label:Q}"'))
def saved_a_private_workspace(world, name, label):
    _save_workspace(world, name, label, [], public=False)


@when(parsers.re(rf'(?P<name>[A-Z][a-z]+) saves a workspace "(?P<label>[^"]*)" with the views? (?P<views>{LABELS})'))
def save_a_workspace(world, name, label, views):
    _post_workspace(world, name, label, _view_ids(world, views))


@when(phrase('{name:Actor} saves a workspace "{label:Q}" without any views'))
def save_an_empty_workspace(world, name, label):
    _post_workspace(world, name, label, [])


@when(phrase('{name:Actor} saves a workspace "{label:Q}" holding {content}'))
def save_a_bad_workspace(world, name, label, content):
    _post_workspace(world, name, label, NOT_A_VIEW[content])


@when(phrase("{name:Actor} lists the workspaces"))
def list_workspaces(world, name):
    world.remember(name, world.api(name).get("/api/v1/WSP/"))


@when(phrase('{name:Actor} searches the workspaces for "{text:Q}"'))
def search_workspaces(world, name, text):
    world.remember(name, world.api(name).get("/api/v1/WSP/", {"_q": text}))


@then(parsers.re(rf"the workspaces listed are (?P<labels>{LABELS})"))
def workspaces_listed(world, labels):
    assert _names(world.response) == labels_in(labels), _names(world.response)


@then(parsers.re(rf'the workspace "(?P<label>[^"]*)" has the tabs (?P<views>{LABELS}) in order'))
def workspace_tabs(world, label, views):
    assert world.record(label).views == _view_ids(world, views), world.record(label).views


@then(phrase('the workspace "{label:Q}" has no tabs'))
def workspace_without_tabs(world, label):
    assert world.record(label).views == [], world.record(label).views


@then(phrase('there is no workspace "{label:Q}"'))
def no_such_workspace(world, label):
    assert not Workspace.objects.filter(name=label).exists()
