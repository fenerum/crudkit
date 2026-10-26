"""Signing in, the signed-in person's profile, and the dashboard.

Phrases this area adds:

Signing in
- `When Alice signs in with the password "password"` (also `Given Alice signed in ...`)
- `When Alice signs in again with her refresh token` (also `Given Alice signed in again ...`)
- `When someone renews a sign-in with a made-up refresh token`
- `When Alice uses her access token to view her profile`
- `Then Alice is signed in and receives her account details`
- `Then a new access token is issued`
- `Then the sign-in is refused with "Invalid credentials"`

The profile
- `Given the project keeps people's profiles` (a profile store the project provides)
- `Given Alice's profile lists the pictures:` (a one-column table)
- `Given the project has no AI model set up`
- `Given the assistant is called "Ada" and pictured at "/static/ada.png"`
- `When Alice views her profile` / `When Alice changes her language to "da"`
- `When someone who is not signed in views a profile` / `... opens the dashboard`
- `Then the profile is Alice's`
- `Then the profile shows the language "da"` / `Then the profile shows no pictures`
- `Then the profile shows the pictures:` (a one-column table)
- `Then the profile says the assistant is available` / `is not available`
- `Then the profile says proposals can be reviewed`
- `Then the profile names the assistant "Ada" pictured at "/static/ada.png"`
- `Then the creator's picture on the record is shown as "http://testserver/media/alice.png"`

The dashboard
- `Given the dashboard is not set up` / `Given the dashboard is set up with something that does not exist`
- `Given the dashboard shows {widget}` (see WIDGETS)
- `Given Metabase is connected`
- `When Alice opens the dashboard`
- `Then the dashboard is empty` / `Then the dashboard shows {labels}` (titles, in order)
- `Then the widget "Churned customers" is a list widget 2 columns wide`
- `Then the widget "Churned customers" lists up to 3 customers whose status is "churned"`
- `Then the widget "Churned customers" shows the fields name and owner`
- `Then the widget "Signups" draws a line chart of "Signups"`
- `Then the widget "Broken chart" draws a bar chart explaining "Error: no data"`
- `Then the widget "Revenue" embeds Metabase question 7 with a link that expires in 10 minutes`
- `Then the widget "Revenue" explains "METABASE_SECRET_KEY / METABASE_SITE_URL not set in settings."`
"""

import time
from urllib.parse import urlparse

import jwt
from parse import with_pattern
from pytest_bdd import given, then, when
from rest_framework.test import APIClient

from crudkit.widgets import ChartWidget, ListWidget, MetabaseEmbeddedQuestionWidget
from tests.bdd.steps.records import field_name
from tests.bdd.world import phrase as world_phrase
from tests.testapp.adapters import InMemoryUserProfileAdapter
from tests.testapp.models import Customer

METABASE_SITE = "https://metabase.example.test"
METABASE_SECRET = "metabase-secret"


class ChurnedCustomers(ListWidget):
    obj = Customer
    limit = 3

    def __init__(self):
        super().__init__(width=2)

    def get_title(self):
        return "Churned customers"

    def get_filters(self):
        return [["status", "=", "churned"]]

    def get_display_fields(self):
        return ["name", "owner"]


class Signups(ChartWidget):
    def _get_chart_data(self):
        return {"labels": ["May", "June"], "datasets": [{"label": "Signups", "data": [3, 5]}]}


class BrokenChart(ChartWidget):
    chart_type = "line"

    def get_title(self):
        return "Broken chart"

    def _get_chart_data(self):
        raise ValueError("no data")


class Revenue(MetabaseEmbeddedQuestionWidget):
    question_id = 7


# How a widget reads in a feature.
WIDGETS = {
    "a list of churned customers": ChurnedCustomers,
    "a chart of signups": Signups,
    "a chart that fails to load": BrokenChart,
    "a Metabase question about revenue": Revenue,
}

# The widgets the dashboard of the current scenario shows; see `dashboard_widgets`.
dashboard = []


def dashboard_widgets(user):
    """What CRUDKIT_DASHBOARD_WIDGETS points at in these scenarios."""
    return [widget() for widget in dashboard]


@with_pattern("|".join(WIDGETS))
def _widget(text):
    return WIDGETS[text]


def phrase(pattern: str):
    """The shared `phrase` plus `{x:Widget}`, a widget from WIDGETS."""
    return world_phrase(pattern, Widget=_widget)


# Signing in


def _sign_in(world, name, password):
    world.response = APIClient().post(
        "/api/v1/token/", {"username": world.user(name).username, "password": password}, format="json"
    )
    world.tokens = world.response.data if world.response.status_code == 200 else {}


