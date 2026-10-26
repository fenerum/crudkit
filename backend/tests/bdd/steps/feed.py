"""Notes and activity, work logs, snippets and links to external systems.

Phrases this area adds:

- `Given a note "Called them" was left on "Acme"` / `... was left on "Support" about "Acme"`
- `When Alice leaves the note "Called them" on "Acme"`
- `When the assistant adds the note "Called them" to "Acme" on Alice's behalf`
  / `Then the note is refused with "Note body is empty"`
- `Then the activity of "Acme" is "Second call" and "First call"` (newest first) / `... is empty`
- `Then the note "Called them" is by Alice` / `Then the note "Renewal call" is about "Acme"`
- `Given Alice is tracking time on "Acme"` / `When Alice starts tracking time on "Acme"`
  / `When Alice stops tracking time` (`Given … stopped …`) / `Then Alice is tracking time on "Acme"` / `Then Alice is not tracking time`
- `Then a second timer for Alice on "Globex" is refused`
- `When Alice saves the snippet "Greeting" with "Hello" for customers` (or without `for ...`)
  / `Then the snippet "Greeting" is meant for customers` / `... is not limited to any record type`
- `When Alice searches the snippets for "greet"`
- `Given "Acme" is linked to "42" in the "billing" system` / `Then "42" in the "billing" system is linked to "Acme"`
- `When the "billing" system imports customer "42" named "Initech"` (`, matching on email "x"` to adopt a record)
- `Then looking up customer "42" in the "billing" system finds "Initech"` / `... finds nothing`
- `Then linking "Globex" to "42" in the "billing" system is refused`
"""

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone
from pytest_bdd import given, then, when

from crudkit.audit import audit
from crudkit.models import ExternalObject, FeedItem, Snippet, WorkLog
from crudkit.utils import get_model_types, get_system_user
from crudkit_api.services import create_note, get_feed
from tests.bdd.world import phrase, split_list

# Notes and activity


@given(phrase('a note "{body:Q}" was left on "{label:Q}"'))
def a_note(world, body, label):
    world.create(FeedItem, body, {"parent_object": label})


@given(phrase('a note "{body:Q}" was left on "{label:Q}" about "{about:Q}"'))
def a_note_about(world, body, label, about):
    world.create(FeedItem, body, {"parent_object": label, "related_object": about})


@when(phrase('{name:Actor} leaves the note "{body:Q}" on "{label:Q}"'))
def leaves_a_note(world, name, body, label):
    payload = {"parent_object": world.ck_id(label), "body": body}
    response = world.remember(name, world.api(name).post("/api/v1/FEI/", payload, format="json"))
    if response.status_code == 201:
        world.add(body, FeedItem.objects.get(pk=response.data["id"]))


@when(phrase('the assistant adds the note "{body:Q}" to "{label:Q}" on {name:Actor}\'s behalf'))
def the_assistant_adds_a_note(world, body, label, name):
    world.refusal = None
    user = world.user(name)
    try:
        with audit("assistant", user=user) as context:
            outcome = create_note(world.record(label), body, user)
    except ValueError as error:
        world.refusal = str(error)
        return
    world.change_set = world.change_sets[name] = str(context.change_set)
    world.add(body, FeedItem.objects.get(pk=outcome["feeditem_id"]))


@then(phrase('the note is refused with "{message:Q}"'))
def the_note_is_refused(world, message):
    assert world.refusal and message in world.refusal, world.refusal


def _activity(world, label) -> list[str]:
    return [entry["body"] for entry in get_feed(world.record(label))]


@then(phrase('the activity of "{label:Q}" is {bodies:Labels}'))
def the_activity_is(world, label, bodies):
    """Newest first."""
    shown = _activity(world, label)
    assert shown == bodies, shown


@then(phrase('the activity of "{label:Q}" is empty'))
def the_activity_is_empty(world, label):
    shown = _activity(world, label)
    assert shown == [], shown


@then(phrase('the note "{body:Q}" is by {name:Actor}'))
def the_note_is_by(world, body, name):
    assert world.record(body).created_by == world.user(name)


@then(phrase('the note "{body:Q}" is about "{about:Q}"'))
def the_note_is_about(world, body, about):
    assert world.record(body).related_object == world.record(about)


# Work logs


def _active_work_log(world, name):
    return WorkLog.objects.filter(created_by=world.user(name), end_at__isnull=True, deleted=False).first()


def _start_timer(world, name, label):
    user = world.user(name)
    WorkLog.objects.create(related_object=world.record(label), created_by=user, updated_by=user)


@given(phrase('{name:Actor} is tracking time on "{label:Q}"'))
def is_tracking_time(world, name, label):
    _start_timer(world, name, label)


@when(phrase('{name:Actor} starts tracking time on "{label:Q}"'))
def starts_tracking_time(world, name, label):
    payload = {"related_object": world.ck_id(label)}
    world.remember(name, world.api(name).post("/api/v1/WLG/", payload, format="json"))


@given(phrase("{name:Actor} stopped tracking time"))
@when(phrase("{name:Actor} stops tracking time"))
def stops_tracking_time(world, name):
    work_log = _active_work_log(world, name)
    url = f"/api/v1/WLG/{work_log.pk}/"
    world.remember(name, world.api(name).patch(url, {"end_at": timezone.now().isoformat()}, format="json"))


