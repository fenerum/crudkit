"""Background agents: setting one up, what starts a run, what a run does, dry
runs, the failure streak and reverting a run.

The agents' AI is a stand-in (the `agent_ai` fixture, active as soon as a
scenario has an agent). By default it answers "Nothing to do." and proposes
nothing; the `the agent's AI ...` steps script it. Runs are started by hand
with the history phrase `When Alice uses the "Run now" action on "Fixer"`.

Phrases this area adds:

Agents (created directly, as their owner's)
- `Given Alice has an agent "Renamer" that runs when the status of a customer changes`
- `Given Alice has an agent "Tidier" that runs whenever a customer changes`
- `Given Alice has an agent "Welcomer" that runs when a customer is created`
- `Given Alice has an agent "Sweeper" that runs daily on customers` (hourly, daily or weekly)
- `Given Alice has an agent "Fixer" that runs on customers when started by hand`
- `Given the agent "Fixer" applies changes itself` (auto mode) / `Given the agent "Fixer" is turned off`
- `Given the agent "Fixer" only works on customers named "Acme"` (through a saved view)
- `Given the agent "Fixer" works on at most 2 records per run` / `... may run at most 3 times a day`
- `Given the agent "Fixer" was set to run as Bob by a superuser`
- `Given the agent "Fixer" was switched off after 3 failed runs in a row`
- `Given the record type of the agent "Broken" no longer exists`
- `Given Alice has a saved view "Open tickets" listing tickets`
- `Given Bob has permission to view agents and agent runs` / `Given Alice has permission to delete notes`
  (`Alice can view agent runs` does not parse: the shared phrase reads "view agent" as the actions)

Runs (as setup)
- `Given the agent "Fixer" has already worked on "Acme"`: a finished run, known as the record "Fixer on Acme"
- `Given the agent "Fixer" already ran 2 times today`
- `Given a run of "Fixer" on "Acme" has been queued for 10 minutes` (or `running`)
- `Given the agent "Sweeper" last ran on its schedule 25 hours ago` (minutes, hours or days)

The agents' AI and the machinery around it
- `Given the agent's AI will propose changing the name to "Acme Inc"` (repeat for several proposals)
- `Given the agent's AI will propose the note "Checked the account."`
- `Given the agent's AI will propose running "Run now"` (an action, by its label)
- `Given the agent's AI is down` / `Given the agent's AI is back`
- `Given the background task queue is unreachable` (`Given no AI model is configured` comes from the assistant
  and AI-field steps)
- `Given changes to the email of customers need a person's approval`

Doing
- `When Alice sets up an agent "Checker" with:` a `| record type | trigger | schedule | watch fields | saved view
  | runs as |` table (rows as needed; the rest default to a manual agent on customers)
- `When Alice makes the agent "Fixer" run as Bob`
- `When Alice turns the agent "Fixer" off` / `... back on`
- `When Alice uses the "Run now" action on "Fixer" 3 times` (any action label; also `Given Alice used ...`)
- `When Alice reverts the run of "Fixer" on "Acme"` / `Given Alice reverted ...`
- `When the scheduler checks for due agents` (`... again`)

Outcomes
- `Then the agent "Fixer" ran on "Acme"` / `did not run on "Acme"` / `did not run`
- `Then the agent "Fixer" ran once` (`twice`, `3 times`), `... ran twice on "Acme"`
- `Then the latest run of "Fixer" succeeded` / `failed with "The model is down"` / `was on "Acme"`
- `Then the agent was asked to work on "Acme", which just changed (status)`
- `Then the agent was told that nothing it proposes will be saved` (a dry run)
- `Then the agent "Fixer" was given its instructions`
- `Then the agent "Fixer" proposed changing the name of "Acme" to "Acme Inc"` (waiting for a person)
- `Then the agent "Kicker" proposed running "Run now" on "Fixer"` / `Then the agent "Fixer" left no proposals`
- `Then the change to "Acme" is credited to the agent "Fixer"`
- `Then the dry run of "Fixer" on "Beta" would have changed the name to "Beta Inc"`
- `Then the agent "Fixer" is turned on` / `is turned off`
- `Then the agent "Fixer" has 2 failures in a row` / `has no failures in a row`
- `Then the agent "Fixer" runs as Alice`
- `Then the scheduler started 2 runs` (`1 run`, `no runs`)
- `Then Alice is told "Started 2 runs of Fixer."`
"""

