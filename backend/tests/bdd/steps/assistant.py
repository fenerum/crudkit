"""The assistant sidebar: the socket, conversations, turns, what the assistant
is told about the screen, and its instructions. The tools themselves are in
`assistant_tools.py`.

The AI model is never real: `ScriptedModel` plays it, doing what the scenario
scripted ("Given the assistant will reply ...", "... will call <tool> with:").
A turn runs over the sidebar socket once someone has opened the assistant,
and directly otherwise.

Phrases this area adds:

Scripting the AI model
- `Given the assistant will reply "Noted."` / `Given the assistant will think "Checking." first`
- `Given the assistant will call get_object` / `... call get_object for "Acme"` / `... call propose_patch with:`
  (an argument table, see `assistant_tools.py`)
- `Given the assistant will call get_object for "Acme" with its name garbled by invisible tag characters`
- `Given the assistant takes its time to finish after proposing`
- `Given the AI model is down` (`Given no AI model is configured` comes from steps/ai_fields.py)
- `Given the project's assistant prompt is "..."` / `Given the assistant is called "Ada"`
- `Given customers have their own assistant tool check_credit`
- `Given an AI context document "Ideal customer" saying "..."` / `... for customers saying "..."`

The screen (what the browser reports)
- `Given Alice is chatting with the assistant` / `Given Alice is looking at "Acme"` / `... on the "notes" tab`
- `Given Alice is looking at the list of customers` / `Given Alice is looking at the inbox page`
- `Given the list shows "Acme, Beta and Gamma"` / `Given the list shows 150 customers`
- `Given Alice has selected "Beta"` / `Given the list shows Alice's saved view "Churn risk"`
- `Given the list is searched for "ac"` / `... filtered on status "active"` / `... on page 2`
- `Given the list is searched for a text of 300 characters` / `... filtered on 25 different fields`
- `Given Alice has a new customer form open` (`... open with:` a table of values) / `... the edit form of "Acme" open`
- `Given Alice has a ticket edit form open that points at "Acme"`
- `Given Alice has a new customer form open with 150 values of 900 characters`
- `Given the playbook for customers is "..."`
- `When the assistant reads the screen`
- `Then the assistant sees "..."` / `Then the assistant does not see "..."` (the screen, or the latest message it got)

The socket and conversations
- `When Alice opens the assistant` (`Given Alice opened ...`) / `... opens the assistant on "Acme"` / `Then the assistant is ready for Alice`
- `Then the assistant turns Alice away`
- `When someone opens the assistant and talks to it without signing in` / `... signs in with a bad token`
- `Then the assistant answers with the error "Auth required." and hangs up`
- `When Alice sends the assistant a "dance" message` / `When Alice sends the assistant an empty message`
- `Then Alice sees the error "..."` / `Then the assistant does not start a turn`
- `When Alice starts a new conversation` (`Given ... started ...`) / `... reopens the conversation "Renewal"` / `... comes back and reopens that conversation`
- `Given Alice has a conversation "Renewal"` (`... whose memory can no longer be read`) / `Given Alice deleted the conversation "Old"`
- `Then Alice is in the conversation "Renewal"` / `Then Alice is in a new, empty conversation`
- `Then the conversation shows:` (a `| who | what |` table) / `Then Alice's conversation is titled "..."`
- `Then the conversation is titled with the first 120 characters of the question`

Turns
- `When Alice asks the assistant "..."` (`Given ... asked ...`) / `... a question of 150 characters` / `... "..." and a card appears`
- `Then the assistant answers "..."` / `Then Alice sees the turn:` (a `| event | detail |` table)
- `Then the assistant is still answering` / `Then the assistant remembers "..."` / `... remembers nothing earlier`

Cards in the sidebar
- `When Alice confirms the card` (`Given ... confirmed ...`) / `... skips the card` / `... confirms all the cards` / `... confirms the card again`
- `When Alice confirms the card from the other conversation`
- `Given the proposal on the card was confirmed in the Inbox` / `Given Alice may no longer change customers`
- `Given the assistant proposed in another conversation changing the status of "Beta" to "churned"`
- `Then the card says "Applied fields: status"` / `Then every card says "..."`

Instructions
- `When a background agent works on "Acme" for Alice`
- `Then the assistant's instructions start with "..."` / `... say, in this order:` (a one-column table)
- `Then the assistant's instructions include the AI context "Ideal customer"` / `... do not include ...`
- `Then the assistant is offered exactly these tools:` / `Then the assistant is offered check_credit` /
  `... is not offered ...` / `Then the assistant works with a temperature of 0.2`
- `Then the tool get_object ran`
"""

