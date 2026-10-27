"""The change stream: the socket that tells open browsers a record changed, so
they can refetch it.

Scenarios that use it are tagged @transactional: hints are only sent once a
change is committed.

Phrases:
- `Given Alice is watching the change stream` (signed in, ready)
- `When Alice connects to the change stream` / `... with her token`
- `Given someone connects to the change stream without signing in`, then
  `When they send a message that is not a sign-in`, `... sign in without a token`,
  `... sign in with a forged token`, `... sign in with Alice's token`, `... send something that is not JSON`
- `When someone connects to the change stream and stays silent for five seconds`
- `Given live updates are switched off`
- `When a change to "Acme" is abandoned before it is saved`
- `Then Alice's change stream is ready`, `Then Alice hears that "Acme" was saved by Bob`,
  `Then Alice hears that a customer was removed`, `Then Alice hears nothing more`
- `Then the change stream tells them "Invalid token."`, `Then the change stream stays open`,
  `Then the change stream closes because signing in failed` / `because live updates are switched off`
"""

import asyncio
import json

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings as django_settings
from django.db import transaction
from django.test import Client
from pytest_bdd import given, then, when
from rest_framework_simplejwt.tokens import AccessToken

from crudkit_api import ws_auth
from crudkit_api.routing import websocket_urlpatterns
from tests.bdd.world import phrase

IN_MEMORY_LAYER = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
ROUTE = "/ws/changes/"
UNAUTHENTICATED = 4001
UNAVAILABLE = 4503
ANONYMOUS = "someone"


class ChangeStream:
    """One browser's socket, driven from synchronous steps on an event loop of its own.

    The loop only runs while a step waits on the socket, so hints sent from a
    save in between are queued on it and delivered at the next wait."""

    def __init__(self, cookies: str = ""):
        self.loop = asyncio.new_event_loop()
        headers = [(b"cookie", cookies.encode())] if cookies else []
        self.communicator = self._run(self._open(headers))

    async def _open(self, headers):
        communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), ROUTE, headers=headers)
        connected, _ = await communicator.connect()
        assert connected
        return communicator

    def _run(self, awaitable):
        return self.loop.run_until_complete(awaitable)

    def send(self, text: str):
        self._run(self.communicator.send_to(text_data=text))

    def receive(self) -> dict:
        output = self._run(self.communicator.receive_output(timeout=2))
        if output["type"] == "websocket.close":
            return {"closed": output.get("code")}
        return json.loads(output["text"])

    def is_quiet(self) -> bool:
        return self._run(self.communicator.receive_nothing(timeout=0.3))

    def close(self):
        self._run(self.communicator.disconnect())
        self._run(_cancel_other_tasks())
        self.loop.close()


async def _cancel_other_tasks():
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _open(world, request, settings, key, cookies=""):
    if not getattr(world, "live_updates_off", False):
        settings.CHANNEL_LAYERS = IN_MEMORY_LAYER
    stream = ChangeStream(cookies)
    request.addfinalizer(stream.close)
    world.streams = {**getattr(world, "streams", {}), key: stream}
    return stream


def _session_cookie(world, name) -> str:
    client = Client()
    client.force_login(world.user(name))
    cookie = django_settings.SESSION_COOKIE_NAME
    return f"{cookie}={client.cookies[cookie].value}"


def _stream(world, key):
    return world.streams[key]


def _token(world, name) -> str:
    return str(AccessToken.for_user(world.user(name)))


# Connecting


@given(phrase("live updates are switched off"))
def live_updates_off(world, settings):
    world.live_updates_off = True
    settings.CHANNEL_LAYERS = {}


@given(phrase("{name:Actor} is watching the change stream"))
def watching(world, request, settings, name):
    stream = _open(world, request, settings, name, _session_cookie(world, name))
    assert stream.receive() == {"type": "ready"}


@when(phrase("{name:Actor} connects to the change stream"))
def connect_signed_in(world, request, settings, name):
    _open(world, request, settings, name, _session_cookie(world, name))