from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from pytest_bdd import given, parsers, then, when

from crudkit.models import ChangeLog, FeedItem, View
from crudkit.utils import get_model_types
from crudkit_api.services import action_for_label
from crudkit_assistant import tasks
from crudkit_assistant.models import Agent, AgentRun, AssistantProposal
from tests.bdd.steps.permissions import patch_for_scenario
from tests.bdd.world import label_field, model_named, phrase, split_list
from tests.support import grant

INSTRUCTIONS = "Tidy up the record."
TIMES = {"once": 1, "twice": 2}


class AgentAI:
    """Stands in for the AI model agents use: proposes what the steps scripted, or fails."""

    def __init__(self):
        self.calls: list[ToolCallPart] = []
        self.error: str | None = None
        self.prompts: list[str] = []
        self.instructions: list[str] = []

    def respond(self, messages, info):
        parts = info.model_request_parameters.instruction_parts or []
        self.instructions.append("\n".join(part.content for part in parts))
        last = messages[-1].parts[-1]
        if not isinstance(last, UserPromptPart):
            return ModelResponse(parts=[TextPart("Done.")])
        self.prompts.append(last.content)
        if self.error:
            raise RuntimeError(self.error)
        if self.calls:
            return ModelResponse(parts=list(self.calls))
        return ModelResponse(parts=[TextPart("Nothing to do.")])

    @asynccontextmanager
    async def create_model(self):
        yield FunctionModel(self.respond)


@pytest.fixture
def agent_ai():
    ai = AgentAI()
    with patch("tests.testapp.ai.create_model", ai.create_model):
        yield ai


def _times(text: str) -> int:
    """ "once", "twice", "3 times", "2 runs", "1 run", "no runs" -> a number"""
    if text in TIMES:
        return TIMES[text]
    count = text.split()[0]
    return 0 if count == "no" else int(count)


# Agents


def _add_agent(world, owner, label, model, **fields):
    user = world.user(owner)
    agent = Agent.objects.create(
        name=label,
        instructions=INSTRUCTIONS,
        model_type=model.TYPE_ID,
        created_by=user,
        updated_by=user,
        **fields,
    )
    return world.add(label, agent)


def _update_agent(world, label, **fields):
    """Saved like the app saves it, so the cached table of agents is refreshed."""
    agent = world.record(label)
    for name, value in fields.items():
        setattr(agent, name, value)
    agent.save()


@given(phrase('{name:Actor} has an agent "{label:Q}" that runs when the {field:Words} of a {model:Model} changes'))
def an_agent_watching_a_field(world, agent_ai, name, label, field, model):
    _add_agent(world, name, label, model, trigger=Agent.Trigger.RECORD_CHANGED, watch_fields=[field.replace(" ", "_")])


@given(phrase('{name:Actor} has an agent "{label:Q}" that runs whenever a {model:Model} changes'))
def an_agent_watching_everything(world, agent_ai, name, label, model):
    _add_agent(world, name, label, model, trigger=Agent.Trigger.RECORD_CHANGED)


@given(phrase('{name:Actor} has an agent "{label:Q}" that runs when a {model:Model} is created'))
def an_agent_on_new_records(world, agent_ai, name, label, model):
    _add_agent(world, name, label, model, trigger=Agent.Trigger.RECORD_CREATED)


@given(phrase('{name:Actor} has an agent "{label:Q}" that runs {schedule:Words} on {model:Model}'))
def a_scheduled_agent(world, agent_ai, name, label, schedule, model):
    _add_agent(world, name, label, model, trigger=Agent.Trigger.SCHEDULE, schedule=Agent.Schedule(schedule))


@given(phrase('{name:Actor} has an agent "{label:Q}" that runs on {model:Model} when started by hand'))
def a_manual_agent(world, agent_ai, name, label, model):
    _add_agent(world, name, label, model, trigger=Agent.Trigger.MANUAL)


