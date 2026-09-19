import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from crudkit.fields import DEFAULT_CURRENCY
from crudkit.models import ExchangeRate
from crudkit_api.serializers import GenericSerializer, _nested_relation_field, get_serializer
from crudkit_api.views import GenericViewSet
from tests.testapp.models import Customer, Ticket, Topic

ROWS = 200


class ListSerializationTest(TestCase):
    """The list endpoint reuses one serializer for all rows; its output must
    match serializing each row with a fresh serializer."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="testuser", password="testpass")
        audit = {"created_by": cls.user, "updated_by": cls.user}
        ExchangeRate.objects.create(currency="EUR", rate=Decimal("0.13"), **audit)
        topic = Topic.objects.create(name="Billing", **audit)
        for i in range(ROWS):
            # Alternate currencies so state leaking between rows would show up
            customer = Customer.objects.create(
                name=f"Customer {i}",
                topic=topic,
                owner=cls.user,
                balance=Decimal(i) + Decimal("0.5"),
                currency="EUR" if i % 2 else DEFAULT_CURRENCY,
                **audit,
            )
            Ticket.objects.create(subject=f"Ticket {i}", customer=customer, topic=topic, **audit)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _per_row_serialization(self, model):
        request = Request(APIRequestFactory().get("/"))
        serializer_class = get_serializer(model)
        rows = [serializer_class(obj, context={"request": request}).data for obj in model.objects.order_by("id")]
        return json.loads(json.dumps(rows, default=str))

    def _list(self, type_id, rows=ROWS):
        response = self.client.get(f"/api/v1/{type_id}/?page_size={rows}&ordering=id")
        self.assertEqual(response.status_code, 200)
        return response.json()["results"]

    def test_ticket_list_matches_per_row_serialization(self):
        results = self._list("TIC")
        self.assertEqual(len(results), ROWS)
        self.assertEqual(results, self._per_row_serialization(Ticket))

        odd = results[1]
        self.assertTrue(odd["id"].startswith("TIC"))
        self.assertTrue(odd["customer"]["id"].startswith("CUS"))
        self.assertEqual(
            odd["customer"]["balance"],
            {
                "currency": "EUR",
                "amount": "1.50",
                "amount_default_currency": "11.54",
                "default_currency": DEFAULT_CURRENCY,
            },
        )
        self.assertEqual(results[2]["customer"]["balance"]["currency"], DEFAULT_CURRENCY)

    def test_customer_list_matches_per_row_serialization(self):
        results = self._list("CUS")
        self.assertEqual(results, self._per_row_serialization(Customer))
        self.assertEqual(results[1]["balance"]["currency"], "EUR")
        self.assertEqual(results[1]["balance"]["amount_default_currency"], "11.54")
        self.assertEqual(results[2]["balance"]["currency"], DEFAULT_CURRENCY)

    def test_unpaginated_list_matches_per_row_serialization(self):
        with mock.patch.object(GenericViewSet, "pagination_class", None):
            response = self.client.get("/api/v1/TIC/?ordering=id")
        self.assertEqual(response.json(), self._per_row_serialization(Ticket))

    def test_serializer_count_is_independent_of_row_count(self):
        def count_serializers(rows):
            with mock.patch.object(
                GenericSerializer, "__init__", autospec=True, side_effect=GenericSerializer.__init__
            ) as init:
                self.assertEqual(len(self._list("TIC", rows)), rows)
            return init.call_count

        self.assertEqual(count_serializers(ROWS), count_serializers(10))

    def test_nested_field_classes_are_cached(self):
        self.assertIs(_nested_relation_field(Customer, 1), _nested_relation_field(Customer, 1))