import asyncio
import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Permission
from pydantic_ai import Tool
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import DeltaThinkingPart, DeltaToolCall, FunctionModel
from pytest_bdd import given, then, when
from rest_framework_simplejwt.tokens import AccessToken

from crudkit.models import AIContext
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import AssistantConversation, AssistantProposal
from crudkit_assistant.proposals import create_proposal, patch_label
from crudkit_assistant.routing import websocket_urlpatterns
from crudkit_assistant.runner import run_turn
from crudkit_assistant.screen import describe_screen, parse_screen
from tests.bdd.world import model_named, phrase, split_list

SOCKET_TIMEOUT = 5
# How a model garbles a tool name; the assistant still has to understand it.
GARBLES = {
    "invisible tag characters": "{name}\U000e006a\U000e007f",
    "its arguments glued on": '{name}\U000e006a{{"id": "x"}}',
    "a trailing space": "{name} ",
    "empty brackets": "{name}()",
}
# Sidebar events as a person would describe them.
EVENT_NAMES = {
    "conversation": "a conversation opens",
    "turn_start": "the turn starts",
    "thinking_delta": "the assistant thinks",
    "text_delta": "the assistant writes",
    "tool_start": "a step starts",
    "tool_end": "the step ends",
    "tool_call_pending": "a card appears",
    "tool_outcome": "the card is resolved",
    "form_fill": "the form is filled in",
    "form_open": "a form opens",
    "assistant_message": "the answer arrives",
    "error": "an error is shown",
    "turn_end": "the turn ends",
}


# ---------------------------------------------------------------------------
# The scenario's assistant


class ScriptedModel:
    """Plays the AI model: on a person's message it makes the scripted tool
    calls (if any), then answers with the scripted reply."""

    def __init__(self):
        self.calls: list[ToolCallPart] = []
        self.reply = "Done."
        # Reasoning streamed before the tool calls.
        self.thinking = ""
        self.fails = False
        # Set to hold the answer after the tool calls until the scenario ends.
        self.hold: asyncio.Event | None = None
        self.requests: list = []

    def respond(self, messages, info):
        self.requests.append((messages, info))
        if isinstance(messages[-1].parts[-1], UserPromptPart):
            if self.fails:
                raise RuntimeError("The AI model is down")
            if self.calls:
                return ModelResponse(parts=list(self.calls))
        return ModelResponse(parts=[TextPart(self.reply)])

    async def stream(self, messages, info):
        if self.hold is not None and not isinstance(messages[-1].parts[-1], UserPromptPart):
            await self.hold.wait()
        response = self.respond(messages, info)
        if self.thinking and _is_prompt(messages):
            yield {0: DeltaThinkingPart(content=self.thinking)}
        for index, part in enumerate(response.parts, start=1):
            if isinstance(part, TextPart):
                yield part.content
            else:
                yield {index: DeltaToolCall(name=part.tool_name, json_args=part.args_as_json_str())}

    @asynccontextmanager
    async def factory(self):
        yield FunctionModel(self.respond, stream_function=self.stream)

    # What the model was given

    def latest(self):
        if not self.requests:
            raise AssertionError("The AI model was never asked anything")
        return self.requests[-1]

    def prompts(self) -> list[str]:
        return [messages[-1].parts[-1].content for messages, _ in self.requests if _is_prompt(messages)]

    def instructions(self) -> str:
        parts = self.latest()[1].model_request_parameters.instruction_parts
        assert len(parts) == 1, "The instructions must be one system message"
        return parts[0].content

    def tool_names(self) -> set[str]:
        return {tool.name for tool in self.latest()[1].function_tools}

    def tool_returns(self) -> list[ToolReturnPart]:
        return [
            part for messages, _ in self.requests for part in messages[-1].parts if isinstance(part, ToolReturnPart)
        ]


def _is_prompt(messages) -> bool:
    return isinstance(messages[-1].parts[-1], UserPromptPart)


class Socket:
    """The sidebar's connection. It stays open across steps on its own event
    loop, which only runs while a step waits for it."""

    def __init__(self, path: str):
        self.loop = asyncio.new_event_loop()
        self.closed_with: int | None = None
        self.received: list[dict] = []
        self.ws = self.run(self._connect(path))

    @staticmethod
    async def _connect(path):
        ws = WebsocketCommunicator(URLRouter(websocket_urlpatterns), path)
        connected, _ = await ws.connect()
        assert connected, path
        return ws

    def run(self, coroutine):
        return self.loop.run_until_complete(coroutine)

    def send(self, payload: dict):
        self.run(self.ws.send_json_to(payload))

    def receive(self) -> dict | None:
        """The next message, or None once the assistant has hung up."""
        output = self.run(self.ws.receive_output(SOCKET_TIMEOUT))
        if output["type"] == "websocket.close":
            self.closed_with = output.get("code")
            return None
        self.received.append(json.loads(output["text"]))
        return self.received[-1]

    def receive_until(self, done) -> list[dict]:
        """Messages up to and including the first one `done` accepts."""
        messages = [self.receive()]
        while messages[-1] is not None and not done(messages[-1]):
            messages.append(self.receive())
        return [message for message in messages if message is not None]

    def quiet(self) -> bool:
        return self.run(self.ws.receive_nothing())

    def close(self):
        if self.loop.is_closed():
            return
        self.run(self.ws.disconnect())
        self.loop.close()