@given(phrase('the agent "{label:Q}" applies changes itself'))
def applies_changes_itself(world, label):
    _update_agent(world, label, mode=Agent.Mode.AUTO)


@given(phrase('the agent "{label:Q}" is turned off'))
def turned_off(world, label):
    _update_agent(world, label, enabled=False)


@given(phrase('the agent "{label:Q}" only works on {model:Model} named "{value:Q}"'))
def only_works_on(world, label, model, value):
    agent = world.record(label)
    name = label_field(model)
    view = View.objects.create(
        name=f"{model._meta.verbose_name_plural} named {value}",
        model=model.TYPE_ID,
        fields=[name],
        filters=[[name, "=", value]],
        created_by=agent.created_by,
        updated_by=agent.created_by,
    )
    _update_agent(world, label, view=view)


@given(phrase('the agent "{label:Q}" works on at most {count:d} records per run'))
@given(phrase('the agent "{label:Q}" works on at most {count:d} record per run'))
def records_per_run(world, label, count):
    _update_agent(world, label, max_records_per_run=count)


@given(phrase('the agent "{label:Q}" may run at most {count:d} times a day'))
@given(phrase('the agent "{label:Q}" may run at most {count:d} time a day'))
def runs_per_day(world, label, count):
    _update_agent(world, label, max_runs_per_day=count)


@given(phrase('the agent "{label:Q}" was set to run as {name:Actor} by a superuser'))
def set_to_run_as(world, label, name):
    Agent.objects.filter(pk=world.records[label].pk).update(run_as=world.user(name))


@given(phrase('the agent "{label:Q}" was switched off after {count:d} failed runs in a row'))
def switched_off_after_failures(world, label, count):
    Agent.objects.filter(pk=world.records[label].pk).update(enabled=False, consecutive_failures=count)


@given(phrase('the record type of the agent "{label:Q}" no longer exists'))
def record_type_gone(world, label):
    Agent.objects.filter(pk=world.records[label].pk).update(model_type="GONE")


@given(phrase("{name:Actor} has permission to view agents and agent runs"))
def may_view_agents_and_runs(world, name):
    user = world.users.get(name) or world.add_user(name)
    grant(user, Agent, "view")
    grant(user, AgentRun, "view")


@given(phrase("{name:Actor} has permission to delete notes"))
def may_delete_notes(world, name):
    grant(world.users.get(name) or world.add_user(name), FeedItem, "delete")


@given(phrase('{name:Actor} has a saved view "{label:Q}" listing {model:Model}'))
def a_saved_view(world, name, label, model):
    user = world.user(name)
    view = View.objects.create(
        name=label, model=model.TYPE_ID, fields=[label_field(model)], created_by=user, updated_by=user
    )
    world.add(label, view)


# Runs, as setup


def _add_run(world, agent_label, target=None, **fields):
    agent = world.record(agent_label)
    run = AgentRun.objects.create(
        agent=agent,
        target_content_type=ContentType.objects.get_for_model(target) if target else None,
        target_object_id=target.pk if target else None,
        created_by=agent.created_by,
        updated_by=agent.created_by,
        **fields,
    )
    return world.add(str(run), run)


@given(phrase('the agent "{agent:Q}" has already worked on "{label:Q}"'))
def already_worked_on(world, agent, label):
    _add_run(world, agent, world.record(label), status=AgentRun.Status.SUCCEEDED)


@given(phrase('the agent "{agent:Q}" already ran {count:d} times today'))
def already_ran_today(world, agent, count):
    for _ in range(count):
        _add_run(world, agent, status=AgentRun.Status.SUCCEEDED)


@given(phrase('a run of "{agent:Q}" on "{label:Q}" has been {status:Words} for {minutes:d} minutes'))
def a_waiting_run(world, agent, label, status, minutes):
    run = _add_run(world, agent, world.record(label), status=AgentRun.Status(status))
    AgentRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(minutes=minutes))


@given(phrase('the agent "{label:Q}" last ran on its schedule {amount:d} {unit:Words} ago'))
def last_scheduled(world, label, amount, unit):
    when = timezone.now() - timedelta(**{unit: amount})
    Agent.objects.filter(pk=world.records[label].pk).update(last_scheduled_at=when)


