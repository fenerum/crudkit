"""Steps every area uses: who the people are, which records exist, writing
through the app, and how an attempt turned out."""

from pytest_bdd import given, parsers, then, when

from tests.bdd.world import phrase
from tests.support import grant

# People


@given(phrase("{name:Actor} is a superuser"))
def a_superuser(world, name):
    world.add_user(name, superuser=True)


@given(phrase("{name:Actor} is a user without any permissions"))
def a_user_without_permissions(world, name):
    world.add_user(name)


@given(phrase("{name:Actor} can {actions:Perms} {model:Model}"))
def a_user_with_permissions(world, name, actions, model):
    """`Alice can view, change and delete customers`. Adds to what Alice can already do."""
    user = world.users.get(name) or world.add_user(name)
    grant(user, model, *actions)


@given(phrase("{name:Actor} is inactive"))
def an_inactive_user(world, name):
    user = world.user(name)
    user.is_active = False
    user.save()


# Records


@given(phrase('a {model:Model} "{label:Q}"'))
def a_record(world, model, label):
    world.create(model, label)


@given(phrase('a {model:Model} "{label:Q}" with {field:Words} "{value:Q}"'))
def a_record_with_one_value(world, model, label, field, value):
    world.create(model, label, {field.replace(" ", "_"): value})


@given(phrase('a {model:Model} "{label:Q}" with:'))
def a_record_with_values(world, model, label, datatable):
    """A table of `| field | value |` rows."""
    world.create(model, label, {row[0].replace(" ", "_"): row[1] for row in datatable})


@given(phrase('{name:Actor} owns a {model:Model} "{label:Q}"'))
def an_owned_record(world, name, model, label):
    """The record was created by `name`, which is what "own" means to owner access and private views."""
    world.create(model, label, by=world.user(name))


@given(phrase('the {field:Words} of "{label:Q}" is "{value:Q}"'))
def a_field_value(world, field, label, value):
    instance = world.record(label)
    name = field.replace(" ", "_")
    setattr(instance, name, world.value(type(instance), name, value))
    instance.save()


# Writing through the app (the REST API the SPA uses)


@given(phrase('{name:Actor} changed the {field:Words} of "{label:Q}" to "{value:Q}"'))
@when(phrase('{name:Actor} changes the {field:Words} of "{label:Q}" to "{value:Q}"'))
def change_a_field(world, name, field, label, value):
    instance = world.records[label]
    field = field.replace(" ", "_")
    payload = {field: world.api_value(type(instance), field, value)}
    world.remember(name, world.api(name).patch(world.url(label), payload, format="json"))


@given(phrase('{name:Actor} deleted "{label:Q}"'))
@when(phrase('{name:Actor} deletes "{label:Q}"'))
def delete_a_record(world, name, label):
    world.remember(name, world.api(name).delete(world.url(label)))


# The state of records


@then(phrase('"{label:Q}" has {field:Words} "{value:Q}"'))
@then(phrase('"{label:Q}" still has {field:Words} "{value:Q}"'))
def has_value(world, label, field, value):
    assert world.shown(world.record(label), field.replace(" ", "_")) == value


@then(phrase('"{label:Q}" is deleted'))
def is_deleted(world, label):
    assert world.record(label).deleted


@then(phrase('"{label:Q}" is not deleted'))
def is_not_deleted(world, label):
    assert not world.record(label).deleted


# How the latest attempt turned out. Features say what happened, never a status code.


def _status(world):
    return world.response.status_code


@then("it succeeds")
def it_succeeds(world):
    assert 200 <= _status(world) < 300, (_status(world), getattr(world.response, "data", world.response.content))


@then("it is forbidden")
def it_is_forbidden(world):
    assert _status(world) == 403, _status(world)


@then("it requires signing in")
def it_requires_signing_in(world):
    assert _status(world) == 401, _status(world)


@then("it is not found")
def it_is_not_found(world):
    assert _status(world) == 404, _status(world)


@then("it is rejected")
def it_is_rejected(world):
    assert _status(world) == 400, (_status(world), world.response.content)


@then(parsers.parse('it is rejected with "{message}"'))
def it_is_rejected_with(world, message):
    assert _status(world) == 400, (_status(world), world.response.content)
    assert message in world.response.content.decode(), world.response.content


@then("it conflicts")
def it_conflicts(world):
    assert _status(world) == 409, (_status(world), world.response.content)
