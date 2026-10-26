"""Who changed what: the change log, change sets and the History tab.

Writing
- `When Alice changes the name of "Acme" to "Acme Inc" in her browser`: a signed-in browser session
- `When Alice changes the name of "Acme" to "Acme Inc" from the script "nightly-sync"`: the API, naming the script
- `When Alice changes the name of "Acme" to "Acme Inc" from a script that does not give its name`
- `When Alice changes the name of "Acme" to "Acme Inc" from a script whose name is 300 characters long`
- `When a background job changes the status of "Acme" to "churned"`: outside any request
- `Given Alice changed the status of "Acme" and "Globex" to "churned" in one go`: one change set, two records
- `Given Alice used the "Mark churned" action on "Acme"`
- `Given Alice merged the duplicate "Acme copy" into "Acme"`
- `Given Alice added "Acme" to the watchers of "Printer broken"` (also `removed … from`)
- `When Alice looks at "Acme"`
- `When Alice reads the history of "Acme"`
- `Given "Acme" has been changed 205 times`
- `Given "Acme" has 2 changes logged before change sets existed`

Reading the change log (sources read as the History tab shows them: "the app",
"the API", `the script "nightly-sync"`, "an undo", "the system")
- `Then the latest change to "Acme" came from the app`
- `Then the latest change to "Acme" was made by Alice` / `was made by the system`
- `Then the latest change to "Acme" is an update` (a creation, a deletion, a restore, an action, a merge, an undo)
- `Then the latest change to "Acme" is labelled "Imported from billing"`
- `Then the latest change to "Acme" changed the name from "Acme" to "Acme Inc"`
- `Then the latest change to "Acme" changed only the name` / `changed nothing`
- `Then the change log of "Acme" has 2 entries`
- `Then the app is told the change set of the latest change to "Acme"` / `Then the app is told no change set`
- `Then the watchers of "Printer broken" are "Acme" and "Globex"`
- `Then the history of "Acme" reads, newest first:` a `| by | from | did |` table
"""

import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from pytest_bdd import given, parsers, then, when
from rest_framework.test import APIClient

from crudkit.audit import audit
from crudkit.models import ChangeLog
from crudkit.utils import get_system_user
from crudkit_api import services
from crudkit_api.views import CHANGE_SET_HEADER
from tests.bdd.steps.views import labels_in
from tests.bdd.world import LABELS, phrase, split_list

User = get_user_model()

# How the History tab names an entry's source.
SOURCES = {
    "the app": "ui",
    "the API": "api",
    "an MCP client": "mcp",
    "the assistant": "assistant",
    "an agent": "agent",
    "an undo": "revert",
    "the system": "system",
}

# How the History tab titles what a change set did.
ACTIONS = {
    "Created": "create",
    "Updated": "update",
    "Deleted": "delete",
    "Restored": "restore",
    "Ran an action": "action",
    "Merged": "merge",
    "Reverted a change": "revert",
}

# A source as a step names it: one of SOURCES, optionally `by the script "…"`, or just `the script "…"`.
SOURCE_PATTERN = r'(?:the script "[^"]*"|(?:%s)(?: by the script "[^"]*")?)' % "|".join(SOURCES)

KINDS = {
    "a creation": "create",
    "an update": "update",
    "a deletion": "delete",
    "a restore": "restore",
    "an action": "action",
    "a merge": "merge",
    "an undo": "revert",
}


def entries_of(instance):
    """The change log of `instance`, oldest first."""
    return ChangeLog.objects.filter(
        related_content_type=ContentType.objects.get_for_model(instance), related_object_id=instance.pk
    ).order_by("created_at", "id")


def latest_entry(world, label):
    entry = entries_of(world.record(label)).last()
    assert entry is not None, f'Nothing is logged for "{label}"'
    return entry


