"""Approving proposals outside the sidebar: the confirm/skip actions behind
the Inbox, CREATE proposals, owner access to ASP rows, and approval rules."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from crudkit.authorization import requires_approval
from crudkit.models import ChangeLog
from crudkit_api.metadata import build_model_metadata
from crudkit_assistant.proposals import create_proposal
from tests.testapp.models import Customer, Topic

User = get_user_model()


def changes(instance):
    return ChangeLog.objects.filter(
        related_content_type=ContentType.objects.get_for_model(instance), related_object_id=instance.pk
    )


def grant(user, model, *actions):
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label=model._meta.app_label,
            codename__in=[f"{action}_{model._meta.model_name}" for action in actions],
        )
    )


class ApprovalTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("approver")
        grant(self.user, Customer, "view", "add", "change")
        self.customer = Customer.objects.create(name="Acme", created_by=self.user, updated_by=self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def propose(self, kind="patch", payload=None, instance=None, model=Customer, user=None):
        return create_proposal(
            user or self.user,
            model,
            instance if instance is not None or kind == "create" else self.customer,
            kind,
            "Test proposal",
            payload or {"fields": {"name": "Acme Inc"}},
            source="mcp",
            client="Research Bot",
        )

    def act(self, proposal, action, user=None):
        if user:
            self.api.force_authenticate(user)
        return self.api.post(f"/api/v1/ASP/{proposal.id}/action/", {"action": action}, format="json")


class ConfirmActionTests(ApprovalTestCase):
    def test_confirm_applies_as_the_proposals_source(self):
        proposal = self.propose()

        response = self.act(proposal, "confirm")

        self.assertEqual(response.status_code, 200, response.content)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Acme Inc")
        proposal.refresh_from_db()
        self.assertEqual((proposal.status, proposal.confirmed_by), ("confirmed", self.user))
        change = changes(self.customer).get()
        self.assertEqual((change.source, change.client, change.created_by), ("mcp", "Research Bot", self.user))
        self.assertEqual(proposal.outcome["change_set"], str(change.change_set))
        # The proposal's own status change is the approver's request, in another change set.
        status_change = changes(proposal).get(action=ChangeLog.Action.ACTION)
        self.assertNotEqual(status_change.change_set, change.change_set)

    def test_confirm_needs_permission_on_the_target(self):
        creator = User.objects.create_user("viewer")
        grant(creator, Customer, "view")
        proposal = self.propose(user=creator)

        response = self.act(proposal, "confirm", user=creator)

        self.assertEqual(response.status_code, 403)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "pending")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Acme")

    def test_other_users_proposals_are_hidden(self):
        proposal = self.propose()
        other = User.objects.create_user("other")
        grant(other, Customer, "view", "change")
        self.assertEqual(self.act(proposal, "confirm", user=other).status_code, 404)

    def test_resolved_proposals_cannot_be_confirmed(self):
        proposal = self.propose()
        self.act(proposal, "skip")
        self.assertEqual(self.act(proposal, "confirm").status_code, 403)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Acme")

    def test_failed_apply_reports_the_error(self):
        proposal = self.propose(payload={"fields": {"status": "bogus"}})
        response = self.act(proposal, "confirm")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Validation failed", response.json()["errors"][0])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "failed")

    def test_skip(self):
        proposal = self.propose()
        self.assertEqual(self.act(proposal, "skip").status_code, 200)
        proposal.refresh_from_db()
        self.assertEqual((proposal.status, proposal.confirmed_by), ("skipped", self.user))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Acme")


class CreateProposalTests(ApprovalTestCase):
    def test_create_round_trip(self):
        grant(self.user, Topic, "view")
        topic = Topic.objects.create(name="Billing", created_by=self.user, updated_by=self.user)
        proposal = self.propose("create", {"type": "CUS", "fields": {"name": "Globex", "topic": topic.id}})

        listed = self.api.get("/api/v1/ASP/", {"status": "pending"}).json()["results"]
        self.assertEqual([(row["id"], row["target"], row["kind"]) for row in listed], [(proposal.id, None, "create")])

        self.assertEqual(self.act(proposal, "confirm").status_code, 200)

        created = Customer.objects.get(name="Globex")
        self.assertEqual(created.topic, topic)
        proposal.refresh_from_db()
        self.assertEqual(proposal.target, created)
        self.assertEqual(proposal.outcome["id"], created.id)
        self.assertEqual(self.api.get(f"/api/v1/ASP/{proposal.id}/").json()["target"], created.id)
        self.assertEqual(changes(created).get().source, "mcp")

    def test_create_needs_add_permission(self):
        creator = User.objects.create_user("editor")
        grant(creator, Customer, "view", "change")
        proposal = self.propose("create", {"type": "CUS", "fields": {"name": "Globex"}}, user=creator)
        self.assertEqual(self.act(proposal, "confirm", user=creator).status_code, 403)
        self.assertFalse(Customer.objects.filter(name="Globex").exists())


class OwnerAccessTests(ApprovalTestCase):
    def test_users_without_proposal_permissions_list_their_own(self):
        mine = self.propose()
        other = User.objects.create_user("other")
        grant(other, Customer, "view", "change")
        self.propose(user=other)

        response = self.api.get("/api/v1/ASP/")

        self.assertEqual([row["id"] for row in response.json()["results"]], [mine.id])

    def test_owner_access_does_not_grant_delete(self):
        proposal = self.propose()
        self.assertEqual(self.api.delete(f"/api/v1/ASP/{proposal.id}/").status_code, 403)

    def test_superusers_see_every_proposal(self):
        self.propose()
        admin = User.objects.create_superuser("admin")
        self.api.force_authenticate(admin)
        self.assertEqual(self.api.get("/api/v1/ASP/").json()["count"], 1)


class RequiresApprovalTests(TestCase):
    def test_actions_and_fields(self):
        self.assertFalse(requires_approval(Customer, action="mark_churned"))
        self.assertFalse(requires_approval(Customer, fields=["status"]))
        with (
            patch.object(Customer.mark_churned, "requires_approval", True),
            patch.object(Customer.CrudKitSettings, "approval_fields", ["status"], create=True),
        ):
            self.assertTrue(requires_approval(Customer, action="mark_churned"))
            self.assertTrue(requires_approval(Customer, fields={"name": "x", "status": "churned"}))
            self.assertFalse(requires_approval(Customer, fields=["name"]))
            self.assertFalse(requires_approval(Customer, action="missing"))
            self.assertTrue(build_model_metadata(Customer)["actions"][0]["requires_approval"])