# The agents' AI and the machinery around it


@given(phrase('the agent\'s AI will propose changing the {field:Words} to "{value:Q}"'))
def will_propose_a_change(agent_ai, field, value):
    agent_ai.calls.append(ToolCallPart("propose_patch", {"fields": {field.replace(" ", "_"): value}}))


@given(phrase('the agent\'s AI will propose the note "{body:Q}"'))
def will_propose_a_note(agent_ai, body):
    agent_ai.calls.append(ToolCallPart("propose_create_note", {"body": body}))


def _action_name(label: str) -> str:
    """The method behind the action labelled `label` on any record type."""
    for model in get_model_types().values():
        name = action_for_label(model, label)
        if name:
            return name
    raise LookupError(f'No record type has an action called "{label}"')


@given(phrase('the agent\'s AI will propose running "{action:Q}"'))
def will_propose_an_action(agent_ai, action):
    agent_ai.calls.append(ToolCallPart("propose_action", {"action_name": _action_name(action)}))


@given("the agent's AI is down")
def ai_is_down(agent_ai):
    agent_ai.error = "The model is down"


@given("the agent's AI is back")
def ai_is_back(agent_ai):
    agent_ai.error = None


@given("the background task queue is unreachable")
def task_queue_unreachable(request):
    def refuse(*args, **kwargs):
        raise ConnectionError("Connection refused")

    patch_for_scenario(request, tasks.run_agent, "delay", refuse)


@given(phrase("changes to the {field:Words} of {model:Model} need a person's approval"))
def field_needs_approval(request, field, model):
    patch_for_scenario(request, model.CrudKitSettings, "approval_fields", [field.replace(" ", "_")])


# Doing

AGENT_FIELDS = {
    "record type": "model_type",
    "trigger": "trigger",
    "schedule": "schedule",
    "watch fields": "watch_fields",
    "saved view": "view",
    "runs as": "run_as",
}


def _type_id(text: str) -> str:
    """The TYPE_ID of the record type called `text`, or `text` itself when no type is called that."""
    try:
        return model_named(text).TYPE_ID
    except LookupError:
        return text


def _agent_field(world, field, text):
    if field == "record type":
        return _type_id(text)
    if field == "watch fields":
        return split_list(text)
    if field == "saved view":
        return world.records[text].pk
    if field == "runs as":
        return world.user(text).pk
    return text.replace(" ", "_")


@when(phrase('{name:Actor} sets up an agent "{label:Q}" with:'))
def sets_up_an_agent(world, agent_ai, name, label, datatable):
    payload = {"name": label, "instructions": INSTRUCTIONS, "model_type": "CUS", "trigger": "manual"}
    for field, text in datatable:
        if text:
            payload[AGENT_FIELDS[field]] = _agent_field(world, field, text)
    response = world.remember(name, world.api(name).post(f"/api/v1/{Agent.TYPE_ID}/", payload, format="json"))
    if response.status_code == 201:
        world.add(label, Agent.objects.get(name=label))


def _patch_agent(world, name, label, payload):
    world.remember(name, world.api(name).patch(world.url(label), payload, format="json"))


@when(phrase('{name:Actor} makes the agent "{label:Q}" run as {other:Actor}'))
def makes_run_as(world, name, label, other):
    _patch_agent(world, name, label, {"run_as": world.user(other).pk})


@when(phrase('{name:Actor} turns the agent "{label:Q}" off'))
def turns_off(world, name, label):
    _patch_agent(world, name, label, {"enabled": False})


@when(phrase('{name:Actor} turns the agent "{label:Q}" back on'))
def turns_back_on(world, name, label):
    _patch_agent(world, name, label, {"enabled": True})


def _use_action(world, name, action, label):
    payload = {"action": _action_name(action)}
    world.remember(name, world.api(name).post(world.url(label, "action"), payload, format="json"))