@dataclass
class Assistant:
    """What one scenario knows about the assistant."""

    person: str = ""
    # The screen as the browser reports it.
    screen: dict = field(default_factory=dict)
    model: ScriptedModel | None = None
    socket: Socket | None = None
    session: str = "bdd-session"
    conversation: dict | None = None
    # What reached the sidebar in the latest exchange, and every card so far.
    events: list = field(default_factory=list)
    cards: list = field(default_factory=list)
    question: str = ""
    reply: str = ""
    # What the assistant saw: the screen block, or the latest message it got.
    seen: str = ""
    # The latest direct tool call: what it returned and what it sent to the browser.
    result: object = None
    sent: list = field(default_factory=list)
    dry_run: bool = False


def assistant(world) -> Assistant:
    if not hasattr(world, "assistant"):
        world.assistant = Assistant()
    return world.assistant


def scripted_model(world, monkeypatch) -> ScriptedModel:
    state = assistant(world)
    if state.model is None:
        state.model = ScriptedModel()
        monkeypatch.setattr("tests.testapp.ai.create_model", state.model.factory)
    return state.model


def person(world):
    state = assistant(world)
    if not state.person:
        raise LookupError("Say who is using the assistant, e.g. 'Given Alice is chatting with the assistant'")
    return world.user(state.person)


def deps(world, source: str = "assistant") -> AssistantDeps:
    state = assistant(world)
    return AssistantDeps(
        user_id=person(world).pk,
        session_key=state.session,
        screen=parse_screen(state.screen),
        source=source,
        dry_run=state.dry_run,
    )


def readable(world, text: str) -> str:
    """`text` with record ids replaced by the records' labels, the way a step
    names them: "Reading CUS1" -> "Reading Acme", "customer CUS1 (Acme)" and
    "Acme (CUS1)" -> "Acme"."""
    labels = _labels(world)
    for object_id, label in labels.items():
        text = text.replace(f"{object_id} ({label})", label).replace(f"{label} ({object_id})", label)
    return re.sub(r"\b[A-Z]{3}\d+\b", lambda match: labels.get(match[0], match[0]), text)


def _labels(world) -> dict[str, str]:
    return {world.ck_id(label): label for label in world.records}


def labels_of(world, ids) -> set[str]:
    labels = _labels(world)
    return {labels.get(str(object_id), str(object_id)) for object_id in ids}


def proposals():
    return AssistantProposal.objects.order_by("pk")


# ---------------------------------------------------------------------------
# Scripting the AI model


def script_call(world, monkeypatch, tool, arguments):
    scripted_model(world, monkeypatch).calls.append(ToolCallPart(tool, arguments))


@given(phrase('the assistant will reply "{text:Q}"'))
def will_reply(world, monkeypatch, text):
    scripted_model(world, monkeypatch).reply = text


@given(phrase('the assistant will think "{text:Q}" first'))
def will_think(world, monkeypatch, text):
    scripted_model(world, monkeypatch).thinking = text


@given(phrase("the assistant will call {tool:Words}"))
def will_call(world, monkeypatch, tool):
    script_call(world, monkeypatch, tool, {})


@given(phrase('the assistant will call {tool:Words} for "{label:Q}"'))
def will_call_for(world, monkeypatch, tool, label):
    script_call(world, monkeypatch, tool, {"id": world.ck_id(label)})


@given(phrase('the assistant will call {tool:Words} for "{label:Q}" with its name garbled by {garble:Words}'))
def will_call_garbled(world, monkeypatch, tool, label, garble):
    script_call(world, monkeypatch, GARBLES[garble].format(name=tool), {"id": world.ck_id(label)})


@given("the assistant takes its time to finish after proposing")
def takes_its_time(world, monkeypatch):
    scripted_model(world, monkeypatch).hold = asyncio.Event()


@given("the AI model is down")
def model_is_down(world, monkeypatch):
    scripted_model(world, monkeypatch).fails = True


