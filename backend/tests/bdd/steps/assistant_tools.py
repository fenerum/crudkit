"""The assistant's tools, called the way the AI model calls them, for the
person using the assistant and with what is on their screen.

Arguments are given as a table of `| argument | value |` rows:

- `record` / `records`: a record by its label, or several ("Acme, Beta and Gamma");
- `type`: a record type by name ("customers");
- `view`: a saved view by its label; `change set`: "that change" or "the undone change";
- `set <field>`: a value to set (relations by label, people by name), `filter <field>`: a filter;
- `fields`, `group by`, `metrics`: lists; `limit`, `offset`: numbers; anything else as written.

Phrases this area adds:

- `When the assistant calls get_object` / `... calls get_object for "Acme"` / `... calls propose_patch with:`
- `Given the assistant has proposed changing the status of "Acme" to "churned"` (filed as "the proposal")
- `Given the assistant is making a dry run`
- `Given Alice may read the change history` / `Given there are 51 topics to choose from`
- `Then the assistant is told "..."` / `Then the assistant is refused with "..."`
- `Then the assistant gets the records "Acme, Beta"` / `Then the assistant gets no records`
- `Then the assistant learns that status is currently "active"` / `... that status can be "active, churned"`
- `Then the assistant learns that topic can point at "Billing"` / `... there are too many topics to list for topic`
- `Then the assistant learns the actions "mark_churned"` / `... that 1 ticket points at it through "ticket_set"`
- `Then the assistant learns about no related records` / `Then the assistant does not learn about created by`
- `Then the assistant learns about the record types "customers, tickets"` / `... does not learn about ...`
- `Then the assistant learns that Alice may create customers` / `... may not create ...`
- `Then the assistant reads that Alice changed the status of "Acme" from "active" to "churned"`
- `Then the assistant reads the note "..."` / `Then the assistant gets the groups:` (a table with a header)
- `Then the assistant reads only the columns "id, label, name"`
- `Then the assistant has proposed changing the status of "Acme" to "churned"` (and a card shows it)
- `Then the assistant has proposed running "mark_churned" on "Acme"` / `... adding the note "..." to "Acme"`
- `Then the assistant has proposed creating a customer with:` / `... undoing that change on "Acme"`
- `Then the proposal is labelled "..."` / `Then the assistant has made 2 proposals` / `... has proposed nothing`
- `Then the assistant would have proposed changing the status of "Acme" to "churned"` (a dry run)
- `Then the form on the screen is filled in with:` / `Then a new customer form opens filled in with:`
- `Then no form is touched`
"""

import asyncio
from uuid import UUID

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from pytest_bdd import given, then, when

from crudkit.models import ChangeLog
from crudkit.utils import get_model_types
from crudkit_assistant import tools
from tests.bdd.steps.assistant import (
    assistant,
    deps,
    labels_of,
    person,
    proposals,
    readable,
    script_call,
)
from tests.bdd.world import model_named, phrase, split_list
from tests.support import grant

ARGUMENT_NAMES = {"record": "id", "records": "ids"}
LISTS = {"fields", "group_by", "metrics"}
NUMBERS = {"limit", "offset"}
UNKNOWN_CHANGE_SET = "00000000-0000-0000-0000-000000000000"


class _Ctx:
    """What a tool gets from the agent: the dependencies of this conversation."""

    def __init__(self, deps):
        self.deps = deps


def _record_id(world, label: str) -> str:
    """A record's id; text that names no record is passed on as written."""
    return world.ck_id(label) if label in world.records else label


def _type_id(text: str) -> str:
    try:
        return model_named(text).TYPE_ID
    except LookupError:
        return text


def _change_set(world, text: str) -> str:
    known = {"that change": world.change_set, "the undone change": world.undone, "a change that never happened": None}
    if text not in known:
        return text
    return known[text] or UNKNOWN_CHANGE_SET


def _argument(world, name: str, text: str):
    if name == "id":
        return _record_id(world, text)
    if name == "ids":
        return [_record_id(world, label) for label in split_list(text)]
    if name == "type":
        return _type_id(text)
    if name == "view":
        return _record_id(world, text)
    if name == "change_set":
        return _change_set(world, text)
    if name in LISTS:
        return split_list(text)
    if name in NUMBERS:
        return int(text)
    return text


def _model_of(world, arguments: dict):
    """The record type the `set` values are for."""
    if "type" in arguments:
        return get_model_types().get(arguments["type"])
    ids = [arguments["id"]] if "id" in arguments else arguments.get("ids") or []
    screen = assistant(world).screen
    record_id = next(iter(ids), None) or (screen.get("form") or {}).get("type_id") or screen.get("record_id") or ""
    return get_model_types().get(record_id[:3])


