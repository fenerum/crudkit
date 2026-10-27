"""OAuth for MCP clients: registering, the consent page, tokens and the discovery documents.

Clients are named ("Claude") and registered with one secure redirect address.
A client holding tokens keeps every token pair it was given, newest last.

Phrases this area adds:

- `Given an MCP client "Claude" is registered`, `Given the MCP client "Claude" has been deactivated`
- `Given the server runs in production mode` (redirect addresses must be secure)
- `When an MCP client registers as "My App" with a secure redirect address` (also `with an unencrypted redirect
  address on "localhost"`, `with no redirect addresses`, `with 11 redirect addresses`, `with a redirect address that
  is not text`), `When an MCP client registers without a name`, `Given 30 MCP clients registered within the hour`
- `Given "Claude" asks for "read propose" access`, `Given "Claude" passes the state "a=1&b=2"`
- `When Alice opens the consent page for "Claude"` (also `with response type "token"` and the like), `When Alice
  allows "Claude" with "propose" access`, `When Alice denies "Claude" access`
- `Given "Claude" holds an authorization code from Alice`, `When "Claude" exchanges the authorization code`
- `Given "Claude" holds tokens from Alice for "read propose"`, `When "Claude" refreshes its tokens`
- `When an MCP client fetches the authorization server document` / `the protected resource document`
- `Then the token request fails with "invalid_grant"` (the OAuth error code the client sees)
"""

import base64
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.test import Client as HttpClient
from django.urls import reverse
from django.utils import timezone
from pytest_bdd import given, then, when

from crudkit_mcp.models import AuthorizationCode, OAuthClient, RefreshToken
from tests.bdd.steps.mcp import MCP_PATH, REDIRECT_URI, post_message
from tests.bdd.world import phrase, split_list

REGISTER_PATH = "/api/v1/oauth/register/"
AUTHORIZE_PATH = "/api/v1/oauth/authorize/"
TOKEN_PATH = "/api/v1/oauth/token/"
CODE_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CODE_CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(CODE_VERIFIER.encode()).digest()).rstrip(b"=").decode()
THIS_SERVER = "http://testserver"
CONSENT_CHOICES = ("Read only", "Propose changes", "Write directly")
# What the consent page's query parameters are called, by what a step calls them.
AUTHORIZE_PARAMETERS = {
    "response type": "response_type",
    "challenge method": "code_challenge_method",
    "code challenge": "code_challenge",
    "scope": "scope",
    "client id": "client_id",
}
# Discovery document fields, by what a step calls them.
DOCUMENT_FIELDS = {
    "response types": "response_types_supported",
    "grant types": "grant_types_supported",
    "code challenge methods": "code_challenge_methods_supported",
    "client authentication": "token_endpoint_auth_methods_supported",
    "scopes": "scopes_supported",
    "bearer methods": "bearer_methods_supported",
}


def _clients(world) -> dict:
    if not hasattr(world, "oauth_clients"):
        world.oauth_clients = {}
    return world.oauth_clients


def _client(world, name) -> OAuthClient:
    return OAuthClient.objects.get(pk=_clients(world)[name].pk)


@given(phrase('an MCP client "{name:Q}" is registered'))
def registered(world, name):
    _clients(world)[name] = OAuthClient.objects.create(client_name=name, redirect_uris=[REDIRECT_URI])


@given(phrase('the MCP client "{name:Q}" has been deactivated'))
def deactivated(world, name):
    OAuthClient.objects.filter(client_name=name).update(is_active=False)


@given("the server runs in production mode")
def production_mode(settings):
    settings.DEBUG = False


@given("the server runs in debug mode")
def debug_mode(settings):
    settings.DEBUG = True


# Registering


def _register(world, payload):
    world.response = HttpClient().post(REGISTER_PATH, data=payload, content_type="application/json")


@when(phrase('an MCP client registers as "{name:Q}" with a secure redirect address'))
def register_secure(world, name):
    _register(world, {"client_name": name, "redirect_uris": ["https://app.example.com/callback"]})