@given(phrase('the project\'s assistant prompt is "{text:Q}"'))
def project_prompt(settings, text):
    settings.CRUDKIT_ASSISTANT_SYSTEM_PROMPT = text


@given(phrase('the assistant is called "{name:Q}"'))
def assistant_name(settings, name):
    settings.CRUDKIT_ASSISTANT_NAME = name


@given(phrase("{model:Model} have their own assistant tool {tool:Words}"))
def own_tool(monkeypatch, model, tool):
    def project_tool(ctx) -> str:
        return "ok"

    monkeypatch.setattr(model.CrudKitSettings, "assistant_tools", [Tool(project_tool, name=tool)], raising=False)


@given(phrase('an AI context document "{label:Q}" saying "{body:Q}"'))
def ai_context(world, label, body):
    world.create(AIContext, label, {"body": body})


@given(phrase('an AI context document "{label:Q}" for {model:Model} saying "{body:Q}"'))
def scoped_ai_context(world, label, model, body):
    world.create(AIContext, label, {"body": body, "model_types": json.dumps([model.TYPE_ID])})


# ---------------------------------------------------------------------------
# The screen


def _look_at(world, name, screen):
    state = assistant(world)
    state.person = name
    state.screen = screen


@given(phrase("{name:Actor} is chatting with the assistant"))
def chatting(world, name):
    _look_at(world, name, {"route": "other", "path": "/"})


@given(phrase('{name:Actor} is looking at "{label:Q}"'))
def looking_at_record(world, name, label):
    _look_at(world, name, {"route": "detail", "record_id": world.ck_id(label)})


@given(phrase('{name:Actor} is looking at "{label:Q}" on the "{tab:Q}" tab'))
def looking_at_tab(world, name, label, tab):
    _look_at(world, name, {"route": "detail", "record_id": world.ck_id(label), "tab": tab})


@given(phrase("{name:Actor} is looking at the list of {model:Model}"))
def looking_at_list(world, name, model):
    _look_at(world, name, {"route": "list", "type_id": model.TYPE_ID})


@given(phrase("{name:Actor} is looking at the {route:Words} page"))
def looking_at_page(world, name, route):
    _look_at(world, name, {"route": route, "path": f"/{route}"})


@given(phrase('the list shows "{labels:Q}"'))
def list_shows(world, labels):
    assistant(world).screen["visible_ids"] = [world.ck_id(label) for label in split_list(labels)]


@given(phrase("the list shows {count:d} {model:Model}"))
def list_shows_many(world, count, model):
    assistant(world).screen["visible_ids"] = [f"{model.TYPE_ID}{n}" for n in range(1, count + 1)]


@given(phrase('{name:Actor} has selected "{labels:Q}"'))
def has_selected(world, name, labels):
    assistant(world).screen["selected_ids"] = [world.ck_id(label) for label in split_list(labels)]


@given(phrase('the list shows {name:Actor}\'s saved view "{label:Q}"'))
def list_shows_view(world, name, label):
    screen = assistant(world).screen
    view_model = model_named("view")
    view = world.create(view_model, label, {"model": screen["type_id"], "fields": '["name"]'}, by=world.user(name))
    screen["view_id"] = view.pk


@given(phrase('the list is searched for "{text:Q}"'))
def list_searched(world, text):
    assistant(world).screen["q"] = text


@given(phrase("the list is searched for a text of {length:d} characters"))
def list_searched_long(world, length):
    assistant(world).screen["q"] = "x" * length


@given(phrase('the list is filtered on {field:Words} "{value:Q}"'))
def list_filtered(world, field, value):
    assistant(world).screen.setdefault("filters", {})[field.replace(" ", "_")] = value


@given(phrase("the list is filtered on {count:d} different fields"))
def list_filtered_many(world, count):
    assistant(world).screen["filters"] = {f"field{n}": "x" for n in range(1, count + 1)}


@given(phrase("the list is on page {page:d}"))
def list_page(world, page):
    assistant(world).screen["page"] = page


def _open_form(world, name, form):
    state = assistant(world)
    state.person = name
    state.screen.setdefault("route", form["mode"])
    state.screen["form"] = form


@given(phrase("{name:Actor} has a new {model:Model} form open"))
def new_form(world, name, model):
    _open_form(world, name, {"type_id": model.TYPE_ID, "mode": "create", "values": {}})


@given(phrase("{name:Actor} has a new {model:Model} form open with:"))
def new_form_with(world, name, model, datatable):
    _open_form(world, name, {"type_id": model.TYPE_ID, "mode": "create", "values": dict(datatable)})


