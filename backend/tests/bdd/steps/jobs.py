"""Tasks: the progress a long-running action reports to the person who started it.

Phrases this area adds:

- `Given customers have an action "Recount" that works through 3 steps`
- `Given customers have an action "Recount" that gives up with "Ledger locked" after 1 step`
- `Given customers have an action "Import" that hands its task to the background`
- `When the background task works through 2 steps` / `When the background task fails with "Mailbox full"`
- `Then Alice's task "Recount" has succeeded with 3 of 3 steps done`
- `Then Alice's task "Import" is still running` / `Then Alice's task "Recount" has failed with "Ledger locked"`
- `Then Alice has no tasks` / `Then Bob cannot see Alice's task "Recount"`
- `Then Alice sees the task "Recount" in her list of tasks`
- `Then Alice hears her task "Recount" go through 1 of 3, 2 of 3 and 3 of 3 and succeed`
"""

from parse import with_pattern
from pytest_bdd import given, then, when
from rest_framework.response import Response

from crudkit import jobs
from crudkit.decorators import crm_action
from crudkit.models import Job
from tests.bdd.steps.permissions import patch_for_scenario
from tests.bdd.world import phrase, split_list


def _add_action(request, model, verbose_name, method):
    name = verbose_name.lower().replace(" ", "_")
    patch_for_scenario(request, model, name, crm_action(verbose_name)(method))


@given(phrase('{model:Model} have an action "{verbose_name:Q}" that works through {steps:d} steps'))
def an_action_with_steps(request, model, verbose_name, steps):
    def work(self, request):
        for step in range(1, steps + 1):
            jobs.progress(step, total=steps, message=f"Step {step}")

    # Every step reaches the browser, however quickly the steps come.
    patch_for_scenario(request, jobs, "PUSH_EVERY", 0)
    _add_action(request, model, verbose_name, work)


@given(phrase('{model:Model} have an action "{verbose_name:Q}" that gives up with "{reason:Q}" after {steps:d} step'))
def an_action_that_gives_up(request, model, verbose_name, reason, steps):
    def give_up(self, request):
        for step in range(1, steps + 1):
            jobs.progress(step, total=steps + 1)
        return Response({"errors": [reason]}, status=400)

    _add_action(request, model, verbose_name, give_up)


@given(phrase('{model:Model} have an action "{verbose_name:Q}" that hands its task to the background'))
def an_action_that_hands_off(world, request, model, verbose_name):
    def hand_off(self, request):
        # A real action would queue a background task with this.
        world.handed_off = jobs.hand_off().pk

    _add_action(request, model, verbose_name, hand_off)


@when(phrase("the background task works through {steps:d} steps"))
def background_works(world, steps):
    with jobs.resume(world.handed_off):
        for step in range(1, steps + 1):
            jobs.progress(step, total=steps)


@when(phrase('the background task fails with "{reason:Q}"'))
def background_fails(world, reason):
    try:
        with jobs.resume(world.handed_off):
            raise RuntimeError(reason)
    except RuntimeError:
        pass


def _task(world, name, label) -> Job:
    return Job.objects.get(created_by=world.user(name), label=label)


@then(phrase('{name:Actor}\'s task "{label:Q}" has succeeded with {done:d} of {total:d} steps done'))
def task_succeeded(world, name, label, done, total):
    job = _task(world, name, label)
    assert (job.status, job.done, job.total) == (Job.Status.SUCCEEDED, done, total), job.as_event()


@then(phrase('{name:Actor}\'s task "{label:Q}" is still running'))
def task_running(world, name, label):
    job = _task(world, name, label)
    assert job.status == Job.Status.RUNNING, job.as_event()
    assert world.response.data["job"] == job.pk, world.response.data


@then(phrase('{name:Actor}\'s task "{label:Q}" has failed with "{reason:Q}"'))
def task_failed(world, name, label, reason):
    job = _task(world, name, label)
    assert (job.status, job.error) == (Job.Status.FAILED, reason), job.as_event()


@then(phrase("{name:Actor} has no tasks"))
def no_tasks(world, name):
    assert not Job.objects.filter(created_by=world.user(name)).exists()


@then(phrase('{name:Actor} sees the task "{label:Q}" in {their:Their} list of tasks'))
def sees_task(world, name, label, their):
    response = world.api(name).get("/api/v1/JOB/")
    assert response.status_code == 200, response.content
    assert [row["label"] for row in response.data["results"]] == [label], response.data


@then(phrase('{name:Actor} cannot see {owner:Actor}\'s task "{label:Q}"'))
def cannot_see_task(world, name, owner, label):
    job = _task(world, owner, label)
    api = world.api(name)
    assert api.get("/api/v1/JOB/").data["results"] == []
    assert api.get(f"/api/v1/JOB/{job.pk[3:]}/").status_code == 404


@with_pattern(r"\d+ of \d+(?:(?:, | and )\d+ of \d+)*")
def _steps(text):
    return [tuple(int(n) for n in step.split(" of ")) for step in split_list(text)]


@with_pattern(r"succeed|fail")
def _outcome(text):
    return Job.Status.SUCCEEDED if text == "succeed" else Job.Status.FAILED


@then(
    phrase(
        '{name:Actor} hears {their:Their} task "{label:Q}" go through {steps:Steps} and {outcome:Outcome}',
        Steps=_steps,
        Outcome=_outcome,
    )
)
def hears_task(world, name, their, label, steps, outcome):
    heard = []
    while True:
        message = world.streams[name].receive()
        if message.get("type") != "job":
            continue  # change hints for the records the action touched
        job = message["job"]
        assert job["label"] == label, job
        if job["status"] != Job.Status.RUNNING:
            break
        heard.append((job["done"], job["total"]))
    assert heard == steps, heard
    assert job["status"] == outcome, job