def _field_value(world, model, name: str, text: str):
    """`text` as the AI model would write it for `name`: relations by id, people by pk."""
    if model is None:
        return text
    try:
        model_field = model._meta.get_field(name)
    except FieldDoesNotExist:
        return text
    if model_field.is_relation and model_field.related_model is get_user_model():
        return world.user(text).pk if text in world.users else text
    if model_field.is_relation:
        return _record_id(world, text)
    return text


def tool_arguments(world, datatable) -> dict:
    arguments, values, filters = {}, {}, {}
    for name, text in datatable:
        if name.startswith("set "):
            values[name.removeprefix("set ").replace(" ", "_")] = text
        elif name.startswith("filter "):
            filters[name.removeprefix("filter ").replace(" ", "_")] = text
        else:
            key = ARGUMENT_NAMES.get(name, name.replace(" ", "_"))
            arguments[key] = _argument(world, key, text)
    if values:
        model = _model_of(world, arguments)
        arguments["fields"] = {name: _field_value(world, model, name, text) for name, text in values.items()}
    if filters:
        arguments["filters"] = filters
    return arguments


def call_tool(world, tool: str, arguments: dict):
    state = assistant(world)
    context = _Ctx(deps(world))
    context.deps._outbox = asyncio.Queue()
    state.result = async_to_sync(getattr(tools, tool))(context, **arguments)
    state.sent = []
    while not context.deps._outbox.empty():
        state.sent.append(context.deps._outbox.get_nowait())


@when(phrase("the assistant calls {tool:Words}"))
def calls(world, tool):
    call_tool(world, tool, {})


@when(phrase('the assistant calls {tool:Words} for "{label:Q}"'))
def calls_for(world, tool, label):
    call_tool(world, tool, {"id": world.ck_id(label)})


@when(phrase("the assistant calls {tool:Words} with:"))
def calls_with(world, tool, datatable):
    call_tool(world, tool, tool_arguments(world, datatable))


@when(phrase('the assistant calls {tool:Words} on every {model:Model}, setting {field:Words} to "{value:Q}"'))
def calls_on_every(world, tool, model, field, value):
    ids = [str(pk) for pk in model.objects.values_list("pk", flat=True)]
    call_tool(world, tool, {"ids": ids, "fields": {field.replace(" ", "_"): value}})


@given(phrase("the assistant will call {tool:Words} with:"))
def will_call_with(world, monkeypatch, tool, datatable):
    script_call(world, monkeypatch, tool, tool_arguments(world, datatable))


@given(phrase('the assistant has proposed changing the {field:Words} of "{label:Q}" to "{value:Q}"'))
def has_proposed(world, field, label, value):
    call_tool(world, "propose_patch", {"id": world.ck_id(label), "fields": {field.replace(" ", "_"): value}})
    world.add("the proposal", proposals().last())


@given("the assistant is making a dry run")
def dry_run(world):
    assistant(world).dry_run = True


@given(phrase("{name:Actor} may read the change history"))
def may_read_history(world, name):
    grant(world.user(name), ChangeLog, "view")


@given(phrase("there are {count:d} {model:Model} to choose from"))
def there_are(world, count, model):
    for n in range(1, count + 1):
        world.create(model, f"{model._meta.verbose_name} {n}")


# ---------------------------------------------------------------------------
# What the tool returned


def _result(world):
    return assistant(world).result


def _error(result) -> str | None:
    if isinstance(result, str) and result.startswith("ERROR"):
        return result
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    return None


@then(phrase('the assistant is told "{text:Q}"'))
def is_told(world, text):
    result = _result(world)
    assert _error(result) is None, result
    assert text in readable(world, str(result)), readable(world, str(result))


@then(phrase('the assistant is refused with "{text:Q}"'))
def is_refused(world, text):
    error = _error(_result(world))
    assert error is not None, _result(world)
    assert text in readable(world, error), readable(world, error)


def _rows(result) -> list:
    rows = result.get("results", []) if isinstance(result, dict) else result
    assert isinstance(rows, list), result
    return rows


@then(phrase('the assistant gets the records "{labels:Q}"'))
def gets_records(world, labels):
    found = labels_of(world, [row["id"] for row in _rows(_result(world))])
    assert found == set(split_list(labels)), found


@then("the assistant gets no records")
def gets_no_records(world):
    assert _rows(_result(world)) == [], _result(world)


def _field(world, name: str) -> dict:
    fields = _result(world)["fields"]
    assert name in fields, sorted(fields)
    return fields[name]