@given(phrase("{name:Actor} has a new {model:Model} form open with {count:d} values of {length:d} characters"))
def new_form_with_many(world, name, model, count, length):
    values = {f"field{n}": "x" * length for n in range(1, count + 1)}
    _open_form(world, name, {"type_id": model.TYPE_ID, "mode": "create", "values": values})


@given(phrase('{name:Actor} has the edit form of "{label:Q}" open'))
def edit_form(world, name, label):
    record = world.records[label]
    _open_form(world, name, {"type_id": record.TYPE_ID, "mode": "edit", "record_id": record.pk, "values": {}})


@given(phrase('{name:Actor} has a {model:Model} edit form open that points at "{label:Q}"'))
def mismatched_edit_form(world, name, model, label):
    _open_form(world, name, {"type_id": model.TYPE_ID, "mode": "edit", "record_id": world.ck_id(label)})


@given(phrase('the playbook for {model:Model} is "{text:Q}"'))
def playbook(monkeypatch, model, text):
    monkeypatch.setattr(model.CrudKitSettings, "assistant_prompt", text, raising=False)


@when("the assistant reads the screen")
def reads_the_screen(world):
    state = assistant(world)
    state.seen = describe_screen(person(world), parse_screen(state.screen))


@then(phrase('the assistant sees "{text:Q}"'))
def sees(world, text):
    seen = readable(world, assistant(world).seen)
    assert text in seen, seen


@then(phrase('the assistant does not see "{text:Q}"'))
def does_not_see(world, text):
    seen = readable(world, assistant(world).seen)
    assert text not in seen, seen


@then(phrase("the assistant is told about {count:d} rows but lists only {shown:d}"))
def rows_capped(world, count, shown):
    seen = assistant(world).seen
    assert f"Visible rows ({count}):" in seen, seen
    assert f"(+{count - shown} more)" in seen, seen


@then(phrase("the assistant sees a search of {length:d} characters"))
def search_capped(world, length):
    match = re.search(r"search '(x+)'", assistant(world).seen)
    assert match and len(match[1]) == length, assistant(world).seen


@then(phrase("the assistant sees {count:d} filters"))
def filters_capped(world, count):
    assert len(re.findall(r"'field\d+': 'x'", assistant(world).seen)) == count, assistant(world).seen


@then(phrase("the assistant sees {count:d} form values of {length:d} characters"))
def form_values_capped(world, count, length):
    values = re.findall(r"'field\d+': '(x+)'", assistant(world).seen)
    assert len(values) == count, len(values)
    assert {len(value) for value in values} == {length}


# ---------------------------------------------------------------------------
# The socket


def open_socket(world, request, path: str) -> Socket:
    state = assistant(world)
    if state.socket is not None:
        state.socket.close()
    state.socket = Socket(path)
    request.addfinalizer(state.socket.close)
    return state.socket


def _sign_in(world, request, name, path):
    state = assistant(world)
    state.person = name
    socket = open_socket(world, request, path)
    socket.send({"type": "auth", "token": str(AccessToken.for_user(world.user(name)))})
    state.events = socket.receive_until(lambda message: True)
    if state.events and state.events[0]["type"] == "ready":
        state.session = state.events[0]["session"]


@given(phrase("{name:Actor} opened the assistant"))
@when(phrase("{name:Actor} opens the assistant"))
def opens_the_assistant(world, request, name):
    _sign_in(world, request, name, "/ws/assistant/")


@when(phrase('{name:Actor} opens the assistant on "{label:Q}"'))
def opens_the_assistant_on(world, request, name, label):
    record = world.records[label]
    _sign_in(world, request, name, f"/ws/assistant/{record.TYPE_ID}/{world.number(label)}/")


@when("someone opens the assistant and talks to it without signing in")
def talks_without_signing_in(world, request):
    socket = open_socket(world, request, "/ws/assistant/")
    socket.send({"type": "user_message", "text": "Hello?"})
    assistant(world).events = socket.receive_until(lambda message: False)


@when("someone opens the assistant and signs in with a bad token")
def bad_token(world, request):
    socket = open_socket(world, request, "/ws/assistant/")
    socket.send({"type": "auth", "token": "not-a-token"})
    assistant(world).events = socket.receive_until(lambda message: False)


def _socket(world) -> Socket:
    socket = assistant(world).socket
    if socket is None:
        raise LookupError("Nobody has opened the assistant")
    return socket


@then(phrase("the assistant is ready for {name:Actor}"))
def is_ready(world, name):
    state = assistant(world)
    assert [event["type"] for event in state.events] == ["ready"], state.events
    assert state.session


