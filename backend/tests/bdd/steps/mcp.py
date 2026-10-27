"""MCP clients: connecting with a token, calling tools, and what they are told.

Every call goes through the MCP endpoint with a real OAuth access token, so
signing in, scopes, the write limit and attribution behave as for a real
client. "An MCP client acting for Alice" uses the client Alice connected, or a
read-only one called "Claude" when she connected none.

Phrases this area adds:

- `Given Alice connected an MCP client with read access` (or propose or write access, or `without any access`)
- `Given Alice connected the MCP client "Research Bot" with write access`, `Given Alice's MCP token has expired`
- Server set-up: `Given the server lets MCP clients write directly`, `Given MCP clients may make 2 writes per
  minute`, `Given the MCP write limit is "10/fortnight"`, `Given there is no MCP write limit`, `Given the server's
  cache is local to each process` / `... stores nothing`, `Given the assistant app is not installed`, `Given the MCP
  server is called "acme-crm"`, `Given customers are hidden from MCP clients`, `Given MCP clients may only use
  customers`, `Given the project adds the MCP tool "crm_status"` (also `replaces the MCP tool "list_records"` and
  `adds the MCP write tool "sync_now"`)
- `Given running "Mark churned" needs approval` (approval fields: `changes to the status of customers need a
  person's approval`, in steps/agents.py)
- Records: `Given 25 more customers`, `Given "Beta" was created on "2026-01-15"`, `Given 25 notes were left on
  "Acme"`, `Given the view "Churned" was deleted` (saved views themselves come from steps/views.py)
- Calls, all starting `When an MCP client acting for Alice ...`: `starts a session`, `asks which tools it may use`, `describes
  customers`, `searches for "acme"`, `lists customers with status "churned"`, `counts customers, grouped by status`, `opens
  "Acme"`, `creates a customer "Globex"`, `changes the status of "Acme" to "churned"`, `runs "Mark churned" on
  "Acme"`, `adds the note "Renewal due" to "Acme"`, `undoes that change`, and `calls "list_records" with:` (a
  `| argument | value |` table; rows that are not arguments are filters, `a or b` is a list)
- Outcomes: `Then the client sees "Acme" and "Beta"`, `Then the client is refused with "Permission denied"`,
  `Then the client is told "No results found"`, `Then the client gets the groups:` (a table with a header row),
  `Then the change waits for Alice's approval as "Run Mark churned"`, `Then nothing waits for approval`

A proposal the client files becomes "the proposal" of the approvals steps, so `When Alice confirms the proposal` works.
`mcp_phrase` is `phrase` plus `{x:Labels}` (a list of quoted names).
"""

import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.contenttypes.models import ContentType
from django.core import checks
from django.core.exceptions import FieldDoesNotExist
from django.test import Client as HttpClient
from django.utils import timezone, translation
from pytest_bdd import given, then, when

from crudkit.models import ChangeLog, FeedItem, View, parse_ck_id
from crudkit.utils import get_model_types, get_system_user
from crudkit_api import records
from crudkit_api.services import action_for_label
from crudkit_assistant.models import Agent, AssistantProposal
from crudkit_mcp import conf
from crudkit_mcp.models import AccessToken, OAuthClient
from crudkit_mcp.server import PROTOCOL_VERSION
from crudkit_mcp.tools import Tool
from tests.bdd.world import label_field, missing_id, model_named, phrase, split_list

MCP_PATH = "/api/v1/mcp/"
REDIRECT_URI = "https://claude.example.com/callback"
SCOPES = {"read": "read", "propose": "read propose", "write": "read write", "propose and write": "read propose write"}

# Tools a project could add with CRUDKIT_MCP_EXTRA_TOOLS, by name.
CRM_STATUS = Tool("crm_status", "How the CRM is doing", lambda user, arguments: "all good")
CUSTOM_LIST = Tool("list_records", "The project's own listing", lambda user, arguments: "the project's own listing")
SYNC_NOW = Tool("sync_now", "Sync with the ERP", lambda user, arguments: "synced", scope="write")
EXTRA_TOOLS = {
    "crm_status": f"{__name__}.CRM_STATUS",
    "list_records": f"{__name__}.CUSTOM_LIST",
    "sync_now": f"{__name__}.SYNC_NOW",
}

