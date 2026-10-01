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
from pydantic_ai.messages import ModelResponse, SystemPromptPart, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import DeltaThinkingPart, DeltaToolCall, FunctionModel
from rest_framework_simplejwt.tokens import AccessToken

from crudkit.models import AIContext, View
from crudkit_assistant import tools
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import AssistantConversation, AssistantProposal
from crudkit_assistant.routing import websocket_urlpatterns
from crudkit_assistant.screen import MAX_IDS, Screen, describe_screen, parse_screen
from tests.testapp.models import Comment, Customer, Ticket

User = get_user_model()


def grant(user, *codenames):
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))


def make_customer(user, name):
    return Customer.objects.create(name=name, created_by=user, updated_by=user)


def make_ai_context(user, name, body, model_types=()):
    return AIContext.objects.create(
        name=name, body=body, model_types=list(model_types), created_by=user, updated_by=user
    )


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
        self.assertTrue(self.run_tool(tools.get_object).startswith("ERROR: No record is open"))
        self.assertTrue(self.run_tool(tools.get_related, "notes", id=self.other.pk).startswith("ERROR: Unknown"))
        self.assertIn("Other", self.run_tool(tools.get_object, id=self.other.pk))

    def test_related_records_are_listed_and_followable(self):
        grant(self.user, "view_ticket", "view_comment")
        ticket = Ticket.objects.create(
            customer=self.other, subject="Broken", created_by=self.user, updated_by=self.user
        )
        Ticket.objects.create(
            customer=self.other, subject="Gone", deleted=True, created_by=self.user, updated_by=self.user
        )
        Comment.objects.create(ticket=ticket, body="Still broken", created_by=self.user, updated_by=self.user)

        related = self.run_tool(tools.describe_object, id=self.other.pk)["related"]
        self.assertEqual(related, [{"relation": "ticket_set", "type": "TIC", "field": "customer", "count": 1}])
        for name in ("ticket_set", "ticket", "TIC"):
            rows = self.run_tool(tools.get_related, name, id=self.other.pk)
            self.assertEqual([row["id"] for row in rows], [ticket.pk])
        error = self.run_tool(tools.get_related, "case_set", id=self.other.pk)
        self.assertIn("Valid: ['ticket_set (TIC)']", error)
        # Rows name the records they point at by id, so the assistant can follow them.
        comment = self.run_tool(tools.get_related, "comment_set", id=ticket.pk)[0]
        self.assertIn(f"ticket: Broken ({ticket.pk})", comment["context"])

    def test_related_types_the_user_cannot_view_are_left_out(self):
        Ticket.objects.create(customer=self.other, subject="Broken", created_by=self.user, updated_by=self.user)
        self.assertEqual(self.run_tool(tools.describe_object, id=self.other.pk)["related"], [])
        self.assertTrue(self.run_tool(tools.get_related, "ticket_set", id=self.other.pk).startswith("ERROR"))

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


class BulkPatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="x")
        grant(self.user, "view_customer", "change_customer")
        self.customers = [make_customer(self.user, name) for name in ("Acme", "Beta", "Gamma")]
        self.ids = [c.pk for c in self.customers]
        self.deps = AssistantDeps(user_id=self.user.pk, session_key="s1", screen=Screen(route="list", type_id="CUS"))
        self.deps._outbox = asyncio.Queue()  # type: ignore[attr-defined]

    def run_tool(self, *args, **kwargs):
        return async_to_sync(tools.propose_bulk_patch)(_FakeCtx(self.deps), *args, **kwargs)

    def envelopes(self):
        out = []
        while not self.deps._outbox.empty():  # type: ignore[attr-defined]
            out.append(self.deps._outbox.get_nowait())  # type: ignore[attr-defined]
        return out

    def test_one_pending_proposal_per_record(self):
        result = self.run_tool(self.ids, {"status": "churned"}, reasoning="Lost them")
        proposals = AssistantProposal.objects.filter(session_key="s1").order_by("pk")
        self.assertEqual([p.target for p in proposals], self.customers)
        self.assertTrue(all(p.status == AssistantProposal.Status.PENDING for p in proposals))
        self.assertEqual({p.kind for p in proposals}, {AssistantProposal.Kind.PATCH})
        self.assertEqual(proposals[0].payload, {"fields": {"status": "churned"}})
        self.assertEqual(proposals[0].reasoning, "Lost them")
        self.assertEqual([e["target"] for e in self.envelopes()], self.ids)
        self.assertIn("3 proposal(s)", result)
        self.assertEqual(set(Customer.objects.values_list("status", flat=True)), {"active"})

    def test_rejects_unknown_fields_and_invalid_choices(self):
        for fields in ({"nope": 1}, {"status": "gone"}):
            result = self.run_tool(self.ids, fields)
            self.assertTrue(result.startswith("ERROR"), result)
        self.assertIn("valid: ['active', 'churned']", result)
        self.assertFalse(AssistantProposal.objects.exists())
        self.assertEqual(self.envelopes(), [])

    def test_refused_ids_are_reported_and_the_rest_proposed(self):
        hidden = self.customers[1]
        with hide(hidden):
            result = self.run_tool([*self.ids, "bad"], {"status": "churned"})
        self.assertEqual([e["target"] for e in self.envelopes()], [self.ids[0], self.ids[2]])
        self.assertIn(f"{hidden.pk} not found, or not available for change.", result)
        self.assertIn("Invalid id 'bad'", result)
        self.assertFalse(result.startswith("ERROR"))

    def test_nothing_proposed_without_change_permission(self):
        self.user.user_permissions.remove(Permission.objects.get(codename="change_customer"))
        result = self.run_tool(self.ids, {"status": "churned"})
        self.assertTrue(result.startswith("ERROR"))
        self.assertFalse(AssistantProposal.objects.exists())

    def test_records_already_set_are_skipped(self):
        Customer.objects.filter(pk=self.ids[0]).update(status="churned")
        result = self.run_tool(self.ids, {"status": "churned"})
        self.assertEqual([e["target"] for e in self.envelopes()], self.ids[1:])
        self.assertIn(f"Already set, not proposed: {self.ids[0]}.", result)

    def test_caps_the_number_of_ids(self):
        result = self.run_tool([f"CUS{i}" for i in range(1, tools.MAX_BULK_IDS + 2)], {"status": "churned"})
        self.assertTrue(result.startswith("ERROR: at most"))

    def test_label(self):
        self.assertEqual(tools.describe_call("propose_bulk_patch", {"ids": self.ids}), "Drafting changes to 3 records")


