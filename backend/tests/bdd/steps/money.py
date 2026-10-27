"""Amounts, currencies and exchange rates. The default currency in these
features is DKK; a rate means 1 DKK buys that much of the other currency.

Rates
- `Given the EUR rate is "0.85" from "2023-01-01" to "2023-12-31"` (or `… from "2023-01-01" onwards`)
- `Given overlapping EUR rates were stored directly:` `| from | to | rate |` rows (to may be "onwards")
- `When Alice adds an EUR rate of "0.9" from "2023-06-01" to "2023-12-31"` (or `… onwards`)
- `When Alice changes that EUR rate to "0.86"` / `When Alice looks at that EUR rate`
- `When an EUR rate ending before it starts is stored directly` / `Then the database refuses it`
- `Then the EUR rate on "2023-06-01" is "0.85"` / `Then there is no EUR rate on "2024-06-01"`
- `Then there are 2 EUR rates`

Amounts on a record (the record's currency field decides the currency)
- `Then "Acme" shows an amount of "1234.5" as "1,234.50 €"` (`… without its symbol as …`)
- `Then "Acme" shows a missing amount as "N/A"`
- `Then "Acme" shows its own empty amount as "N/A"`: for record types whose amount field is called "amount"
- `Then the currency of "Acme" reads "Euro" with the symbol "€"`
- `Then "Acme" converts "1000" into USD as "150.00"` (`… at a rate of "1.2" …`, `… on "2023-06-01" …`)
- `Then "Acme" cannot convert "1000" into EUR on "2024-06-01"`
- `When Alice changes the balance of "Acme" to an amount of "12.5"`: written as an amount, not a plain number
- `When Alice lists the customers with their balances`
- `Then the balance reads "1000.00" EUR, which is "7462.69" DKK` / `Then the balance reads nothing`
- `Then the balance reads "250.00" USD, with no known worth in DKK`
- `Then the balance of "Acme" in the list reads "1000.00" EUR, which is "7462.69" DKK`

Management commands
- `When an operator runs "set_exchange_rate EUR 0.13425 --from-date 2024-01-01"`
- `Then the command reports "Created exchange rate"` / `Then the command fails with "Invalid from-date format"`
- `Then there is an EUR rate of "0.13425" from today with no end, set by the system`
  (or `from "2024-01-01" to "2024-12-31"`)
"""

import datetime
import shlex
from decimal import Decimal
from io import StringIO

from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from pytest_bdd import given, parsers, then, when

from crudkit.models import ExchangeRate
from crudkit.utils import get_system_user
from tests.bdd.world import phrase

CENT = Decimal("0.01")


def _date(text: str) -> datetime.date | None:
    """ "2023-01-01", "today", or "onwards" (no date)."""
    if text == "onwards":
        return None
    if text == "today":
        return timezone.now().date()
    return datetime.date.fromisoformat(text)


def _store_rate(world, currency, rate, start, end):
    system = get_system_user()
    world.rate = ExchangeRate.objects.create(
        currency=currency,
        rate=Decimal(rate),
        from_date=_date(start),
        to_date=_date(end),
        created_by=system,
        updated_by=system,
    )


# Rates


@given(phrase('the {currency:Currency} rate is "{rate:Q}" from "{start:Q}" to "{end:Q}"'))
def a_rate(world, currency, rate, start, end):
    _store_rate(world, currency, rate, start, end)


@given(phrase('the {currency:Currency} rate is "{rate:Q}" from "{start:Q}" onwards'))
def an_open_rate(world, currency, rate, start):
    _store_rate(world, currency, rate, start, "onwards")


@given(phrase("overlapping {currency:Currency} rates were stored directly:"))
def overlapping_rates(world, currency, datatable):
    """`| from | to | rate |` rows, stored without the overlap check (as an import might)."""
    for start, end, rate in datatable[1:]:
        _store_rate(world, currency, rate, start, end)


def _add_rate(world, name, currency, rate, start, end):
    payload = {"currency": currency, "rate": rate, "from_date": start, "to_date": _date(end)}
    world.remember(name, world.api(name).post("/api/v1/EXR/", payload, format="json"))


@when(phrase('{name:Actor} adds an {currency:Currency} rate of "{rate:Q}" from "{start:Q}" to "{end:Q}"'))
@when(phrase('{name:Actor} adds a {currency:Currency} rate of "{rate:Q}" from "{start:Q}" to "{end:Q}"'))
def add_a_rate(world, name, currency, rate, start, end):
    _add_rate(world, name, currency, rate, start, end)


