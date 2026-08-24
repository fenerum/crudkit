from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from crudkit.models import View, Workspace


class WorkspaceCleanTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="agent", password="pw")
        self.view = View.objects.create(
            name="All views",
            model="VIW",
            fields=["name"],
            created_by=self.user,
            updated_by=self.user,
        )

    def make_workspace(self, views):
        return Workspace(
            name="Sales",
            views=views,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_valid_view_ids_pass(self):
        self.make_workspace([self.view.pk]).full_clean()

    def test_empty_list_passes(self):
        self.make_workspace([]).full_clean()

    def test_non_list_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_workspace("VIW1").full_clean()
        self.assertIn("views", ctx.exception.message_dict)

    def test_non_view_type_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_workspace(["BOK1"]).full_clean()
        self.assertIn("views", ctx.exception.message_dict)

    def test_malformed_id_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_workspace(["not-an-id"]).full_clean()
        self.assertIn("views", ctx.exception.message_dict)

    def test_nonexistent_view_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_workspace(["VIW999999"]).full_clean()
        self.assertIn("views", ctx.exception.message_dict)


class WorkspaceAPITests(TestCase):
    """The generic CRUD machinery must serve Workspace with zero bespoke code."""

    def setUp(self):
        self.user = User.objects.create_superuser(username="admin", password="pw")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.view = View.objects.create(
            name="All views",
            model="VIW",
            fields=["name"],
            created_by=self.user,
            updated_by=self.user,
        )

    def test_create_and_list(self):
        response = self.client.post(
            "/api/v1/WSP/",
            {"name": "Sales", "views": [self.view.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["name"], "Sales")
        self.assertEqual(response.data["views"], [self.view.pk])

        response = self.client.get("/api/v1/WSP/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_metadata_includes_views_jsonfield(self):
        response = self.client.get("/api/v1/WSP/metadata/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["type"], "WSP")
        self.assertEqual(response.data["fields"]["views"]["type"], "JSONField")

    def test_invalid_create_does_not_persist(self):
        response = self.client.post(
            "/api/v1/WSP/",
            {"name": "Invalid", "views": "not-a-list"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Workspace.objects.filter(name="Invalid").exists())

    def test_invalid_update_does_not_persist(self):
        workspace = Workspace.objects.create(
            name="Sales",
            views=[self.view.pk],
            created_by=self.user,
            updated_by=self.user,
        )
        response = self.client.patch(
            f"/api/v1/WSP/{workspace.pk}/",
            {"views": "not-a-list"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        workspace.refresh_from_db()
        self.assertEqual(workspace.views, [self.view.pk])

    def test_create_rolls_back_when_change_log_fails(self):
        with (
            patch("crudkit_api.views.ChangeLog.objects.create_from_objects", side_effect=RuntimeError("failed")),
            self.assertRaises(RuntimeError),
        ):
            self.client.post(
                "/api/v1/WSP/",
                {"name": "Rolled back", "views": [self.view.pk]},
                format="json",
            )
        self.assertFalse(Workspace.objects.filter(name="Rolled back").exists())