@then(phrase("the assistant turns {name:Actor} away"))
def turned_away(world, name):
    socket = _socket(world)
    assert socket.closed_with == 4403, (socket.closed_with, assistant(world).events)
    assert not any(event["type"] == "ready" for event in assistant(world).events)


@then(phrase('the assistant answers with the error "{message:Q}" and hangs up'))
def hangs_up(world, message):
    assert {"type": "error", "message": message} in assistant(world).events, assistant(world).events
    assert _socket(world).closed_with == 4001


@when(phrase('{name:Actor} sends the assistant a "{kind:Q}" message'))
def sends_a_message_of_kind(world, name, kind):
    socket = _socket(world)
    socket.send({"type": kind})
    assistant(world).events = [socket.receive()]


@when(phrase("{name:Actor} sends the assistant an empty message"))
def sends_an_empty_message(world, name):
    _socket(world).send({"type": "user_message", "text": "   "})


@then(phrase('{name:Actor} sees the error "{message:Q}"'))
def sees_the_error(world, name, message):
    errors = [readable(world, event["message"]) for event in assistant(world).events if event["type"] == "error"]
    assert message in errors, assistant(world).events


@then("the assistant does not start a turn")
def no_turn(world):
    assert _socket(world).quiet()


# Conversations


def _open_conversation(world, conversation_id):
    socket = _socket(world)
    socket.send({"type": "open_conversation", "id": conversation_id})
    state = assistant(world)
    state.events = socket.receive_until(lambda message: message["type"] == "conversation")
    state.conversation = state.events[-1]
    state.session = AssistantConversation.objects.get(pk=state.conversation["id"]).session_key


@given(phrase("{name:Actor} started a new conversation"))
@when(phrase("{name:Actor} starts a new conversation"))
def starts_a_conversation(world, name):
    _open_conversation(world, None)


@when(phrase('{name:Actor} reopens the conversation "{label:Q}"'))
def reopens_a_conversation(world, name, label):
    _open_conversation(world, world.ck_id(label))


@when(phrase("{name:Actor} comes back and reopens that conversation"))
def comes_back(world, request, name):
    conversation_id = assistant(world).conversation["id"]
    opens_the_assistant(world, request, name)
    _open_conversation(world, conversation_id)


def _a_conversation(world, name, label, **values):
    user = world.user(name)
    conversation = AssistantConversation.objects.create(
        title=label,
        transcript=[{"role": "user", "text": f"About {label}"}, {"role": "assistant", "text": "Happy to help."}],
        created_by=user,
        updated_by=user,
        **values,
    )
    return world.add(label, conversation)


@given(phrase('{name:Actor} has a conversation "{label:Q}"'))
def has_a_conversation(world, name, label):
    _a_conversation(world, name, label)


@given(phrase('{name:Actor} has a conversation "{label:Q}" whose memory can no longer be read'))
def has_an_unreadable_conversation(world, name, label):
    _a_conversation(world, name, label, messages=[{"kind": "from an older version"}])


@given(phrase('{name:Actor} deleted the conversation "{label:Q}"'))
def deleted_a_conversation(world, name, label):
    AssistantConversation.objects.filter(pk=world.records[label].pk).update(deleted=True)


@then(phrase('{name:Actor} is in the conversation "{label:Q}"'))
def in_the_conversation(world, name, label):
    assert assistant(world).conversation["id"] == world.ck_id(label), assistant(world).conversation


@then(phrase("{name:Actor} is in a new, empty conversation"))
def in_a_new_conversation(world, name):
    conversation = assistant(world).conversation
    known = {str(instance.pk) for instance in world.records.values()}
    assert conversation["id"] not in known, conversation
    assert (conversation["title"], conversation["transcript"]) == ("", []), conversation
    assert AssistantConversation.objects.get(pk=conversation["id"]).created_by == world.user(name)


def _transcript_row(world, item) -> list[str]:
    role = item["role"]
    if role == "activity":
        return [role, "; ".join(readable(world, step["label"]) for step in item["steps"])]
    if role == "proposal":
        return [role, item["status"]]
    return [role, item["text"]]


@then("the conversation shows:")
def conversation_shows(world, datatable):
    transcript = assistant(world).conversation["transcript"]
    assert [_transcript_row(world, item) for item in transcript] == datatable[1:], transcript


def _current_conversation(world):
    state = assistant(world)
    if state.conversation is not None:
        return AssistantConversation.objects.get(pk=state.conversation["id"])
    return AssistantConversation.objects.filter(created_by=person(world)).latest("created_at")


@then(phrase('{name:Actor}\'s conversation is titled "{title:Q}"'))
def conversation_titled(world, name, title):
    conversation = _current_conversation(world)
    assert conversation.created_by == world.user(name)
    assert conversation.title == title, conversation.title