@when(phrase("{name:Actor} connects to the change stream with {whose:Their} token"))
def connect_with_token(world, request, settings, name, whose):
    _open(world, request, settings, name).send(json.dumps({"type": "auth", "token": _token(world, name)}))


@given(phrase("someone connects to the change stream without signing in"))
def connect_anonymously(world, request, settings):
    _open(world, request, settings, ANONYMOUS)


@when(phrase("someone connects to the change stream and stays silent for five seconds"))
def connect_and_stay_silent(world, request, settings, monkeypatch):
    assert ws_auth.AUTH_TIMEOUT_SECONDS == 5
    # Five seconds pass in an instant.
    monkeypatch.setattr(ws_auth, "AUTH_TIMEOUT_SECONDS", 0.01)
    _open(world, request, settings, ANONYMOUS)


@when(phrase("they send a message that is not a sign-in"))
def send_other_message(world):
    _stream(world, ANONYMOUS).send(json.dumps({"type": "subscribe"}))


@when(phrase("they sign in without a token"))
def sign_in_without_token(world):
    _stream(world, ANONYMOUS).send(json.dumps({"type": "auth"}))


@when(phrase("they sign in with a forged token"))
def sign_in_with_forged_token(world):
    _stream(world, ANONYMOUS).send(json.dumps({"type": "auth", "token": "forged.token.value"}))


@when(phrase("they sign in with {name:Actor}'s token"))
def sign_in_with_token_of(world, name):
    _stream(world, ANONYMOUS).send(json.dumps({"type": "auth", "token": _token(world, name)}))


@when(phrase("they send something that is not JSON"))
def send_garbage(world):
    _stream(world, ANONYMOUS).send("hello?")


# Changes


@when(phrase('a change to "{label:Q}" is abandoned before it is saved'))
def abandoned_change(world, label):
    with transaction.atomic():
        instance = world.record(label)
        instance.save()
        transaction.set_rollback(True)


# What the socket says


def _hint(world, name) -> dict:
    message = _stream(world, name).receive()
    assert message.get("type") == "change", message
    return message


@then(phrase("{name:Actor}'s change stream is ready"))
def is_ready(world, name):
    assert _stream(world, name).receive() == {"type": "ready"}


@then(phrase('{name:Actor} hears that "{label:Q}" was saved by {editor:Actor}'))
def hears_saved_by(world, name, label, editor):
    instance = world.records[label]
    expected = {"type": "change", "model": instance.TYPE_ID, "id": instance.pk, "action": "saved"}
    assert _hint(world, name) == {**expected, "by": world.user(editor).pk}


@then(phrase('{name:Actor} hears that "{label:Q}" was saved'))
def hears_saved(world, name, label):
    instance = world.records[label]
    hint = _hint(world, name)
    assert (hint["model"], hint["id"], hint["action"]) == (instance.TYPE_ID, instance.pk, "saved"), hint


@then(phrase("{name:Actor} hears that a {model:Model} was removed"))
def hears_removed(world, name, model):
    assert _hint(world, name) == {"type": "change", "model": model.TYPE_ID, "id": None, "action": "deleted", "by": None}


@then(phrase("{name:Actor} hears nothing more"))
@then(phrase("{name:Actor} hears nothing"))
def hears_nothing(world, name):
    assert _stream(world, name).is_quiet()


@then(phrase('the change stream tells them "{message:Q}"'))
def tells_them(world, message):
    assert _stream(world, ANONYMOUS).receive() == {"type": "error", "message": message}


@then(phrase("the change stream stays open"))
def stays_open(world):
    assert _stream(world, ANONYMOUS).is_quiet()


@then(phrase("the change stream closes because signing in failed"))
def closed_unauthenticated(world):
    assert _stream(world, ANONYMOUS).receive() == {"closed": UNAUTHENTICATED}


@then(phrase("{name:Actor}'s change stream closes because live updates are switched off"))
def closed_unavailable(world, name):
    assert _stream(world, name).receive() == {"closed": UNAVAILABLE}