def parse_source(text: str) -> tuple[str, str | None]:
    """`the script "nightly-sync"` -> ("api", "nightly-sync"); `an undo by the script "x"` -> ("revert", "x").
    The client is None when the text does not name one."""
    text = text.replace('"', "")
    source_text, _, client = text.partition(" by the script ")
    if source_text.startswith("the script "):
        return "api", source_text.removeprefix("the script ")
    return SOURCES[source_text], client or None


def shown_logged(world, value) -> str:
    """A logged value as a step reads it: record ids by label, lists joined with "and"."""
    if value is None:
        return ""
    if isinstance(value, list):
        return " and ".join(shown_logged(world, item) for item in value)
    labels = {world.ck_id(label): label for label in world.records}
    return labels.get(value, str(value))


def person(world, who: str):
    return get_system_user() if who == "the system" else world.user(who)


def _api_change(world, name, label, field, value, client):
    instance = world.records[label]
    field = field.replace(" ", "_")
    payload = {field: world.api_value(type(instance), field, value)}
    world.remember(name, client.patch(world.url(label), payload, format="json"))


def _script_client(world, name, script_name):
    client = APIClient(headers={"Client-Id": script_name} if script_name else {})
    client.force_authenticate(world.user(name))
    return client


def remember_change_set(world, name, context):
    world.change_set = world.change_sets[name] = str(context.change_set)


# Writing


@when(phrase('{name:Actor} changes the {field:Words} of "{label:Q}" to "{value:Q}" in {whose:Their} browser'))
def change_in_browser(world, name, field, label, value, whose):
    client = APIClient()
    assert client.login(username=world.user(name).username, password="password")
    _api_change(world, name, label, field, value, client)


@when(phrase('{name:Actor} changes the {field:Words} of "{label:Q}" to "{value:Q}" from the script "{script:Q}"'))
def change_from_script(world, name, field, label, value, script):
    _api_change(world, name, label, field, value, _script_client(world, name, script))


@when(
    phrase(
        '{name:Actor} changes the {field:Words} of "{label:Q}" to "{value:Q}" from a script that does not give its name'
    )
)
def change_from_anonymous_script(world, name, field, label, value):
    _api_change(world, name, label, field, value, _script_client(world, name, ""))


@when(
    phrase(
        '{name:Actor} changes the {field:Words} of "{label:Q}" to "{value:Q}" '
        "from a script whose name is {length:d} characters long"
    )
)
def change_from_long_named_script(world, name, field, label, value, length):
    _api_change(world, name, label, field, value, _script_client(world, name, "x" * length))


@given(phrase('a background job changed the {field:Words} of "{label:Q}" to "{value:Q}"'))
@when(phrase('a background job changes the {field:Words} of "{label:Q}" to "{value:Q}"'))
def change_in_background(world, field, label, value):
    instance = world.record(label)
    name = field.replace(" ", "_")
    services.patch_fields(instance, {name: world.api_value(type(instance), name, value)}, get_system_user())


@given(phrase('{name:Actor} changed the {field:Words} of "{first:Q}" and "{second:Q}" to "{value:Q}" in one go'))
def change_two_in_one_go(world, name, field, first, second, value):
    """One change set across two records, as one save in the app that touches both would make."""
    user = world.user(name)
    field = field.replace(" ", "_")
    with audit("ui", user=user) as context:
        for label in (first, second):
            instance = world.record(label)
            services.patch_fields(instance, {field: world.api_value(type(instance), field, value)}, user)
    remember_change_set(world, name, context)


@given(phrase('{name:Actor} used the "{action:Q}" action on "{label:Q}"'))
@when(phrase('{name:Actor} uses the "{action:Q}" action on "{label:Q}"'))
def use_an_action(world, name, action, label):
    instance = world.record(label)
    method = next(m for m, func in instance._actions.items() if getattr(func, "verbose_name", None) == action)
    world.remember(name, world.api(name).post(world.url(label, "action"), {"action": method}, format="json"))