@given(phrase('{name:Actor} signed in with the password "{password:Q}"'))
@when(phrase('{name:Actor} signs in with the password "{password:Q}"'))
def sign_in(world, name, password):
    _sign_in(world, name, password)


@then(phrase("{name:Actor} is signed in and receives {whose:Their} account details"))
def signed_in(world, name, whose):
    assert world.response.status_code == 200, world.response.data
    user = world.user(name)
    assert world.tokens["access"] and world.tokens["refresh"], world.tokens
    assert world.tokens["user"] == {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }, world.tokens["user"]


@then(phrase('the sign-in is refused with "{message:Q}"'))
def sign_in_refused(world, message):
    assert world.response.status_code == 401, world.response.status_code
    assert world.response.data["detail"] == message, world.response.data


@when(phrase("{name:Actor} uses {whose:Their} access token to view {own:Their} profile"))
def view_profile_with_token(world, name, whose, own):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {world.tokens['access']}")
    world.response = client.get("/api/v1/user/me/")


@given(phrase("{name:Actor} signed in again with {whose:Their} refresh token"))
@when(phrase("{name:Actor} signs in again with {whose:Their} refresh token"))
def refresh(world, name, whose):
    world.response = APIClient().post("/api/v1/token/refresh/", {"refresh": world.tokens["refresh"]}, format="json")
    if world.response.status_code == 200:
        world.tokens = world.tokens | world.response.data


@when(phrase("someone renews a sign-in with a made-up refresh token"))
def refresh_made_up(world):
    world.response = APIClient().post("/api/v1/token/refresh/", {"refresh": "made-up"}, format="json")


@then(phrase("a new access token is issued"))
def new_access_token(world):
    assert world.response.status_code == 200, world.response.data
    assert world.response.data["access"], world.response.data


# The profile


@given(phrase("the project keeps people's profiles"))
def profile_store(settings, request):
    settings.CRUDKIT_USER_PROFILE_ADAPTER = "tests.testapp.adapters.InMemoryUserProfileAdapter"
    InMemoryUserProfileAdapter.reset()
    request.addfinalizer(InMemoryUserProfileAdapter.reset)


@given(phrase("{name:Actor}'s profile lists the pictures:"))
def profile_pictures(world, name, datatable):
    InMemoryUserProfileAdapter.images[world.user(name).pk] = [row[0] for row in datatable]


@given(phrase("the project has no AI model set up"))
def no_ai_model(settings):
    settings.CRUDKIT_AI_MODEL_FACTORY = None
    settings.CRUDKIT_AI_MODEL = None


@given(phrase('the assistant is called "{assistant:Q}" and pictured at "{avatar:Q}"'))
def assistant_named(settings, assistant, avatar):
    settings.CRUDKIT_ASSISTANT_NAME = assistant
    settings.CRUDKIT_ASSISTANT_AVATAR_URL = avatar


@when(phrase("{name:Actor} views {whose:Their} profile"))
def view_profile(world, name, whose):
    world.remember(name, world.api(name).get("/api/v1/user/me/"))


@when(phrase('{name:Actor} changes {whose:Their} language to "{language:Q}"'))
def change_language(world, name, whose, language):
    world.remember(name, world.api(name).patch("/api/v1/user/me/", {"preferred_language": language}, format="json"))


@when(phrase("someone who is not signed in views a profile"))
def anonymous_profile(world):
    world.response = APIClient().get("/api/v1/user/me/")


def _profile(world) -> dict:
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    return world.response.data


@then(phrase("the profile is {name:Actor}'s"))
def profile_of(world, name):
    assert _profile(world)["username"] == world.user(name).username, _profile(world)


@then(phrase('the profile shows the language "{language:Q}"'))
def profile_language(world, language):
    assert _profile(world)["preferred_language"] == language, _profile(world)


@then(phrase("the profile shows no pictures"))
def profile_without_pictures(world):
    assert _profile(world)["object_images"] == [], _profile(world)


@then(phrase("the profile shows the pictures:"))
def profile_shows_pictures(world, datatable):
    assert _profile(world)["object_images"] == [row[0] for row in datatable], _profile(world)


@then(phrase("the profile says the assistant is available"))
def assistant_available(world):
    assert _profile(world)["assistant"]["enabled"] is True, _profile(world)["assistant"]


@then(phrase("the profile says the assistant is not available"))
def assistant_unavailable(world):
    assert _profile(world)["assistant"]["enabled"] is False, _profile(world)["assistant"]


@then(phrase("the profile says proposals can be reviewed"))
def proposals_reviewable(world):
    assert _profile(world)["assistant"]["proposals"] is True, _profile(world)["assistant"]