@given(phrase('{name:Actor} used the "{action:Q}" action on "{label:Q}" {count:d} times'))
@when(phrase('{name:Actor} uses the "{action:Q}" action on "{label:Q}" {count:d} times'))
def uses_an_action_repeatedly(world, name, action, label, count):
    for _ in range(count):
        _use_action(world, name, action, label)


@given(phrase('{name:Actor} reverted the run of "{agent:Q}" on "{label:Q}"'))
@when(phrase('{name:Actor} reverts the run of "{agent:Q}" on "{label:Q}"'))
def reverts_a_run(world, name, agent, label):
    run = _latest(_runs_on(world, agent, label))
    world.add(str(run), run)
    _use_action(world, name, "Revert this run", str(run))


@when("the scheduler checks for due agents")
@when("the scheduler checks for due agents again")
def scheduler_checks(world):
    world.scheduled = tasks.run_scheduled_agents.delay().get()


# Outcomes


def _runs(world, agent_label, dry_run=False):
    return AgentRun.objects.filter(agent=world.records[agent_label].pk, dry_run=dry_run)


def _latest(runs):
    run = runs.order_by("-created_at", "-pk").first()
    assert run is not None, "The agent has not run"
    return run


def _is(world, instance, label) -> bool:
    """Whether `instance` is the record called `label` (or, for records made through the app, reads as it)."""
    if label in world.records:
        known = world.records[label]
        return type(instance) is type(known) and instance.pk == known.pk
    return str(instance) == label


def _runs_on(world, agent_label, label, dry_run=False):
    matching = [run.pk for run in _runs(world, agent_label, dry_run) if _is(world, run.target, label)]
    return AgentRun.objects.filter(pk__in=matching)


def _proposals(world, agent_label):
    keys = [run.session_key for run in AgentRun.objects.filter(agent=world.records[agent_label].pk)]
    return AssistantProposal.objects.filter(session_key__in=keys)


@then(phrase('the agent "{agent:Q}" ran on "{label:Q}"'))
def ran_on(world, agent, label):
    assert _runs_on(world, agent, label).exists(), list(_runs(world, agent))


@then(phrase('the agent "{agent:Q}" did not run on "{label:Q}"'))
def did_not_run_on(world, agent, label):
    assert not _runs_on(world, agent, label).exists(), list(_runs(world, agent))


@then(phrase('the agent "{agent:Q}" did not run'))
def did_not_run(world, agent):
    assert not AgentRun.objects.filter(agent=world.records[agent].pk).exists()


@then(parsers.re(r'the agent "(?P<agent>[^"]*)" ran (?P<times>once|twice|\d+ times)'))
def ran_times(world, agent, times):
    assert _runs(world, agent).count() == _times(times), list(_runs(world, agent))


@then(parsers.re(r'the agent "(?P<agent>[^"]*)" ran (?P<times>once|twice|\d+ times) on "(?P<label>[^"]*)"'))
def ran_times_on(world, agent, times, label):
    assert _runs_on(world, agent, label).count() == _times(times), list(_runs(world, agent))


@then(phrase('the latest run of "{agent:Q}" succeeded'))
def latest_succeeded(world, agent):
    run = _latest(AgentRun.objects.filter(agent=world.records[agent].pk))
    assert run.status == AgentRun.Status.SUCCEEDED, (run.status, run.error)


@then(phrase('the latest run of "{agent:Q}" failed with "{message:Q}"'))
def latest_failed(world, agent, message):
    run = _latest(AgentRun.objects.filter(agent=world.records[agent].pk))
    assert run.status == AgentRun.Status.FAILED, run.status
    assert message in run.error, run.error


@then(phrase('the latest run of "{agent:Q}" was on "{label:Q}"'))
def latest_was_on(world, agent, label):
    run = _latest(_runs(world, agent))
    assert _is(world, run.target, label), run.target


def _record_id(world, label):
    if label in world.records:
        return world.record(label).id
    return next(run.target.id for run in AgentRun.objects.all() if run.target and str(run.target) == label)


@then(phrase('the agent was asked to work on "{label:Q}", which {reason}'))
def asked_to_work_on(world, agent_ai, label, reason):
    asked = f"Carry out your agent instructions on {_record_id(world, label)}, which {reason}"
    assert any(asked in prompt for prompt in agent_ai.prompts), agent_ai.prompts


