"""Background agents: what starts a run, what a run proposes or applies, dry
runs, schedules, guards, reverting a run, and creating agents from the sidebar."""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from rest_framework.test import APIClient

from crudkit.audit import audit
from crudkit.models import ChangeLog, FeedItem, View
from crudkit_api import services
from crudkit_assistant import background, tools
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import Agent, AgentRun, AssistantProposal
from crudkit_assistant.screen import Screen
from crudkit_assistant.tasks import run_scheduled_agents
from tests.testapp.models import Customer

User = get_user_model()


def grant(user, model, *actions):
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label=model._meta.app_label,
            codename__in=[f"{action}_{model._meta.model_name}" for action in actions],
        )
    )


def changes(instance):
    return ChangeLog.objects.filter(
        related_content_type=ContentType.objects.get_for_model(instance), related_object_id=instance.pk
    )


class _FakeCtx:
    def __init__(self, deps):
        self.deps = deps


class AgentTestCase(TestCase):
    def setUp(self):
        background.forget_record_agents()
        self.user = User.objects.create_user("owner")
        grant(self.user, Customer, "view", "add", "change")
        self.acme = self.make_customer("Acme")
        self.beta = self.make_customer("Beta")
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        # What the fake model does with a run's prompt: tool calls, or raise.
        self.calls: list[ToolCallPart] = []
        self.fail = False
        self.instructions: list[str] = []
        self.prompts: list[str] = []

    def make_customer(self, name):
        return Customer.objects.create(name=name, created_by=self.user, updated_by=self.user)

    def make_agent(self, **fields):
        defaults = {
            "name": "Renamer",
            "instructions": "Add Inc to the name.",
            "trigger": Agent.Trigger.RECORD_CHANGED,
            "model_type": "CUS",
            "watch_fields": ["status"],
            "created_by": self.user,
            "updated_by": self.user,
        }
        return Agent.objects.create(**(defaults | fields))

    def model_fn(self, messages, info):
        parts = info.model_request_parameters.instruction_parts
        self.assertEqual(len(parts), 1)
        self.instructions.append(parts[0].content)
        last = messages[-1].parts[-1]
        if isinstance(last, UserPromptPart):
            self.prompts.append(last.content)
            if self.fail:
                raise RuntimeError("The model is down")
            if self.calls:
                return ModelResponse(parts=list(self.calls))
            return ModelResponse(parts=[TextPart("Nothing to do.")])
        return ModelResponse(parts=[TextPart("Proposed a rename.")])

    @asynccontextmanager
    async def fake_factory(self):
        yield FunctionModel(self.model_fn)

    def model(self):
        return patch("tests.testapp.ai.create_model", self.fake_factory)

    def patch_customer(self, customer, fields, source="ui"):
        """A logged write, as the REST API makes it, with its on-commit hooks run."""
        with self.model(), self.captureOnCommitCallbacks(execute=True), audit(source, user=self.user):
            services.patch_fields(customer, fields, self.user)

    def start(self, agent):
        with self.model(), self.captureOnCommitCallbacks(execute=True):
            return background.enqueue_runs(agent)


class TriggerTests(AgentTestCase):
    def test_record_changed_needs_a_watched_field(self):
        self.make_agent()
        self.patch_customer(self.acme, {"name": "Acme 2"})
        self.assertFalse(AgentRun.objects.exists())

        self.patch_customer(self.acme, {"status": "churned"})
        run = AgentRun.objects.get()
        self.assertEqual((run.status, run.target, run.trigger_info["fields"]), ("succeeded", self.acme, ["status"]))
        self.assertIn("which just changed (status)", self.prompts[0])

    def test_action_changing_a_watched_field_triggers(self):
        self.make_agent()
        with self.model(), self.captureOnCommitCallbacks(execute=True), audit("ui", user=self.user):
            services.perform_action(self.acme, "mark_churned", self.user)
        run = AgentRun.objects.get()
        self.assertEqual((run.target, run.trigger_info["fields"]), (self.acme, ["status"]))

    def test_empty_watch_fields_match_any_change(self):
        self.make_agent(watch_fields=[])
        self.patch_customer(self.acme, {"name": "Acme 2"})
        self.assertEqual(AgentRun.objects.count(), 1)

    def test_record_must_be_in_the_view(self):
        view = View.objects.create(
            name="Acme only", model="CUS", fields=["name"], filters=[["name", "=", "Acme"]],
            created_by=self.user, updated_by=self.user,
        )  # fmt: skip
        self.make_agent(view=view)
        self.patch_customer(self.beta, {"status": "churned"})
        self.assertFalse(AgentRun.objects.exists())
        self.patch_customer(self.acme, {"status": "churned"})
        self.assertEqual(AgentRun.objects.get().target, self.acme)

    def test_record_created(self):
        self.make_agent(trigger=Agent.Trigger.RECORD_CREATED, watch_fields=[])
        self.patch_customer(self.acme, {"status": "churned"})
        self.assertFalse(AgentRun.objects.exists())
        with self.model(), self.captureOnCommitCallbacks(execute=True), audit("ui", user=self.user):
            created = services.create_object(Customer, {"name": "Gamma"}, self.user)
        self.assertEqual(AgentRun.objects.get().target, created)

    def test_disabled_agents_and_agent_changes_do_not_trigger(self):
        agent = self.make_agent()
        self.patch_customer(self.acme, {"status": "churned"}, source="agent")
        agent.enabled = False
        agent.save()
        self.patch_customer(self.beta, {"status": "churned"})
        self.assertFalse(AgentRun.objects.exists())

    def test_plain_orm_saves_do_not_trigger(self):
        self.make_agent()
        with self.captureOnCommitCallbacks(execute=True):
            Customer.objects.filter(pk=self.acme.pk).update(status="churned")
            self.beta.status = "churned"
            self.beta.save()
        self.assertFalse(AgentRun.objects.exists())

    def test_daily_cap(self):
        self.make_agent(max_runs_per_day=1)
        self.patch_customer(self.acme, {"status": "churned"})
        self.patch_customer(self.beta, {"status": "churned"})
        self.assertEqual(AgentRun.objects.count(), 1)


