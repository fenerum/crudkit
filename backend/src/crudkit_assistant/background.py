"""
Background agents: which runs a logged change, a schedule or a click starts,
and carrying out one run with the assistant.

Runs start from ChangeLog entries, so only writes that are logged (the REST
API, MCP, the assistant, actions) trigger agents; plain ORM saves don't.
Changes made by agents (source "agent") never trigger agents.
"""

import logging
from datetime import timedelta
from functools import partial

from asgiref.sync import async_to_sync
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from crudkit import llm
from crudkit.authorization import get_authorized_queryset
from crudkit.models import ChangeLog
from crudkit.utils import get_system_user
from crudkit_api.services import RequestShim, create_note
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import Agent, AgentRun, AssistantProposal
from crudkit_assistant.runner import run_turn
from crudkit_assistant.screen import Screen

logger = logging.getLogger(__name__)

CACHE_KEY = "crudkit_assistant:record_agents"
# Agent saves clear the cache; the timeout bounds staleness in other processes
# when the cache backend is per-process.
CACHE_TIMEOUT = 60
SCHEDULE_INTERVALS = {
    Agent.Schedule.HOURLY: timedelta(hours=1),
    Agent.Schedule.DAILY: timedelta(days=1),
    Agent.Schedule.WEEKLY: timedelta(weeks=1),
}
TRIGGER_REASONS = {
    Agent.Trigger.RECORD_CREATED: "was just created",
    Agent.Trigger.RECORD_CHANGED: "just changed",
    Agent.Trigger.SCHEDULE: "is due on the agent's schedule",
    Agent.Trigger.MANUAL: "was picked by hand",
}


# ---------------------------------------------------------------------------
# Triggers


def record_agents(type_id: str) -> list[dict]:
    """The enabled record-triggered agents on `type_id`, cached."""
    table = cache.get(CACHE_KEY)
    if table is None:
        table = {}
        agents = Agent.objects.filter(
            enabled=True,
            deleted=False,
            trigger__in=[Agent.Trigger.RECORD_CREATED, Agent.Trigger.RECORD_CHANGED],
        ).values("id", "model_type", "trigger", "watch_fields")
        for agent in agents:
            table.setdefault(agent.pop("model_type"), []).append(agent)
        cache.set(CACHE_KEY, table, CACHE_TIMEOUT)
    return table.get(type_id, [])


def forget_record_agents() -> None:
    cache.delete(CACHE_KEY)


def on_change_logged(entry: ChangeLog) -> None:
    """Start the agents watching the record `entry` logged, once it commits."""
    if entry.source == "agent" or entry.related_content_type_id is None:
        return
    # Actions are logged as ACTION with the fields they changed.
    if entry.action not in (ChangeLog.Action.CREATE, ChangeLog.Action.UPDATE, ChangeLog.Action.ACTION):
        return
    type_id = getattr(entry.related_content_type.model_class(), "TYPE_ID", None)
    agents = record_agents(type_id) if type_id else []
    changed = sorted(entry.field_changes or {}) if entry.action != ChangeLog.Action.CREATE else []
    for agent in agents:
        if entry.action == ChangeLog.Action.CREATE:
            if agent["trigger"] != Agent.Trigger.RECORD_CREATED:
                continue
        elif agent["trigger"] != Agent.Trigger.RECORD_CHANGED or not changed:
            continue
        elif agent["watch_fields"] and not set(changed) & set(agent["watch_fields"]):
            continue
        info = {"trigger": agent["trigger"], "fields": changed, "change_set": str(entry.change_set)}
        transaction.on_commit(partial(enqueue_record_run, agent["id"], entry.related_object_id, info))


def matching_records(agent: Agent, queryset=None):
    """The records `agent` may work on, newest first: those `run_as` can see,
    narrowed to the agent's view."""
    model = agent.get_model()
    queryset = model.objects.all() if queryset is None else queryset
    queryset = get_authorized_queryset(agent.run_as, queryset, "view").filter(deleted=False)
    if agent.view_id:
        queryset = agent.view.filter(queryset, request=RequestShim(agent.run_as))
    return queryset.order_by("-updated_at")


def runs_today(agent: Agent) -> int:
    midnight = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return agent.runs.filter(dry_run=False, created_at__gte=midnight).count()


def enqueue_record_run(agent_id, pk, trigger_info: dict) -> AgentRun | None:
    agent = Agent.objects.filter(pk=agent_id, enabled=True, deleted=False).first()
    if agent is None:
        return None
    record = matching_records(agent, agent.get_model().objects.filter(pk=pk)).first()
    if record is None:
        return None
    if runs_today(agent) >= agent.max_runs_per_day:
        logger.warning("Agent %s reached its %d runs today; not running on %s", agent.pk, agent.max_runs_per_day, pk)
        return None
    return _start(agent, record, trigger_info)


def enqueue_runs(agent: Agent, trigger: str = Agent.Trigger.MANUAL) -> list[AgentRun]:
    """One run per matching record, up to the per-run and per-day caps."""
    room = max(agent.max_runs_per_day - runs_today(agent), 0)
    records = list(matching_records(agent)[: min(agent.max_records_per_run, room)])
    return [_start(agent, record, {"trigger": trigger}) for record in records]


def start_dry_run(agent: Agent) -> AgentRun | None:
    record = matching_records(agent).first()
    return _start(agent, record, {"trigger": Agent.Trigger.MANUAL}, dry_run=True) if record else None


