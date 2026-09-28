"""Celery tasks for background agents. Add `run_scheduled_agents` to
CELERY_BEAT_SCHEDULE (every 5 minutes) for scheduled agents to run."""

from celery import shared_task

from crudkit_assistant import background


@shared_task
def run_agent(run_id) -> None:
    background.execute_run(run_id)


@shared_task
def run_scheduled_agents() -> int:
    return background.run_scheduled_agents()