# Table rows that are tool arguments; every other row is a filter.
TEXT_ARGUMENTS = ("query", "order_by")
LIST_ARGUMENTS = ("fields", "group_by", "metrics")
NUMBER_ARGUMENTS = ("limit", "offset")
RECORD_ARGUMENTS = ("view", "id")
READ_TOOLS = ("describe_types", "search", "list_records", "aggregate_records", "get_record")


def _field(words: str) -> str:
    return words.replace(" ", "_")


# Connecting


def _tokens(world) -> dict:
    if not hasattr(world, "mcp_tokens"):
        world.mcp_tokens = {}
    return world.mcp_tokens


def connect(world, name, scopes, client_name="Claude"):
    client = OAuthClient.objects.create(client_name=client_name, redirect_uris=[REDIRECT_URI])
    token = AccessToken.objects.create(
        client=client, user=world.user(name), scopes=scopes, expires_at=timezone.now() + timedelta(hours=1)
    )
    _tokens(world)[name] = token
    return token


def _token(world, name):
    return _tokens(world).get(name) or connect(world, name, SCOPES["read"])


@given(phrase("{name:Actor} connected an MCP client with {access:Words} access"))
def connected(world, name, access):
    connect(world, name, SCOPES[access])


@given(phrase('{name:Actor} connected the MCP client "{client:Q}" with {access:Words} access'))
def connected_named(world, name, client, access):
    connect(world, name, SCOPES[access], client_name=client)


@given(phrase("{name:Actor} connected an MCP client without any access"))
def connected_without_scopes(world, name):
    connect(world, name, "")


@given(phrase("{name:Actor}'s MCP token has expired"))
def token_expired(world, name):
    AccessToken.objects.filter(pk=_token(world, name).pk).update(expires_at=timezone.now() - timedelta(minutes=1))


# Talking to the server


def post_message(world, message, token=None, path=MCP_PATH):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    world.response = HttpClient().post(path, data=json.dumps(message), content_type="application/json", **headers)
    world.mcp_reply = world.response.json()
    return world.mcp_reply


def _send(world, name, method, params=None, path=MCP_PATH):
    message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return post_message(world, message, _token(world, name).token, path)


def call(world, name, tool, arguments=None):
    """Call `tool` as `name`'s MCP client and keep what it returned, or its error, for the Then steps."""
    result = _send(world, name, "tools/call", {"name": tool, "arguments": arguments or {}})["result"]
    text = result["content"][0]["text"]
    world.mcp_error = text if result["isError"] else None
    world.mcp_result = None if result["isError"] else _parsed(text)
    if isinstance(world.mcp_result, dict):
        if world.mcp_result.get("change_set"):
            world.change_set = world.change_sets[name] = world.mcp_result["change_set"]
        if world.mcp_result.get("status") == "pending_approval":
            world.proposal = AssistantProposal.objects.get(pk=world.mcp_result["proposal"])
    return world.mcp_result


def _parsed(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _result(world):
    assert world.mcp_error is None, world.mcp_error
    return world.mcp_result


def _type_id(text):
    try:
        return model_named(text).TYPE_ID
    except LookupError:
        return text


def _record_id(world, text):
    return world.ck_id(text) if text in world.records else text


def _model_of(world, rows):
    """The record type a table of tool arguments is about, by its `type` or its `view` row."""
    for key, value in rows:
        if key == "type":
            return get_model_types().get(_type_id(value))
        if key == "view" and isinstance(world.records.get(value), View):
            return get_model_types().get(world.records[value].model)
    return None


def _filter_value(world, model, key, text):
    """A `filters` value as a client sends it: relations by record ID, `a or b` as a list."""
    if key.endswith("_isnull"):
        return text == "true"
    values = [part.strip() for part in text.split(" or ")]
    base = re.sub(r"_(from|to)$", "", key)
    if model and base in {f.name for f in model._meta.concrete_fields} and model._meta.get_field(base).is_relation:
        values = [_record_id(world, value) for value in values]
    return values if len(values) > 1 else values[0]


def _arguments(world, rows) -> dict:
    """Tool arguments from `| argument | value |` rows; rows that are not tool arguments are filters."""
    rows = [(_field(key), value) for key, value in rows]
    arguments = {}
    for key, value in rows:
        if key == "type":
            arguments[key] = _type_id(value)
        elif key in RECORD_ARGUMENTS:
            arguments[key] = _record_id(world, value)
        elif key in LIST_ARGUMENTS:
            arguments[key] = split_list(value)
        elif key in NUMBER_ARGUMENTS:
            arguments[key] = int(value)
        elif key in TEXT_ARGUMENTS:
            arguments[key] = value
    model = _model_of(world, rows)
    filters = {key: _filter_value(world, model, key, value) for key, value in rows if key not in arguments}
    if filters:
        arguments["filters"] = filters
    return arguments


@when(phrase('an MCP client acting for {name:Actor} calls "{tool:Q}"'))
def call_without_arguments(world, name, tool):
    call(world, name, tool)


@when(phrase('an MCP client acting for {name:Actor} calls "{tool:Q}" with:'))
def call_with_arguments(world, name, tool, datatable):
    call(world, name, tool, _arguments(world, datatable))


# The protocol


@when(phrase("an MCP client acting for {name:Actor} starts a session"))
def initialize(world, name):
    _send(world, name, "initialize")


@when(phrase('an MCP client acting for {name:Actor} starts a session asking for protocol version "{version:Q}"'))
def initialize_with_version(world, name, version):
    _send(world, name, "initialize", {"protocolVersion": version})


@when(phrase("an MCP client acting for {name:Actor} starts a session at the address without a trailing slash"))
def initialize_without_slash(world, name):
    _send(world, name, "initialize", path=MCP_PATH.rstrip("/"))


@when("an MCP client starts a session without signing in")
def initialize_anonymously(world):
    post_message(world, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})