def run_scheduled_agents(now=None) -> int:
    """Start the scheduled agents whose interval has passed. Returns the number of runs."""
    now = now or timezone.now()
    started = 0
    for agent in Agent.objects.filter(enabled=True, deleted=False, trigger=Agent.Trigger.SCHEDULE):
        interval = SCHEDULE_INTERVALS.get(agent.schedule)
        if interval is None or (agent.last_scheduled_at and now - agent.last_scheduled_at < interval):
            continue
        Agent.objects.filter(pk=agent.pk).update(last_scheduled_at=now)
        started += len(enqueue_runs(agent, Agent.Trigger.SCHEDULE))
    return started


def _start(agent: Agent, record, trigger_info: dict, dry_run: bool = False) -> AgentRun:
    run = AgentRun.objects.create(
        agent=agent,
        target_content_type=ContentType.objects.get_for_model(record),
        target_object_id=record.pk,
        dry_run=dry_run,
        trigger_info=trigger_info,
        created_by=agent.created_by,
        updated_by=agent.created_by,
    )
    transaction.on_commit(partial(_dispatch, run.pk))
    return run


def _dispatch(run_id) -> None:
    from crudkit_assistant.tasks import run_agent  # circular: tasks imports this module

    try:
        run_agent.delay(run_id)
    except Exception as exc:
        # A missing broker must not fail the write that triggered the agent.
        logger.exception("Failed to enqueue run_agent for %s", run_id)
        AgentRun.objects.filter(pk=run_id, status=AgentRun.Status.QUEUED).update(
            status=AgentRun.Status.FAILED, error=f"Could not queue the run: {exc}", finished_at=timezone.now()
        )


# ---------------------------------------------------------------------------
# Running


def execute_run(run_id) -> None:
    # No close_old_connections() here: Celery's Django fixup does that around
    # worker tasks, and an eager run shares the caller's connection (and, in
    # tests, its transaction), which closing would break.
    run = AgentRun.objects.select_related("agent__run_as").filter(pk=run_id, status=AgentRun.Status.QUEUED).first()
    if run is None:
        return
    agent = run.agent
    run.status = AgentRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at", "updated_at"])
    try:
        if not agent.enabled and not run.dry_run:
            raise RuntimeError("The agent is disabled.")
        if not llm.is_configured():
            raise RuntimeError("No AI model is configured.")
        result = async_to_sync(run_turn)(_prompt(run), _deps(run))
        run.output = result.output_text.strip()
        run.preview = result.pending_events
        if agent.mode == Agent.Mode.AUTO and not run.dry_run:
            run.preview = _apply(run)
        run.status = AgentRun.Status.SUCCEEDED
    except Exception as exc:
        logger.exception("Agent run %s failed", run.pk)
        run.status = AgentRun.Status.FAILED
        run.error = str(exc) or exc.__class__.__name__
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "output", "preview", "error", "finished_at", "updated_at"])
    if not run.dry_run and agent.enabled:
        _count_outcome(agent, run)


def _prompt(run: AgentRun) -> str:
    trigger = run.trigger_info.get("trigger", Agent.Trigger.MANUAL)
    reason = TRIGGER_REASONS.get(trigger, TRIGGER_REASONS[Agent.Trigger.MANUAL])
    if fields := run.trigger_info.get("fields"):
        reason += f" ({', '.join(fields)})"
    prompt = f"Carry out your agent instructions on {run.target.id}, which {reason}."
    if run.dry_run:
        prompt += " This is a dry run: nothing you propose will be saved."
    return prompt


def _deps(run: AgentRun) -> AssistantDeps:
    agent = run.agent
    return AssistantDeps(
        user_id=agent.run_as_id,
        session_key=run.session_key,
        screen=Screen(route="detail", record_id=str(run.target.id)),
        source="agent",
        client=agent.name,
        agent_instructions=agent.instructions,
        dry_run=run.dry_run,
    )


def _apply(run: AgentRun) -> list[dict]:
    """Apply the run's proposals that need no approval, as one change set; the
    rest wait in the inbox. Returns the preview with each proposal's status."""
    outcomes = {}
    proposals = AssistantProposal.objects.filter(session_key=run.session_key, status=AssistantProposal.Status.PENDING)
    for proposal in proposals.order_by("created_at"):
        if not proposal.needs_approval():
            proposal.apply(run.agent.run_as, change_set=run.change_set)
        outcomes[proposal.id] = {"status": proposal.status}
        if proposal.status == AssistantProposal.Status.FAILED:
            outcomes[proposal.id]["error"] = (proposal.outcome or {}).get("error", "")
    return [event | outcomes.get(event.get("id"), {}) for event in run.preview]


def _count_outcome(agent: Agent, run: AgentRun) -> None:
    """Reset the failure streak on success; disable the agent after too many failures."""
    agents = Agent.objects.filter(pk=agent.pk)
    if run.status == AgentRun.Status.SUCCEEDED:
        agents.update(consecutive_failures=0)
        return
    agents.update(consecutive_failures=F("consecutive_failures") + 1)
    agent.refresh_from_db(fields=["consecutive_failures", "enabled"])
    if agent.enabled and agent.consecutive_failures >= Agent.MAX_CONSECUTIVE_FAILURES:
        agent.enabled = False
        agent.save(update_fields=["enabled", "updated_at"])
        create_note(
            agent,
            f"Disabled after {agent.consecutive_failures} failed runs in a row. Last error: {run.error}",
            get_system_user(),
        )