class RunTests(AgentTestCase):
    def test_propose_mode_leaves_pending_proposals(self):
        self.calls = [ToolCallPart("propose_patch", {"fields": {"name": "Acme Inc"}})]
        self.make_agent()
        self.patch_customer(self.acme, {"status": "churned"})

        run = AgentRun.objects.get()
        proposal = AssistantProposal.objects.get()
        self.assertEqual((proposal.status, proposal.source, proposal.client), ("pending", "agent", "Renamer"))
        self.assertEqual((proposal.target, proposal.session_key), (self.acme, run.session_key))
        self.assertEqual(run.output, "Proposed a rename.")
        self.assertEqual([(p["id"], p["label"]) for p in run.preview], [(proposal.id, 'Update name="Acme Inc"')])
        self.acme.refresh_from_db()
        self.assertEqual(self.acme.name, "Acme")

    def test_instructions_are_agent_mode_with_the_agents_instructions(self):
        self.make_agent()
        self.patch_customer(self.acme, {"status": "churned"})
        self.assertIn("You are a background agent", self.instructions[0])
        self.assertTrue(self.instructions[0].endswith("# Agent instructions\n\nAdd Inc to the name."))
        self.assertNotIn("Style:", self.instructions[0])
        self.assertTrue(self.prompts[0].startswith("[Screen]\nOpen record: customer"))

    def test_auto_mode_applies_all_but_approval_required(self):
        self.calls = [
            ToolCallPart("propose_patch", {"fields": {"name": "Acme Inc"}}),
            ToolCallPart("propose_patch", {"fields": {"email": "ceo@acme.test"}}),
        ]
        agent = self.make_agent(mode=Agent.Mode.AUTO, watch_fields=["name", "email"], max_records_per_run=1)
        self.acme.save()  # the newest record gets the run
        with patch.object(Customer.CrudKitSettings, "approval_fields", ["email"], create=True):
            [run] = self.start(agent)

        run.refresh_from_db()
        self.acme.refresh_from_db()
        self.assertEqual((self.acme.name, self.acme.email), ("Acme Inc", None))
        applied = changes(self.acme).get(change_set=run.change_set)
        self.assertEqual((applied.source, applied.client), ("agent", "Renamer"))
        self.assertEqual([p["status"] for p in run.preview], ["confirmed", "pending"])
        self.assertEqual(
            AssistantProposal.objects.get(status="pending").payload, {"fields": {"email": "ceo@acme.test"}}
        )
        # The applied rename touched a watched field, yet started no second run.
        self.assertEqual(AgentRun.objects.count(), 1)

    def test_dry_run_persists_nothing(self):
        self.calls = [ToolCallPart("propose_patch", {"fields": {"name": "Beta Inc"}})]
        agent = self.make_agent(mode=Agent.Mode.AUTO)
        logged = ChangeLog.objects.count()
        with self.model(), self.captureOnCommitCallbacks(execute=True):
            response = self.api.post(f"/api/v1/AGT/{agent.id}/action/", {"action": "dry_run"}, format="json")

        run = AgentRun.objects.get()
        self.assertEqual(response.data, {"redirect": run.id})
        self.assertEqual((run.dry_run, run.status, run.target), (True, "succeeded", self.beta))
        self.assertEqual(run.preview[0]["dry_run"], True)
        self.assertEqual(run.preview[0]["payload"], {"fields": {"name": "Beta Inc"}})
        self.assertIn("dry run", self.prompts[0])
        self.assertFalse(AssistantProposal.objects.exists())
        # Only the action itself on the agent is logged.
        self.assertEqual(ChangeLog.objects.count(), logged + 1)
        self.beta.refresh_from_db()
        self.assertEqual(self.beta.name, "Beta")

    def test_revert_run_restores_the_records(self):
        self.calls = [ToolCallPart("propose_patch", {"fields": {"name": "Renamed"}})]
        agent = self.make_agent(mode=Agent.Mode.AUTO, trigger=Agent.Trigger.MANUAL, watch_fields=[])
        runs = self.start(agent)
        self.assertEqual(set(Customer.objects.values_list("name", flat=True)), {"Renamed"})

        for run in runs:
            response = self.api.post(f"/api/v1/AGR/{run.id}/action/", {"action": "revert"}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(set(Customer.objects.values_list("name", flat=True)), {"Acme", "Beta"})

        response = self.api.post(f"/api/v1/AGR/{runs[0].id}/action/", {"action": "revert"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_revert_run_removes_its_notes(self):
        self.calls = [ToolCallPart("propose_create_note", {"body": "Finished it."})]
        agent = self.make_agent(mode=Agent.Mode.AUTO, max_records_per_run=1)
        [run] = self.start(agent)
        note = FeedItem.objects.get(body="Finished it.")
        grant(self.user, FeedItem, "delete")  # undoing a create deletes

        response = self.api.post(f"/api/v1/AGR/{run.id}/action/", {"action": "revert"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        note.refresh_from_db()
        self.assertTrue(note.deleted)

    def test_revert_a_run_that_changed_nothing(self):
        [run] = self.start(self.make_agent(max_records_per_run=1))
        response = self.api.post(f"/api/v1/AGR/{run.id}/action/", {"action": "revert"}, format="json")
        self.assertEqual(response.data, {"errors": ["This run changed nothing."]})

    def test_disabled_after_three_failures_in_a_row(self):
        agent = self.make_agent(trigger=Agent.Trigger.MANUAL, max_records_per_run=1)
        self.fail = True
        for _ in range(Agent.MAX_CONSECUTIVE_FAILURES):
            self.start(agent)
        agent.refresh_from_db()
        self.assertFalse(agent.enabled)
        self.assertEqual(set(agent.runs.values_list("status", flat=True)), {"failed"})
        self.assertEqual(agent.runs.first().error, "The model is down")
        note = FeedItem.objects.get(parent_object_id=agent.pk)
        self.assertIn("Disabled after 3 failed runs in a row", note.body)

    def test_success_resets_the_failure_streak(self):
        agent = self.make_agent(trigger=Agent.Trigger.MANUAL, max_records_per_run=1)
        self.fail = True
        self.start(agent)
        self.start(agent)
        self.fail = False
        self.start(agent)
        agent.refresh_from_db()
        self.assertEqual((agent.consecutive_failures, agent.enabled), (0, True))


class ScheduleTests(AgentTestCase):
    def test_interval_and_caps(self):
        self.make_customer("Gamma")
        agent = self.make_agent(
            trigger=Agent.Trigger.SCHEDULE, schedule=Agent.Schedule.DAILY, max_records_per_run=2, max_runs_per_day=3
        )
        with self.model(), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(run_scheduled_agents.delay().get(), 2)
            self.assertEqual(background.run_scheduled_agents(), 0)
            # A day later it is due again, but only one run is left for today.
            self.assertEqual(background.run_scheduled_agents(timezone.now() + timedelta(days=1, minutes=1)), 1)
        self.assertEqual(agent.runs.filter(status="succeeded").count(), 3)
        self.assertEqual({run.trigger_info["trigger"] for run in agent.runs.all()}, {"schedule"})


class AgentRecordTests(AgentTestCase):
    def test_run_as_defaults_to_the_creator(self):
        self.assertEqual(self.make_agent().run_as, self.user)

    def test_only_superusers_make_agents_run_as_someone_else(self):
        grant(self.user, Agent, "add", "change")
        other = User.objects.create_user("other")
        fields = {"name": "A", "instructions": "B", "trigger": "manual", "model_type": "CUS"}
        response = self.api.post("/api/v1/AGT/", fields | {"run_as": other.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("run_as", response.data)

        agent = self.make_agent()
        response = self.api.patch(f"/api/v1/AGT/{agent.id}/", {"run_as": other.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.api.patch(f"/api/v1/AGT/{agent.id}/", {"name": "Still mine"}, format="json")
        self.assertEqual(response.status_code, 200)

        self.api.force_authenticate(User.objects.create_superuser("root"))
        response = self.api.patch(f"/api/v1/AGT/{agent.id}/", {"run_as": other.pk}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def test_validation(self):
        grant(self.user, Agent, "add")
        base = {"name": "A", "instructions": "B", "model_type": "CUS"}
        for fields in (
            {"trigger": "schedule"},
            {"trigger": "manual", "schedule": "daily"},
            {"trigger": "record_changed", "watch_fields": ["nope"]},
            {"trigger": "manual", "model_type": "NOP"},
        ):
            response = self.api.post("/api/v1/AGT/", base | fields, format="json")
            self.assertEqual(response.status_code, 400, fields)

    def test_agents_and_runs_are_their_owners(self):
        agent = self.make_agent()
        self.start(agent)
        other = User.objects.create_user("other")
        grant(other, Agent, "view")
        grant(other, AgentRun, "view")
        self.api.force_authenticate(other)
        self.assertEqual(self.api.get("/api/v1/AGT/").data["count"], 0)
        self.assertEqual(self.api.get("/api/v1/AGR/").data["count"], 0)

    def test_metadata_carries_default_inlines(self):
        metadata = self.api.get("/api/v1/AGT/metadata/").data
        self.assertEqual(metadata["default_inlines"], [["AGR", ["status", "dry_run", "output", "finished_at"]]])
        self.assertEqual(self.api.get("/api/v1/CUS/metadata/").data["default_inlines"], [])


class SidebarCreatesAgentTests(AgentTestCase):
    def setUp(self):
        super().setUp()
        grant(self.user, Agent, "add")
        self.deps = AssistantDeps(user_id=self.user.pk, session_key="s1", screen=Screen(route="list", type_id="CUS"))
        self.deps._outbox = asyncio.Queue()  # type: ignore[attr-defined]

    def propose_create(self, type_id, fields):
        return async_to_sync(tools.propose_create)(_FakeCtx(self.deps), type_id, fields, reasoning="Asked for it")

    def test_create_proposal_makes_an_agent_once_confirmed(self):
        fields = {
            "name": "Weekly churn check",
            "instructions": "Flag at-risk customers.",
            "trigger": "schedule",
            "schedule": "weekly",
            "model_type": "CUS",
        }
        result = self.propose_create("AGT", fields)
        proposal = AssistantProposal.objects.get()
        self.assertIn(f"Proposal {proposal.id}", result)
        self.assertEqual((proposal.kind, proposal.label), ("create", "Create agent"))
        self.assertEqual(proposal.payload, {"type": "AGT", "fields": fields})
        self.assertEqual(self.deps._outbox.get_nowait()["id"], proposal.id)  # type: ignore[attr-defined]
        self.assertTrue(proposal.needs_approval())

        proposal.apply(self.user)
        self.assertEqual(proposal.status, "confirmed", proposal.outcome)
        agent = Agent.objects.get()
        self.assertEqual((agent.name, agent.run_as, agent.created_by), ("Weekly churn check", self.user, self.user))
        self.assertEqual(proposal.target, agent)

    def test_create_is_checked(self):
        self.assertTrue(self.propose_create("AGT", {"trigger": "whenever"}).startswith("ERROR"))
        invalid = {"name": "A", "instructions": "B", "model_type": "RDG", "trigger": "manual"}
        self.assertIn("Unknown record type", self.propose_create("AGT", invalid))
        self.assertIn("instructions", self.propose_create("AGT", {"name": "A", "model_type": "CUS"}))
        self.assertTrue(self.propose_create("AGT", {"nope": 1}).startswith("ERROR"))
        self.assertTrue(self.propose_create("NOP", {"name": "x"}).startswith("ERROR"))
        self.user.user_permissions.remove(Permission.objects.get(codename="add_agent"))
        self.user = User.objects.get(pk=self.user.pk)
        self.assertTrue(self.propose_create("AGT", {"name": "x"}).startswith("ERROR"))
        self.assertFalse(AssistantProposal.objects.exists())

    def test_dry_run_tools_file_nothing(self):
        self.deps.dry_run = True
        result = self.propose_create("CUS", {"name": "Gamma"})
        self.assertTrue(result.startswith("Dry run"))
        envelope = self.deps._outbox.get_nowait()  # type: ignore[attr-defined]
        self.assertEqual((envelope["id"], envelope["dry_run"], envelope["kind"]), (None, True, "create"))
        self.assertFalse(AssistantProposal.objects.exists())
