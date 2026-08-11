from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import models

# Default currency choices if not defined in settings
DEFAULT_CURRENCY_CHOICES = [
    ("USD", "US Dollar"),
    ("EUR", "Euro"),
    ("DKK", "Danish Krone"),
    ("GBP", "British Pound"),
    ("SEK", "Swedish Krona"),
    ("NOK", "Norwegian Krone"),
]

# Currency symbols dictionary
CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "DKK": "kr",
    "GBP": "£",
    "SEK": "kr",
    "NOK": "kr",
}

# Get currency choices from settings or use defaults. The CRUDKIT_-prefixed
# names take precedence; the unprefixed ones are kept for compatibility.
CURRENCY_CHOICES = getattr(
    settings, "CRUDKIT_CURRENCY_CHOICES", getattr(settings, "CURRENCY_CHOICES", DEFAULT_CURRENCY_CHOICES)
)
DEFAULT_CURRENCY = getattr(settings, "CRUDKIT_DEFAULT_CURRENCY", getattr(settings, "DEFAULT_CURRENCY", "EUR"))


class ModelField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 3
        super().__init__(*args, **kwargs)


class FieldChoiceField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 128
        super().__init__(*args, **kwargs)


class CurrencyField(models.CharField):
    """
    A field for storing currency codes with helper methods for formatting
    and conversion. Works together with MoneyField.

    This field should be defined on a model along with a MoneyField to
    represent a monetary value with its currency.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 3)
        kwargs.setdefault("choices", CURRENCY_CHOICES)
        kwargs.setdefault("default", DEFAULT_CURRENCY)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        # Settings-derived choices/default must not be baked into migrations:
        # projects with different CRUDKIT_CURRENCY_CHOICES / default currency
        # would see spurious model/migration drift. They are re-applied from
        # settings by __init__ on load.
        name, path, args, kwargs = super().deconstruct()
        if dict(kwargs.get("choices") or {}) == dict(CURRENCY_CHOICES):
            kwargs.pop("choices", None)
        if kwargs.get("default") == DEFAULT_CURRENCY:
            kwargs.pop("default", None)
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name, **kwargs):
        """
        Add additional methods to the model class when this field is added.
        """
        super().contribute_to_class(cls, name, **kwargs)

        def get_currency_display(model_instance):
            """Returns the display value of the currency."""
            currency_dict = dict(CURRENCY_CHOICES)
            currency_code = getattr(model_instance, name)
            return currency_dict.get(currency_code, currency_code)

        def get_currency_symbol(model_instance):
            """Returns the symbol for the currency."""
            currency_code = getattr(model_instance, name)
            return CURRENCY_SYMBOLS.get(currency_code, "")

        def format_amount(model_instance, amount=None, include_symbol=True):
            """
            Formats the amount with currency symbol.
            If no amount is provided, tries to use the model's 'amount' field.
            """
            currency_code = getattr(model_instance, name)

            # Get amount either from parameter or model's amount field
            if amount is None:
                if not hasattr(model_instance, "amount"):
                    return "N/A"
                amount = model_instance.amount

            symbol = CURRENCY_SYMBOLS.get(currency_code, "")

            if include_symbol:
                if currency_code in ["USD", "GBP"]:  # Symbol before amount
                    return f"{symbol}{amount:,.2f}"
                else:  # Symbol after amount
                    return f"{amount:,.2f} {symbol}"
            else:
                return f"{amount:,.2f}"

        def convert_to(model_instance, target_currency, exchange_rate=None, amount=None, date=None):
            """
            Converts the amount to another currency.

            Args:
                target_currency (str): The target currency code
                exchange_rate (float, optional): The exchange rate to use. If not provided,
                                                looks up the rate from the ExchangeRate model.
                amount (float, optional): The amount to convert. Uses model's amount field if not provided.
                date (date, optional): The date to get the exchange rate for. Defaults to today.

            Returns:
                float: The converted amount
            """
            # Get amount either from parameter or model's amount field
            if amount is None:
                if not hasattr(model_instance, "amount"):
                    return 0
                amount = model_instance.amount

            # Get currency from model
            source_currency = getattr(model_instance, name)

            # If source and target currencies are the same, no conversion needed
            if source_currency == target_currency:
                return amount

            # If exchange rate is provided, use it directly
            if exchange_rate:
                return amount * exchange_rate

            # Otherwise, look up the exchange rate from the ExchangeRate model
            from crudkit.models import ExchangeRate

            # First, convert to base currency (if needed)
            base_amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
            if source_currency != DEFAULT_CURRENCY:
                source_rate = ExchangeRate.objects.get_rate_for_date(source_currency, date)
                if source_rate:
                    # Convert to base currency (inverse of the rate)
                    base_amount = base_amount / source_rate
                else:
                    # If no rate found, return None to indicate conversion not possible
                    return None

            # Then convert from base currency to target currency
            if target_currency == DEFAULT_CURRENCY:
                return base_amount

            target_rate = ExchangeRate.objects.get_rate_for_date(target_currency, date)
            if target_rate:
                return base_amount * target_rate
            else:
                # If no rate found, return None to indicate conversion not possible
                return None

        # Add these methods to the model class
        setattr(cls, f"get_{name}_display", get_currency_display)
        setattr(cls, f"get_{name}_symbol", get_currency_symbol)
        cls.format_amount = format_amount
        cls.convert_to = convert_to


class MoneyField(models.DecimalField):
    """
    A specialized DecimalField for currency amounts.
    Use together with CurrencyField for full money representation.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 2)
        super().__init__(*args, **kwargs)