@then(phrase("the conversation is titled with the first {length:d} characters of the question"))
def conversation_title_cut(world, length):
    question = assistant(world).question
    assert _current_conversation(world).title == question[:length]
    assert len(question) > length


# ---------------------------------------------------------------------------
# Turns


def _over_the_socket(world, text, done):
    state = assistant(world)
    socket = _socket(world)
    if state.screen:
        socket.send({"type": "screen", "screen": state.screen})
    socket.send({"type": "user_message", "text": text})
    state.events = socket.receive_until(done)
    state.cards += [event for event in state.events if event["type"] == "tool_call_pending"]
    state.reply = next((e["text"] for e in state.events if e["type"] == "assistant_message"), "")


def ask(world, monkeypatch, text, source="assistant"):
    """One turn: over the socket when the assistant is open, else directly."""
    state = assistant(world)
    model = scripted_model(world, monkeypatch)
    if state.socket is not None:
        _over_the_socket(world, text, lambda message: message["type"] == "turn_end")
    else:
        result = async_to_sync(run_turn)(text, deps=deps(world, source))
        state.reply = result.output_text
        state.sent = result.pending_events
    if model.requests:
        state.seen = model.prompts()[-1]


@given(phrase('{name:Actor} asked the assistant "{text:Q}"'))
@when(phrase('{name:Actor} asks the assistant "{text:Q}"'))
def asks(world, monkeypatch, name, text):
    assistant(world).person = name
    assistant(world).question = text
    ask(world, monkeypatch, text)


@when(phrase("{name:Actor} asks the assistant a question of {length:d} characters"))
def asks_a_long_question(world, monkeypatch, name, length):
    asks(world, monkeypatch, name, ("What about this? " * length)[:length])


@when(phrase('{name:Actor} asks the assistant "{text:Q}" and a card appears'))
def asks_until_a_card(world, monkeypatch, name, text):
    scripted_model(world, monkeypatch)
    _over_the_socket(world, text, lambda message: message["type"] in ("tool_call_pending", "turn_end"))


@when(phrase('a background agent works on "{label:Q}" for {name:Actor}'))
def an_agent_works_on(world, monkeypatch, label, name):
    _look_at(world, name, {"route": "detail", "record_id": world.ck_id(label)})
    ask(world, monkeypatch, "Carry out your instructions.", source="agent")


@then(phrase('the assistant answers "{text:Q}"'))
def answers(world, text):
    assert assistant(world).reply == text, assistant(world).reply


def _event_rows(world, events) -> list[list[str]]:
    """Sidebar events as `[event, detail]` rows; streamed text is joined up."""
    rows = []
    for event in events:
        kind = event["type"]
        if kind in ("thinking_delta", "text_delta") and rows and rows[-1][0] == EVENT_NAMES[kind]:
            rows[-1][1] += event["text"]
            continue
        detail = {
            "thinking_delta": event.get("text"),
            "text_delta": event.get("text"),
            "tool_start": readable(world, event.get("label", "")),
            "tool_end": "succeeded" if event.get("ok") else "failed",
            "tool_call_pending": f"for {readable(world, str(event.get('target')))}",
            "assistant_message": event.get("text"),
            "error": event.get("message"),
        }.get(kind, "")
        rows.append([EVENT_NAMES[kind], detail])
    return rows


@then(phrase("{name:Actor} sees the turn:"))
def sees_the_turn(world, name, datatable):
    rows = _event_rows(world, assistant(world).events)
    assert rows == datatable[1:], rows


@then("the assistant is still answering")
def still_answering(world):
    seen = [event["type"] for event in _socket(world).received]
    assert "tool_call_pending" in seen and "turn_end" not in seen, seen


@then(phrase('the assistant remembers "{text:Q}"'))
def remembers(world, text):
    messages, _ = assistant(world).model.latest()
    earlier = [part.content for message in messages[:-1] for part in message.parts if isinstance(part, UserPromptPart)]
    assert any(text in content for content in earlier), earlier


@then("the assistant remembers nothing earlier")
def remembers_nothing(world):
    messages, _ = assistant(world).model.latest()
    assert len(messages) == 1, messages


# ---------------------------------------------------------------------------
# Cards in the sidebar


def _confirm(world, ids, ok=True):
    state = assistant(world)
    socket = _socket(world)
    socket.send({"type": "confirm", "ids": ids, "ok": ok})
    answered = []

    def done(message):
        if message["type"] in ("tool_outcome", "error"):
            answered.append(message)
        return len(answered) == len(ids)

    state.events = socket.receive_until(done)


