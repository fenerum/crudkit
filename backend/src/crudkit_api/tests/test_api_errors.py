from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from tests.testapp.models import Customer


class APIErrorResponseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="errors", password="pw")
        self.customer = Customer.objects.create(
            name="Customer",
            created_by=self.user,
            updated_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_malformed_typed_search_is_handled(self):
        response = self.client.get("/api/v1/search/", {"q": "CUS:a:b"})
        self.assertEqual(response.status_code, 200)

    def test_missing_saved_view_returns_404(self):
        response = self.client.get("/api/v1/CUS/", {"_view": "VIW999999"})
        self.assertEqual(response.status_code, 404)

    def test_unknown_ordering_field_returns_400(self):
        response = self.client.get("/api/v1/CUS/", {"_order_by": "not_a_field"})
        self.assertEqual(response.status_code, 400)

    def test_unknown_action_returns_400(self):
        response = self.client.post(
            f"/api/v1/CUS/{self.customer.pk}/action/",
            {"action": "not_an_action"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_merge_requires_object_ids(self):
        response = self.client.post(
            f"/api/v1/CUS/{self.customer.pk}/merge/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