class ConversationSocketTests(TransactionTestCase):
    """open_conversation → screen → user_message → proposal → confirm → reopen."""

    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="x")
        grant(self.user, "view_customer", "change_customer")
        self.customer = make_customer(self.user, "Acme")
        self.other = make_customer(self.user, "Beta")
        make_ai_context(self.user, "Ideal customer", "Small agencies.")
        make_ai_context(self.user, "Churn playbook", "Call before renewal.", model_types=["CUS"])
        make_ai_context(self.user, "Ticket triage", "Billing first.", model_types=["TIC"])
        self.prompts: list[str] = []
        self.instructions: list[str] = []
        # Set by a test to hold the model's answer after its tool calls.
        self.release: asyncio.Event | None = None

    def model_fn(self, messages, info):
        # One instructions part (sent as one system message), no system parts in the
        # history: chat templates like Qwen's reject a system message after the first.
        parts = info.model_request_parameters.instruction_parts
        self.assertEqual(len(parts), 1)
        self.assertIn("Your name is", parts[0].content)
        self.assertIn("# Company context\n\n", parts[0].content)
        self.assertIn("## Ideal customer (AIC", parts[0].content)
        self.instructions.append(parts[0].content)
        self.assertFalse(any(isinstance(part, SystemPromptPart) for message in messages for part in message.parts))
        last = messages[-1].parts[-1]
        if isinstance(last, UserPromptPart):
            self.prompts.append(last.content)
            if "churn all" in last.content:
                ids = [self.customer.pk, self.other.pk]
                return ModelResponse(
                    parts=[ToolCallPart("propose_bulk_patch", {"ids": ids, "fields": {"status": "churned"}})]
                )
            if "rename both" in last.content:
                return ModelResponse(
                    parts=[
                        ToolCallPart("propose_patch", {"fields": {"name": f"{c.name} Inc"}, "id": c.pk})
                        for c in (self.customer, self.other)
                    ]
                )
            if "rename" in last.content:
                return ModelResponse(
                    parts=[ToolCallPart("propose_patch", {"fields": {"name": "Acme Inc"}, "id": self.customer.pk})]
                )
            return ModelResponse(parts=[TextPart("Noted.")])
        return ModelResponse(parts=[TextPart("I proposed a rename.")])

    async def stream_fn(self, messages, info):
        """model_fn's response, streamed after a little reasoning."""
        if self.release is not None and not isinstance(messages[-1].parts[-1], UserPromptPart):
            await self.release.wait()
        response = self.model_fn(messages, info)
        yield {0: DeltaThinkingPart(content="Checking the screen.")}
        for index, part in enumerate(response.parts, start=1):
            if isinstance(part, TextPart):
                yield part.content
            else:
                yield {index: DeltaToolCall(name=part.tool_name, json_args=part.args_as_json_str())}

    @asynccontextmanager
    async def fake_factory(self):
        yield FunctionModel(self.model_fn, stream_function=self.stream_fn)

    async def receive_turn(self, ws) -> list[dict]:
        """The events of one streamed turn, turn_start through turn_end."""
        events = [await ws.receive_json_from()]
        self.assertEqual(events[0]["type"], "turn_start")
        while events[-1]["type"] != "turn_end":
            events.append(await ws.receive_json_from())
        return events

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
            events = await self.receive_turn(ws)
            self.assertIn(f"Selected rows (1): {self.customer.pk}.", self.prompts[0])
            # Documents for the type on screen go in the instructions, not the stored user turn.
            self.assertIn("## Churn playbook (AIC", self.instructions[0])
            self.assertNotIn("Billing first.", self.instructions[0])
            self.assertNotIn("Call before renewal.", self.prompts[0])
            # Reasoning, the tool step and the proposal stream before the final reply.
            self.assertEqual(
                [event["type"] for event in events if not event["type"].endswith("_delta")],
                ["turn_start", "tool_start", "tool_end", "tool_call_pending", "assistant_message", "turn_end"],
            )
            by_type = {event["type"]: event for event in events}
            self.assertEqual(by_type["thinking_delta"]["text"], "Checking the screen.")
            self.assertEqual(by_type["tool_start"]["label"], f"Drafting a change to {self.customer.pk}")
            self.assertTrue(by_type["tool_end"]["ok"])
            self.assertEqual(by_type["tool_call_pending"]["target"], self.customer.pk)
            self.assertEqual(by_type["assistant_message"]["text"], "I proposed a rename.")
            streamed = "".join(event["text"] for event in events if event["type"] == "text_delta")
            self.assertEqual(streamed, "I proposed a rename.")

            await ws.send_json_to({"type": "confirm", "id": by_type["tool_call_pending"]["id"], "ok": True})
            outcome = await ws.receive_json_from()
            self.assertEqual((outcome["type"], outcome["ok"]), ("tool_outcome", True))
            self.assertTrue(await ws.receive_nothing())  # no model turn to acknowledge it

            # The outcome reaches the agent with the next message, once.
            await ws.send_json_to({"type": "user_message", "text": "thanks"})
            self.assertIn({"type": "assistant_message", "text": "Noted."}, await self.receive_turn(ws))
            self.assertIn("[system] Outcome of proposal", self.prompts[-1])
            self.assertTrue(self.prompts[-1].endswith("thanks"))
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
                ("activity", None),
                ("proposal", "confirmed"),
                ("assistant", "I proposed a rename."),
                ("user", "thanks"),
                ("assistant", "Noted."),
            ],
        )
        self.assertEqual(reopened["transcript"][1]["steps"][0]["label"], f"Drafting a change to {self.customer.pk}")
        conversation = await AssistantConversation.objects.aget(pk=opened["id"])
        self.assertGreater(len(conversation.messages), 4)

    async def test_confirm_all_applies_while_the_turn_is_still_running(self):
        self.release = asyncio.Event()
        with patch("tests.testapp.ai.create_model", self.fake_factory):
            ws = await self.connect()
            await ws.send_json_to({"type": "open_conversation", "id": None})
            await ws.receive_json_from()
            await ws.send_json_to({"type": "user_message", "text": "rename both"})
            pending = []
            while len(pending) < 2:
                event = await ws.receive_json_from()
                if event["type"] == "tool_call_pending":
                    pending.append(event["id"])

            # The model is still busy; confirming must not wait for it. The two tool calls
            # run concurrently, so the turn's own events (e.g. the second tool_end) may
            # still interleave with the outcomes.
            await ws.send_json_to({"type": "confirm", "ids": pending, "ok": True})
            outcomes = []
            while len(outcomes) < 2:
                event = await ws.receive_json_from()
                self.assertNotEqual(event["type"], "turn_end")
                if event["type"] == "tool_outcome":
                    outcomes.append(event)
            self.assertEqual([o["ok"] for o in outcomes], [True, True])
            self.assertEqual({c.name async for c in Customer.objects.all()}, {"Acme Inc", "Beta Inc"})

            self.release.set()
            while (await ws.receive_json_from())["type"] != "turn_end":
                pass
            await ws.send_json_to({"type": "user_message", "text": "ok"})
            await self.receive_turn(ws)
            await ws.disconnect()

        with_outcomes = [prompt for prompt in self.prompts if "[system] Outcome" in prompt]
        self.assertEqual(len(with_outcomes), 1)
        self.assertEqual(with_outcomes[0].count("[system] Outcome"), 2)

    async def test_bulk_patch_streams_a_card_per_record(self):
        with patch("tests.testapp.ai.create_model", self.fake_factory):
            ws = await self.connect()
            await ws.send_json_to({"type": "open_conversation", "id": None})
            await ws.receive_json_from()
            await ws.send_json_to({"type": "user_message", "text": "churn all of them"})
            events = await self.receive_turn(ws)
            starts = [event for event in events if event["type"] == "tool_start"]
            self.assertEqual([event["label"] for event in starts], ["Drafting changes to 2 records"])
            pending = [event for event in events if event["type"] == "tool_call_pending"]
            self.assertEqual([event["target"] for event in pending], [self.customer.pk, self.other.pk])

            await ws.send_json_to({"type": "confirm", "ids": [event["id"] for event in pending], "ok": True})
            outcomes = [await ws.receive_json_from() for _ in pending]
            await ws.disconnect()

        self.assertEqual([(o["type"], o["ok"]) for o in outcomes], [("tool_outcome", True)] * 2)
        self.assertEqual({c.status async for c in Customer.objects.all()}, {"churned"})

    async def test_new_conversation_waits_for_the_running_turn(self):
        self.release = asyncio.Event()
        with patch("tests.testapp.ai.create_model", self.fake_factory):
            ws = await self.connect()
            await ws.send_json_to({"type": "open_conversation", "id": None})
            first = await ws.receive_json_from()
            await ws.send_json_to({"type": "user_message", "text": "rename it"})
            while (await ws.receive_json_from())["type"] != "tool_call_pending":
                pass

            await ws.send_json_to({"type": "open_conversation", "id": None})
            self.release.set()
            events = [await ws.receive_json_from()]
            while events[-1]["type"] != "conversation":
                events.append(await ws.receive_json_from())
            await ws.disconnect()

        self.assertIn("turn_end", [event["type"] for event in events])
        self.assertEqual(events[-1]["transcript"], [])
        conversation = await AssistantConversation.objects.aget(pk=first["id"])
        self.assertEqual(
            [item["role"] for item in conversation.transcript], ["user", "activity", "proposal", "assistant"]
        )

    async def test_other_users_conversation_is_not_reopened(self):
        other = await User.objects.acreate(username="other")
        theirs = await AssistantConversation.objects.acreate(created_by=other, updated_by=other, title="secret")
        ws = await self.connect()
        await ws.send_json_to({"type": "open_conversation", "id": theirs.pk})
        opened = await ws.receive_json_from()
        await ws.disconnect()
        self.assertNotEqual(opened["id"], theirs.pk)
        self.assertEqual(opened["title"], "")