@then(phrase('the profile names the assistant "{assistant:Q}" pictured at "{avatar:Q}"'))
def assistant_identity(world, assistant, avatar):
    shown = _profile(world)["assistant"]
    assert (shown["name"], shown["avatar_url"]) == (assistant, avatar), shown


@then(phrase('the creator\'s picture on the record is shown as "{url:Q}"'))
def creator_picture(world, url):
    assert world.response.data["created_by"]["object_images"] == [url], world.response.data["created_by"]


# The dashboard


@given(phrase("the dashboard is not set up"))
def no_dashboard(settings):
    if hasattr(settings, "CRUDKIT_DASHBOARD_WIDGETS"):
        del settings.CRUDKIT_DASHBOARD_WIDGETS


@given(phrase("the dashboard is set up with something that does not exist"))
def missing_dashboard(settings):
    settings.CRUDKIT_DASHBOARD_WIDGETS = "tests.testapp.no_such_module.widgets"


@given(phrase("the dashboard shows {widget:Widget}"))
def dashboard_shows(settings, monkeypatch, widget):
    settings.CRUDKIT_DASHBOARD_WIDGETS = f"{__name__}.dashboard_widgets"
    monkeypatch.setattr(f"{__name__}.dashboard", [*dashboard, widget])


@given(phrase("Metabase is connected"))
def metabase_connected(settings):
    settings.METABASE_SITE_URL = METABASE_SITE
    settings.METABASE_SECRET_KEY = METABASE_SECRET


@when(phrase("{name:Actor} opens the dashboard"))
def open_dashboard(world, name):
    world.remember(name, world.api(name).get("/api/v1/widgets/"))


@when(phrase("someone who is not signed in opens the dashboard"))
def anonymous_dashboard(world):
    world.response = APIClient().get("/api/v1/widgets/")


def _widgets(world) -> list[dict]:
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    return world.response.data


def _widget_titled(world, title) -> dict:
    return next(w for w in _widgets(world) if w["title"] == title)


@then(phrase("the dashboard is empty"))
def dashboard_empty(world):
    assert _widgets(world) == [], _widgets(world)


@then(phrase("the dashboard shows {titles:Labels}"))
def dashboard_titles(world, titles):
    assert [w["title"] for w in _widgets(world)] == titles, _widgets(world)


@then(phrase('the widget "{title:Q}" is a {kind:Words} widget {width:d} columns wide'))
@then(phrase('the widget "{title:Q}" is a {kind:Words} widget {width:d} column wide'))
def widget_kind(world, title, kind, width):
    kinds = {"list": "ListWidget", "chart": "ChartWidget", "metabase": "MetabaseEmbeddedQuestionWidget"}
    shown = _widget_titled(world, title)
    assert (shown["type"], shown["width"]) == (kinds[kind], width), shown


@then(phrase('the widget "{title:Q}" lists up to {limit:d} {model:Model} whose {field:Words} is "{value:Q}"'))
def widget_lists(world, title, limit, model, field, value):
    data = _widget_titled(world, title)["data"]
    assert (data["object"], data["limit"]) == (model.TYPE_ID, limit), data
    assert data["filters"] == [[field_name(field), "=", value]], data


@then(phrase('the widget "{title:Q}" shows the fields {fields:List}'))
def widget_fields(world, title, fields):
    assert _widget_titled(world, title)["data"]["display_fields"] == [field_name(f) for f in fields]


@then(phrase('the widget "{title:Q}" draws a {chart:Words} chart of "{series:Q}"'))
def widget_chart(world, title, chart, series):
    data = _widget_titled(world, title)["data"]
    assert data["type"] == chart, data
    assert [dataset["label"] for dataset in data["chartData"]["datasets"]] == [series], data


@then(phrase('the widget "{title:Q}" draws a bar chart explaining "{error:Q}"'))
def widget_error_chart(world, title, error):
    data = _widget_titled(world, title)["data"]
    assert data["type"] == "bar", data
    assert data["chartData"]["datasets"][0]["label"] == error, data


@then(
    phrase(
        'the widget "{title:Q}" embeds Metabase question {question:d} with a link that expires in {minutes:d} minutes'
    )
)
def widget_metabase(world, title, question, minutes):
    url = urlparse(_widget_titled(world, title)["data"]["url"])
    assert f"{url.scheme}://{url.netloc}" == METABASE_SITE, url
    token = url.path.removeprefix("/embed/question/")
    claims = jwt.decode(token, METABASE_SECRET, algorithms=["HS256"])
    assert claims["resource"] == {"question": question}, claims
    assert abs(claims["exp"] - (time.time() + minutes * 60)) < 5, claims


@then(phrase('the widget "{title:Q}" explains "{message:Q}"'))
def widget_explains(world, title, message):
    assert _widget_titled(world, title)["data"] == {"error": message}