# --- AI Field Types ---
# These fields are real Django fields with an `ai_field = True` marker so that
# generic tasks can discover them via model._meta.get_fields().


class AIField:
    ai_field: bool = True
    ai_prompt: str

    def deconstruct(self) -> tuple[str, str, list, dict]:
        name, path, args, kwargs = super().deconstruct()
        if self.ai_prompt:
            kwargs["prompt"] = self.ai_prompt
        return name, path, args, kwargs


class AISummaryField(AIField, models.TextField):
    def __init__(self, prompt: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("blank", True)
        kwargs.setdefault("null", True)
        kwargs.setdefault("editable", False)
        self.ai_prompt = prompt
        super().__init__(**kwargs)


class AICategoryField(AIField, models.CharField):
    def __init__(self, prompt: str = "", **kwargs: Any) -> None:
        self.ai_prompt = prompt
        kwargs.setdefault("max_length", 64)
        kwargs.setdefault("blank", True)
        kwargs.setdefault("null", True)
        kwargs.setdefault("editable", False)
        super().__init__(**kwargs)


class AIBooleanField(AIField, models.BooleanField):
    def __init__(self, prompt: str = "", **kwargs: Any) -> None:
        self.ai_prompt = prompt
        kwargs.setdefault("null", True)
        kwargs.setdefault("editable", False)
        super().__init__(**kwargs)


class AITagsField(AIField, models.JSONField):
    def __init__(self, prompt: str = "", max_tags: int = 10, **kwargs: Any) -> None:
        self.ai_prompt = prompt
        self.max_tags = max_tags
        kwargs.setdefault("default", list)
        kwargs.setdefault("blank", True)
        kwargs.setdefault("editable", False)
        super().__init__(**kwargs)

    def deconstruct(self) -> tuple[str, str, list, dict]:
        name, path, args, kwargs = super().deconstruct()
        if self.max_tags != 10:
            kwargs["max_tags"] = self.max_tags
        return name, path, args, kwargs


class AIForeignKeyField(AIField, models.ForeignKey):
    def __init__(self, to: type | str, prompt: str = "", **kwargs: Any) -> None:
        self.ai_prompt = prompt
        kwargs.setdefault("null", True)
        kwargs.setdefault("blank", True)
        kwargs.setdefault("editable", False)
        kwargs.setdefault("on_delete", models.SET_NULL)
        super().__init__(to, **kwargs)
