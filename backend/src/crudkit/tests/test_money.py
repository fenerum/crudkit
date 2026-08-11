import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase

from crudkit.fields import DEFAULT_CURRENCY, CurrencyField, MoneyField
from crudkit.models import ExchangeRate


class TestMoneyModel(models.Model):
    """A test model using CurrencyField and MoneyField."""

    amount = MoneyField()
    currency = CurrencyField()
    name = models.CharField(max_length=100)


class CurrencyFieldTests(TestCase):
    def test_currency_field_methods(self):
        # Create a test instance
        instance = TestMoneyModel(amount=1000.00, currency="EUR", name="Test")

        # Test formatted amount
        self.assertEqual(instance.format_amount(), "1,000.00 €")
        self.assertEqual(instance.format_amount(include_symbol=False), "1,000.00")

        # Test currency display
        self.assertEqual(instance.get_currency_display(), "Euro")
        self.assertEqual(instance.get_currency_symbol(), "€")

        # Test currency with dollar symbol placement
        instance.currency = "USD"
        self.assertEqual(instance.format_amount(), "$1,000.00")

    def test_currency_conversion(self):
        instance = TestMoneyModel(amount=1000.00, currency="EUR", name="Test")

        # Test conversion with exchange rate
        converted = instance.convert_to("USD", exchange_rate=1.2)
        self.assertEqual(converted, 1200.00)


class ExchangeRateTests(TestCase):
    def setUp(self):
        user = User.objects.create(username="testuser")

        # Create exchange rates
        self.rate_eur = ExchangeRate.objects.create(
            currency="EUR",
            from_date=datetime.date(2023, 1, 1),
            to_date=datetime.date(2023, 12, 31),
            rate=0.85,  # 1 DKK = 0.85 EUR
            created_by=user,
            updated_by=user,
        )

        self.rate_usd = ExchangeRate.objects.create(
            currency="USD",
            from_date=datetime.date(2023, 1, 1),
            to_date=None,  # No end date
            rate=0.15,  # 1 DKK = 0.15 USD
            created_by=user,
            updated_by=user,
        )

    def test_exchange_rate_str(self):
        self.assertTrue(str(self.rate_eur).startswith(f"1 {DEFAULT_CURRENCY} = 0.85 EUR"))
        self.assertTrue("ongoing" in str(self.rate_usd))

    def test_get_rate_for_date(self):
        # Test getting rates for a date within range
        rate = ExchangeRate.objects.get_rate_for_date("EUR", datetime.date(2023, 6, 1))
        self.assertEqual(rate, Decimal("0.85"))  # Compare with Decimal instead of float

        # Test getting rates for a date outside range
        rate = ExchangeRate.objects.get_rate_for_date("EUR", datetime.date(2024, 6, 1))
        self.assertIsNone(rate)

        # Test getting rates for a currency with no end date
        rate = ExchangeRate.objects.get_rate_for_date("USD", datetime.date(2024, 6, 1))
        self.assertEqual(rate, Decimal("0.15"))  # Compare with Decimal instead of float

    def test_overlapping_rates(self):
        user = User.objects.get(username="testuser")

        # Try to create an overlapping exchange rate
        overlapping_rate = ExchangeRate(
            currency="EUR",
            from_date=datetime.date(2023, 6, 1),  # This overlaps with existing EUR rate
            to_date=datetime.date(2023, 12, 31),
            rate=Decimal("0.9"),
            created_by=user,
            updated_by=user,
        )

        # The clean method needs to be called explicitly
        with self.assertRaises(ValidationError):
            # First call save() to validate, but in a transaction that will be rolled back
            overlapping_rate.full_clean()

    def test_exchange_rate_manager(self):
        # Create test instance with Decimal amount instead of float
        instance = TestMoneyModel(amount=Decimal("1000.00"), currency="DKK", name="Test")

        # Convert to EUR using exchange rates from database
        # Test date: 2023-06-01 (should use the rate we defined in setUp)
        converted = instance.convert_to("EUR", date=datetime.date(2023, 6, 1))
        self.assertEqual(converted, Decimal("850.0"))  # 1000 DKK × 0.85 = 850 EUR

        # Convert DKK to USD
        converted = instance.convert_to("USD", date=datetime.date(2023, 6, 1))
        self.assertEqual(converted, Decimal("150.0"))  # 1000 DKK × 0.15 = 150 USD

        # Try conversion with a date for which we have no rate
        converted = instance.convert_to("EUR", date=datetime.date(2024, 6, 1))
        self.assertIsNone(converted)