@when("an MCP client starts a session with a made-up token")
def initialize_with_unknown_token(world):
    post_message(world, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, token="made-up")


@when(phrase("an MCP client acting for {name:Actor} pings the server"))
def ping(world, name):
    _send(world, name, "ping")


@when(phrase('an MCP client acting for {name:Actor} sends the notification "{method:Q}"'))
def notify(world, name, method):
    post_message(world, {"jsonrpc": "2.0", "method": method}, _token(world, name).token)


@when(phrase('an MCP client acting for {name:Actor} calls the method "{method:Q}"'))
def call_method(world, name, method):
    _send(world, name, method)


@when(phrase("an MCP client acting for {name:Actor} sends a batch of requests"))
def send_batch(world, name):
    post_message(world, [{"jsonrpc": "2.0", "id": 1, "method": "ping"}], _token(world, name).token)


@when(phrase("an MCP client acting for {name:Actor} sends a tool call with malformed parameters"))
def malformed_tool_call(world, name):
    post_message(
        world, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": ["search"]}, _token(world, name).token
    )


@when("an MCP client opens the event stream")
def open_event_stream(world):
    world.response = HttpClient().get(MCP_PATH)


@then(phrase('the server agrees on protocol version "{version:Q}"'))
def agreed_version(world, version):
    assert world.mcp_reply["result"]["protocolVersion"] == version, world.mcp_reply


@then(phrase('the server introduces itself as "{server:Q}"'))
def server_name(world, server):
    assert world.mcp_reply["result"]["serverInfo"]["name"] == server, world.mcp_reply


@then("the reply says which protocol version the server speaks")
def protocol_header(world):
    assert world.response["Mcp-Protocol-Version"] == PROTOCOL_VERSION


@then("the server answers the ping")
def answered_ping(world):
    assert world.mcp_reply == {"jsonrpc": "2.0", "id": 1, "result": {}}, world.mcp_reply


@then("the server accepts it without a reply")
def accepted_without_reply(world):
    assert world.response.status_code == 202, world.response.content
    assert world.mcp_reply == {}


def _rpc_error(world, code):
    error = world.mcp_reply.get("error")
    assert error and error["code"] == code, world.mcp_reply
    return error


@then(phrase('the client is told the method "{method:Q}" does not exist'))
def method_not_found(world, method):
    assert _rpc_error(world, -32601)["message"] == f"Method not found: {method}"


@then("the client is told the request is invalid")
def invalid_request(world):
    _rpc_error(world, -32600)
    assert world.mcp_reply["id"] is None


@then("the client is told the server failed to handle it")
def internal_error(world):
    _rpc_error(world, -32603)


@then("the client receives an empty event stream")
def empty_event_stream(world):
    assert world.response.status_code == 200
    assert world.response["Content-Type"].startswith("text/event-stream")
    assert world.response["Cache-Control"] == "no-cache"
    assert world.response["Mcp-Protocol-Version"] == PROTOCOL_VERSION
    assert b"".join(world.response.streaming_content) == b""


@then("the client is told where to find out how to sign in")
def told_where_to_sign_in(world):
    expected = 'Bearer resource_metadata="http://testserver/.well-known/oauth-protected-resource"'
    assert world.response["WWW-Authenticate"] == expected, world.response.headers