@given(phrase('{name:Actor} merged the duplicate "{duplicate:Q}" into "{label:Q}"'))
def merge_a_duplicate(world, name, duplicate, label):
    payload = {"merge": [world.ck_id(label), world.ck_id(duplicate)], "id": world.ck_id(label)}
    world.remember(name, world.api(name).post(world.url(label, "merge"), payload, format="json"))
    assert world.response.status_code == 200, world.response.content


def _watchers(world, name, label, ticket, method):
    user = world.user(name)
    with audit("ui", user=user) as context:
        getattr(world.record(ticket).watchers, method)(world.record(label))
    remember_change_set(world, name, context)


@given(phrase('{name:Actor} added "{label:Q}" to the watchers of "{ticket:Q}"'))
@when(phrase('{name:Actor} adds "{label:Q}" to the watchers of "{ticket:Q}"'))
def add_a_watcher(world, name, label, ticket):
    _watchers(world, name, label, ticket, "add")


@given(phrase('{name:Actor} removed "{label:Q}" from the watchers of "{ticket:Q}"'))
@when(phrase('{name:Actor} removes "{label:Q}" from the watchers of "{ticket:Q}"'))
def remove_a_watcher(world, name, label, ticket):
    _watchers(world, name, label, ticket, "remove")


@given(phrase('"{label:Q}" is a watcher of "{ticket:Q}"'))
def a_watcher(world, label, ticket):
    world.record(ticket).watchers.add(world.record(label))


@when(phrase('{name:Actor} looks at "{label:Q}"'))
def look_at(world, name, label):
    world.remember(name, world.api(name).get(world.url(label)))


@when(phrase('{name:Actor} reads the history of "{label:Q}"'))
def read_history(world, name, label):
    world.remember(name, world.api(name).get(world.url(label, "history")))


@given(phrase('"{label:Q}" has been changed {count:d} times'))
def changed_many_times(world, label, count):
    instance = world.record(label)
    for number in range(count):
        before = type(instance)._base_manager.get(pk=instance.pk)
        instance.name = f"{label} {number}"
        instance.save()
        ChangeLog.objects.create_from_objects(before, instance)


@given(phrase('"{label:Q}" has {count:d} changes logged before change sets existed'))
def legacy_changes(world, label, count):
    instance = world.record(label)
    system = get_system_user()
    for _ in range(count):
        ChangeLog.objects.create(
            related_content_type=ContentType.objects.get_for_model(instance),
            related_object_id=world.number(label),
            field_changes={"status": ["active", "churned"]},
            created_by=system,
            updated_by=system,
        )


# Records kept in step with another system


def _external(world, system, model, system_id, defaults, **lookup):
    return model.objects.update_or_create_external(system, system_id, defaults=defaults, **lookup)[0]


@given(phrase('the "{system:Q}" system imported its {model:Model} "{system_id:Q}" as "{label:Q}"'))
@when(phrase('the "{system:Q}" system imports its {model:Model} "{system_id:Q}" as "{label:Q}"'))
def import_external(world, system, model, system_id, label):
    by = get_system_user()
    world.add(label, _external(world, system, model, system_id, {"name": label, "created_by": by, "updated_by": by}))


@when(
    phrase(
        'the "{system:Q}" system imports its {model:Model} "{system_id:Q}", '
        'which matches "{label:Q}" by email, with the name "{name:Q}"'
    )
)
def import_matching_external(world, system, model, system_id, label, name):
    email = world.record(label).email
    _external(world, system, model, system_id, {"name": name}, email=email)


@when(phrase('the "{system:Q}" system renames its {model:Model} "{system_id:Q}" to "{name:Q}"'))
def rename_external(world, system, model, system_id, name):
    _external(world, system, model, system_id, {"name": name})


@when(phrase('the "{system:Q}" system sends its {model:Model} "{system_id:Q}" again unchanged'))
def resend_external(world, system, model, system_id):
    current = model.objects.get_external(system, system_id)
    _external(world, system, model, system_id, {"name": current.name})


