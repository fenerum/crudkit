"""
Proposals can't be tampered with or applied twice, agents can't be turned
against the user they run as or set each other off, and the assistant's
proposal tools refuse what the serializer would silently mangle.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models.signals import post_save
from django.test import TestCase, override_settings, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from pydantic_ai import RunContext, Tool
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from rest_framework.test import APIClient

from crudkit.audit import audit
from crudkit.authorization import requires_approval
from crudkit.models import AIContext, ChangeLog
from crudkit_api import services
from crudkit_assistant import background, tools
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import Agent, AgentRun, AssistantProposal
from crudkit_assistant.proposals import create_proposal
from crudkit_assistant.runner import _load_extra_tools, run_turn
from crudkit_assistant.screen import Screen
from crudkit_assistant.tests.test_agents import AgentTestCase, User, _FakeCtx, grant
from tests.testapp.models import Customer, Ticket, Topic


def hide_from_non_superusers(customer):
    """Row rule: only superusers see (and so may change) `customer`."""
    return patch.object(
        Customer.CrudKitSettings,
        "get_authorized_queryset",
        staticmethod(lambda user, queryset, action: queryset.exclude(pk=customer.pk)),
        create=True,
    )


def propose_rename(user, customer, name="Renamed"):
    return create_proposal(user, Customer, customer, "patch", f"Rename to {name}", {"fields": {"name": name}})


class ProposalTamperingTests(TestCase):
    def setUp(self):
        self.low = User.objects.create_user("low")
        grant(self.low, Customer, "view", "change")
        self.admin = User.objects.create_superuser("admin")
        self.mine = Customer.objects.create(name="Mine", created_by=self.low, updated_by=self.low)
        self.victim = Customer.objects.create(name="Victim", created_by=self.admin, updated_by=self.admin)
        self.proposal = propose_rename(self.low, self.mine)
        self.api = APIClient()
        self.api.force_authenticate(self.low)
        self.admin_api = APIClient()
        self.admin_api.force_authenticate(self.admin)

    def test_a_filed_proposal_cannot_be_edited(self):
        for change in (
            {"payload": {"fields": {"name": "PWNED"}}},
            {"status": "pending", "kind": "action"},
            {"target": self.victim.id},
        ):
            response = self.api.patch(f"/api/v1/ASP/{self.proposal.id}/", change, format="json")
            self.assertEqual(response.status_code, 400, change)
        self.proposal.refresh_from_db()
        self.assertEqual((self.proposal.target, self.proposal.payload), (self.mine, {"fields": {"name": "Renamed"}}))

    def test_generic_target_must_be_visible(self):
        # A user who can add proposals still can't point one at a record they can't see.
        grant(self.low, AssistantProposal, "add")
        with hide_from_non_superusers(self.victim):
            response = self.api.post(
                "/api/v1/ASP/",
                {"target": self.victim.id, "kind": "patch", "label": "x", "payload": {"fields": {"name": "x"}}},
                format="json",
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("not found", str(response.json()))

    def test_confirm_needs_the_creator_to_be_allowed_too(self):
        # Filed directly (as a bug or another path might), aimed at a record the creator may not change.
        proposal = propose_rename(self.low, self.victim, "PWNED")
        with hide_from_non_superusers(self.victim):
            response = self.admin_api.post(f"/api/v1/ASP/{proposal.id}/action/", {"action": "confirm"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.victim.refresh_from_db()
        self.assertEqual(self.victim.name, "Victim")

    def test_a_superuser_may_confirm_what_the_creator_could_do(self):
        response = self.admin_api.post(f"/api/v1/ASP/{self.proposal.id}/action/", {"action": "confirm"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.name, "Renamed")


class ProposalRaceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user")
        grant(self.user, Customer, "view", "change")
        self.customer = Customer.objects.create(name="Acme", created_by=self.user, updated_by=self.user)

    def test_two_confirms_apply_once(self):
        proposal = create_proposal(self.user, Customer, self.customer, "action", "Churn", {"action": "mark_churned"})
        # Two tabs load the proposal while it is pending, then both confirm.
        first, second = AssistantProposal.objects.get(pk=proposal.pk), AssistantProposal.objects.get(pk=proposal.pk)
        self.assertNotIn("error", first.apply(self.user))
        self.assertTrue(second.apply(self.user)["already_resolved"])
        self.assertEqual(second.status, AssistantProposal.Status.CONFIRMED)
        actions = ChangeLog.objects.filter(action=ChangeLog.Action.ACTION, related_object_id=self.customer.pk)
        self.assertEqual(actions.count(), 1)

    def test_skip_after_confirm_is_refused(self):
        proposal = propose_rename(self.user, self.customer)
        stale = AssistantProposal.objects.get(pk=proposal.pk)
        proposal.apply(self.user)
        self.assertFalse(stale.mark_skipped(self.user))
        self.assertEqual(stale.status, AssistantProposal.Status.CONFIRMED)

    def test_a_fresh_proposal_passes_its_own_edit_check(self):
        # In memory its target id is a CK-ID ("CUS1"); stored it is 1.
        propose_rename(self.user, self.customer).clean()

    def test_skip_notifies_other_tabs(self):
        proposal = propose_rename(self.user, self.customer)
        saved = []

        def receiver(sender, instance, **kwargs):
            saved.append(instance.pk)

        post_save.connect(receiver, sender=AssistantProposal)
        try:
            self.assertTrue(proposal.mark_skipped(self.user))
        finally:
            post_save.disconnect(receiver, sender=AssistantProposal)
        self.assertEqual(saved, [proposal.pk])

    def test_a_failed_apply_is_marked_failed(self):
        proposal = create_proposal(self.user, Customer, self.customer, "action", "Nope", {"action": "no_such_action"})
        outcome = proposal.apply(self.user)
        self.assertIn("error", outcome)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, AssistantProposal.Status.FAILED)


class RevertApprovalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user")
        grant(self.user, Customer, "view", "change")
        self.customer = Customer.objects.create(name="Acme", created_by=self.user, updated_by=self.user)

    def change(self, fields):
        with audit("ui", user=self.user) as context:
            services.patch_fields(self.customer, fields, self.user)
        return context.change_set

    def revert_proposal(self, change_set):
        return create_proposal(
            self.user, Customer, self.customer, "revert", "Undo", {"change_set": str(change_set)}, source="agent"
        )

    def test_undoing_an_approval_field_needs_approval(self):
        change_set = self.change({"status": "churned"})
        with patch.object(Customer.CrudKitSettings, "approval_fields", ["status"], create=True):
            self.assertTrue(services.revert_requires_approval(change_set))
            self.assertTrue(self.revert_proposal(change_set).needs_approval())
        self.assertFalse(services.revert_requires_approval(change_set))

    def test_undoing_an_approval_required_action_needs_approval(self):
        with audit("ui", user=self.user) as context:
            services.perform_action(self.customer, "mark_churned", self.user)
        self.assertFalse(services.revert_requires_approval(context.change_set))
        with patch.object(Customer.mark_churned, "requires_approval", True):
            self.assertTrue(services.revert_requires_approval(context.change_set))


class AgentHardeningTests(AgentTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin")
        self.admin_api = APIClient()
        self.admin_api.force_authenticate(self.admin)

    def superuser_assigned_agent(self):
        agent = self.make_agent()
        response = self.admin_api.patch(f"/api/v1/AGT/{agent.id}/", {"run_as": self.admin.pk}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        return agent

    def test_owner_cannot_repurpose_an_agent_that_runs_as_someone_else(self):
        agent = self.superuser_assigned_agent()
        for change in ({"instructions": "Export everything"}, {"mode": "auto"}, {"model_type": "TOP"}):
            response = self.api.patch(f"/api/v1/AGT/{agent.id}/", change, format="json")
            self.assertEqual(response.status_code, 400, change)
        # Turning it off is fine.
        response = self.api.patch(f"/api/v1/AGT/{agent.id}/", {"enabled": False}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_owner_cannot_revert_their_way_back_to_the_superuser(self):
        agent = self.superuser_assigned_agent()
        with audit("ui", user=self.admin) as context:
            services.patch_fields(agent, {"run_as": self.user.pk}, self.admin)
        with self.assertRaisesRegex(ValueError, "Only superusers"):
            services.revert_change_set(context.change_set, self.user)
        agent.refresh_from_db()
        self.assertEqual(agent.run_as, self.user)

    def test_starting_runs_needs_approval_for_agents_and_mcp(self):
        self.assertTrue(requires_approval(Agent, action="run_now"))
        self.assertTrue(requires_approval(Agent, action="dry_run"))
        self.assertTrue(requires_approval(AgentRun, action="revert"))
        # A person still clicks them directly.
        agent = self.make_agent(trigger=Agent.Trigger.MANUAL, watch_fields=[])
        with self.model(), self.captureOnCommitCallbacks(execute=True):
            response = self.api.post(f"/api/v1/AGT/{agent.id}/action/", {"action": "run_now"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_auto_agent_cannot_set_off_an_agent(self):
        other = self.make_agent(name="Other", trigger=Agent.Trigger.MANUAL, watch_fields=[])
        self.calls = [ToolCallPart("propose_action", {"action_name": "run_now", "id": other.id})]
        agent = self.make_agent(mode=Agent.Mode.AUTO, trigger=Agent.Trigger.MANUAL, watch_fields=[])
        self.start(agent)  # one run per customer, each proposing run_now
        proposals = AssistantProposal.objects.filter(kind="action")
        self.assertEqual({p.status for p in proposals}, {AssistantProposal.Status.PENDING})
        self.assertEqual(proposals.count(), 2)
        self.assertFalse(other.runs.exists())

    def test_agents_only_work_on_exposed_types(self):
        for model_type in ("ASP", "CHG", "FEI", "AGR"):
            agent = Agent(
                name="x", instructions="x", model_type=model_type, trigger=Agent.Trigger.MANUAL, updated_by=self.user
            )
            with self.assertRaisesRegex(Exception, "can't work on"):
                agent.clean()

    def test_an_agent_on_a_type_excluded_since_can_still_be_disabled(self):
        agent = self.make_agent()
        Agent.objects.filter(pk=agent.pk).update(model_type="FEI", watch_fields=[])
        response = self.api.patch(f"/api/v1/AGT/{agent.id}/", {"enabled": False}, format="json")
        self.assertEqual(response.status_code, 200, response.content)

    @override_settings(CRUDKIT_MCP_MODELS=["TOP"])
    def test_the_mcp_allowlist_does_not_limit_agents(self):
        agent = self.make_agent()
        agent.model_type = "TOP"
        agent.watch_fields = []
        agent.clean()  # a type change is checked, against all exposed types

    def test_a_stuck_run_does_not_block_the_agent(self):
        agent = self.make_agent(watch_fields=[])
        stuck = AgentRun.objects.create(
            agent=agent,
            target_content_type=ContentType.objects.get_for_model(Customer),
            target_object_id=self.acme.pk,
            status=AgentRun.Status.RUNNING,
            created_by=self.user,
            updated_by=self.user,
        )
        AgentRun.objects.filter(pk=stuck.pk).update(created_at=timezone.now() - timedelta(hours=2))
        self.patch_customer(self.acme, {"name": "Acme 2"})
        self.assertEqual(agent.runs.count(), 2)

    def test_many_to_many_changes_trigger_watching_agents(self):
        grant(self.user, Ticket, "view", "change")
        ticket = Ticket.objects.create(subject="Help", created_by=self.user, updated_by=self.user)
        agent = self.make_agent(model_type="TIC", watch_fields=["watchers"])
        agent.updated_by = self.user
        agent.clean()
        with self.model(), self.captureOnCommitCallbacks(execute=True), audit("ui", user=self.user):
            ticket.watchers.add(self.acme)
        self.assertEqual(AgentRun.objects.get().trigger_info["fields"], ["watchers"])

    @skipUnlessDBFeature("has_select_for_update")
    def test_starting_runs_locks_the_agent(self):
        agent = self.make_agent(trigger=Agent.Trigger.MANUAL, watch_fields=[])
        with CaptureQueriesContext(connection) as queries, self.model(), self.captureOnCommitCallbacks(execute=True):
            background.enqueue_runs(agent)
        self.assertTrue(any("FOR UPDATE" in q["sql"] for q in queries.captured_queries))

    def test_reenabling_resets_the_failure_streak(self):
        agent = self.make_agent(enabled=False)
        Agent.objects.filter(pk=agent.pk).update(consecutive_failures=3)
        agent.refresh_from_db()
        agent.enabled = True
        agent.save()
        agent.refresh_from_db()
        self.assertEqual(agent.consecutive_failures, 0)

    def test_a_burst_of_changes_runs_the_agent_once(self):
        self.make_agent(watch_fields=[])
        with self.model():
            with self.captureOnCommitCallbacks() as callbacks, audit("ui", user=self.user):
                services.patch_fields(self.acme, {"name": "A1"}, self.user)
                services.patch_fields(self.acme, {"name": "A2"}, self.user)
            # Run the enqueue callbacks first, then the dispatch they register, as a worker would later.
            with patch.object(background, "_dispatch"):
                for callback in callbacks:
                    callback()
        self.assertEqual(AgentRun.objects.count(), 1)

    def test_a_broken_agent_does_not_fail_the_write(self):
        self.make_agent(watch_fields=[])
        with patch.object(background, "matching_records", side_effect=RuntimeError("bad view")):
            response = self.api.patch(f"/api/v1/CUS/{self.acme.id}/", {"name": "Still saved"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.acme.refresh_from_db()
        self.assertEqual(self.acme.name, "Still saved")

    def test_schedules_work_through_the_whole_view(self):
        agent = self.make_agent(
            trigger=Agent.Trigger.SCHEDULE, schedule=Agent.Schedule.HOURLY, watch_fields=[], max_records_per_run=1
        )
        now = timezone.now()
        with self.model(), self.captureOnCommitCallbacks(execute=True):
            background.run_scheduled_agents(now)
            background.run_scheduled_agents(now + timedelta(hours=1))
        self.assertEqual({run.target for run in agent.runs.all()}, {self.acme, self.beta})

    def test_overlapping_schedule_ticks_start_once(self):
        agent = self.make_agent(trigger=Agent.Trigger.SCHEDULE, schedule=Agent.Schedule.HOURLY, watch_fields=[])
        stale = Agent.objects.get(pk=agent.pk)
        now = timezone.now()
        real_filter = Agent.objects.filter

        def second_process_filter(*args, **kwargs):
            # It listed the due agents before the first process claimed this one.
            return [stale] if kwargs.get("trigger") == Agent.Trigger.SCHEDULE else real_filter(*args, **kwargs)

        with self.model(), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(background.run_scheduled_agents(now), 2)
            with patch.object(Agent.objects, "filter", side_effect=second_process_filter):
                self.assertEqual(background.run_scheduled_agents(now), 0)
        self.assertEqual(agent.runs.count(), 2)  # both customers, once

    def test_runs_today_without_time_zones(self):
        agent = self.make_agent()
        with self.settings(USE_TZ=False):
            self.assertEqual(background.runs_today(agent), 0)

    def test_agent_runs_skip_project_tools(self):
        with patch.object(Customer.CrudKitSettings, "assistant_tools", [lambda ctx: "x"], create=True):
            chat = AssistantDeps(user_id=self.user.pk, session_key="s", screen=Screen(record_id=self.acme.id))
            agent = AssistantDeps(
                user_id=self.user.pk, session_key="s", screen=Screen(record_id=self.acme.id), source="agent"
            )
            self.assertEqual(len(_load_extra_tools(chat)), 1)
            self.assertEqual(_load_extra_tools(agent), [])

    def test_ai_context_teaching_is_for_the_chat_only(self):
        agent = self.make_agent(trigger=Agent.Trigger.MANUAL, watch_fields=[])
        self.start(agent)
        self.assertNotIn('propose_patch(id="AIC', self.instructions[0])


class ProjectToolTests(TestCase):
    def test_project_tools_run_in_the_chat(self):
        user = User.objects.create_user("user")
        grant(user, Customer, "view")
        customer = Customer.objects.create(name="Acme", created_by=user, updated_by=user)
        ran = []

        def ping(ctx: RunContext[AssistantDeps]) -> str:
            ran.append(ctx.deps.screen.record_id)
            return "pong"

        def model_fn(messages, info):
            if isinstance(messages[-1].parts[-1], UserPromptPart):
                return ModelResponse(parts=[ToolCallPart(tool_name="ping", args={})])
            return ModelResponse(parts=[TextPart("Pinged.")])

        @asynccontextmanager
        async def fake_factory():
            yield FunctionModel(model_fn)

        deps = AssistantDeps(user_id=user.pk, session_key="s", screen=Screen(record_id=customer.id))
        with (
            patch("tests.testapp.ai.create_model", fake_factory),
            patch.object(Customer.CrudKitSettings, "assistant_tools", [Tool(ping)], create=True),
        ):
            async_to_sync(run_turn)("Ping it", deps)
        self.assertEqual(ran, [customer.id])


class ProposalToolTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user")
        grant(self.user, Customer, "view", "change")
        grant(self.user, Topic, "view")
        self.customer = Customer.objects.create(name="Acme", created_by=self.user, updated_by=self.user)
        self.deps = AssistantDeps(user_id=self.user.pk, session_key="s", screen=Screen(record_id=self.customer.id))
        self.deps._outbox = asyncio.Queue()  # type: ignore[attr-defined]

    def run_tool(self, tool, *args, **kwargs):
        return async_to_sync(tool)(_FakeCtx(self.deps), *args, **kwargs)

    def test_unknown_foreign_key_is_refused(self):
        for tool, args in (
            (tools.propose_patch, ({"topic": "TOP999999"},)),
            (tools.propose_bulk_patch, ([self.customer.id], {"topic": "TOP999999"})),
        ):
            self.assertIn("not found", self.run_tool(tool, *args))
        self.assertFalse(AssistantProposal.objects.exists())

    def test_foreign_key_in_describe_object_shape_is_accepted(self):
        topic = Topic.objects.create(name="Billing", created_by=self.user, updated_by=self.user)
        result = self.run_tool(tools.propose_patch, {"topic": {"id": topic.id, "display": "Billing"}})
        self.assertIn("awaiting user confirmation", result)

    def test_read_only_fields_are_refused(self):
        for fields in ({"deleted": True}, {"created_by": self.user.pk}):
            self.assertIn("read-only", self.run_tool(tools.propose_bulk_patch, [self.customer.id], fields))
        self.assertFalse(AssistantProposal.objects.exists())

    def test_crudkit_bookkeeping_is_off_limits(self):
        proposal = propose_rename(self.user, self.customer)
        grant(self.user, AssistantProposal, "change")
        result = self.run_tool(tools.propose_action, "confirm", id=proposal.id)
        self.assertIn("can't be changed by the assistant", result)

    @override_settings(CRUDKIT_MCP_MODELS=["TOP"])
    def test_the_mcp_allowlist_does_not_limit_the_sidebar(self):
        self.assertIn("awaiting", self.run_tool(tools.propose_patch, {"name": "Acme Inc"}))

    def test_change_history_needs_its_permission(self):
        self.assertIn("may not view change history", self.run_tool(tools.get_changelog))

    def test_ai_context_edits_are_proposals_everywhere_but_the_ui(self):
        self.assertTrue(requires_approval(AIContext, fields=["body"]))
        doc = AIContext.objects.create(name="ICP", body="SMBs", created_by=self.user, updated_by=self.user)
        grant(self.user, AIContext, "view", "change")
        self.assertIn("awaiting", self.run_tool(tools.propose_patch, {"body": "Enterprises"}, id=doc.id))


class ProposalContentTypeTests(TestCase):
    def test_locked_fields_cover_the_target(self):
        self.assertIn("target_object_id", AssistantProposal.LOCKED_FIELDS)
        self.assertIn("target_content_type_id", AssistantProposal.LOCKED_FIELDS)
        self.assertIsNotNone(ContentType.objects.get_for_model(AssistantProposal))
