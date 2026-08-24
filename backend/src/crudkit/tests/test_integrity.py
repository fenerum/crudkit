from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from crudkit.checks import check_type_ids
from crudkit.models import ExchangeRate, WorkLog, parse_ck_id
from tests.testapp.models import Customer, Topic


class CrudKitIDTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ids", password="pw")
        self.customer = Customer.objects.create(
            name="Customer",
            created_by=self.user,
            updated_by=self.user,
        )
        self.topic = Topic.objects.create(
            name="Topic",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_wrong_model_prefix_is_rejected(self):
        with self.assertRaises(ValueError):
            Customer.objects.get(pk=self.topic.pk)

    def test_parse_rejects_malformed_ids(self):
        for value in ("CUS", "CUS1x", "cus1", "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_ck_id(value)

    def test_system_check_rejects_duplicate_type_ids(self):
        with (
            patch.object(Topic, "TYPE_ID", Customer.TYPE_ID),
            patch("crudkit.checks.apps.get_models", return_value=[Customer, Topic]),
        ):
            errors = check_type_ids(None)
        self.assertEqual([error.id for error in errors], ["crudkit.E002"])


class DatabaseInvariantTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="integrity", password="pw")
        self.customer = Customer.objects.create(
            name="Customer",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_only_one_active_worklog_per_user(self):
        content_type = ContentType.objects.get_for_model(self.customer)
        values = {
            "related_content_type": content_type,
            "related_object_id": self.customer.pk,
            "created_by": self.user,
            "updated_by": self.user,
        }
        WorkLog.objects.create(**values)

        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkLog.objects.create(**values)

    def test_exchange_rate_rejects_overlap_with_open_interval(self):
        ExchangeRate.objects.create(
            currency="USD",
            from_date=date(2024, 1, 1),
            to_date=None,
            rate=Decimal("7.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        overlapping = ExchangeRate(
            currency="USD",
            from_date=date(2025, 1, 1),
            to_date=date(2025, 12, 31),
            rate=Decimal("7.10"),
            created_by=self.user,
            updated_by=self.user,
        )

        with self.assertRaises(ValidationError):
            overlapping.full_clean()

    def test_exchange_rate_database_constraint_orders_dates(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExchangeRate.objects.create(
                currency="USD",
                from_date=date(2025, 2, 1),
                to_date=date(2025, 1, 1),
                rate=Decimal("7.00"),
                created_by=self.user,
                updated_by=self.user,
            )