@when(phrase('the "{system:Q}" system marks its {model:Model} "{system_id:Q}" as not deleted'))
def undelete_external(world, system, model, system_id):
    _external(world, system, model, system_id, {"deleted": False})


@then(phrase('"{label:Q}" is linked to the "{system:Q}" system as "{system_id:Q}"'))
def linked_to(world, label, system, system_id):
    instance = world.record(label)
    assert type(instance).objects.get_external(system, system_id).pk == instance.pk


# The change log


@then(parsers.re(r'the latest change to "(?P<label>[^"]*)" came from (?P<source>%s)' % SOURCE_PATTERN))
def came_from(world, label, source):
    entry = latest_entry(world, label)
    expected_source, expected_client = parse_source(source)
    assert entry.source == expected_source, (entry.source, expected_source)
    if expected_client is not None or expected_source == "api":
        assert entry.client == (expected_client or ""), entry.client


@then(phrase('the latest change to "{label:Q}" came from the API with a script name of {length:d} characters'))
def came_from_long_named_script(world, label, length):
    entry = latest_entry(world, label)
    assert (entry.source, len(entry.client)) == ("api", length), (entry.source, len(entry.client))


@then(phrase('the latest change to "{label:Q}" was made by {who}'))
def made_by(world, label, who):
    entry = latest_entry(world, label)
    assert entry.created_by == person(world, who), entry.created_by


@then(parsers.re(r'the latest change to "(?P<label>[^"]*)" is (?P<kind>%s)' % "|".join(KINDS)))
def is_kind(world, label, kind):
    assert latest_entry(world, label).action == KINDS[kind], latest_entry(world, label).action


@then(phrase('the latest change to "{label:Q}" is labelled "{text:Q}"'))
def is_labelled(world, label, text):
    assert latest_entry(world, label).label == text, latest_entry(world, label).label


@then(phrase('the latest change to "{label:Q}" changed the {field:Words} from "{old:Q}" to "{new:Q}"'))
def changed_from_to(world, label, field, old, new):
    changes = latest_entry(world, label).field_changes
    logged_old, logged_new = changes[field.replace(" ", "_")]
    assert (shown_logged(world, logged_old), shown_logged(world, logged_new)) == (old, new), changes


@then(phrase('the latest change to "{label:Q}" changed only the {field:Words}'))
def changed_only(world, label, field):
    changes = latest_entry(world, label).field_changes
    assert list(changes) == [field.replace(" ", "_")], changes


@then(phrase('the latest change to "{label:Q}" changed nothing'))
def changed_nothing(world, label):
    assert latest_entry(world, label).field_changes == {}, latest_entry(world, label).field_changes


@then(phrase('the deletion of "{label:Q}" kept a snapshot of:'))
def deletion_snapshot(world, label, datatable):
    """`| field | value |` rows of what the deleted record held; nothing else may be in it."""
    entry = latest_entry(world, label)
    assert entry.action == ChangeLog.Action.DELETE, entry.action
    snapshot = {field: shown_logged(world, old) for field, (old, _new) in entry.field_changes.items()}
    assert snapshot == {row[0].replace(" ", "_"): row[1] for row in datatable}, snapshot


@then(phrase('the change log of "{label:Q}" has {count:d} entries'))
@then(phrase('the change log of "{label:Q}" has {count:d} entry'))
def entry_count(world, label, count):
    assert entries_of(world.record(label)).count() == count, list(entries_of(world.record(label)).values())


@then(phrase('the last {count:d} changes to "{label:Q}" each have their own change set'))
def own_change_sets(world, label, count):
    change_sets = [entry.change_set for entry in entries_of(world.record(label)).reverse()[:count]]
    assert len(change_sets) == count and None not in change_sets, change_sets
    assert len(set(change_sets)) == count, change_sets


