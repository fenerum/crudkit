from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from crudkit.models import ChangeLog
from crudkit_api.tests.test_authorization import grant
from crudkit_api.views import CHANGE_SET_HEADER
from tests.testapp.models import Topic


class ReorderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="admin", password="pw")
        self.a, self.b, self.c = (
            Topic.objects.create(name=name, created_by=self.user, updated_by=self.user) for name in ("a", "b", "c")
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def reorder(self, field, ids):
        return self.client.post("/api/v1/TOP/reorder/", {"field": field, "ids": ids}, format="json")

    def sort_orders(self):
        return dict(Topic.objects.values_list("name", "sort_order"))

    def test_sets_field_to_position_in_one_change_set(self):
        response = self.reorder("sort_order", [self.c.pk, self.a.pk, self.b.pk])

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.sort_orders(), {"c": 0, "a": 1, "b": 2})
        # `c` already had 0, so only `a` and `b` changed.
        entries = ChangeLog.objects.filter(field_changes__has_key="sort_order")
        self.assertEqual(entries.count(), 2)
        self.assertEqual({str(e.change_set) for e in entries}, {response[CHANGE_SET_HEADER]})

    def test_rejects_invalid_field_or_ids(self):
        for field in ("name", "id", "missing", None):
            self.assertEqual(self.reorder(field, [self.a.pk]).status_code, 400, field)
        for ids in ("nope", ["nope"], [1], ["CUS1"]):
            self.assertEqual(self.reorder("sort_order", ids).status_code, 400, ids)

    def test_requires_change_permission(self):
        viewer = User.objects.create_user(username="viewer", password="pw")
        grant(viewer, Topic, "view")
        self.client.force_authenticate(viewer)

        self.assertEqual(self.reorder("sort_order", [self.c.pk, self.b.pk, self.a.pk]).status_code, 403)
        self.assertEqual(set(self.sort_orders().values()), {0})