@when(phrase('an MCP client registers as "{name:Q}" with an unencrypted redirect address on "{host:Q}"'))
def register_unencrypted(world, name, host):
    _register(world, {"client_name": name, "redirect_uris": [f"http://{host}:3000/callback"]})


@when(phrase('an MCP client registers as "{name:Q}" with no redirect addresses'))
def register_without_redirects(world, name):
    _register(world, {"client_name": name, "redirect_uris": []})


@when(phrase('an MCP client registers as "{name:Q}" with {count:d} redirect addresses'))
def register_many_redirects(world, name, count):
    _register(world, {"client_name": name, "redirect_uris": [f"https://app.example.com/{i}" for i in range(count)]})


@when(phrase('an MCP client registers as "{name:Q}" with a redirect address that is not text'))
def register_non_text_redirect(world, name):
    _register(world, {"client_name": name, "redirect_uris": [42]})


@when("an MCP client registers without a name")
def register_without_name(world):
    _register(world, {"redirect_uris": ["https://app.example.com/callback"]})


@given(phrase("{count:d} MCP clients registered within the hour"))
def many_registered(world, count):
    for i in range(count):
        register_secure(world, f"Client {i}")
        assert world.response.status_code == 201, world.response.content


@then(phrase('the client is registered as "{name:Q}"'))
def is_registered(world, name):
    assert world.response.status_code == 201, world.response.content
    data = world.response.json()
    client = OAuthClient.objects.get(client_id=data["client_id"])
    assert (data["client_name"], client.client_name, client.is_active) == (name, name, True)
    assert data["redirect_uris"] == client.redirect_uris
    assert data["client_id_issued_at"] > 0


@then(phrase('the registration is refused with "{message:Q}"'))
def registration_refused(world, message):
    assert world.response.status_code == 400, world.response.content
    data = world.response.json()
    assert data["error"] == "invalid_client_metadata", data
    assert message in data["error_description"], data


@then("registering is throttled")
def registration_throttled(world):
    assert world.response.status_code == 429, world.response.content


# The consent page


def _authorize_parameters(world, name) -> dict:
    parameters = {
        "client_id": _clients(world)[name].client_id,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": CODE_CHALLENGE,
        "state": getattr(world, "oauth_state", "xyz"),
    }
    if getattr(world, "oauth_scope", None) is not None:
        parameters["scope"] = world.oauth_scope
    return parameters


def _browser(world, name):
    browser = HttpClient()
    browser.force_login(world.user(name))
    return browser


@given(phrase('"{client:Q}" asks for "{scope:Q}" access'))
def asks_for_scope(world, client, scope):
    world.oauth_scope = scope


@given(phrase('"{client:Q}" passes the state "{state:Q}"'))
def passes_state(world, client, state):
    world.oauth_state = state


@when(phrase('{name:Actor} opens the consent page for "{client:Q}"'))
def open_consent(world, name, client):
    world.response = _browser(world, name).get(AUTHORIZE_PATH, _authorize_parameters(world, client))


@when(phrase('{name:Actor} opens the consent page for "{client:Q}" with {parameter:Words} "{value:Q}"'))
def open_consent_with(world, name, client, parameter, value):
    parameters = _authorize_parameters(world, client) | {AUTHORIZE_PARAMETERS[parameter]: value}
    world.response = _browser(world, name).get(AUTHORIZE_PATH, parameters)


@when(phrase('{name:Actor} opens the consent page for "{client:Q}" with a redirect address it did not register'))
def open_consent_bad_redirect(world, name, client):
    parameters = _authorize_parameters(world, client) | {"redirect_uri": "https://elsewhere.example.com/callback"}
    world.response = _browser(world, name).get(AUTHORIZE_PATH, parameters)


@when(phrase('someone who is not signed in opens the consent page for "{client:Q}"'))
def open_consent_anonymously(world, client):
    world.response = HttpClient().get(AUTHORIZE_PATH, _authorize_parameters(world, client))


