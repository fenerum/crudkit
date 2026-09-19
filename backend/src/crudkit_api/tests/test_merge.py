from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from tests.testapp.models import Customer


class MergeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="admin", password="pw")
        self.a, self.b, self.c = (
            Customer.objects.create(name=name, email=f"{name}@example.com", created_by=self.user, updated_by=self.user)
            for name in ("a", "b", "c")
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_selected_id_survives_regardless_of_url_pk(self):
        response = self.client.post(
            f"/api/v1/CUS/{self.a.pk}/merge/",
            {"merge": [self.a.pk, self.b.pk, self.c.pk], "id": self.b.pk, "name": self.a.pk, "email": self.c.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["redirect"], self.b.pk)
        for obj in (self.a, self.b, self.c):
            obj.refresh_from_db()
        self.assertFalse(self.b.deleted)
        self.assertEqual((self.b.name, self.b.email), ("a", "c@example.com"))
        for merged in (self.a, self.c):
            self.assertTrue(merged.deleted)
            self.assertEqual(merged.merged_into_id, self.b.pk)