def _card(world) -> dict:
    cards = assistant(world).cards
    if not cards:
        raise LookupError("The assistant has not shown a card")
    return cards[-1]


@given(phrase("{name:Actor} confirmed the card"))
@when(phrase("{name:Actor} confirms the card"))
@when(phrase("{name:Actor} confirms the card again"))
def confirms_the_card(world, name):
    _confirm(world, [_card(world)["id"]])


@when(phrase("{name:Actor} skips the card"))
def skips_the_card(world, name):
    _confirm(world, [_card(world)["id"]], ok=False)


@when(phrase("{name:Actor} confirms all the cards"))
def confirms_all_cards(world, name):
    _confirm(world, [card["id"] for card in assistant(world).cards])


@when(phrase("{name:Actor} confirms the card from the other conversation"))
def confirms_a_foreign_card(world, name):
    _confirm(world, [world.foreign_proposal.pk])


@given(
    phrase('the assistant proposed in another conversation changing the {field:Words} of "{label:Q}" to "{value:Q}"')
)
def proposed_elsewhere(world, field, label, value):
    instance = world.record(label)
    fields = {field.replace(" ", "_"): value}
    user = person(world)
    world.foreign_proposal = create_proposal(
        user, type(instance), instance, "patch", patch_label(fields), {"fields": fields}, session_key="another"
    )


@given("the proposal on the card was confirmed in the Inbox")
def confirmed_in_the_inbox(world):
    AssistantProposal.objects.get(pk=_card(world)["id"]).apply(person(world))


@given(phrase("{name:Actor} may no longer {actions:List} {model:Model}"))
def may_no_longer(world, name, actions, model):
    codenames = [f"{action}_{model._meta.model_name}" for action in actions]
    world.user(name).user_permissions.remove(*Permission.objects.filter(codename__in=codenames))


@then(phrase('the card says "{summary:Q}"'))
def the_card_says(world, summary):
    outcomes = [event for event in assistant(world).events if event["type"] == "tool_outcome"]
    assert [readable(world, outcome["summary"]) for outcome in outcomes][-1:] == [summary], assistant(world).events


@then(phrase('every card says "{summary:Q}"'))
def every_card_says(world, summary):
    outcomes = [event for event in assistant(world).events if event["type"] == "tool_outcome"]
    assert len(outcomes) == len(assistant(world).cards), outcomes
    assert {readable(world, outcome["summary"]) for outcome in outcomes} == {summary}, outcomes


# ---------------------------------------------------------------------------
# Instructions


def _instructions(world) -> str:
    return assistant(world).model.instructions()


@then(phrase('the assistant\'s instructions start with "{text:Q}"'))
def instructions_start_with(world, text):
    assert _instructions(world).startswith(text), _instructions(world)[:200]


@then("the assistant's instructions say, in this order:")
def instructions_in_order(world, datatable):
    instructions = _instructions(world)
    positions = [instructions.find(row[0]) for row in datatable]
    assert -1 not in positions, list(zip([row[0] for row in datatable], positions, strict=True))
    assert positions == sorted(positions), positions


@then(phrase('the assistant\'s instructions include the AI context "{label:Q}"'))
def instructions_include_context(world, label):
    document = world.record(label)
    assert f"## {document.name} ({document.pk})\n{document.body}" in _instructions(world)


@then(phrase('the assistant\'s instructions do not include the AI context "{label:Q}"'))
def instructions_exclude_context(world, label):
    document = world.record(label)
    assert document.name not in _instructions(world)
    assert document.body not in _instructions(world)


@then(phrase('the assistant\'s instructions do not mention "{text:Q}"'))
def instructions_do_not_mention(world, text):
    assert text not in _instructions(world)


@then("the assistant is offered exactly these tools:")
def offered_exactly(world, datatable):
    assert assistant(world).model.tool_names() == {row[0] for row in datatable}, assistant(world).model.tool_names()


@then(phrase("the assistant is offered {tool:Words}"))
def offered(world, tool):
    assert tool in assistant(world).model.tool_names()


@then(phrase("the assistant is not offered {tools:List}"))
def not_offered(world, tools):
    assert not set(tools) & assistant(world).model.tool_names(), assistant(world).model.tool_names()


@then(phrase("the assistant works with a temperature of {temperature:f}"))
def temperature(world, temperature):
    assert assistant(world).model.latest()[1].model_settings["temperature"] == temperature


@then(phrase("the tool {tool:Words} ran"))
def tool_ran(world, tool):
    returns = assistant(world).model.tool_returns()
    assert [part.tool_name for part in returns] == [tool], returns
    assert not str(returns[0].content).startswith("ERROR"), returns[0].content
