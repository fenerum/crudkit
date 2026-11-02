"""Progress bars for long-running @crm_actions.

Inside an action, or anything it calls, ``progress(done, total)`` reports how
far it got. The person who started the action sees the bar move live in their
task tray and on the record. The task finishes when the action returns, or
fails if it raises::

    @crm_action("Recalculate invoices")
    def recalculate(self, request):
        for i, invoice in enumerate(invoices, 1):
            invoice.recalculate()
            jobs.progress(i, total=len(invoices))

To carry on in the background, ``hand_off()`` the task and finish it in a
Celery task under ``resume(job_id)``::

    @crm_action("Import contacts")
    def import_contacts(self, request):
        import_contacts_task.delay(jobs.hand_off().pk)

    @shared_task
    def import_contacts_task(job_id):
        with jobs.resume(job_id):
            ...
            jobs.progress(i, total=n)

The current task is held in a ContextVar, like ``crudkit.audit``'s context:
each thread, asyncio task and Celery task has its own, so actions running at
the same time never report into each other's bar. Outside an action or
``resume()``, ``progress()`` does nothing. An action run inside another task
(e.g. once per record of a bulk run) reports into that task's bar instead:
its own ``progress()`` calls are ignored, while ``hand_off()`` still gives it
a task of its own.
"""

import time
from contextvars import ContextVar

from django.utils import timezone

from crudkit.audit import audit
from crudkit.models import Job
from crudkit.realtime import send_to_user

# Progress is pushed to the browser more often than it is written to the
# database; the database copy is for page reloads and polling clients.
PUSH_EVERY = 0.25
SAVE_EVERY = 1.0


class _Tracker:
    """The task an action is reporting into; its Job row is created on first use."""

    def __init__(self, label, user, target=None, job=None, muted=False):
        self.label = label
        self.muted = muted
        self.user = user
        self.target = target
        self.job = job
        self._pushed_at = self._saved_at = time.monotonic()

    @property
    def detached(self) -> bool:
        return self.job is not None and self.job.detached

    def get_job(self, **progress) -> Job:
        if self.job is None:
            self.job = Job.objects.create(
                label=self.label, target=self.target, created_by=self.user, updated_by=self.user, **progress
            )
            self._saved_at = time.monotonic()
            self._push()
        return self.job

    def update(self, done, total=None, message=None):
        message = message[:255] if message is not None else None
        if self.job is None:
            self.get_job(done=done, total=total, message=message or "")
            return
        job = self.job
        job.done = done
        if total is not None:
            job.total = total
        if message is not None:
            job.message = message
        now = time.monotonic()
        if now - self._saved_at >= SAVE_EVERY:
            self._save()
        if now - self._pushed_at >= PUSH_EVERY:
            self._push()

    def finish(self, error: BaseException | None = None):
        job = self.job
        if job is None or job.finished_at is not None:
            return
        if error is None:
            job.status = Job.Status.SUCCEEDED
            if job.total is not None:
                job.done = job.total
        else:
            job.status = Job.Status.FAILED
            job.error = str(error) or error.__class__.__name__
        job.finished_at = timezone.now()
        self._save()
        self._push()

    def _save(self):
        self._saved_at = time.monotonic()
        self.job.save()

    def _push(self):
        self._pushed_at = time.monotonic()
        send_to_user(self.job.created_by_id, {"type": "crudkit.job", "job": self.job.as_event()})


_current: ContextVar[_Tracker | None] = ContextVar("crudkit_job", default=None)


def current() -> Job | None:
    """The task the running action or background task reports into, if it has one yet."""
    tracker = _current.get()
    return tracker.job if tracker else None


def progress(done: int, total: int | None = None, message: str | None = None) -> None:
    """Report that `done` of `total` steps are done; `total` may stay unknown.
    `message` (e.g. the item being worked on) shows under the bar."""
    tracker = _current.get()
    if tracker is not None and not tracker.muted:
        tracker.update(done, total, message)


def hand_off() -> Job:
    """Keep the action's task running after the action returns; finish it
    from a background task wrapped in resume(job.pk)."""
    tracker = _current.get()
    if tracker is None:
        raise RuntimeError("hand_off() is only available inside a @crm_action")
    job = tracker.get_job()
    job.detached = True
    job.save(update_fields=["detached", "updated_at"])
    return job


class track:
    """Report progress() calls made inside into a task labelled after the
    action. perform_action wraps every action in one."""

    def __init__(self, label, user, target=None):
        self.tracker = _Tracker(label, user, target, muted=_current.get() is not None)

    def __enter__(self) -> _Tracker:
        self._token = _current.set(self.tracker)
        return self.tracker

    def __exit__(self, exc_type, exc, tb):
        _current.reset(self._token)
        if not self.tracker.detached:
            self.tracker.finish(exc)
        return False


class resume:
    """Carry on a handed-off task; it finishes when the block exits, failed if it raises."""

    def __init__(self, job_id):
        self.job = Job.objects.select_related("created_by").get(pk=job_id)
        self.tracker = _Tracker(self.job.label, self.job.created_by, job=self.job)
        self.audit = audit("system", user=self.job.created_by)

    def __enter__(self) -> Job:
        self._token = _current.set(self.tracker)
        self.audit.__enter__()
        return self.job

    def __exit__(self, exc_type, exc, tb):
        self.audit.__exit__(exc_type, exc, tb)
        _current.reset(self._token)
        self.tracker.finish(exc)
        return False