# The tool list


@when(phrase("an MCP client acting for {name:Actor} asks which tools it may use"))
def list_tools(world, name):
    world.mcp_tools = _send(world, name, "tools/list")["result"]["tools"]


def _tool_names(world):
    return [tool["name"] for tool in world.mcp_tools]


@then(phrase("the client is offered the tools {tools:Labels}"))
def offered_tools(world, tools):
    assert _tool_names(world) == tools, _tool_names(world)


@then(phrase('the client is offered the tool "{tool:Q}"'))
def offered_tool(world, tool):
    assert tool in _tool_names(world), _tool_names(world)


@then(phrase('the client is not offered the tool "{tool:Q}"'))
def not_offered_tool(world, tool):
    assert tool not in _tool_names(world), _tool_names(world)


@then("every tool is marked as read-only")
def all_read_only(world):
    assert all(tool["annotations"]["readOnlyHint"] for tool in world.mcp_tools), world.mcp_tools


@then("every write tool is marked as changing data")
def write_tools_marked(world):
    writes = [tool for tool in world.mcp_tools if tool["name"] not in READ_TOOLS]
    assert writes and not any(tool["annotations"]["readOnlyHint"] for tool in writes)


@then(phrase("the tools accept the record types {names:Labels}"))
def type_choices(world, names):
    for tool in world.mcp_tools:
        if "type" in tool["inputSchema"]["properties"]:
            enum = tool["inputSchema"]["properties"]["type"]["enum"]
            assert sorted(enum) == sorted(model_named(n).TYPE_ID for n in names), (tool["name"], enum)


# How the server is set up


@given("the server lets MCP clients write directly")
def writes_enabled(settings):
    settings.CRUDKIT_MCP_WRITE_ENABLED = True


@given(phrase("MCP clients may make {count:d} writes per minute"))
@given(phrase("MCP clients may make {count:d} write per minute"))
def write_rate(settings, count):
    settings.CRUDKIT_MCP_WRITE_RATE = f"{count}/min"


@given(phrase('the MCP write limit is "{rate:Q}"'))
def write_rate_text(settings, rate):
    settings.CRUDKIT_MCP_WRITE_RATE = rate


@given("there is no MCP write limit")
def no_write_rate(settings):
    settings.CRUDKIT_MCP_WRITE_RATE = None