@then(phrase('the assistant learns that {field:Words} is currently "{value:Q}"'))
def currently(world, field, value):
    current = _field(world, field.replace(" ", "_"))["current"]
    shown = current.get("display") if isinstance(current, dict) else current
    assert str(shown) == value, current


@then(phrase('the assistant learns that {field:Words} can be "{choices:Q}"'))
def can_be(world, field, choices):
    assert _field(world, field.replace(" ", "_"))["choices"] == split_list(choices)


@then(phrase('the assistant learns that {field:Words} can point at "{labels:Q}"'))
def can_point_at(world, field, labels):
    options = _field(world, field.replace(" ", "_"))["fk_choices"]["options"]
    assert {option["display"] for option in options} == set(split_list(labels)), options


@then(phrase("the assistant learns there are too many {model:Model} to list for {field:Words}"))
def too_many_to_list(world, model, field):
    choices = _field(world, field.replace(" ", "_"))["fk_choices"]
    assert choices["options"] is None, choices
    assert "too many to list" in choices["reason"]


@then(phrase('the assistant learns the actions "{names:Q}"'))
def learns_actions(world, names):
    assert _result(world)["actions"] == split_list(names)


@then(phrase('the assistant learns that {count:d} {model:Model} points at it through "{relation:Q}"'))
@then(phrase('the assistant learns that {count:d} {model:Model} point at it through "{relation:Q}"'))
def learns_related(world, count, model, relation):
    related = {entry["relation"]: entry for entry in _result(world)["related"]}
    assert relation in related, related
    assert (related[relation]["type"], related[relation]["count"]) == (model.TYPE_ID, count)


@then("the assistant learns about no related records")
def no_related(world):
    assert _result(world)["related"] == []


@then(phrase("the assistant does not learn about {names:List}"))
def does_not_learn_fields(world, names):
    fields = _result(world)["fields"]
    assert not {name.replace(" ", "_") for name in names} & set(fields), sorted(fields)


def _type_names(world) -> set[str]:
    return {entry["name_plural"] for entry in _result(world)}


@then(phrase('the assistant learns about the record types "{names:Q}"'))
def learns_types(world, names):
    assert set(split_list(names)) <= _type_names(world), _type_names(world)


@then(phrase('the assistant does not learn about the record types "{names:Q}"'))
def does_not_learn_types(world, names):
    assert not set(split_list(names)) & _type_names(world), _type_names(world)


@then(phrase("the assistant learns that {name:Actor} may create {model:Model}"))
def may_create(world, name, model):
    assert (_result(world)["type"], _result(world)["can_create"]) == (model.TYPE_ID, True)


@then(phrase("the assistant learns that {name:Actor} may not create {model:Model}"))
def may_not_create(world, name, model):
    assert (_result(world)["type"], _result(world)["can_create"]) == (model.TYPE_ID, False)


@then(phrase('the assistant learns the writable fields "{names:Q}"'))
def learns_writable_fields(world, names):
    assert set(_result(world)["fields"]) == set(split_list(names)), sorted(_result(world)["fields"])


@then(
    phrase('the assistant reads that {name:Actor} changed the {field:Words} of "{label:Q}" from "{old:Q}" to "{new:Q}"')
)
def reads_change(world, name, field, label, old, new):
    entries = _result(world)
    assert isinstance(entries, list), entries
    changes = [
        (entry["by"], entry["field_changes"].get(field.replace(" ", "_")), bool(entry["change_set"]))
        for entry in entries
    ]
    assert (str(world.user(name)), [old, new], True) in changes, entries


@then(phrase('the assistant reads the note "{body:Q}"'))
def reads_note(world, body):
    assert body in [entry["body"] for entry in _rows(_result(world))], _result(world)


@then("the assistant gets the groups:")
def gets_groups(world, datatable):
    header, *rows = datatable
    groups = [[readable(world, str(group.get(key))) for key in header] for group in _result(world)["groups"]]
    assert sorted(groups) == sorted(rows), groups


@then(phrase('the assistant reads only the columns "{names:Q}"'))
def reads_columns(world, names):
    result = _result(world)
    columns = set(result["results"][0]) if "results" in result else set(result) - {"actions"}
    assert columns == set(split_list(names)), columns


# ---------------------------------------------------------------------------
# What the assistant proposed


def _sent(world) -> list[dict]:
    state = assistant(world)
    return [event for event in [*state.sent, *state.events] if event["type"] == "tool_call_pending"]