def _decide(world, name, client, **decision):
    parameters = _authorize_parameters(world, client) | decision
    world.response = _browser(world, name).post(AUTHORIZE_PATH, parameters)


@when(phrase('{name:Actor} allows "{client:Q}" with "{access:Q}" access'))
def allow(world, name, client, access):
    _decide(world, name, client, action="allow", access=access)


@when(phrase('{name:Actor} allows "{client:Q}" without picking an access level'))
def allow_without_choice(world, name, client):
    _decide(world, name, client, action="allow")


@when(phrase('{name:Actor} denies "{client:Q}" access'))
def deny(world, name, client):
    _decide(world, name, client, action="deny")


@then(phrase('{name:Actor} is asked whether "{client:Q}" may access {whose:Their} data'))
def asked_for_consent(world, name, client, whose):
    assert world.response.status_code == 200, world.response.content
    page = world.response.content.decode()
    assert f"Authorize {client}" in page
    assert world.user(name).get_username() in page


@then("they are sent to sign in first")
def sent_to_sign_in(world):
    assert world.response.status_code == 302, world.response.status_code
    assert "login" in world.response["Location"], world.response["Location"]


def _offered_choices(world) -> list[str]:
    page = world.response.content.decode()
    return [choice for choice in CONSENT_CHOICES if choice in page]


@then(phrase("the consent page offers {choices:Labels}"))
def consent_offers(world, choices):
    assert _offered_choices(world) == choices, _offered_choices(world)