@then(phrase('{name:Actor} is tracking time on "{label:Q}"'))
def tracks_time_on(world, name, label):
    work_log = _active_work_log(world, name)
    assert work_log is not None, f"{name} is not tracking time"
    assert work_log.related_object == world.record(label)


@then(phrase('a second timer for {name:Actor} on "{label:Q}" is refused'))
def second_timer_refused(world, name, label):
    try:
        with transaction.atomic():
            _start_timer(world, name, label)
    except IntegrityError:
        return
    raise AssertionError(f"{name} could run two timers at once")


@then(phrase("{name:Actor} is not tracking time"))
def tracks_no_time(world, name):
    assert _active_work_log(world, name) is None


# Snippets


def _type_ids(model_words: str) -> list[str]:
    """ "customers and tickets" -> ["CUS", "TIC"]"""
    plurals = {str(m._meta.verbose_name_plural).lower(): m.TYPE_ID for m in get_model_types().values()}
    return [plurals[words] for words in split_list(model_words)]


def _save_snippet(world, name, snippet, body, model_types):
    payload = {"name": snippet, "body": body} | ({"model_types": model_types} if model_types else {})
    response = world.remember(name, world.api(name).post("/api/v1/SNP/", payload, format="json"))
    if response.status_code == 201:
        world.add(snippet, Snippet.objects.get(pk=response.data["id"]))


@when(phrase('{name:Actor} saves the snippet "{snippet:Q}" with "{body:Q}"'))
def saves_a_snippet(world, name, snippet, body):
    _save_snippet(world, name, snippet, body, [])


@when(phrase('{name:Actor} saves the snippet "{snippet:Q}" with "{body:Q}" for {models}'))
def saves_a_snippet_for(world, name, snippet, body, models):
    _save_snippet(world, name, snippet, body, _type_ids(models))


@then(phrase('the snippet "{snippet:Q}" is not limited to any record type'))
def snippet_for_everything(world, snippet):
    assert world.record(snippet).model_types == []


@then(phrase('the snippet "{snippet:Q}" is meant for {models}'))
def snippet_for(world, snippet, models):
    assert world.record(snippet).model_types == _type_ids(models)


@when(phrase('{name:Actor} searches the {model:Model} for "{query:Q}"'))
def searches(world, name, model, query):
    world.remember(name, world.api(name).get(f"/api/v1/{model.TYPE_ID}/", {"_q": query}))


# Links to external systems


def _content_type(model):
    return ContentType.objects.get_for_model(model)


def _link(world, label, system_id, system):
    system_user = get_system_user()
    return ExternalObject.objects.create(
        system_name=system,
        system_id=system_id,
        related_object=world.record(label),
        created_by=system_user,
        updated_by=system_user,
    )


@given(phrase('"{label:Q}" is linked to "{system_id:Q}" in the "{system:Q}" system'))
def is_linked(world, label, system_id, system):
    _link(world, label, system_id, system)


@then(phrase('"{system_id:Q}" in the "{system:Q}" system is linked to "{label:Q}"'))
def links_to(world, system_id, system, label):
    instance = world.record(label)
    link = ExternalObject.objects.get(
        system_name=system, system_id=system_id, related_content_type=_content_type(type(instance))
    )
    assert link.related_object_id == world.number(label)


@then(phrase('linking "{label:Q}" to "{system_id:Q}" in the "{system:Q}" system is refused'))
def linking_is_refused(world, label, system_id, system):
    try:
        with transaction.atomic():
            _link(world, label, system_id, system)
    except IntegrityError:
        return
    raise AssertionError(f'"{label}" could be linked to {system} {system_id} a second time')


def _import(world, model, system, system_id, label, match=None):
    system_user = get_system_user()
    instance, _ = model.objects.update_or_create_external(
        system,
        system_id,
        defaults={"name": label},
        create_defaults={"name": label, "created_by": system_user, "updated_by": system_user},
        **(match or {}),
    )
    known = [existing for existing, record in world.records.items() if record.pk == instance.pk]
    if not known:
        world.add(label, instance)


@given(phrase('the "{system:Q}" system imported {model:Model} "{system_id:Q}" named "{label:Q}"'))
@when(phrase('the "{system:Q}" system imports {model:Model} "{system_id:Q}" named "{label:Q}"'))
def imports(world, system, model, system_id, label):
    _import(world, model, system, system_id, label)


@when(
    phrase(
        'the "{system:Q}" system imports {model:Model} "{system_id:Q}" named "{label:Q}",'
        ' matching on {field:Words} "{value:Q}"'
    )
)
def imports_matching(world, system, model, system_id, label, field, value):
    _import(world, model, system, system_id, label, match={field.replace(" ", "_"): value})


@then(phrase('looking up {model:Model} "{system_id:Q}" in the "{system:Q}" system finds "{label:Q}"'))
def lookup_finds(world, model, system_id, system, label):
    assert model.objects.get_external(system, system_id).pk == world.record(label).pk


@then(phrase('looking up {model:Model} "{system_id:Q}" in the "{system:Q}" system finds nothing'))
def lookup_finds_nothing(world, model, system_id, system):
    try:
        model.objects.get_external(system, system_id)
    except model.DoesNotExist:
        return
    raise AssertionError(f"{system} {system_id} was found")