@when(phrase('{name:Actor} adds an {currency:Currency} rate of "{rate:Q}" from "{start:Q}" onwards'))
@when(phrase('{name:Actor} adds a {currency:Currency} rate of "{rate:Q}" from "{start:Q}" onwards'))
def add_an_open_rate(world, name, currency, rate, start):
    _add_rate(world, name, currency, rate, start, "onwards")


@when(phrase('{name:Actor} changes that {currency:Currency} rate to "{rate:Q}"'))
def change_a_rate(world, name, currency, rate):
    assert world.rate.currency == currency
    response = world.api(name).patch(f"/api/v1/EXR/{world.rate.pk}/", {"rate": rate}, format="json")
    world.remember(name, response)


@when(phrase("{name:Actor} looks at that {currency:Currency} rate"))
def look_at_a_rate(world, name, currency):
    assert world.rate.currency == currency
    world.remember(name, world.api(name).get(f"/api/v1/EXR/{world.rate.pk}/"))


@when(phrase("an {currency:Currency} rate ending before it starts is stored directly"))
@when(phrase("a {currency:Currency} rate ending before it starts is stored directly"))
def store_a_backwards_rate(world, currency):
    world.error = None
    try:
        with transaction.atomic():
            _store_rate(world, currency, "0.9", "2023-12-31", "2023-01-01")
    except IntegrityError as error:
        world.error = error


@then("the database refuses it")
def database_refuses(world):
    assert isinstance(world.error, IntegrityError), world.error


@then(phrase('the {currency:Currency} rate on "{day:Q}" is "{rate:Q}"'))
def rate_on(world, currency, day, rate):
    assert ExchangeRate.objects.get_rate_for_date(currency, _date(day)) == Decimal(rate)


@then(phrase('there is no {currency:Currency} rate on "{day:Q}"'))
def no_rate_on(world, currency, day):
    assert ExchangeRate.objects.get_rate_for_date(currency, _date(day)) is None


@then(phrase("there are {count:d} {currency:Currency} rates"))
@then(phrase("there is {count:d} {currency:Currency} rate"))
def rate_count(world, count, currency):
    assert ExchangeRate.objects.filter(currency=currency).count() == count


@then(phrase("there is no {currency:Currency} rate"))
def no_rate(world, currency):
    assert not ExchangeRate.objects.filter(currency=currency).exists()


@then(phrase('that rate is labelled "{text:Q}"'))
def rate_labelled(world, text):
    assert world.response.status_code == 200, world.response.content
    assert world.response.data["label"] == text, world.response.data["label"]


# Amounts on a record


@then(phrase('"{label:Q}" shows an amount of "{amount:Q}" as "{text:Q}"'))
def shows_amount(world, label, amount, text):
    assert world.record(label).format_amount(Decimal(amount)) == text


@then(phrase('"{label:Q}" shows an amount of "{amount:Q}" without its symbol as "{text:Q}"'))
def shows_amount_without_symbol(world, label, amount, text):
    assert world.record(label).format_amount(Decimal(amount), include_symbol=False) == text


@then(phrase('"{label:Q}" shows a missing amount as "{text:Q}"'))
def shows_missing_amount(world, label, text):
    assert world.record(label).format_amount() == text


@then(phrase('"{label:Q}" shows its own empty amount as "{text:Q}"'))
def shows_own_empty_amount(world, label, text):
    """Without an amount given, a record shows its own field called "amount". Customers keep theirs in
    "balance", so the empty "amount" field of such a record type is stood in for here."""
    instance = world.record(label)
    instance.amount = None
    assert instance.format_amount() == text


@then(phrase('the currency of "{label:Q}" reads "{name:Q}" with the symbol "{symbol:Q}"'))
def currency_reads(world, label, name, symbol):
    instance = world.record(label)
    assert (instance.get_currency_display(), instance.get_currency_symbol()) == (name, symbol)


def _converted(world, label, amount, target, **kwargs):
    return world.record(label).convert_to(target, amount=Decimal(amount), **kwargs)


@then(phrase('"{label:Q}" converts "{amount:Q}" into {target:Currency} as "{result:Q}"'))
def converts(world, label, amount, target, result):
    assert _converted(world, label, amount, target).quantize(CENT) == Decimal(result)


@then(phrase('"{label:Q}" converts "{amount:Q}" into {target:Currency} at a rate of "{rate:Q}" as "{result:Q}"'))
def converts_at(world, label, amount, target, rate, result):
    converted = _converted(world, label, amount, target, exchange_rate=Decimal(rate))
    assert converted.quantize(CENT) == Decimal(result)


