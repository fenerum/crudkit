from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from crudkit_api.tests.test_authorization import grant
from tests.testapp.models import Comment, Customer, Ticket


class SearchByIdTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="searcher", password="pw")
        for model in (Customer, Ticket, Comment):
            grant(self.user, model, "view")
        self.customer = Customer.objects.create(name="Acme", created_by=self.user, updated_by=self.user)
        Customer.objects.create(name="Other", created_by=self.user, updated_by=self.user)
        self.ticket = Ticket.objects.create(subject="Broken", created_by=self.user, updated_by=self.user)
        self.comment = Comment.objects.create(
            ticket=self.ticket, body="Looking into it", created_by=self.user, updated_by=self.user
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def list_ids(self, type_id, query):
        response = self.client.get(f"/api/v1/{type_id}/", {"_q": query})
        self.assertEqual(response.status_code, 200)
        return [row["id"] for row in response.data["results"]]

    def search_ids(self, query):
        response = self.client.get("/api/v1/search/", {"q": query})
        self.assertEqual(response.status_code, 200)
        return [row["id"] for row in response.data["results"]]

    def test_list_search_matches_id_case_insensitively(self):
        self.assertEqual(self.list_ids("CUS", self.customer.pk), [self.customer.pk])
        self.assertEqual(self.list_ids("CUS", f" {self.customer.pk.lower()} "), [self.customer.pk])

    def test_list_search_ignores_other_types_ids(self):
        self.assertEqual(self.list_ids("CUS", self.ticket.pk), [])
        self.assertEqual(self.list_ids("CUS", "acm"), [self.customer.pk])

    def test_model_without_search_fields(self):
        self.assertEqual(self.list_ids("COM", "Looking"), [])
        self.assertEqual(self.list_ids("COM", self.comment.pk), [self.comment.pk])

    def test_global_search_by_id(self):
        self.assertEqual(self.search_ids(self.comment.pk.lower()), [self.comment.pk])
        self.assertEqual(self.search_ids(f"TIC:{self.ticket.pk}"), [self.ticket.pk])
        self.assertEqual(self.search_ids("CUS:a:b"), [])
