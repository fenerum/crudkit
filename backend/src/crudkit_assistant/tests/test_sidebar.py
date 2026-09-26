"""
The assistant sidebar: screen parsing, the `[Screen]` prompt block,
cross-record tools and persisted conversations over the WebSocket.
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, TransactionTestCase
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from rest_framework_simplejwt.tokens import AccessToken

from crudkit.models import View
from crudkit_assistant import tools
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import AssistantConversation, AssistantProposal
from crudkit_assistant.routing import websocket_urlpatterns
from crudkit_assistant.screen import MAX_IDS, Screen, describe_screen, parse_screen
from tests.testapp.models import Customer

User = get_user_model()


def grant(user, *codenames):
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))


def make_customer(user, name):
    return Customer.objects.create(name=name, created_by=user, updated_by=user)


def hide(customer):
    """Row-level rule hiding one customer from everybody."""
    return patch.object(
        Customer.CrudKitSettings,
        "get_authorized_queryset",
        staticmethod(lambda user, queryset, action: queryset.exclude(pk=customer.pk)),
        create=True,
    )


class _FakeCtx:
    def __init__(self, deps):
        self.deps = deps


class ParseScreenTests(TestCase):
    def test_keeps_valid_fields(self):
        screen = parse_screen(
            {
                "route": "list",
                "type_id": "CUS",
                "view_id": "VIW3",
                "q": "acme",
                "filters": {"status": "active"},
                "page": "2",
                "visible_ids": ["CUS1", "CUS2"],
                "selected_ids": ["CUS2"],
            }
        )
        self.assertEqual(screen.route, "list")
        self.assertEqual(screen.type_id, "CUS")
        self.assertEqual(screen.view_id, "VIW3")
        self.assertEqual(screen.filters, {"status": "active"})
        self.assertEqual(screen.page, 2)
        self.assertEqual(screen.selected_ids, ["CUS2"])

    def test_drops_malformed_input(self):
        screen = parse_screen(
            {
                "route": "admin",
                "type_id": "XXX",
                "record_id": "CUS1; DROP",
                "page": "nope",
                "visible_ids": ["CUS1", 7, "bad", {"x": 1}],
                "filters": ["not", "a", "dict"],
            }
        )
        self.assertEqual(screen.route, "other")
        self.assertEqual(screen.type_id, "")
        self.assertEqual(screen.record_id, "")
        self.assertEqual(screen.page, 1)
        self.assertEqual(screen.visible_ids, ["CUS1"])
        self.assertEqual(screen.filters, {})
        self.assertEqual(parse_screen("garbage"), Screen())

    def test_caps_id_lists(self):
        screen = parse_screen({"visible_ids": [f"CUS{i}" for i in range(MAX_IDS + 50)]})
        self.assertEqual(len(screen.visible_ids), MAX_IDS)


class DescribeScreenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="x")
        grant(self.user, "view_customer", "view_view")
        self.customer = make_customer(self.user, "Acme")

    def test_open_record(self):
        block = describe_screen(self.user, Screen(route="detail", record_id=self.customer.pk, tab="properties"))
        self.assertIn(f"Open record: customer {self.customer.pk} (Acme), tab 'properties'.", block)

    def test_list_with_view_and_selection(self):
        view = View.objects.create(
            name="Churn risk", model="CUS", fields=["name"], public=True, created_by=self.user, updated_by=self.user
        )
        block = describe_screen(
            self.user,
            Screen(route="list", type_id="CUS", view_id=view.pk, q="ac", page=2, selected_ids=[self.customer.pk]),
        )
        self.assertIn(f"List of customers (CUS), saved view 'Churn risk' ({view.pk}), search 'ac', page 2.", block)
        self.assertIn(f"Selected rows (1): {self.customer.pk}.", block)

    def test_hidden_record_is_not_described(self):
        with hide(self.customer):
            block = describe_screen(self.user, Screen(route="detail", record_id=self.customer.pk))
        self.assertNotIn("Acme", block)


class CrossRecordToolTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="x")
        grant(self.user, "view_customer", "change_customer")
        self.open = make_customer(self.user, "Open")
        self.other = make_customer(self.user, "Other")
        self.deps = AssistantDeps(
            user_id=self.user.pk,
            session_key="s1",
            screen=Screen(route="list", type_id="CUS", selected_ids=[self.open.pk, self.other.pk]),
        )
        self.deps._outbox = asyncio.Queue()  # type: ignore[attr-defined]

    def run_tool(self, tool, *args, **kwargs):
        return async_to_sync(tool)(_FakeCtx(self.deps), *args, **kwargs)

    def test_record_tools_need_an_id_without_an_open_record(self):
        self.assertIn("No record is open", self.run_tool(tools.get_object))
        self.assertIn("Other", self.run_tool(tools.get_object, id=self.other.pk))

    def test_screen_rows_skip_hidden_records(self):
        with hide(self.other):
            rows = self.run_tool(tools.get_screen_rows)
        self.assertEqual([row["id"] for row in rows], [self.open.pk])

    def test_search_and_list(self):
        self.assertEqual([r["id"] for r in self.run_tool(tools.search, "Other")], [self.other.pk])
        listed = self.run_tool(tools.list_records, type="CUS")
        self.assertEqual(listed["total"], 2)
        self.assertIn("error", self.run_tool(tools.list_records, type="NOPE"))

    def test_propose_patch_on_another_record(self):
        result = self.run_tool(tools.propose_patch, {"name": "Renamed"}, id=self.other.pk)
        proposal = AssistantProposal.objects.get(session_key="s1")
        self.assertIn(str(proposal.id), result)
        self.assertEqual(proposal.target, self.other)
        envelope = self.deps._outbox.get_nowait()  # type: ignore[attr-defined]
        self.assertEqual((envelope["target"], envelope["target_label"]), (self.other.pk, "Other"))
        self.other.refresh_from_db()
        self.assertEqual(self.other.name, "Other")

    def test_propose_patch_refused_without_change_permission(self):
        self.user.user_permissions.remove(Permission.objects.get(codename="change_customer"))
        self.user = User.objects.get(pk=self.user.pk)  # drop the permission cache
        result = self.run_tool(tools.propose_patch, {"name": "Renamed"}, id=self.other.pk)
        self.assertTrue(result.startswith("ERROR"))
        self.assertFalse(AssistantProposal.objects.exists())


class ConversationSocketTests(TransactionTestCase):
    """open_conversation → screen → user_message → proposal → confirm → reopen."""

    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="x")
        grant(self.user, "view_customer", "change_customer")
        self.customer = make_customer(self.user, "Acme")
        self.prompts: list[str] = []

    def model_fn(self, messages, info):
        last = messages[-1].parts[-1]
        if isinstance(last, UserPromptPart):
            self.prompts.append(last.content)
            if "rename" in last.content:
                return ModelResponse(
                    parts=[ToolCallPart("propose_patch", {"fields": {"name": "Acme Inc"}, "id": self.customer.pk})]
                )
            return ModelResponse(parts=[TextPart("Noted.")])
        return ModelResponse(parts=[TextPart("I proposed a rename.")])

    @asynccontextmanager
    async def fake_factory(self):
        yield FunctionModel(self.model_fn)

    async def connect(self):
        communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), "/ws/assistant/")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.send_json_to({"type": "auth", "token": str(AccessToken.for_user(self.user))})
        self.assertEqual((await communicator.receive_json_from())["type"], "ready")
        return communicator

    async def test_conversation_round_trip(self):
        with patch("tests.testapp.ai.create_model", self.fake_factory):
            ws = await self.connect()
            await ws.send_json_to({"type": "open_conversation", "id": None})
            opened = await ws.receive_json_from()
            self.assertEqual((opened["type"], opened["transcript"]), ("conversation", []))

            await ws.send_json_to(
                {"type": "screen", "screen": {"route": "list", "type_id": "CUS", "selected_ids": [self.customer.pk]}}
            )
            await ws.send_json_to({"type": "user_message", "text": "rename the selected one"})
            pending = await ws.receive_json_from()
            self.assertEqual((pending["type"], pending["target"]), ("tool_call_pending", self.customer.pk))
            self.assertEqual((await ws.receive_json_from())["text"], "I proposed a rename.")
            self.assertIn(f"Selected rows (1): {self.customer.pk}.", self.prompts[0])

            await ws.send_json_to({"type": "confirm", "id": pending["id"], "ok": True})
            outcome = await ws.receive_json_from()
            self.assertEqual((outcome["type"], outcome["ok"]), ("tool_outcome", True))
            self.assertEqual((await ws.receive_json_from())["text"], "Noted.")
            await ws.disconnect()

            ws = await self.connect()
            await ws.send_json_to({"type": "open_conversation", "id": opened["id"]})
            reopened = await ws.receive_json_from()
            await ws.disconnect()

        self.assertEqual(reopened["id"], opened["id"])
        self.assertEqual(reopened["title"], "rename the selected one")
        roles = [(item["role"], item.get("text") or item.get("status")) for item in reopened["transcript"]]
        self.assertEqual(
            roles,
            [
                ("user", "rename the selected one"),
                ("proposal", "confirmed"),
                ("assistant", "I proposed a rename."),
                ("assistant", "Noted."),
            ],
        )
        conversation = await AssistantConversation.objects.aget(pk=opened["id"])
        self.assertGreater(len(conversation.messages), 4)

    async def test_other_users_conversation_is_not_reopened(self):
        other = await User.objects.acreate(username="other")
        theirs = await AssistantConversation.objects.acreate(created_by=other, updated_by=other, title="secret")
        ws = await self.connect()
        await ws.send_json_to({"type": "open_conversation", "id": theirs.pk})
        opened = await ws.receive_json_from()
        await ws.disconnect()
        self.assertNotEqual(opened["id"], theirs.pk)
        self.assertEqual(opened["title"], "")
