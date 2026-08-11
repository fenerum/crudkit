from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from tests.testapp.models import Ticket, Topic


class BackfillAIFieldsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="backfill", password="pw")

    def _create_ticket(self, **overrides):
        defaults = {
            "subject": "Backfill test",
            "created_by": self.user,
            "updated_by": self.user,
        }
        defaults.update(overrides)
        return Ticket.objects.create(**defaults)

    def test_bad_model_format_raises(self):
        with self.assertRaises(CommandError, msg="app_label.ModelName format"):
            call_command("backfill_ai_fields", model="BadFormat")

    def test_model_not_found_raises(self):
        with self.assertRaises(CommandError, msg="not found"):
            call_command("backfill_ai_fields", model="testapp.NonExistent")

    def test_not_basecrudkitmodel_raises(self):
        with self.assertRaises(CommandError, msg="not a BaseCrudKitModel"):
            call_command("backfill_ai_fields", model="auth.User")

    def test_no_ai_fields_raises(self):
        with self.assertRaises(CommandError, msg="no AI fields"):
            call_command("backfill_ai_fields", model="crudkit.Layout")

    @patch("crudkit.management.commands.backfill_ai_fields.process_ai_fields")
    def test_async_mode_calls_delay(self, mock_task):
        ticket = self._create_ticket()
        call_command("backfill_ai_fields", model="testapp.Ticket", stdout=StringIO())
        mock_task.delay.assert_called()
        call_args = mock_task.delay.call_args
        self.assertEqual(call_args[0], ("testapp", "Ticket", ticket.pk))

    @patch("crudkit.management.commands.backfill_ai_fields.process_ai_fields")
    def test_sync_mode_calls_directly(self, mock_task):
        ticket = self._create_ticket()
        call_command("backfill_ai_fields", model="testapp.Ticket", sync=True, stdout=StringIO())
        mock_task.assert_called()
        call_args = mock_task.call_args
        self.assertEqual(call_args[0], ("testapp", "Ticket", ticket.pk))
        mock_task.delay.assert_not_called()

    @patch("crudkit.management.commands.backfill_ai_fields.process_ai_fields")
    def test_skips_instances_with_filled_fields(self, mock_task):
        topic = Topic.objects.create(name="Billing", created_by=self.user, updated_by=self.user)
        ticket = self._create_ticket()
        ticket.summary = "Already filled"
        ticket.topic = topic
        ticket.is_urgent = False
        ticket.tags = ["billing"]
        ticket.save(update_fields=["summary", "topic_id", "is_urgent", "tags"])

        call_command("backfill_ai_fields", model="testapp.Ticket", stdout=StringIO())
        mock_task.delay.assert_not_called()

    @patch("crudkit.management.commands.backfill_ai_fields.process_ai_fields")
    def test_includes_instances_with_empty_fields(self, mock_task):
        ticket = self._create_ticket()
        self.assertIsNone(ticket.summary)

        call_command("backfill_ai_fields", model="testapp.Ticket", stdout=StringIO())
        mock_task.delay.assert_called_once()
