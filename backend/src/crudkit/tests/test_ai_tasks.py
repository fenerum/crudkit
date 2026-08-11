from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from crudkit.fields import AIBooleanField, AICategoryField, AISummaryField, AITagsField
from crudkit.tasks import _build_field_specs, process_ai_fields
from tests.testapp.models import Comment, Ticket, Topic


class BuildFieldSpecsTests(TestCase):
    def test_summary_field(self):
        field = AISummaryField(prompt="a summary")
        field.name = "summary"
        field.verbose_name = "summary"
        specs = _build_field_specs([field])
        self.assertEqual(specs, {"summary": {"type": "string", "description": "a summary"}})

    def test_category_field_with_choices(self):
        field = AICategoryField(prompt="cat", choices=[("a", "A"), ("b", "B")])
        field.name = "cat"
        field.verbose_name = "cat"
        specs = _build_field_specs([field])
        self.assertEqual(specs["cat"]["type"], "string")
        self.assertEqual(specs["cat"]["enum"], ["a", "b"])

    def test_boolean_field(self):
        field = AIBooleanField(prompt="is spam")
        field.name = "is_spam"
        field.verbose_name = "is spam"
        specs = _build_field_specs([field])
        self.assertEqual(specs["is_spam"]["type"], "boolean")

    def test_tags_field_includes_max_tags(self):
        field = AITagsField(prompt="tags", max_tags=5)
        field.name = "tags"
        field.verbose_name = "tags"
        specs = _build_field_specs([field])
        self.assertEqual(specs["tags"]["type"], "array")
        self.assertIn("max 5 tags", specs["tags"]["description"])

    def test_falls_back_to_verbose_name(self):
        field = AISummaryField()
        field.name = "summary"
        field.verbose_name = "My Summary"
        specs = _build_field_specs([field])
        self.assertEqual(specs["summary"]["description"], "My Summary")

    def test_fk_field_builds_enum_from_related_objects(self):
        user = User.objects.create_user(username="spectest", password="pw")
        t1 = Topic.objects.create(name="Billing", created_by=user, updated_by=user)
        t2 = Topic.objects.create(name="Technical", created_by=user, updated_by=user)

        field = Ticket._meta.get_field("topic")
        specs = _build_field_specs([field])
        spec = specs["topic"]
        self.assertEqual(spec["type"], "string")
        self.assertIn(str(t1.pk), spec["enum"])
        self.assertIn(str(t2.pk), spec["enum"])
        self.assertTrue(len(spec["options"]) >= 2)


@patch("crudkit.tasks.close_old_connections")
class ProcessAIFieldsTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="aitest", password="pw")

    def _create_ticket(self, **overrides):
        defaults = {
            "subject": "Test ticket",
            "created_by": self.user,
            "updated_by": self.user,
        }
        defaults.update(overrides)
        return Ticket.objects.create(**defaults)

    @patch("crudkit.tasks.process")
    def test_happy_path_updates_fields(self, mock_process, _mock_close):
        ticket = self._create_ticket()
        mock_process.return_value = {
            "summary": "AI generated summary",
        }
        process_ai_fields("testapp", "Ticket", ticket.pk)
        ticket.refresh_from_db()
        self.assertEqual(ticket.summary, "AI generated summary")

    @patch("crudkit.tasks.process")
    def test_fk_field_resolved_by_pk(self, mock_process, _mock_close):
        topic = Topic.objects.create(name="Billing", created_by=self.user, updated_by=self.user)
        ticket = self._create_ticket()
        mock_process.return_value = {"topic": str(topic.pk)}
        process_ai_fields("testapp", "Ticket", ticket.pk)
        ticket.refresh_from_db()
        self.assertEqual(ticket.topic, topic)

    @patch("crudkit.tasks.process")
    def test_fk_field_invalid_pk_skipped(self, mock_process, _mock_close):
        ticket = self._create_ticket()
        mock_process.return_value = {"topic": "999999"}
        with self.assertLogs("crudkit.tasks", level="WARNING"):
            process_ai_fields("testapp", "Ticket", ticket.pk)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.topic)

    @patch("crudkit.tasks.process")
    def test_none_values_skipped(self, mock_process, _mock_close):
        ticket = self._create_ticket()
        mock_process.return_value = {"summary": None}
        process_ai_fields("testapp", "Ticket", ticket.pk)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.summary)

    @patch("crudkit.tasks.process")
    def test_unknown_field_names_ignored(self, mock_process, _mock_close):
        ticket = self._create_ticket()
        mock_process.return_value = {"nonexistent_field": "value", "summary": "ok"}
        process_ai_fields("testapp", "Ticket", ticket.pk)
        ticket.refresh_from_db()
        self.assertEqual(ticket.summary, "ok")

    @patch("crudkit.tasks.process")
    def test_empty_context_skips(self, mock_process, _mock_close):
        ticket = self._create_ticket()
        with patch.object(Ticket, "get_ai_context", return_value="   "):
            process_ai_fields("testapp", "Ticket", ticket.pk)
        mock_process.assert_not_called()

    @patch("crudkit.tasks.process")
    def test_missing_instance_skips(self, mock_process, _mock_close):
        with self.assertLogs("crudkit.tasks", level="WARNING"):
            process_ai_fields("testapp", "Ticket", 999999)
        mock_process.assert_not_called()

    @patch("crudkit.tasks.process", side_effect=RuntimeError("boom"))
    def test_backend_exception_skips(self, _mock_process, _mock_close):
        ticket = self._create_ticket()
        with self.assertLogs("crudkit.tasks", level="ERROR"):
            process_ai_fields("testapp", "Ticket", ticket.pk)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.summary)

    @patch("crudkit.tasks.process")
    def test_empty_result_skips(self, mock_process, _mock_close):
        ticket = self._create_ticket()
        mock_process.return_value = {}
        process_ai_fields("testapp", "Ticket", ticket.pk)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.summary)


class AiTriggerChildrenTests(TestCase):
    """Saving/deleting a child listed in CrudKitSettings.ai_trigger_children
    must re-dispatch AI processing for the parent."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="trigger", password="pw")

    def _create_ticket(self):
        return Ticket.objects.create(subject="Parent ticket", created_by=self.user, updated_by=self.user)

    def test_child_save_dispatches_parent_processing(self):
        ticket = self._create_ticket()
        with (
            patch("crudkit.tasks.process_ai_fields.delay") as mock_delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            Comment.objects.create(
                ticket=ticket,
                body="New info from the customer",
                created_by=self.user,
                updated_by=self.user,
            )
        dispatched = [call.args for call in mock_delay.call_args_list]
        self.assertIn(("testapp", "Ticket", ticket.pk), dispatched)

    def test_child_delete_dispatches_parent_processing(self):
        ticket = self._create_ticket()
        comment = Comment.objects.create(
            ticket=ticket,
            body="To be removed",
            created_by=self.user,
            updated_by=self.user,
        )
        with (
            patch("crudkit.tasks.process_ai_fields.delay") as mock_delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            comment.delete()
        dispatched = [call.args for call in mock_delay.call_args_list]
        self.assertIn(("testapp", "Ticket", ticket.pk), dispatched)