@given("the server's cache is local to each process")
def local_cache(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@given("the server's cache stores nothing")
def dummy_cache(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}


@given("the assistant app is not installed")
def assistant_not_installed(monkeypatch):
    installed = conf.apps.is_installed
    monkeypatch.setattr(conf.apps, "is_installed", lambda app: app != "crudkit_assistant" and installed(app))


@given(phrase('the MCP server is called "{server:Q}"'))
def server_called(settings, server):
    settings.CRUDKIT_MCP_SERVER_NAME = server


@given(phrase("{model:Model} are hidden from MCP clients"))
def hidden_from_mcp(monkeypatch, model):
    monkeypatch.setattr(model.CrudKitSettings, "mcp_exclude", True, raising=False)


@given(phrase("MCP clients may only use {model:Model}"))
def mcp_allowlist(settings, model):
    settings.CRUDKIT_MCP_MODELS = [model.TYPE_ID]


@given(phrase('the project adds the MCP tool "{tool:Q}"'))
@given(phrase('the project replaces the MCP tool "{tool:Q}"'))
@given(phrase('the project adds the MCP write tool "{tool:Q}"'))
def extra_tool(settings, tool):
    settings.CRUDKIT_MCP_EXTRA_TOOLS = [*getattr(settings, "CRUDKIT_MCP_EXTRA_TOOLS", []), EXTRA_TOOLS[tool]]


@given(phrase('running "{action:Q}" needs approval'))
def approval_action(monkeypatch, action):
    for model in get_model_types().values():
        name = action_for_label(model, action)
        if name:
            monkeypatch.setattr(getattr(model, name), "requires_approval", True)
            return
    raise LookupError(f'No record type has an action "{action}"')


# Records


@given(phrase("{count:d} more {model:Model}"))
def more_records(world, count, model):
    by = get_system_user()
    model.objects.bulk_create(
        [model(created_by=by, updated_by=by, **{label_field(model): f"Extra {i}"}) for i in range(count)]
    )


@given(phrase('"{label:Q}" was created on "{day:Q}"'))
def created_on(world, label, day):
    instance = world.record(label)
    at = datetime.fromisoformat(day).replace(hour=12, tzinfo=UTC)
    type(instance).objects.filter(pk=instance.pk).update(created_at=at)


@given(phrase('{count:d} notes were left on "{label:Q}"'))
def many_notes(world, count, label):
    for i in range(count):
        world.create(FeedItem, f"Note {i}", {"parent_object": label})


@given(phrase('the view "{label:Q}" was deleted'))
def view_deleted(world, label):
    world.record(label).soft_delete()


# Reading


@when(phrase("an MCP client acting for {name:Actor} asks which record types there are"))
def describe_all(world, name):
    call(world, name, "describe_types")


@when(phrase("an MCP client acting for {name:Actor} describes {model:Model}"))
def describe(world, name, model):
    call(world, name, "describe_types", {"type": model.TYPE_ID})


@when(phrase("an MCP client acting for {name:Actor} describes {model:Model} to a Danish-speaking server"))
def describe_in_danish(world, name, model):
    with translation.override("da"):
        call(world, name, "describe_types", {"type": model.TYPE_ID})


@when(phrase('an MCP client acting for {name:Actor} searches for "{query:Q}"'))
def search(world, name, query):
    call(world, name, "search", {"query": query})


@when(phrase('an MCP client acting for {name:Actor} searches for "{label:Q}" by its record ID'))
def search_by_id(world, name, label):
    call(world, name, "search", {"query": world.ck_id(label).lower()})


@when(phrase("an MCP client acting for {name:Actor} lists {model:Model}"))
def list_records(world, name, model):
    call(world, name, "list_records", {"type": model.TYPE_ID})


@when(phrase('an MCP client acting for {name:Actor} lists {model:Model} with {field:Words} "{value:Q}"'))
def list_filtered(world, name, model, field, value):
    call(world, name, "list_records", _arguments(world, [("type", model.TYPE_ID), (field, value)]))


@when(phrase('an MCP client acting for {name:Actor} lists {model:Model} matching "{query:Q}"'))
def list_matching(world, name, model, query):
    call(world, name, "list_records", {"type": model.TYPE_ID, "query": query})


@when(phrase('an MCP client acting for {name:Actor} lists the view "{label:Q}"'))
def list_view(world, name, label):
    call(world, name, "list_records", {"view": world.ck_id(label)})


@when(phrase("an MCP client acting for {name:Actor} counts {model:Model}"))
def count(world, name, model):
    call(world, name, "aggregate_records", {"type": model.TYPE_ID})


@when(phrase("an MCP client acting for {name:Actor} counts {model:Model}, grouped by {field:Words}"))
def count_by(world, name, model, field):
    call(world, name, "aggregate_records", {"type": model.TYPE_ID, "group_by": [_field(field)]})


@when(phrase('an MCP client acting for {name:Actor} opens "{label:Q}"'))
def get_record(world, name, label):
    call(world, name, "get_record", {"id": world.ck_id(label)})


@when(phrase('an MCP client acting for {name:Actor} opens "{label:Q}" asking only for {fields:List}'))
def get_record_fields(world, name, label, fields):
    call(world, name, "get_record", {"id": world.ck_id(label), "fields": fields})


@when(phrase("an MCP client acting for {name:Actor} opens a {model:Model} that does not exist"))
def get_missing_record(world, name, model):
    call(world, name, "get_record", {"id": missing_id(model)})


def _rows(world) -> list:
    """The records the client got back: a list's rows, or the one record it opened."""
    result = _result(world)
    if isinstance(result, dict):
        return result["results"] if "results" in result else [result]
    return result


@then(phrase("the client sees {labels:Labels}"))
def sees(world, labels):
    assert sorted(row["label"] for row in _rows(world)) == sorted(labels), _rows(world)


@then(phrase("the client sees {labels:Labels} in that order"))
def sees_in_order(world, labels):
    assert [row["label"] for row in _rows(world)] == labels, _rows(world)


@then("the client sees no records")
def sees_nothing(world):
    assert _rows(world) == [], _rows(world)


@then(phrase("the client is told there are {count:d} in total"))
def total(world, count):
    assert _result(world)["total"] == count, _result(world)


@then(phrase("the client receives {count:d} records"))
def received(world, count):
    assert len(_rows(world)) == count, len(_rows(world))


@then(phrase("each record shows only {fields:List}"))
@then(phrase("the record shows only {fields:List}"))
def columns(world, fields):
    for row in _rows(world):
        assert set(row) == set(fields), row


@then(phrase('the client is told "{text:Q}"'))
def told(world, text):
    assert _result(world) == text, world.mcp_result


@then(phrase('the client is refused with "{message:Q}"'))
def refused_with(world, message):
    assert world.mcp_error is not None, world.mcp_result
    assert message in world.mcp_error, world.mcp_error


@then(phrase("the client is offered the record types {names:Labels}"))
def offered_types(world, names):
    assert sorted(entry["name"] for entry in _result(world)) == sorted(names), _result(world)


@then(phrase('the client is told the type is called "{singular:Q}", or "{plural:Q}" for several'))
def type_names(world, singular, plural):
    assert (_result(world)["name"], _result(world)["name_plural"]) == (singular, plural), _result(world)


@then(phrase("the client may filter on {keys:Labels}"))
def may_filter(world, keys):
    assert set(keys) <= set(_result(world)["filters"]), sorted(_result(world)["filters"])


@then(phrase("the client may not filter on {keys:Labels}"))
def may_not_filter(world, keys):
    assert not set(keys) & set(_result(world)["filters"]), sorted(_result(world)["filters"])


@then(phrase('the client learns that "{field:Q}" is one of {values:Labels}'))
def choices(world, field, values):
    assert _result(world)["filters"][field]["enum"] == values


@then(phrase("the client may write {fields:Labels}"))
def may_write(world, fields):
    assert set(fields) <= set(_result(world)["fields"]), sorted(_result(world)["fields"])


@then(phrase("the client may not write {fields:Labels}"))
def may_not_write(world, fields):
    assert not set(fields) & set(_result(world)["fields"]), sorted(_result(world)["fields"])


@then(phrase("the client must give {fields:Labels} when creating"))
def required_on_create(world, fields):
    assert _result(world)["required_on_create"] == fields


@then(phrase("the client may ask for the columns {fields:Labels}"))
def may_ask_for_columns(world, fields):
    assert set(fields) <= set(_result(world)["columns"]), _result(world)["columns"]


@then(phrase("the client may total {fields:Labels}"))
def may_total(world, fields):
    assert _result(world)["aggregatable"] == fields


@then("the client is told the type can be searched")
def searchable(world):
    assert _result(world)["searchable"] is True


@then("the client is told it may create and update them")
def can_write(world):
    assert (_result(world)["can_create"], _result(world)["can_update"]) == (True, True)


@then("the client is told it may neither create nor update them")
def cannot_write(world):
    assert (_result(world)["can_create"], _result(world)["can_update"]) == (False, False)


def _actions(world) -> dict:
    """{label: needs approval} of the actions the client is offered, by describe_types or get_record."""
    result = _result(world)
    actions = result["actions"]
    if isinstance(actions, dict):
        return {entry["label"]: entry["requires_approval"] for entry in actions.values()}
    model = get_model_types()[parse_ck_id(result["id"])[0]]
    names = records.action_names(model)
    return {names[action]: None for action in actions}


@then(phrase('the client is offered the action "{action:Q}"'))
def offered_action(world, action):
    assert action in _actions(world), _actions(world)
    assert not _actions(world)[action]


@then(phrase('the client is offered the action "{action:Q}", which needs approval'))
def offered_approval_action(world, action):
    assert _actions(world).get(action) is True, _actions(world)


@then("the client is offered no actions")
def offered_no_actions(world):
    assert _actions(world) == {}, _actions(world)


@then(phrase("the client is told changes to {fields:Labels} need approval"))
def approval_fields(world, fields):
    assert _result(world)["approval_fields"] == fields


@then(phrase("the client is offered the saved views {labels:Labels}"))
def lists_views(world, labels):
    assert sorted(_result(world)["views"].values()) == sorted(labels), _result(world)["views"]


def _same(world, actual, expected: str) -> bool:
    """Whether `actual`, as the client got it, reads as `expected`: a record by its label, a number by its value."""
    if actual == expected:
        return True
    if expected in world.records:
        return actual == world.ck_id(expected) or (isinstance(actual, dict) and actual.get("name") == expected)
    if actual is None:
        return expected == ""
    try:
        return Decimal(str(actual)) == Decimal(expected)
    except InvalidOperation:
        return str(actual) == expected


@then(phrase('the client sees the {field:Words} "{value:Q}"'))
def sees_value(world, field, value):
    actual = _result(world)[_field(field)]
    assert _same(world, actual, value), actual


@then(phrase('the client sees the note "{body:Q}" in the feed'))
def sees_note(world, body):
    assert body in [item["body"] for item in _result(world)["feed"]], _result(world)["feed"]


@then(phrase("the client sees {count:d} notes in the feed"))
def feed_length(world, count):
    assert len(_result(world)["feed"]) == count


@then(phrase("the client sees {count:d} entries in the change log"))
def changelog_length(world, count):
    assert len(_result(world)["changelog"]) == count


@then("the client does not see the change log")
def no_changelog(world):
    assert "changelog" not in _result(world), _result(world)


@then("the client does not see the feed")
def no_feed(world):
    assert "feed" not in _result(world), _result(world)


@then("the client gets the groups:")
def groups(world, datatable):
    header, *rows = datatable
    groups = _result(world)["groups"]
    assert len(groups) == len(rows), groups
    for group, row in zip(groups, rows, strict=True):
        for key, expected in zip(header, row, strict=True):
            assert _same(world, group[key], expected), (key, group)


@then(phrase("the client gets {count:d} groups"))
def group_count(world, count):
    assert len(_result(world)["groups"]) == count


@then("the client is told there are more groups")
def truncated(world):
    assert _result(world)["truncated"] is True


@then("the client is told these are all the groups")
def not_truncated(world):
    assert _result(world)["truncated"] is False


# Writing


@when(phrase('an MCP client acting for {name:Actor} creates a {model:Model} "{label:Q}"'))
def create(world, name, model, label):
    _create(world, name, model, label, {})


@when(phrase('an MCP client acting for {name:Actor} creates a {model:Model} "{label:Q}" with:'))
def create_with(world, name, model, label, datatable):
    _create(world, name, model, label, _fields(world, model, datatable))


def _fields(world, model, rows) -> dict:
    """`fields` for a write tool from `| field | value |` rows; unknown fields are sent as written."""
    fields = {}
    for key, value in rows:
        name = _field(key)
        try:
            fields[name] = world.api_value(model, name, value)
        except FieldDoesNotExist:
            fields[name] = value
    return fields


def _create(world, name, model, label, fields):
    result = call(
        world, name, "create_record", {"type": model.TYPE_ID, "fields": {label_field(model): label, **fields}}
    )
    if isinstance(result, dict) and "id" in result:
        world.add(label, model.objects.get(pk=result["id"]))


@given(phrase('an MCP client acting for {name:Actor} changed the {field:Words} of "{label:Q}" to "{value:Q}"'))
@when(phrase('an MCP client acting for {name:Actor} changes the {field:Words} of "{label:Q}" to "{value:Q}"'))
def update(world, name, field, label, value):
    _update(world, name, label, [(field, value)])


@when(phrase('an MCP client acting for {name:Actor} updates "{label:Q}" with:'))
def update_with(world, name, label, datatable):
    _update(world, name, label, datatable)


def _update(world, name, label, rows):
    fields = _fields(world, type(world.records[label]), rows)
    call(world, name, "update_record", {"id": world.ck_id(label), "fields": fields})


@when(
    phrase(
        'an MCP client acting for {name:Actor} points the {field:Words} of "{label:Q}" at a {model:Model} that does not exist'
    )
)
def update_to_missing(world, name, field, label, model):
    call(world, name, "update_record", {"id": world.ck_id(label), "fields": {_field(field): missing_id(model)}})


@when(phrase('an MCP client acting for {name:Actor} runs "{action:Q}" on "{label:Q}"'))
def run_action(world, name, action, label):
    method = action_for_label(type(world.records[label]), action) or action
    call(world, name, "run_action", {"id": world.ck_id(label), "action": method})


@when(phrase('an MCP client acting for {name:Actor} adds the note "{body:Q}" to "{label:Q}"'))
def add_note(world, name, body, label):
    call(world, name, "add_note", {"id": world.ck_id(label), "body": body})


def _undo(world, name, change_set, force=False):
    world.undone = change_set
    call(world, name, "undo", {"change_set": change_set, "force": force})


@given(phrase("an MCP client acting for {name:Actor} undid that change"))
@when(phrase("an MCP client acting for {name:Actor} undoes that change"))
def undo(world, name):
    _undo(world, name, world.change_set)


@when(phrase("an MCP client acting for {name:Actor} undoes that change anyway"))
def undo_forced(world, name):
    _undo(world, name, world.change_set, force=True)


@when(phrase("an MCP client acting for {name:Actor} undoes {whose:Their} change"))
def undo_own(world, name, whose):
    _undo(world, name, world.change_sets[name])


@when(phrase("an MCP client acting for {name:Actor} undoes {whose:Their} change anyway"))
def undo_own_forced(world, name, whose):
    _undo(world, name, world.change_sets[name], force=True)


@when(phrase("an MCP client acting for {name:Actor} undoes the same change again"))
def undo_again(world, name):
    _undo(world, name, world.undone)


@when(phrase("an MCP client acting for {name:Actor} undoes a change that never happened"))
def undo_unknown(world, name):
    _undo(world, name, "00000000-0000-0000-0000-000000000000")


@then(phrase('there is now a {model:Model} "{label:Q}"'))
def now_exists(world, model, label):
    world.add(label, model.objects.get(**{label_field(model): label}))


@then(phrase('"{label:Q}" is recorded as created by {name:Actor}'))
def created_by(world, label, name):
    assert world.record(label).created_by == world.user(name)


@then(phrase('"{label:Q}" has no notes'))
def no_notes(world, label):
    instance = world.records[label]
    notes = FeedItem.objects.filter(
        parent_content_type=ContentType.objects.get_for_model(instance), parent_object_id=instance.pk
    )
    assert not notes.exists(), list(notes.values_list("body", flat=True))


@then(phrase('the client\'s change is recorded as made by {name:Actor} through "{client:Q}"'))
def attributed(world, name, client):
    entries = ChangeLog.objects.filter(change_set=_result(world)["change_set"])
    assert entries.exists()
    for entry in entries:
        assert (entry.source, entry.client, entry.created_by) == ("mcp", client, world.user(name))


@then(phrase('the client is told the undo conflicts on the {field:Words} of "{label:Q}"'))
def undo_conflicts(world, field, label):
    conflicts = {(c["label"], c["field"]) for c in _result(world)["conflicts"]}
    assert (label, _field(field)) in conflicts, conflicts


@then(phrase("the client is told it undid {count:d} change"))
@then(phrase("the client is told it undid {count:d} changes"))
def undid(world, count):
    assert _result(world)["reverted"] == count, _result(world)


@then(phrase('the change waits for {name:Actor}\'s approval as "{label:Q}"'))
def waits_for_approval_as(world, name, label):
    assert _proposal(world, name).label == label


@then(phrase("the change waits for {name:Actor}'s approval"))
def waits_for_approval(world, name):
    _proposal(world, name)


def _proposal(world, name):
    """The proposal the client was just told about, filed for `name` to confirm."""
    result = _result(world)
    assert result["status"] == "pending_approval", result
    proposal = AssistantProposal.objects.get(pk=result["proposal"])
    assert (proposal.status, proposal.source, proposal.created_by) == ("pending", "mcp", world.user(name))
    return proposal


@then(phrase('the proposal comes from the MCP client "{client:Q}"'))
def proposal_client(world, client):
    assert world.proposal.client == client


@then("the proposal would make these changes:")
def proposal_changes(world, datatable):
    model = world.proposal.target_content_type.model_class()
    expected = {_field(k): world.api_value(model, _field(k), v) for k, v in datatable}
    assert world.proposal.payload["fields"] == expected, world.proposal.payload


@then("nothing waits for approval")
def no_proposals(world):
    assert not AssistantProposal.objects.exists()


# Limits and checks


@when("the MCP system checks run")
def run_checks(world):
    world.check_messages = [m for m in checks.run_checks() if m.id and m.id.startswith("crudkit_mcp.")]


@then(phrase('the checks report the error "{check:Q}"'))
def check_error(world, check):
    assert [(m.id, m.level) for m in world.check_messages] == [(check, checks.ERROR)], world.check_messages


@then(phrase('the checks report the warning "{check:Q}"'))
def check_warning(world, check):
    assert [(m.id, m.level) for m in world.check_messages] == [(check, checks.WARNING)], world.check_messages


@then("the checks report nothing about MCP")
def check_nothing(world):
    assert world.check_messages == [], world.check_messages


@then(phrase("an agent may still be set up to work on {model:Model}"))
def agent_may_work_on(world, model):
    Agent(name="Triage", instructions="Tidy up.", trigger=Agent.Trigger.MANUAL, model_type=model.TYPE_ID).clean()