def _proposal(world, kind: str, label: str | None):
    """The pending proposal of `kind` on `label`, filed by the person using the assistant and shown as a card."""
    candidates = proposals().filter(kind=kind, status="pending", created_by=person(world))
    if label is not None:
        record = world.record(label)
        candidates = [proposal for proposal in candidates if proposal.target == record]
    assert candidates, list(proposals().values("kind", "status", "payload", "target_object_id"))
    proposal = list(candidates)[-1]
    cards = {card["id"]: card for card in _sent(world)}
    assert proposal.pk in cards, (proposal.pk, list(cards))
    if label is not None:
        assert cards[proposal.pk]["target_label"] == label
    return proposal


def _proposes(world, fields: dict, name: str, value: str) -> bool:
    return name in fields and readable(world, str(fields[name])) == value


@then(phrase('the assistant has proposed changing the {field:Words} of "{label:Q}" to "{value:Q}"'))
def proposed_change(world, field, label, value):
    record = world.record(label)
    name = field.replace(" ", "_")
    matching = [
        proposal
        for proposal in proposals().filter(kind="patch", status="pending", created_by=person(world))
        if proposal.target == record and _proposes(world, proposal.payload["fields"], name, value)
    ]
    assert matching, list(proposals().values("kind", "payload", "target_object_id"))
    cards = {card["id"]: card for card in _sent(world)}
    assert matching[-1].pk in cards and cards[matching[-1].pk]["target_label"] == label, cards


@then(phrase('the assistant has proposed running "{action:Q}" on "{label:Q}"'))
def proposed_action(world, action, label):
    assert _proposal(world, "action", label).payload == {"action": action}


@then(phrase('the assistant has proposed adding the note "{body:Q}" to "{label:Q}"'))
def proposed_note(world, body, label):
    assert _proposal(world, "note", label).payload == {"body": body}


@then(phrase("the assistant has proposed creating a {model:Model} with:"))
def proposed_create(world, model, datatable):
    proposal = _proposal(world, "create", None)
    assert proposal.payload["type"] == model.TYPE_ID
    fields = {name: readable(world, str(value)) for name, value in proposal.payload["fields"].items()}
    assert fields == {name.replace(" ", "_"): value for name, value in datatable}, fields


@then(phrase('the assistant has proposed undoing that change on "{label:Q}"'))
def proposed_revert(world, label):
    assert _proposal(world, "revert", label).payload == {"change_set": str(UUID(world.change_set))}


@then(phrase('the proposal is labelled "{text:Q}"'))
def proposal_labelled(world, text):
    assert proposals().last().label == text
    assert _sent(world)[-1]["label"] == text


@then(phrase("the assistant has made {count:d} proposals"))
def made_proposals(world, count):
    assert proposals().count() == count == len(_sent(world)), (proposals().count(), _sent(world))


@then("the assistant has proposed nothing")
def proposed_nothing(world):
    assert not proposals().exists(), list(proposals().values("kind", "payload"))
    assert _sent(world) == []


@then(phrase('the assistant would have proposed changing the {field:Words} of "{label:Q}" to "{value:Q}"'))
def would_have_proposed(world, field, label, value):
    assert not proposals().exists()
    [card] = _sent(world)
    assert (card["id"], card["dry_run"], card["target_label"]) == (None, True, label), card
    assert readable(world, str(card["payload"]["fields"][field.replace(" ", "_")])) == value


# ---------------------------------------------------------------------------
# Forms in the browser


def _sent_of(world, kind: str) -> list[dict]:
    return [event for event in [*assistant(world).sent, *assistant(world).events] if event["type"] == kind]


def _form_values(fields: dict) -> list[list[str]]:
    return [[name, value["label"] if isinstance(value, dict) else str(value)] for name, value in fields.items()]


@then("the form on the screen is filled in with:")
def form_filled(world, datatable):
    [fill] = _sent_of(world, "form_fill")
    form = assistant(world).screen["form"]
    assert fill["form"] == {"type_id": form["type_id"], "mode": form["mode"], "record_id": form.get("record_id", "")}
    assert _form_values(fill["fields"]) == datatable, fill


@then(phrase("a new {model:Model} form opens filled in with:"))
def form_opens_filled(world, model, datatable):
    [opened] = _sent_of(world, "form_open")
    assert opened["type_id"] == model.TYPE_ID
    assert _form_values(opened["fields"]) == datatable, opened


@then(phrase("an empty {model:Model} form opens"))
def empty_form_opens(world, model):
    [opened] = _sent_of(world, "form_open")
    assert (opened["type_id"], opened["fields"]) == (model.TYPE_ID, {}), opened


@then("no form is touched")
def no_form_touched(world):
    assert not _sent_of(world, "form_fill") and not _sent_of(world, "form_open")
