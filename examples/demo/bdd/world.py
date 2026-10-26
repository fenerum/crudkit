"""The shared state of one journey, and the vocabulary its steps are written in.

Features name records by label ("Drag me"). A record a scenario creates is
really called "<label> <token>", with one token per scenario, so scenarios
never collide in the shared, seeded database, and a search for the token
finds exactly the scenario's own records. `World.text()` turns the text
written in a step into the text on screen. Records the demo is seeded with
("Kindred", "Octavia E. Butler") are used by their real names.
"""

import random
import re
import time
from contextlib import suppress
from dataclasses import dataclass, field

from parse import with_pattern
from playwright.sync_api import APIRequestContext, Page, expect
from pytest_bdd import parsers

# The superuser `manage.py seed` creates.
USERNAME = "admin"
PASSWORD = "admin"
EMAIL = "admin@example.com"

# Record types by the word a feature uses for them.
MODELS = {"author": "AUT", "book": "BOK", "reading": "RDG", "view": "VIW"}

# Well inside simplejwt's default five-minute access token lifetime.
TOKEN_SECONDS = 60


def model_named(words: str) -> str:
    """`books` or `book` -> `BOK`"""
    return MODELS[words.removesuffix("s")]


@with_pattern(r'[^"]*')
def _quoted(text):
    return text


@with_pattern(r"an?")
def _article(text):
    return text


@with_pattern(r"[A-Z][a-z]+|she|he|they")
def _actor(text):
    return text


@with_pattern("(?:" + "|".join(MODELS) + ")s?")
def _model(text):
    return model_named(text)


@with_pattern(r"[a-z][a-z ]*[a-z]")
def _words(text):
    return text


@with_pattern(r'"[^"]*"(?:(?:, | and )"[^"]*")*')
def _quoted_list(text):
    return re.findall(r'"([^"]*)"', text)


def phrase(pattern: str):
    """A step parser with the suite's vocabulary.

    `{x:A}` a or an, `{x:Q}` quoted text (without the quotes), `{x:Actor}` a capitalised first
    name or she/he/they, `{x:Model}` a record type ("books", converted to its
    type code), `{x:Words}` lowercase words, `{x:QList}` `"a", "b" and "c"`
    (converted to a list).
    """
    types = {"A": _article, "Q": _quoted, "Actor": _actor, "Model": _model, "Words": _words, "QList": _quoted_list}
    return parsers.parse(pattern, extra_types=types)


