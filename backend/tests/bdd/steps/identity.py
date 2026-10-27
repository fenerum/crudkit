"""Record IDs and the three letters every record type declares.

Phrases this area adds:

- `When a customer is looked up by the ID of "Acme"` / `... by the number of "Acme"`
- `When a customer is looked up by the number of "Acme" written as text`
- `When a customer is looked up by the number of "Acme" with the letters of a topic`
- `When a customer is looked up by an empty ID`
- `When the reminders pointing at the ID of "Acme" are looked up` / `... at the number of "Acme" ...`
- `Then the lookup finds "Acme"` / `Then the lookup finds nothing`
- `Then the lookup is refused with "Expected a CUS ID, got TOP"`
- `Given the record type topic declares the letters "top"` / `Given the record type topic declares no letters`
- `When the record types are checked` / `When a new record of that type is made`
- `Then the record type check passes` / `Then the record type check fails with "crudkit.E001" saying "..."`
- `Then making it fails with "Please define TYPE_ID on the BaseCrudKitModel"`
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from pytest_bdd import given, then, when

from crudkit.checks import check_type_ids
from crudkit.models import get_ck_id
from tests.bdd.world import phrase


def _look_up(world, model, **lookup):
    try:
        world.found = list(model._base_manager.filter(**lookup))
        world.refusal = None
    except ValueError as e:
        world.found, world.refusal = [], str(e)


@when(phrase('{a:Article} {model:Model} is looked up by the ID of "{label:Q}"'))
def look_up_by_id(world, a, model, label):
    _look_up(world, model, pk=world.ck_id(label))


@when(phrase('{a:Article} {model:Model} is looked up by the number of "{label:Q}"'))
def look_up_by_number(world, a, model, label):
    _look_up(world, model, pk=world.number(label))


@when(phrase('{a:Article} {model:Model} is looked up by the number of "{label:Q}" written as text'))
def look_up_by_text_number(world, a, model, label):
    _look_up(world, model, pk=str(world.number(label)))


@when(
    phrase(
        '{a:Article} {model:Model} is looked up by the number of "{label:Q}" with the letters of {b:Article} {other:Model}'
    )
)
def look_up_with_other_letters(world, a, model, label, b, other):
    _look_up(world, model, pk=get_ck_id(other.TYPE_ID, world.number(label)))


@when(phrase("{a:Article} {model:Model} is looked up by an empty ID"))
def look_up_empty(world, a, model):
    _look_up(world, model, pk="")


def _pointer_field(model) -> str:
    """The column a generic link (like a reminder's target) keeps the record's number in."""
    link = next(f for f in model._meta.private_fields if isinstance(f, GenericForeignKey))
    return link.fk_field


@when(phrase('the {model:Model} pointing at the ID of "{label:Q}" are looked up'))
def look_up_pointing_at_id(world, model, label):
    _look_up(world, model, **{_pointer_field(model): world.ck_id(label)})


@when(phrase('the {model:Model} pointing at the number of "{label:Q}" are looked up'))
def look_up_pointing_at_number(world, model, label):
    _look_up(world, model, **{_pointer_field(model): world.number(label)})


@then(phrase("the lookup finds {labels:Labels}"))
def lookup_finds(world, labels):
    assert world.refusal is None, world.refusal
    assert sorted(str(instance) for instance in world.found) == sorted(labels), world.found


@then(phrase("the lookup finds nothing"))
def lookup_finds_nothing(world):
    assert world.refusal is None, world.refusal
    assert world.found == [], world.found


@then(phrase('the lookup is refused with "{message:Q}"'))
def lookup_refused(world, message):
    assert world.refusal == message, world.refusal


# The letters of a record type


@given(phrase('the record type {model:Model} declares the letters "{letters:Q}"'))
def declares_letters(monkeypatch, model, letters):
    monkeypatch.setattr(model, "TYPE_ID", letters)


@given(phrase("the record type {model:Model} declares no letters"))
def declares_no_letters(world, monkeypatch, model):
    world.unlettered_type = model
    monkeypatch.setattr(model, "TYPE_ID", None)


@when(phrase("the record types are checked"))
def check_record_types(world):
    world.check_errors = check_type_ids(None)


@then(phrase("the record type check passes"))
def check_passes(world):
    assert world.check_errors == [], world.check_errors


@then(phrase('the record type check fails with "{check_id:Q}" saying "{message:Q}"'))
def check_fails(world, check_id, message):
    assert [e.id for e in world.check_errors] == [check_id], world.check_errors
    assert message in world.check_errors[0].msg, world.check_errors[0].msg


@when(phrase("a new record of that type is made"))
def make_a_record(world):
    try:
        world.unlettered_type()
        world.refusal = None
    except Exception as e:
        world.refusal = str(e)


@then(phrase('making it fails with "{message:Q}"'))
def making_fails(world, message):
    assert world.refusal == message, world.refusal
