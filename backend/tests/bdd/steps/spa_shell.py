"""The page that serves the web app at every address the project does not use
for something else.

Phrases this area adds:

- `Given the web app is served at every other address`
- `Given the web app requires signing in`
- `Given the web app is configured with:` (a `| setting | value |` table)
- `Given static files are served from "/media-x/"`
- `When someone who is not signed in opens a page of the web app` / `When Alice opens a page of the web app`
- `Then the web app is shown`
- `Then they are sent to sign in first, coming back to that page afterwards`
- `Then the page title is "Acme CRM"`
- `Then the settings on the page include app_name "Acme CRM"` / `... the installed CrudKit version`
- `Then the settings on the page cannot break out of the page, yet still read "</script>" as note`
- `Then the web app loads its files from "/media-x/"`
"""

import json
import re
from importlib.metadata import version

from django.test import Client
from pytest_bdd import given, then, when

from crudkit_frontend.tests.test_frontend import STUB_TEMPLATES
from tests.bdd.world import phrase

# Any client-side route of the app.
APP_PAGE = "/customers/42"


@given(phrase("the web app is served at every other address"))
def web_app_served(settings):
    """The project includes the web app's address catch-all last; the stub page stands in for the built app."""
    settings.ROOT_URLCONF = "crudkit_frontend.tests.urls"
    settings.TEMPLATES = STUB_TEMPLATES


@given(phrase("the web app requires signing in"))
def login_required(settings):
    settings.CRUDKIT_FRONTEND_LOGIN_REQUIRED = True


@given(phrase("the web app is configured with:"))
def configured_with(settings, datatable):
    settings.CRUDKIT_FRONTEND_CONFIG = {row[0]: row[1] for row in datatable}


@given(phrase('static files are served from "{prefix:Q}"'))
def static_prefix(settings, prefix):
    settings.STATIC_URL = prefix


@when(phrase("someone who is not signed in opens a page of the web app"))
def anonymous_opens_app(world):
    world.response = Client().get(APP_PAGE)


@when(phrase("{name:Actor} opens a page of the web app"))
def opens_app(world, name):
    client = Client()
    client.force_login(world.user(name))
    world.response = client.get(APP_PAGE)


def _page(world) -> str:
    assert world.response.status_code == 200, world.response.status_code
    return world.response.content.decode()


def _settings_on_page(world) -> dict:
    found = re.search(r'<script id="crudkit-config" type="application/json">(.*?)</script>', _page(world), re.S)
    return json.loads(found.group(1))


@then(phrase("the web app is shown"))
def app_shown(world):
    _page(world)
    assert "crudkit_frontend/index.html" in [t.name for t in world.response.templates]


@then(phrase("they are sent to sign in first, coming back to that page afterwards"))
def sent_to_sign_in(world):
    assert world.response.status_code == 302, world.response.status_code
    assert world.response["Location"] == f"/accounts/login/?next={APP_PAGE}", world.response["Location"]


@then(phrase('the page title is "{title:Q}"'))
def page_title(world, title):
    assert f"<title>{title}</title>" in _page(world)


@then(phrase('the settings on the page include {key:Words} "{value:Q}"'))
def setting_on_page(world, key, value):
    assert _settings_on_page(world)[key] == value, _settings_on_page(world)


@then(phrase("the settings on the page include the installed CrudKit version"))
def version_on_page(world):
    assert _settings_on_page(world)["crudkit_version"] == version("crudkit"), _settings_on_page(world)


@then(phrase('the settings on the page cannot break out of the page, yet still read "{value:Q}" as {key:Words}'))
def settings_escaped(world, value, key):
    assert value not in _page(world)
    assert _settings_on_page(world)[key] == value, _settings_on_page(world)


@then(phrase('the web app loads its files from "{prefix:Q}"'))
def static_files_from(world, prefix):
    page = _page(world)
    assert f"window.__CRUDKIT_STATIC_URL__ = {json.dumps(prefix)}" in page
    assert f"{prefix}crudkit_frontend/assets/favicon.svg" in page
