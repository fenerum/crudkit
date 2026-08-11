from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from crudkit.fields import DEFAULT_CURRENCY
from crudkit.models import ExchangeRate

User = get_user_model()

# Exchange rates as of today
# These are approximate rates against DKK (Danish Krone)
DEFAULT_EXCHANGE_RATES = {
    "USD": Decimal("0.145"),  # 1 DKK = 0.145 USD
    "EUR": Decimal("0.134"),  # 1 DKK = 0.134 EUR
    "GBP": Decimal("0.114"),  # 1 DKK = 0.114 GBP
    "SEK": Decimal("1.52"),  # 1 DKK = 1.52 SEK
    "NOK": Decimal("1.55"),  # 1 DKK = 1.55 NOK
}


class Command(BaseCommand):
    help = "Add default exchange rates to the database"

    def handle(self, *args, **options):
        # Get or create system user
        system_user, created = User.objects.get_or_create(
            username="system",
            defaults={
                "is_staff": True,
                "is_superuser": True,
                "email": "system@example.com",
            },
        )

        if DEFAULT_CURRENCY in DEFAULT_EXCHANGE_RATES:
            self.stdout.write(self.style.WARNING(f"Skipping {DEFAULT_CURRENCY} as it's the default currency."))
            # Remove default currency from rates to add
            DEFAULT_EXCHANGE_RATES.pop(DEFAULT_CURRENCY, None)

        today = timezone.now().date()

        # Add exchange rates for each currency
        for currency, rate in DEFAULT_EXCHANGE_RATES.items():
            # Check if an active rate already exists
            existing_rate = ExchangeRate.objects.filter(
                currency=currency, from_date__lte=today, to_date__isnull=True
            ).first()

            if existing_rate:
                self.stdout.write(self.style.WARNING(f"Exchange rate for {currency} already exists: {existing_rate}"))
                continue

            # Create new exchange rate
            exchange_rate = ExchangeRate.objects.create(
                currency=currency,
                from_date=today,
                to_date=None,  # Indefinite
                rate=rate,
                created_by=system_user,
                updated_by=system_user,
            )

            self.stdout.write(self.style.SUCCESS(f"Added exchange rate: {exchange_rate}"))

        self.stdout.write(self.style.SUCCESS("All default exchange rates added successfully!"))