@then(phrase('"{label:Q}" converts "{amount:Q}" into {target:Currency} on "{day:Q}" as "{result:Q}"'))
def converts_on(world, label, amount, target, day, result):
    assert _converted(world, label, amount, target, date=_date(day)).quantize(CENT) == Decimal(result)


@then(phrase('"{label:Q}" cannot convert "{amount:Q}" into {target:Currency} on "{day:Q}"'))
def cannot_convert(world, label, amount, target, day):
    assert _converted(world, label, amount, target, date=_date(day)) is None


@when(phrase('{name:Actor} changes the balance of "{label:Q}" to an amount of "{amount:Q}"'))
def change_balance_as_amount(world, name, label, amount):
    payload = {"balance": {"amount": amount}}
    world.remember(name, world.api(name).patch(world.url(label), payload, format="json"))


@when(phrase("{name:Actor} lists the customers with their balances"))
def list_balances(world, name):
    world.remember(name, world.api(name).get("/api/v1/CUS/"))


def _money(amount, currency, default_amount, default_currency):
    return {
        "currency": currency,
        "amount": amount,
        "amount_default_currency": default_amount,
        "default_currency": default_currency,
    }


@then(
    phrase(
        'the balance reads "{amount:Q}" {currency:Currency}, which is "{default_amount:Q}" {default_currency:Currency}'
    )
)
def balance_reads(world, amount, currency, default_amount, default_currency):
    assert world.response.status_code == 200, world.response.content
    expected = _money(amount, currency, default_amount, default_currency)
    assert world.response.data["balance"] == expected, world.response.data["balance"]


@then(phrase('the balance reads "{amount:Q}" {currency:Currency}, with no known worth in {default_currency:Currency}'))
def balance_reads_without_worth(world, amount, currency, default_currency):
    assert world.response.status_code == 200, world.response.content
    expected = _money(amount, currency, None, default_currency)
    assert world.response.data["balance"] == expected, world.response.data["balance"]


@then("the balance reads nothing")
def balance_reads_nothing(world):
    assert world.response.status_code == 200, world.response.content
    assert world.response.data["balance"] is None, world.response.data["balance"]


@then(
    phrase(
        'the balance of "{label:Q}" in the list reads "{amount:Q}" {currency:Currency}, '
        'which is "{default_amount:Q}" {default_currency:Currency}'
    )
)
def listed_balance_reads(world, label, amount, currency, default_amount, default_currency):
    assert world.response.status_code == 200, world.response.content
    rows = {row["label"]: row["balance"] for row in world.response.data["results"]}
    assert rows[label] == _money(amount, currency, default_amount, default_currency), rows[label]


# Management commands


@given(phrase('an operator ran "{command:Q}"'))
@when(phrase('an operator runs "{command:Q}"'))
def run_a_command(world, command):
    world.output = StringIO()
    world.error = None
    try:
        call_command(*shlex.split(command), stdout=world.output)
    except CommandError as error:
        world.error = error


@then(phrase('the command reports "{text:Q}"'))
def command_reports(world, text):
    assert world.error is None, world.error
    assert text in world.output.getvalue(), world.output.getvalue()


@then(phrase('the command fails with "{text:Q}"'))
def command_fails(world, text):
    assert world.error is not None, world.output.getvalue()
    assert text in str(world.error), str(world.error)


def _assert_rate(currency, rate, start, end):
    found = ExchangeRate.objects.get(currency=currency, from_date=_date(start), to_date=_date(end))
    assert found.rate == Decimal(rate), found.rate
    return found


@then(phrase('there is an {currency:Currency} rate of "{rate:Q}" from today with no end'))
@then(phrase('there is a {currency:Currency} rate of "{rate:Q}" from today with no end'))
def open_rate_from_today(world, currency, rate):
    _assert_rate(currency, rate, "today", "onwards")


@then(phrase('there is an {currency:Currency} rate of "{rate:Q}" from today with no end, set by the system'))
def open_rate_by_system(world, currency, rate):
    found = _assert_rate(currency, rate, "today", "onwards")
    assert (found.created_by, found.updated_by) == (get_system_user(), get_system_user())


@then(phrase('there is an {currency:Currency} rate of "{rate:Q}" from "{start:Q}" to "{end:Q}"'))
def rate_between(world, currency, rate, start, end):
    _assert_rate(currency, rate, start, end)


@then(parsers.re(r"there are rates from today with no end for (?P<currencies>[A-Z, and]+)"))
def default_rates(world, currencies):
    expected = sorted(currencies.replace(" and ", ", ").split(", "))
    today = timezone.now().date()
    found = ExchangeRate.objects.filter(from_date=today, to_date__isnull=True).values_list("currency", flat=True)
    assert sorted(found) == expected, sorted(found)
