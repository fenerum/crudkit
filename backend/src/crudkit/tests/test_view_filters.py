from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from crudkit.models import View
from tests.testapp.models import Customer, Topic


class ViewFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="agent", password="pw")
        self.other = User.objects.create_user(username="other", password="pw")
        audit = {"created_by": self.user, "updated_by": self.user}
        self.topic = Topic.objects.create(name="Billing", **audit)
        self.acme = Customer.objects.create(
            name="Acme", topic=self.topic, owner=self.user, balance=Decimal("10"), **audit
        )
        self.globex = Customer.objects.create(
            name="Globex", status="churned", owner=self.other, balance=Decimal("50"), **audit
        )

    def make_view(self, filters):
        return View(
            name="Filtered",
            model="CUS",
            fields=["name"],
            filters=filters,
            created_by=self.user,
            updated_by=self.user,
        )

    def names(self, filters):
        request = SimpleNamespace(user=self.user)
        return sorted(c.name for c in self.make_view(filters).filter(Customer.objects.all(), request))

    def test_clean_accepts_every_comparator(self):
        for comparator in View.FILTER_COMPARATORS:
            self.make_view([["balance", comparator, 10]]).clean()

    def test_clean_rejects_unknown_comparator(self):
        with self.assertRaisesMessage(ValidationError, "Unknown comparator '~'"):
            self.make_view([["name", "~", "Acme"]]).clean()

    def test_clean_rejects_malformed_entries(self):
        for entry in (["name", "="], ["name", "=", "Acme", "extra"], "name", [5, "=", "Acme"]):
            with self.subTest(entry=entry), self.assertRaisesMessage(ValidationError, "Filter format is invalid"):
                self.make_view([entry]).clean()

    def test_filter_comparators(self):
        self.assertEqual(self.names([["status", "!=", "churned"]]), ["Acme"])
        self.assertEqual(self.names([["balance", ">=", 50]]), ["Globex"])
        self.assertEqual(self.names([["balance", "<", 50]]), ["Acme"])

    def test_filter_on_fk_accepts_ck_id_and_plain_pk(self):
        self.assertEqual(self.names([["topic", "=", self.topic.pk]]), ["Acme"])
        self.assertEqual(self.names([["topic", "=", int(self.topic.pk[3:])]]), ["Acme"])

    def test_filter_resolves_current_user(self):
        self.assertEqual(self.names([["owner", "=", "${user}"]]), ["Acme"])