def _redirect_query(world) -> dict:
    assert world.response.status_code == 302, world.response.content
    location = urlparse(world.response["Location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT_URI, location
    return {key: values[0] for key, values in parse_qs(location.query).items()}


@then(phrase('"{client:Q}" is sent back with an authorization code'))
def sent_back_with_code(world, client):
    query = _redirect_query(world)
    code = AuthorizationCode.objects.get(code=query["code"])
    assert code.client == _client(world, client)
    assert query["state"] == getattr(world, "oauth_state", "xyz")


@then(phrase('"{client:Q}" is sent back with the error "{error:Q}"'))
def sent_back_with_error(world, client, error):
    query = _redirect_query(world)
    assert query["error"] == error, query
    assert "code" not in query
    assert not AuthorizationCode.objects.exists()


@then(phrase('"{client:Q}" gets back the state "{state:Q}"'))
def gets_back_state(world, client, state):
    assert _redirect_query(world)["state"] == state


@then(phrase('the authorization code grants "{scopes:Q}"'))
def code_grants(world, scopes):
    assert AuthorizationCode.objects.get().scopes == scopes


@then(phrase("the authorization code is valid for {minutes:d} minutes"))
def code_lifetime(world, minutes):
    code = AuthorizationCode.objects.get()
    assert abs(code.expires_at - code.created_at - timedelta(minutes=minutes)) < timedelta(seconds=5)


@then("no authorization code is issued")
def no_code(world):
    assert not AuthorizationCode.objects.exists()


# Tokens


def _issue_code(world, client, name, scopes="read"):
    world.oauth_code = AuthorizationCode.objects.create(
        client=_clients(world)[client],
        user=world.user(name),
        redirect_uri=REDIRECT_URI,
        code_challenge=CODE_CHALLENGE,
        scopes=scopes,
        expires_at=timezone.now() + timedelta(minutes=10),
    )


def _token_request(world, client, **parameters):
    world.response = HttpClient().post(TOKEN_PATH, parameters)
    if world.response.status_code == 200:
        _issued(world, client).append(world.response.json())
    return world.response


def _issued(world, client) -> list:
    if not hasattr(world, "oauth_tokens"):
        world.oauth_tokens = {}
    return world.oauth_tokens.setdefault(client, [])


def _exchange(world, client, **overrides):
    parameters = {
        "grant_type": "authorization_code",
        "code": world.oauth_code.code,
        "redirect_uri": REDIRECT_URI,
        "client_id": _clients(world)[client].client_id,
        "code_verifier": CODE_VERIFIER,
    }
    return _token_request(world, client, **(parameters | overrides))


@given(phrase('"{client:Q}" holds an authorization code from {name:Actor}'))
def holds_code(world, client, name):
    _issue_code(world, client, name)


@given(phrase('"{client:Q}" holds an authorization code from {name:Actor} for "{scopes:Q}"'))
def holds_code_for(world, client, name, scopes):
    _issue_code(world, client, name, scopes)


@given("the authorization code has expired")
def code_expired(world):
    AuthorizationCode.objects.filter(pk=world.oauth_code.pk).update(expires_at=timezone.now() - timedelta(minutes=1))


@given(phrase('"{client:Q}" exchanged the authorization code'))
@when(phrase('"{client:Q}" exchanges the authorization code'))
@when(phrase('"{client:Q}" exchanges the authorization code again'))
def exchange(world, client):
    _exchange(world, client)


@when(phrase('"{client:Q}" exchanges the authorization code with the wrong verifier'))
def exchange_wrong_verifier(world, client):
    _exchange(world, client, code_verifier="not-the-verifier")


@when(phrase('"{client:Q}" exchanges the authorization code for a different redirect address'))
def exchange_other_redirect(world, client):
    _exchange(world, client, redirect_uri="https://elsewhere.example.com/callback")


@when(phrase('"{client:Q}" exchanges the authorization code without the verifier'))
def exchange_without_verifier(world, client):
    _exchange(world, client, code_verifier="")


@when(phrase('"{client:Q}" asks for a token with the grant type "{grant:Q}"'))
def other_grant(world, client, grant):
    _token_request(world, client, grant_type=grant, client_id=_clients(world)[client].client_id)


@given(phrase('"{client:Q}" holds tokens from {name:Actor} for "{scopes:Q}"'))
def holds_tokens(world, client, name, scopes):
    _issue_code(world, client, name, scopes)
    assert _exchange(world, client).status_code == 200, world.response.content


def _refresh(world, client, refresh_token, presented_by=None, **extra):
    parameters = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": _clients(world)[presented_by or client].client_id,
    }
    return _token_request(world, client, **(parameters | extra))


def _latest(world, client) -> dict:
    return _issued(world, client)[-1]


@given(phrase('"{client:Q}" refreshed its tokens'))
@when(phrase('"{client:Q}" refreshes its tokens'))
def refresh(world, client):
    _refresh(world, client, _latest(world, client)["refresh_token"])


@when(phrase('"{client:Q}" refreshes its tokens narrowed to "{scopes:Q}"'))
def refresh_narrowed(world, client, scopes):
    _refresh(world, client, _latest(world, client)["refresh_token"], scope=scopes)


@when(phrase('"{client:Q}" refreshes with its first refresh token again'))
def refresh_with_first(world, client):
    _refresh(world, client, _issued(world, client)[0]["refresh_token"])


@when(phrase('"{other:Q}" refreshes the tokens of "{client:Q}"'))
def refresh_someone_elses(world, other, client):
    _refresh(world, client, _latest(world, client)["refresh_token"], presented_by=other)


@when(phrase('"{client:Q}" refreshes with a made-up refresh token'))
def refresh_unknown(world, client):
    _refresh(world, client, "made-up")


@when(phrase('"{client:Q}" refreshes without a refresh token'))
def refresh_without_token(world, client):
    _refresh(world, client, "")


@given(phrase('the refresh token of "{client:Q}" has expired'))
def refresh_expired(world, client):
    token = _latest(world, client)["refresh_token"]
    RefreshToken.objects.filter(token=token).update(expires_at=timezone.now() - timedelta(minutes=1))


@then(phrase('"{client:Q}" receives an access token for {hours:d} hour and a refresh token for {days:d} days'))
def receives_tokens(world, client, hours, days):
    assert world.response.status_code == 200, world.response.content
    data = world.response.json()
    assert data["token_type"] == "Bearer"
    assert (data["expires_in"], data["refresh_token_expires_in"]) == (hours * 3600, days * 86400)
    assert data["access_token"] and data["refresh_token"]


@then(phrase('"{client:Q}" receives tokens for "{scopes:Q}"'))
def receives_scopes(world, client, scopes):
    assert world.response.status_code == 200, world.response.content
    assert world.response.json()["scope"] == scopes


@then(phrase('"{client:Q}" receives a new pair of tokens'))
def receives_new_pair(world, client):
    assert world.response.status_code == 200, world.response.content
    before, after = _issued(world, client)[-2:]
    assert before["access_token"] != after["access_token"]
    assert before["refresh_token"] != after["refresh_token"]


@then(phrase('the earlier refresh token of "{client:Q}" no longer works'))
def earlier_revoked(world, client):
    assert RefreshToken.objects.get(token=_issued(world, client)[-2]["refresh_token"]).is_revoked


@then(phrase('none of the refresh tokens of "{client:Q}" work any more'))
def family_revoked(world, client):
    tokens = [issued["refresh_token"] for issued in _issued(world, client)]
    assert all(RefreshToken.objects.get(token=token).is_revoked for token in tokens)


@then(phrase('the access token lets "{client:Q}" act for {name:Actor}'))
def token_works(world, client, name):
    message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    post_message(world, message, token=_latest(world, client)["access_token"])
    assert world.response.status_code == 200, world.response.content


@then(phrase('the token request fails with "{error:Q}"'))
def token_request_fails(world, error):
    assert world.response.status_code == 400, world.response.content
    assert world.response.json()["error"] == error, world.response.json()


# Discovery


@when("an MCP client fetches the authorization server document")
def fetch_authorization_server(world):
    world.response = HttpClient().get("/.well-known/oauth-authorization-server")


@when("an MCP client fetches the authorization server document for the MCP endpoint")
def fetch_authorization_server_suffixed(world):
    world.response = HttpClient().get("/.well-known/oauth-authorization-server" + MCP_PATH.rstrip("/"))


@when("an MCP client fetches the protected resource document")
def fetch_protected_resource(world):
    world.response = HttpClient().get("/.well-known/oauth-protected-resource")


@when("an MCP client fetches the protected resource document for the MCP endpoint")
def fetch_protected_resource_suffixed(world):
    world.response = HttpClient().get("/.well-known/oauth-protected-resource" + MCP_PATH.rstrip("/"))


@given(phrase('the server\'s public address is "{address:Q}"'))
def public_address(settings, address):
    settings.CRUDKIT_MCP_BASE_URL = f"https://{address}/"


def _document(world) -> dict:
    assert world.response.status_code == 200, world.response.content
    return world.response.json()


@then("the document lists:")
def document_lists(world, datatable):
    for name, values in datatable:
        assert _document(world)[DOCUMENT_FIELDS[name]] == split_list(values), (name, _document(world))


def _assert_endpoints(world, base):
    document = _document(world)
    assert document["issuer"] == base
    assert document["authorization_endpoint"] == base + reverse("crudkit_mcp_oauth_authorize")
    assert document["token_endpoint"] == base + reverse("crudkit_mcp_oauth_token")
    assert document["registration_endpoint"] == base + reverse("crudkit_mcp_oauth_register")


@then("the document sends clients to this server to sign in, get tokens and register")
def document_endpoints(world):
    _assert_endpoints(world, THIS_SERVER)


@then(phrase('the document sends clients to "{address:Q}" to sign in, get tokens and register'))
def document_endpoints_at(world, address):
    _assert_endpoints(world, f"https://{address}")


@then("the document names the MCP endpoint as the resource, guarded by this server")
def document_resource(world):
    document = _document(world)
    assert document["resource"] == THIS_SERVER + reverse("crudkit_mcp")
    assert document["authorization_servers"] == [THIS_SERVER]