@then(phrase('the app is told the change set of the latest change to "{label:Q}"'))
def told_the_change_set(world, label):
    header = world.response.headers.get(CHANGE_SET_HEADER)
    assert header is not None, "No change set was reported"
    assert uuid.UUID(header) == latest_entry(world, label).change_set, header


@then("the app is told no change set")
def told_no_change_set(world):
    assert CHANGE_SET_HEADER not in world.response.headers, world.response.headers


@then(parsers.re(rf'the watchers of "(?P<ticket>[^"]*)" are (?P<labels>{LABELS})'))
def watchers_are(world, ticket, labels):
    names = sorted(str(customer) for customer in world.record(ticket).watchers.all())
    assert names == sorted(labels_in(labels)), names


@then(phrase('"{ticket:Q}" has no watchers'))
def no_watchers(world, ticket):
    assert not world.record(ticket).watchers.exists()


# The History tab


def _history(world):
    assert world.response.status_code == 200, (world.response.status_code, world.response.content)
    return world.response.data


@then(phrase("the history reads, newest first:"))
def history_reads(world, datatable):
    """A `| by | from | did |` table: who, the source as in `came from …`, and the History tab's titles."""
    header, *rows = datatable
    expected = [dict(zip(header, row, strict=True)) for row in rows]
    history = _history(world)
    assert len(history) == len(expected), [(g["source"], g["actions"]) for g in history]
    for group, row in zip(history, expected, strict=True):
        assert group["by"]["id"] == person(world, row["by"]).pk, (group["by"], row)
        source, client = parse_source(row["from"])
        assert (group["source"], group["client"]) == (source, client or ""), (group["source"], group["client"], row)
        assert group["actions"] == [ACTIONS[title] for title in split_list(row["did"])], (group["actions"], row)


@then(phrase("the history has {count:d} change sets"))
def history_size(world, count):
    assert len(_history(world)) == count, len(_history(world))


@then(phrase('the newest change set in the history changed the {field:Words} from "{old:Q}" to "{new:Q}"'))
def newest_changed(world, field, old, new):
    changes = [entry["field_changes"] for entry in _history(world)[0]["entries"]]
    logged = [change[field.replace(" ", "_")] for change in changes if field.replace(" ", "_") in change]
    assert [[shown_logged(world, value) for value in pair] for pair in logged] == [[old, new]], changes


@then(phrase('the newest change set in the history is labelled "{text:Q}"'))
def newest_labelled(world, text):
    assert _history(world)[0]["label"] == text, _history(world)[0]["label"]


def _nth_group(world, position):
    return _history(world)[{"newest": 0, "second": 1, "oldest": -1}[position]]


@then(phrase("the {position:Words} change set in the history can be undone"))
def can_be_undone(world, position):
    group = _nth_group(world, position)
    assert group["revertible"] and not group["reverted"], group


@then(phrase("the {position:Words} change set in the history cannot be undone"))
def cannot_be_undone(world, position):
    assert not _nth_group(world, position)["revertible"], _nth_group(world, position)


@then(phrase("the {position:Words} change set in the history is marked as undone"))
def marked_undone(world, position):
    assert _nth_group(world, position)["reverted"], _nth_group(world, position)


@then(phrase("the {position:Words} change set in the history also changed {count:d} other record"))
@then(phrase("the {position:Words} change set in the history also changed {count:d} other records"))
def other_records(world, position, count):
    assert _nth_group(world, position)["other_records"] == count, _nth_group(world, position)


@then(phrase("no change set in the history can be undone"))
def none_undoable(world):
    assert not any(group["revertible"] for group in _history(world)), _history(world)


@then(phrase("every change set in the history has a single entry"))
def single_entries(world):
    assert all(len(group["entries"]) == 1 for group in _history(world)), _history(world)


@then(parsers.parse('it is forbidden with "{message}"'))
def forbidden_with(world, message):
    assert world.response.status_code == 403, world.response.status_code
    assert message in world.response.content.decode(), world.response.content
