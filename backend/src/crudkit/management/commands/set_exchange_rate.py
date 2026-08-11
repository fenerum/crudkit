import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from crudkit.fields import DEFAULT_CURRENCY
from crudkit.models import ExchangeRate
from crudkit.utils import get_system_user


class Command(BaseCommand):
    help = "Set an exchange rate for a specific currency"

    def add_arguments(self, parser):
        parser.add_argument("currency", type=str, help="The currency code (e.g., EUR, USD)")
        parser.add_argument("rate", type=str, help="The exchange rate (e.g., 0.13425)")
        parser.add_argument(
            "--from-date", type=str, help="The start date for this rate (YYYY-MM-DD). Defaults to today."
        )
        parser.add_argument(
            "--to-date",
            type=str,
            help="The end date for this rate (YYYY-MM-DD). Leave empty for rates that apply indefinitely.",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing rate if one exists for the given currency and date range",
        )

    def handle(self, *args, **options):
        currency = options["currency"].upper()
        rate = Decimal(options["rate"])

        # Parse dates
        from_date = None
        if options["from_date"]:
            try:
                from_date = datetime.datetime.strptime(options["from_date"], "%Y-%m-%d").date()
            except ValueError:
                raise CommandError("Invalid from-date format. Use YYYY-MM-DD.")
        else:
            from_date = timezone.now().date()

        to_date = None
        if options["to_date"]:
            try:
                to_date = datetime.datetime.strptime(options["to_date"], "%Y-%m-%d").date()
            except ValueError:
                raise CommandError("Invalid to-date format. Use YYYY-MM-DD.")

            if to_date < from_date:
                raise CommandError("End date must be after start date.")

        # Check if an exchange rate already exists for this currency and date range
        system_user = get_system_user()

        # Find existing rates
        existing_query = ExchangeRate.objects.filter(currency=currency, from_date=from_date)
        if to_date:
            existing_query = existing_query.filter(to_date=to_date)
        else:
            existing_query = existing_query.filter(to_date__isnull=True)

        # Set the exchange rate
        if existing_query.exists():
            exchange_rate = existing_query.first()
            if options["update"]:
                exchange_rate.rate = rate
                exchange_rate.updated_by = system_user
                exchange_rate.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Updated exchange rate: 1 {DEFAULT_CURRENCY} = {rate} {currency} '
                        f'(from {from_date} to {to_date or "indefinitely"})'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'Exchange rate already exists for {currency} from {from_date} to {to_date or "indefinitely"}. '
                        f'Use --update to modify it.'
                    )
                )
        else:
            # Create a new exchange rate
            exchange_rate = ExchangeRate.objects.create(
                currency=currency,
                rate=rate,
                from_date=from_date,
                to_date=to_date,
                created_by=system_user,
                updated_by=system_user,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created exchange rate: 1 {DEFAULT_CURRENCY} = {rate} {currency} '
                    f'(from {from_date} to {to_date or "indefinitely"})'
                )
            )
