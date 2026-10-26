"""Finding records: the search box that looks through every record type, and
searching within one list.

Phrases this area adds (searching one list is `When Alice searches the customers
for "acme"` from steps/feed.py, read back with `Then the list holds ...`):

- `When Alice searches for "acme"` / `When Alice searches only tickets for "acme"`
- `When Alice searches for the ID of "Acme"` / `... in lower case`
- `When someone who is not signed in searches for "acme"`
- `When Alice looks for the ID of "Acme" in the list of customers` / `... in lower case`
- `Then the search finds "Acme Corp" and "Acme printer"` / `Then the search finds nothing`
- `Then the search finds 6 customers`
- `Then each search result gives only its ID, label and pictures`
"""

from pytest_bdd import then, when
from rest_framework.test import APIClient

from tests.bdd.steps.records import list_url
from tests.bdd.world import phrase

SEARCH_URL = "/api/v1/search/"


def _search(world, name, query):
    world.remember(name, world.api(name).get(SEARCH_URL, {"q": query}))


@when(phrase('{name:Actor} searches for "{query:Q}"'))
def search(world, name, query):
    _search(world, name, query)


@when(phrase('{name:Actor} searches only {model:Model} for "{query:Q}"'))
def search_one_type(world, name, model, query):
    """What people type as `TIC:printer` in the search box."""
    _search(world, name, f"{model.TYPE_ID}:{query}")


@when(phrase('{name:Actor} searches for the ID of "{label:Q}"'))
def search_by_id(world, name, label):
    _search(world, name, world.ck_id(label))


@when(phrase('{name:Actor} searches for the ID of "{label:Q}" in lower case'))
def search_by_lowercase_id(world, name, label):
    _search(world, name, world.ck_id(label).lower())


@when(phrase('someone who is not signed in searches for "{query:Q}"'))
def anonymous_search(world, query):
    world.response = APIClient().get(SEARCH_URL, {"q": query})


@when(phrase('{name:Actor} looks for the ID of "{label:Q}" in the list of {model:Model}'))
def list_search_by_id(world, name, label, model):
    world.remember(name, world.api(name).get(list_url(model), {"_q": world.ck_id(label)}))


@when(
    phrase(
        '{name:Actor} looks for the ID of "{label:Q}" in lower case, padded with spaces, in the list of {model:Model}'
    )
)
def list_search_by_sloppy_id(world, name, label, model):
    world.remember(name, world.api(name).get(list_url(model), {"_q": f"  {world.ck_id(label).lower()} "}))


def _found(world) -> list[dict]:
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    return world.response.data["results"]


@then(phrase("the search finds {labels:Labels}"))
def finds(world, labels):
    assert sorted(result["label"] for result in _found(world)) == sorted(labels), _found(world)


@then(phrase("the search finds nothing"))
def finds_nothing(world):
    assert _found(world) == [], _found(world)


@then(phrase("the search finds {count:d} {model:Model}"))
def finds_count(world, count, model):
    found = [result for result in _found(world) if result["id"].startswith(model.TYPE_ID)]
    assert len(found) == count, len(found)


@then(phrase("each search result gives only its ID, label and pictures"))
def result_shape(world):
    found = _found(world)
    assert found
    assert all(set(result) == {"id", "label", "object_images"} for result in found), found
