from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from crudkit.models import View, Workspace
from tests.testapp.models import Customer, Ticket


def grant(user, model, *actions):
    permissions = Permission.objects.filter(
        content_type__app_label=model._meta.app_label,
        codename__in=[f"{action}_{model._meta.model_name}" for action in actions],
    )
    user.user_permissions.add(*permissions)


class GenericAPIAuthorizationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pw")
        self.other = User.objects.create_user(username="other", password="pw")
        self.customer = Customer.objects.create(
            name="Visible customer",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.client = APIClient()

    def test_anonymous_requests_are_rejected(self):
        response = self.client.get("/api/v1/CUS/")
        self.assertEqual(response.status_code, 401)

    def test_authenticated_user_needs_model_permission(self):
        self.client.force_authenticate(self.other)
        response = self.client.get("/api/v1/CUS/")
        self.assertEqual(response.status_code, 403)

    def test_user_with_view_permission_can_list_model(self):
        grant(self.other, Customer, "view")
        self.client.force_authenticate(self.other)
        response = self.client.get("/api/v1/CUS/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [self.customer.pk])

    def test_private_views_and_workspaces_are_owner_scoped(self):
        grant(self.other, View, "view", "change")
        grant(self.other, Workspace, "view")
        public_view = View.objects.create(
            name="Shared",
            model="CUS",
            fields=["name"],
            public=True,
            created_by=self.owner,
            updated_by=self.owner,
        )
        private_view = View.objects.create(
            name="Private",
            model="CUS",
            fields=["name"],
            public=False,
            created_by=self.owner,
            updated_by=self.owner,
        )
        own_view = View.objects.create(
            name="Mine",
            model="CUS",
            fields=["name"],
            public=False,
            created_by=self.other,
            updated_by=self.other,
        )
        public_workspace = Workspace.objects.create(
            name="Shared workspace",
            public=True,
            created_by=self.owner,
            updated_by=self.owner,
        )
        Workspace.objects.create(
            name="Private workspace",
            public=False,
            created_by=self.owner,
            updated_by=self.owner,
        )

        self.client.force_authenticate(self.other)
        views = self.client.get("/api/v1/VIW/").data["results"]
        workspaces = self.client.get("/api/v1/WSP/").data["results"]

        self.assertEqual({row["id"] for row in views}, {public_view.pk, own_view.pk})
        self.assertEqual({row["id"] for row in workspaces}, {public_workspace.pk})

        response = self.client.patch(
            f"/api/v1/VIW/{private_view.pk}/",
            {"name": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_search_only_returns_permitted_models(self):
        grant(self.other, Customer, "view")
        Ticket.objects.create(
            subject="Visible customer internal ticket",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.client.force_authenticate(self.other)

        response = self.client.get("/api/v1/search/", {"q": "Visible customer"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [self.customer.pk])
