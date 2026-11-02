"""crudkit.jobs: the task an action reports progress into."""

import threading
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from crudkit import jobs
from crudkit.decorators import crm_action
from crudkit.models import Job
from crudkit_api import services
from tests.testapp.models import Customer


def counting(self, request):
    for i in range(1, 4):
        jobs.progress(i, total=3, message=f"Step {i}")


class JobTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin")
        self.customer = Customer.objects.create(name="Acme", created_by=self.user, updated_by=self.user)

    def run_action(self, fn, name="count"):
        with patch.object(Customer, name, crm_action("Count")(fn), create=True):
            return services.run_action(self.customer, name, self.user)

    def test_the_task_is_named_after_the_action_and_points_at_the_record(self):
        outcome = self.run_action(counting)
        job = Job.objects.get()
        self.assertEqual(outcome["job"], job.pk)
        self.assertRegex(job.pk, r"^JOB\d+$")
        self.assertEqual((job.label, job.target, job.created_by), ("Count", self.customer, self.user))
        self.assertEqual((job.status, job.done, job.total, job.message), ("succeeded", 3, 3, "Step 3"))
        self.assertEqual((job.as_event()["target"], job.as_event()["target_label"]), (self.customer.pk, "Acme"))

    def test_an_action_that_raises_fails_its_task_and_still_raises(self):
        def crash(self, request):
            jobs.progress(1, total=2)
            raise ValueError("Disk full")

        with self.assertRaisesRegex(ValueError, "Disk full"):
            self.run_action(crash)
        self.assertEqual((Job.objects.get().status, Job.objects.get().error), ("failed", "Disk full"))

    def test_progress_outside_an_action_does_nothing(self):
        jobs.progress(1, total=2)
        self.assertIsNone(jobs.current())
        self.assertFalse(Job.objects.exists())

    def test_hand_off_outside_an_action_is_refused(self):
        with self.assertRaises(RuntimeError):
            jobs.hand_off()

    def test_current_is_the_running_task(self):
        seen = []

        def look(self, request):
            seen.append(jobs.current())
            jobs.progress(1)
            seen.append(jobs.current())

        self.run_action(look)
        self.assertEqual(seen, [None, Job.objects.get()])

    def test_progress_is_saved_at_most_once_a_second(self):
        with patch.object(Job, "save", autospec=True, side_effect=Job.save) as save:
            self.run_action(lambda self, request: [jobs.progress(i, total=100) for i in range(100)])
        # The create, then the final save; the steps in between came too fast.
        self.assertEqual(save.call_count, 2)


class JobThreadTests(TestCase):
    def test_actions_running_at_once_report_into_their_own_tasks(self):
        user = User.objects.create_superuser("admin")
        both_running = threading.Barrier(2)
        trackers = {}

        def run(name):
            with jobs.track(name, user) as tracker:
                trackers[name] = tracker
                for i in range(1, 6):
                    jobs.progress(i, total=5, message=name)
                    both_running.wait(timeout=5)

        # SQLite can't take writes from two threads; the rows aren't the point here.
        with (
            patch.object(Job.objects, "create", side_effect=lambda **kw: Job(**kw)),
            patch.object(Job, "save"),
        ):
            threads = [threading.Thread(target=run, args=(name,)) for name in ("A", "B")]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        for name, tracker in trackers.items():
            self.assertEqual((tracker.job.label, tracker.job.message, tracker.job.done), (name, name, 5))
