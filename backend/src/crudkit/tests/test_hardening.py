"""
The change log's edges: who may read history, undoing actions that are gone
or deleted their record, syncs that change nothing, AI context validation,
merge validation, many-to-many changes and the change log indexes.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from crudkit import llm
from crudkit.audit import audit
from crudkit.decorators import crm_action
from crudkit.models import AIContext, ChangeLog
from crudkit.tests.test_audit import entries, grant
from crudkit_api import services
from tests.testapp.models import Customer, Ticket


class HistoryPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user")
        grant(self.user, Customer, "view", "change")
        self.customer = Customer.objects.create(name="Acme", created_by=self.user, updated_by=self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def url(self):
        return f"/api/v1/CUS/{self.customer.pk[3:]}/history/"

    def test_history_needs_the_change_log_permission(self):
        self.assertEqual(self.api.get(self.url()).status_code, 403)
        grant(self.user, ChangeLog, "view")
        self.user = User.objects.get(pk=self.user.pk)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.get(self.url()).status_code, 200)


class RevertEdgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin")
        self.customer = Customer.objects.create(name="Acme", created_by=self.user, updated_by=self.user)

    def test_an_action_that_no_longer_exists_cannot_be_undone(self):
        with audit("ui", user=self.user) as context:
            services.perform_action(self.customer, "mark_churned", self.user)
        ChangeLog.objects.filter(change_set=context.change_set).update(label="A renamed action")
        with self.assertRaisesRegex(PermissionDenied, "no longer exists"):
            services.revert_change_set(context.change_set, self.user)
        self.assertTrue(services.revert_requires_approval(context.change_set))

    def test_an_action_that_deletes_its_record_is_logged_as_a_delete(self):
        def self_destruct(self, request):
            self.delete()

        pk = self.customer.pk  # delete() clears it
        with patch.object(Customer, "self_destruct", crm_action("Self-destruct")(self_destruct), create=True):
            services.perform_action(self.customer, "self_destruct", self.user)
        entry = ChangeLog.objects.filter(related_object_id=pk).order_by("created_at", "id").last()
        self.assertEqual((entry.action, entry.label), ("delete", "Self-destruct"))

    def test_a_revert_the_model_rejects_is_refused(self):
        with audit("ui", user=self.user) as context:
            services.patch_fields(self.customer, {"name": "Acme 2"}, self.user)
        with patch.object(Customer, "clean", side_effect=ValidationError("no")):
            with self.assertRaisesRegex(ValueError, "Could not revert"):
                services.revert_change_set(context.change_set, self.user)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Acme 2")


class SyncLoggingTests(TestCase):
    def test_a_sync_that_changes_nothing_logs_nothing(self):
        user = User.objects.create_superuser("admin")
        defaults = {"name": "Imported", "created_by": user, "updated_by": user}
        customer, _ = Customer.objects.update_or_create_external("billing", "42", defaults=defaults)
        Customer.objects.update_or_create_external("billing", "42", defaults={"name": "Imported"})
        Customer.objects.update_or_create_external("billing", "42", defaults={"name": "Imported"})
        self.assertEqual([entry.action for entry in entries(customer)], ["create"])


class MergeValidationTests(TestCase):
    def test_merge_runs_model_validation(self):
        user = User.objects.create_superuser("admin")
        a = Customer.objects.create(name="A", created_by=user, updated_by=user)
        b = Customer.objects.create(name="B", created_by=user, updated_by=user)
        api = APIClient()
        api.force_authenticate(user)
        with patch.object(Customer, "clean", side_effect=ValidationError("not allowed")):
            response = api.post(f"/api/v1/CUS/{a.pk}/merge/", {"merge": [a.pk, b.pk], "id": a.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        b.refresh_from_db()
        self.assertFalse(b.deleted)


class AIContextHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin")

    def doc(self, **fields):
        return AIContext(name="Doc", body="Text", created_by=self.user, updated_by=self.user, **fields)

    def test_model_types_must_be_known_type_ids(self):
        for bad in ("CUS", ["NOPE"], [1]):
            with self.assertRaises(ValidationError, msg=bad):
                self.doc(model_types=bad).clean()
        self.doc(model_types=["CUS"]).clean()

    def test_a_malformed_stored_value_matches_nothing(self):
        # Saved before validation existed: "CUSOPP" must not substring-match "CUS".
        AIContext.objects.create(
            name="Old", body="Scoped", model_types="CUSOPP", created_by=self.user, updated_by=self.user
        )
        self.assertNotIn("Scoped", llm.ai_context("CUS"))

    @override_settings(CRUDKIT_AI_CONTEXT_MAX_CHARS=50)
    def test_long_context_is_truncated(self):
        AIContext.objects.create(name="Long", body="x" * 500, created_by=self.user, updated_by=self.user)
        text = llm.ai_context()
        self.assertTrue(text.endswith("[AI context truncated]"))
        self.assertLess(len(text), 100)


class ChangeLogIndexTests(TestCase):
    def test_the_audit_indexes_exist(self):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, ChangeLog._meta.db_table)
        indexed = {tuple(c["columns"]) for c in constraints.values() if c["index"]}
        for columns in (("change_set",), ("revert_of",), ("related_content_type_id", "related_object_id")):
            self.assertIn(columns, indexed)


class ManyToManyLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin")
        self.ticket = Ticket.objects.create(subject="Help", created_by=self.user, updated_by=self.user)
        self.a = Customer.objects.create(name="A", created_by=self.user, updated_by=self.user)
        self.b = Customer.objects.create(name="B", created_by=self.user, updated_by=self.user)

    def m2m_entries(self):
        return [e for e in entries(self.ticket) if "watchers" in (e.field_changes or {})]

    def test_changes_are_logged_with_the_ids_before_and_after(self):
        with audit("ui", user=self.user) as context:
            self.ticket.watchers.add(self.a)
            self.ticket.watchers.add(self.a)  # no change, no entry
            self.ticket.watchers.remove(self.a)
        added, removed = self.m2m_entries()
        self.assertEqual(added.field_changes["watchers"], [[], [self.a.pk]])
        self.assertEqual(removed.field_changes["watchers"], [[self.a.pk], []])
        self.assertEqual({added.change_set, removed.change_set}, {context.change_set})
        self.assertEqual((added.action, added.source, added.created_by), ("update", "ui", self.user))

    def test_the_reverse_side_is_not_logged(self):
        # Customer has no reverse accessor (related_name="+"); a through-model write is the reverse-free case.
        Ticket.watchers.through.objects.create(ticket_id=self.ticket.pk, customer_id=self.a.pk)
        self.assertEqual(self.m2m_entries(), [])

    def test_revert_restores_the_set(self):
        self.ticket.watchers.add(self.a)
        with audit("ui", user=self.user) as context:
            self.ticket.watchers.set([self.b])
        result = services.revert_change_set(context.change_set, self.user)
        self.assertNotIn("conflicts", result)
        self.assertEqual(list(self.ticket.watchers.all()), [self.a])
        self.assertTrue(all(e.revert_of == context.change_set for e in ChangeLog.objects.filter(source="revert")))

    def test_revert_reports_a_set_changed_since(self):
        with audit("ui", user=self.user) as context:
            self.ticket.watchers.add(self.a)
        self.ticket.watchers.add(self.b)
        result = services.revert_change_set(context.change_set, self.user)
        self.assertEqual([c["field"] for c in result["conflicts"]], ["watchers"])
        self.assertEqual(set(self.ticket.watchers.all()), {self.a, self.b})
