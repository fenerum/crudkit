from django.contrib.auth.models import User
from django.test import TestCase

from crudkit.authorization import get_authorized_instance
from crudkit.models import parse_ck_id
from tests.testapp.models import Customer


class GetAuthorizedInstanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="admin", password="pw")
        self.customer = Customer.objects.create(name="Acme", created_by=self.user, updated_by=self.user)
        self.pk = parse_ck_id(self.customer.id)[1]

    def test_returns_instance(self):
        self.assertEqual(get_authorized_instance(self.user, "CUS", self.pk), self.customer)

    def test_skips_soft_deleted(self):
        Customer.objects.filter(pk=self.customer.pk).update(deleted=True)
        self.assertIsNone(get_authorized_instance(self.user, "CUS", self.pk))