@then("the agent was told that nothing it proposes will be saved")
def told_dry_run(agent_ai):
    assert "This is a dry run: nothing you propose will be saved." in agent_ai.prompts[-1], agent_ai.prompts


@then(phrase('the agent "{agent:Q}" was given its instructions'))
def given_its_instructions(world, agent_ai, agent):
    instructions = agent_ai.instructions[-1]
    assert "You are a background agent" in instructions, instructions
    assert instructions.endswith(f"# Agent instructions\n\n{world.record(agent).instructions}"), instructions


def _pending(world, agent, label, kind, payload):
    return [
        proposal
        for proposal in _proposals(world, agent).filter(status=AssistantProposal.Status.PENDING, kind=kind)
        if proposal.payload == payload and _is(world, proposal.target, label)
    ]


@then(phrase('the agent "{agent:Q}" proposed changing the {field:Words} of "{label:Q}" to "{value:Q}"'))
def proposed_a_change(world, agent, field, label, value):
    """The proposal waits for a person to confirm it."""
    payload = {"fields": {field.replace(" ", "_"): value}}
    [proposal] = _pending(world, agent, label, AssistantProposal.Kind.PATCH, payload)
    assert (proposal.source, proposal.client) == ("agent", agent)


@then(phrase('the agent "{agent:Q}" proposed running "{action:Q}" on "{label:Q}"'))
def proposed_an_action(world, agent, action, label):
    """The proposal waits for a person to confirm it."""
    payload = {"action": _action_name(action)}
    [proposal] = _pending(world, agent, label, AssistantProposal.Kind.ACTION, payload)
    assert (proposal.source, proposal.client) == ("agent", agent)


@then(phrase('the agent "{agent:Q}" left no proposals'))
def left_no_proposals(world, agent):
    assert not _proposals(world, agent).exists(), list(_proposals(world, agent))


@then(phrase('the change to "{label:Q}" is credited to the agent "{agent:Q}"'))
def credited_to_the_agent(world, label, agent):
    instance = world.record(label)
    entry = (
        ChangeLog.objects.filter(
            related_content_type=ContentType.objects.get_for_model(instance), related_object_id=instance.pk
        )
        .order_by("-created_at", "-pk")
        .first()
    )
    assert (entry.source, entry.client) == ("agent", agent), (entry.source, entry.client)
    assert entry.change_set in {run.change_set for run in _runs(world, agent)}


@then(phrase('the dry run of "{agent:Q}" on "{label:Q}" would have changed the {field:Words} to "{value:Q}"'))
def dry_run_would_have_changed(world, agent, label, field, value):
    run = _latest(_runs_on(world, agent, label, dry_run=True))
    assert run.status == AgentRun.Status.SUCCEEDED, (run.status, run.error)
    payload = {"fields": {field.replace(" ", "_"): value}}
    assert [(event["dry_run"], event["payload"]) for event in run.preview] == [(True, payload)], run.preview


@then(phrase('the agent "{label:Q}" is turned on'))
def is_turned_on(world, label):
    assert world.record(label).enabled


@then(phrase('the agent "{label:Q}" is turned off'))
def is_turned_off(world, label):
    assert not world.record(label).enabled


@then(phrase('the agent "{label:Q}" has {count:d} failures in a row'))
def failures_in_a_row(world, label, count):
    assert world.record(label).consecutive_failures == count


@then(phrase('the agent "{label:Q}" has no failures in a row'))
def no_failures_in_a_row(world, label):
    assert world.record(label).consecutive_failures == 0


@then(phrase('the agent "{label:Q}" runs as {name:Actor}'))
def runs_as(world, label, name):
    assert world.record(label).run_as == world.user(name)


@then(parsers.re(r"the scheduler started (?P<count>no runs|1 run|\d+ runs)"))
def scheduler_started(world, count):
    assert world.scheduled == _times(count), world.scheduled


@then(phrase('{name:Actor} is told "{message:Q}"'))
def is_told(world, name, message):
    assert world.response.status_code == 200, world.response.content
    assert message in world.response.data["messages"], world.response.data
