from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from crudkit.audit import audit, current
from crudkit.models import ChangeLog
from crudkit.utils import get_system_user
from crudkit_api import services
from crudkit_assistant.models import AssistantProposal
from tests.testapp.models import Customer, Topic


def grant(user, model, *actions):
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label=model._meta.app_label,
            codename__in=[f"{action}_{model._meta.model_name}" for action in actions],
        )
    )


def entries(instance):
    return ChangeLog.objects.filter(related_object_id=instance.pk).order_by("created_at", "id")


class AuditContextTests(TestCase):
    def test_nested_calls_join_the_outer_change_set(self):
        with audit("mcp", client="Claude") as outer:
            with audit("revert") as inner:
                self.assertEqual(inner.change_set, outer.change_set)
                self.assertEqual((inner.source, inner.client), ("revert", "Claude"))
                self.assertIs(current(), inner)
            self.assertIs(current(), outer)

    def test_fallback_is_system_with_a_fresh_change_set(self):
        self.assertEqual(current().source, "system")
        self.assertNotEqual(current().change_set, current().change_set)

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError):
            audit("robot")


class AuditTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="admin", password="pw")
        self.topic = Topic.objects.create(name="Billing", created_by=self.user, updated_by=self.user)
        self.customer = Customer.objects.create(
            name="Acme", status="active", created_by=self.user, updated_by=self.user
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def url(self, instance, suffix=""):
        return f"/api/v1/{instance.TYPE_ID}/{instance.pk[3:]}/{suffix}"

    def patch(self, instance, data, **extra):
        response = self.client.patch(self.url(instance), data, format="json", **extra)
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def revert(self, change_set, force=False):
        return self.client.post(f"/api/v1/changesets/{change_set}/revert/", {"force": force}, format="json")


class EntryPathTests(AuditTestCase):
    def test_session_request_is_ui(self):
        client = APIClient()
        client.login(username="admin", password="pw")
        response = client.patch(self.url(self.customer), {"name": "Session"}, format="json")
        entry = entries(self.customer).get()
        self.assertEqual((entry.source, entry.client, entry.action), ("ui", "", "update"))
        self.assertEqual(response["X-CrudKit-Change-Set"], str(entry.change_set))

    def test_jwt_request_is_api(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.user).access_token}")
        client.patch(self.url(self.customer), {"name": "Script"}, format="json", HTTP_CLIENT_ID="nightly-sync")
        entry = entries(self.customer).get()
        self.assertEqual((entry.source, entry.client), ("api", "nightly-sync"))

    def test_jwt_request_from_the_spa_is_ui(self):
        self.patch(self.customer, {"name": "SPA"}, HTTP_CLIENT_ID="CrudKitAPIClient")
        self.assertEqual(entries(self.customer).get().source, "ui")

    def test_context_is_reset_after_an_unhandled_error(self):
        with patch("crudkit_api.views.ChangeLog.objects.create_from_objects", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.client.patch(self.url(self.customer), {"name": "Boom"}, format="json")
        self.assertEqual(current().source, "system")

    def test_reads_get_no_change_set_header(self):
        response = self.client.get(self.url(self.customer))
        self.assertNotIn("X-CrudKit-Change-Set", response)

    def test_writes_outside_a_request_are_system(self):
        services.patch_fields(self.customer, {"name": "Cron"}, self.user)
        entry = entries(self.customer).get()
        self.assertEqual(entry.source, "system")
        self.assertIsNotNone(entry.change_set)

    def test_assistant_apply(self):
        proposal = AssistantProposal.objects.create(
            target=self.customer,
            session_key="s",
            kind=AssistantProposal.Kind.PATCH,
            label="Rename",
            payload={"fields": {"name": "Assisted"}},
            created_by=self.user,
            updated_by=self.user,
        )
        outcome = proposal.apply(self.user)
        entry = entries(self.customer).get()
        self.assertEqual(entry.source, "assistant")
        self.assertEqual(outcome["change_set"], str(entry.change_set))

    def test_one_request_is_one_change_set(self):
        response = self.client.post(
            f"/api/v1/CUS/{self.customer.pk[3:]}/merge/",
            {"merge": [self.customer.pk, self.other_customer().pk], "name": self.customer.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        change_sets = set(ChangeLog.objects.values_list("change_set", flat=True))
        self.assertEqual(change_sets, {self.uuid(response["X-CrudKit-Change-Set"])})

    def other_customer(self):
        return Customer.objects.create(name="Acme dup", created_by=self.user, updated_by=self.user)

    def uuid(self, value):
        return ChangeLog._meta.get_field("change_set").to_python(value)


class LoggingTests(AuditTestCase):
    def test_delete_snapshots_the_record_and_the_deleter(self):
        deleter = User.objects.create_superuser(username="deleter", password="pw")
        self.client.force_authenticate(deleter)
        self.client.delete(self.url(self.customer))
        entry = entries(self.customer).get()
        self.assertEqual(entry.action, "delete")
        self.assertEqual(entry.field_changes["name"], ["Acme", None])
        self.assertEqual(entry.field_changes["status"], ["active", None])
        self.assertEqual((entry.created_by, entry.updated_by), (deleter, deleter))

    def test_rest_action_is_logged(self):
        response = self.client.post(self.url(self.customer, "action/"), {"action": "mark_churned"}, format="json")
        self.assertEqual(response.data, {"redirect": self.customer.pk})
        entry = entries(self.customer).get()
        self.assertEqual((entry.action, entry.label), ("action", "Mark churned"))
        self.assertEqual(entry.field_changes["status"], ["active", "churned"])
        self.assertEqual(response["X-CrudKit-Change-Set"], str(entry.change_set))

    def test_rest_action_still_rejects_unknown_actions(self):
        response = self.client.post(self.url(self.customer, "action/"), {"action": "nope"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(entries(self.customer).exists())

    def test_service_action_is_logged(self):
        services.run_action(self.customer, "mark_churned", self.user)
        entry = entries(self.customer).get()
        self.assertEqual((entry.action, entry.created_by), ("action", self.user))

    def test_merge_is_logged_and_not_revertible(self):
        dup = Customer.objects.create(name="Acme dup", created_by=self.user, updated_by=self.user)
        response = self.client.post(
            self.url(self.customer, "merge/"), {"merge": [self.customer.pk, dup.pk], "name": dup.pk}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.customer.refresh_from_db()
        self.assertEqual(entries(dup).get().action, "merge")
        self.assertEqual(entries(dup).get().label, f"Merged into {self.customer}")
        survivor = entries(self.customer).get()
        self.assertEqual((survivor.action, survivor.field_changes["name"]), ("merge", ["Acme", "Acme dup"]))

        response = self.revert(survivor.change_set)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Merges cannot be reverted", response.data["error"])

    def test_update_or_create_external_is_logged(self):
        customer, created = Customer.objects.update_or_create_external(
            "billing", "42", defaults={"name": "Imported", "created_by": self.user, "updated_by": self.user}
        )
        self.assertTrue(created)
        Customer.objects.update_or_create_external("billing", "42", defaults={"name": "Synced"})
        create, update = entries(customer)
        system = get_system_user()
        self.assertEqual((create.action, create.label, create.created_by), ("create", "Imported from billing", system))
        self.assertEqual((update.action, update.label, update.source), ("update", "Updated from billing", "system"))
        self.assertEqual(update.field_changes["name"], ["Imported", "Synced"])

    def test_create_from_objects_stays_positional(self):
        old = Customer.objects.get(pk=self.customer.pk)
        self.customer.name = "Renamed"
        entry = ChangeLog.objects.create_from_objects(old, self.customer)
        self.assertEqual((entry.action, entry.field_changes), ("update", {"name": ["Acme", "Renamed"]}))


class RevertTests(AuditTestCase):
    def last_change_set(self, instance):
        return entries(instance).last().change_set

    def test_update_round_trip(self):
        self.patch(self.customer, {"name": "Acme Inc", "topic": self.topic.pk, "balance": "12.50"})
        change_set = self.last_change_set(self.customer)

        response = self.revert(change_set)

        self.assertEqual(response.status_code, 200, response.data)
        self.customer.refresh_from_db()
        self.assertEqual((self.customer.name, self.customer.topic, self.customer.balance), ("Acme", None, None))
        revert = entries(self.customer).last()
        self.assertEqual((revert.action, revert.source, revert.revert_of), ("revert", "revert", change_set))
        self.assertEqual(response.data["change_set"], str(revert.change_set))

    def test_revert_restores_foreign_keys_and_decimals(self):
        self.customer.topic = self.topic
        self.customer.balance = Decimal("10.00")
        self.customer.save()
        self.patch(self.customer, {"topic": None, "balance": "20.00"})

        self.assertEqual(self.revert(self.last_change_set(self.customer)).status_code, 200)

        self.customer.refresh_from_db()
        self.assertEqual((self.customer.topic, self.customer.balance), (self.topic, Decimal("10.00")))

    def test_create_round_trip(self):
        response = self.client.post("/api/v1/CUS/", {"name": "Fresh"}, format="json")
        created = Customer.objects.get(pk=response.data["id"])

        self.assertEqual(self.revert(response["X-CrudKit-Change-Set"]).status_code, 200)

        created.refresh_from_db()
        self.assertTrue(created.deleted)

    def test_delete_round_trip(self):
        response = self.client.delete(self.url(self.customer))

        self.assertEqual(self.revert(response["X-CrudKit-Change-Set"]).status_code, 200)

        self.customer.refresh_from_db()
        self.assertFalse(self.customer.deleted)

    def test_action_round_trip(self):
        services.run_action(self.customer, "mark_churned", self.user)
        self.revert(self.last_change_set(self.customer))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, "active")

    def test_conflicts_block_revert_unless_forced(self):
        self.patch(self.customer, {"name": "B"})
        first = self.last_change_set(self.customer)
        self.patch(self.customer, {"name": "C"})

        response = self.revert(first)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data["conflicts"],
            [
                {
                    "object": self.customer.pk,
                    "label": "C",
                    "field": "name",
                    "expected": "B",
                    "current": "C",
                    "reason": "",
                }
            ],
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "C")
        self.assertFalse(ChangeLog.objects.filter(revert_of=first).exists())

        self.assertEqual(self.revert(first, force=True).status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Acme")

    def test_double_revert_is_refused(self):
        self.patch(self.customer, {"name": "B"})
        change_set = self.last_change_set(self.customer)
        self.assertEqual(self.revert(change_set).status_code, 200)

        response = self.revert(change_set)

        self.assertEqual(response.status_code, 400)
        self.assertIn("already been reverted", response.data["error"])

    def test_a_revert_can_itself_be_reverted(self):
        self.patch(self.customer, {"name": "B"})
        undo = self.revert(self.last_change_set(self.customer)).data["change_set"]
        self.assertEqual(self.revert(undo).status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "B")

    def test_revert_needs_change_permission_on_every_record(self):
        self.patch(self.customer, {"name": "B"})
        viewer = User.objects.create_user("viewer", password="pw")
        grant(viewer, Customer, "view")
        self.client.force_authenticate(viewer)

        response = self.revert(self.last_change_set(self.customer))

        self.assertEqual(response.status_code, 403)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "B")

    def test_undoing_an_action_needs_permission_to_run_it(self):
        services.run_action(self.customer, "mark_churned", self.user)
        staff = User.objects.create_user("staff", password="pw")
        grant(staff, Customer, "view", "change")
        self.client.force_authenticate(staff)
        only_superusers = staticmethod(lambda user, instance, action_name: user.is_superuser)

        with patch.object(Customer.CrudKitSettings, "has_action_permission", only_superusers, create=True):
            response = self.revert(self.last_change_set(self.customer))

        self.assertEqual(response.status_code, 403)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, "churned")

    def test_records_gone_since_are_conflicts(self):
        self.patch(self.customer, {"name": "B"})
        change_set = self.last_change_set(self.customer)
        Customer.objects.filter(pk=self.customer.pk).delete()

        response = self.revert(change_set)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["conflicts"][0]["reason"], "The record no longer exists")
        self.assertEqual(self.revert(change_set, force=True).data["reverted"], 0)

    def test_unknown_change_set_is_404(self):
        self.assertEqual(self.revert("00000000-0000-0000-0000-000000000000").status_code, 404)

    def test_legacy_entries_are_not_revertible(self):
        self.patch(self.customer, {"name": "B"})
        entries(self.customer).update(action="")
        self.assertEqual(self.revert(self.last_change_set(self.customer)).status_code, 400)


class RestoreAndHistoryTests(AuditTestCase):
    def test_restore(self):
        self.client.delete(self.url(self.customer))

        response = self.client.post(self.url(self.customer, "restore/"))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["deleted"])
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.deleted)
        self.assertEqual(entries(self.customer).last().action, "restore")

    def test_restore_refuses_live_and_merged_records(self):
        self.assertEqual(self.client.post(self.url(self.customer, "restore/")).status_code, 400)
        dup = Customer.objects.create(name="dup", created_by=self.user, updated_by=self.user)
        dup.delete_and_merge_with(self.customer)
        self.assertEqual(self.client.post(self.url(dup, "restore/")).status_code, 400)

    def test_restore_needs_change_permission(self):
        self.customer.soft_delete()
        viewer = User.objects.create_user("viewer", password="pw")
        grant(viewer, Customer, "view")
        self.client.force_authenticate(viewer)
        self.assertEqual(self.client.post(self.url(self.customer, "restore/")).status_code, 403)

    def test_history_groups_by_change_set(self):
        self.patch(self.customer, {"name": "B"})
        self.patch(self.customer, {"name": "C"}, HTTP_CLIENT_ID="CrudKitAPIClient")

        history = self.client.get(self.url(self.customer, "history/")).data

        self.assertEqual([batch["source"] for batch in history], ["ui", "api"])
        latest = history[0]
        self.assertEqual(latest["by"], {"id": self.user.pk, "label": "admin"})
        self.assertEqual(latest["actions"], ["update"])
        self.assertEqual(latest["entries"][0]["field_changes"], {"name": ["B", "C"]})
        self.assertEqual((latest["revertible"], latest["reverted"], latest["other_records"]), (True, False, 0))

        self.revert(latest["change_set"])
        history = self.client.get(self.url(self.customer, "history/")).data
        self.assertEqual(history[0]["actions"], ["revert"])
        self.assertEqual((history[1]["revertible"], history[1]["reverted"]), (False, True))

    def test_history_of_a_deleted_record(self):
        self.client.delete(self.url(self.customer))
        history = self.client.get(self.url(self.customer, "history/")).data
        self.assertEqual(history[0]["actions"], ["delete"])

    def test_changelog_service_reports_the_change_set(self):
        self.patch(self.customer, {"name": "B"})
        entry = services.get_changelog(self.customer)[0]
        self.assertEqual(entry["change_set"], str(self.last_change_set()))
        self.assertEqual((entry["action"], entry["source"]), ("update", "api"))

    def last_change_set(self):
        return entries(self.customer).last().change_set