def sign_in(page: Page, username: str, password: str):
    page.goto("/login")
    page.get_by_placeholder("Username").fill(username)
    page.get_by_placeholder("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def goto_with_change_stream(page: Page, path: str):
    """Navigate and wait until the change stream has joined its groups, so a
    change made right after is guaranteed to be pushed to this page."""
    with page.expect_websocket(lambda ws: ws.url.endswith("/ws/changes/")) as socket:
        page.goto(path)
    socket.value.wait_for_event("framereceived", lambda frame: '"ready"' in str(frame))


class Api:
    """The demo's REST API as the seeded admin, for setting the scene (what
    frontend/e2e/helpers.ts does for the TypeScript suite)."""

    def __init__(self, request: APIRequestContext):
        self.request = request
        self._token = None
        self._token_at = 0.0
        self._metadata = {}

    def _headers(self):
        if time.monotonic() - self._token_at > TOKEN_SECONDS:
            response = self.request.post("/api/v1/token/", data={"username": USERNAME, "password": PASSWORD})
            self._token = self._json(response)["access"]
            self._token_at = time.monotonic()
        return {"Authorization": f"Bearer {self._token}"}

    @staticmethod
    def _json(response):
        assert response.ok, f"{response.status} {response.url}: {response.text()}"
        return response.json() if response.status != 204 else None

    @staticmethod
    def _path(ck_id: str) -> str:
        return f"/api/v1/{ck_id[:3]}/{ck_id[3:]}/"

    def get(self, path: str, **params):
        return self._json(self.request.get(path, headers=self._headers(), params=params))

    def create(self, type_id: str, data: dict) -> dict:
        return self._json(self.request.post(f"/api/v1/{type_id}/", headers=self._headers(), data=data))

    def update(self, ck_id: str, data: dict) -> dict:
        return self._json(self.request.patch(self._path(ck_id), headers=self._headers(), data=data))

    def delete(self, ck_id: str):
        return self._json(self.request.delete(self._path(ck_id), headers=self._headers()))

    def metadata(self, type_id: str) -> dict:
        if type_id not in self._metadata:
            self._metadata[type_id] = self.get(f"/api/v1/{type_id}/metadata/")
        return self._metadata[type_id]

    def field(self, type_id: str, words: str) -> dict:
        """The field of `type_id` a feature calls `words`: by its name or its verbose name."""
        for spec in self.metadata(type_id)["fields"].values():
            if words in (spec["name"].replace("_", " "), spec["verbose_name"].lower()):
                return spec
        raise LookupError(f"{type_id} has no field called {words!r}")

    def field_names(self, words: str) -> set[str]:
        """The names of the fields any record type calls `words`."""
        names = set()
        for type_id in MODELS.values():
            with suppress(LookupError):
                names.add(self.field(type_id, words)["name"])
        return names

    def label_field(self, type_id: str) -> str:
        return (self.metadata(type_id)["search_fields"] or ["name"])[0]

    def find(self, label: str) -> str:
        """The id of the record of any type whose label is exactly `label`."""
        for result in self.get("/api/v1/search/", q=label)["results"]:
            if result["label"] == label:
                return result["id"]
        raise LookupError(f'No record is called "{label}"')


@dataclass
class World:
    page: Page
    api: Api
    token: str = field(default_factory=lambda: f"{int(time.time() * 1000)}-{random.randrange(10**6)}")
    # label -> the name the record really has
    names: dict = field(default_factory=dict)
    # label -> CK-ID
    ids: dict = field(default_factory=dict)

    @property
    def main(self):
        return self.page.get_by_role("main")

    @property
    def banner(self):
        return self.page.get_by_role("banner")

    # Names

    def new_name(self, label: str) -> str:
        self.names[label] = f"{label} {self.token}"
        return self.names[label]

    def name_for(self, label: str) -> str:
        """The name to type for `label`: the one it already has, or a new unique one."""
        return self.names.get(label) or self.new_name(label)

    def text(self, text: str) -> str:
        """`text` as it reads on screen: labels of this scenario's records become their real names.

        A label inside longer text is replaced too, so "Lunch renamed" reads
        "Lunch <token> renamed" when "Lunch" is a record of this scenario.
        """
        if text in self.names:
            return self.names[text]
        for label in sorted(self.names, key=len, reverse=True):
            text = re.sub(rf"\b{re.escape(label)}\b", self.names[label], text)
        return text

    # Records

    def create(self, type_id: str, label: str, values: dict | None = None) -> str:
        """Create a `type_id` called `label` through the API, as setup. `values` are as a feature writes them."""
        data = {self.api.label_field(type_id): self.new_name(label)}
        for words, text in (values or {}).items():
            spec = self.api.field(type_id, words)
            data[spec["name"]] = self.api_value(spec, text)
        self.ids[label] = self.api.create(type_id, data)["id"]
        return self.ids[label]

    def id(self, label: str) -> str:
        """The CK-ID of this scenario's record `label`, or of the seeded record called that."""
        if label not in self.ids:
            self.ids[label] = self.api.find(label)
        return self.ids[label]

    def api_value(self, spec: dict, text: str):
        """`text` written in a step, as the API expects it for the field `spec`."""
        if spec["related_model_type"]:
            return self.id(text)
        for value, shown in spec["choices"] or []:
            if shown.lower() == text.lower():
                return value
        return self.text(text)

    # Pages

    def open(self, label: str, action: str = ""):
        self.page.goto(f"/{self.id(label)}" + (f"/{action}" if action else ""))

    def expect_on_page_of(self, label: str):
        expect(self.page).to_have_url(re.compile(rf"/{self.id(label)}(\?.*)?$"))

    def visible_text(self, text: str, scope=None):
        return (scope or self.main).get_by_text(self.text(text)).filter(visible=True)
