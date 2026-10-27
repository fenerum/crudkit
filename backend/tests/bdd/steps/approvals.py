"""Proposals: changes the assistant, an MCP client or an agent filed for a
person to Confirm or Skip.

Phrases:
- `Given Alice proposed changing the status of "Acme" to "churned"`
- `Given Alice's MCP client "Research Bot" proposed changing the name of "Acme" to "Acme Inc"`
- `Given Alice proposed creating a customer "Globex"`
- `Given Alice proposed running "Mark churned" on "Acme"`
- `Given Alice proposed adding the note "Called them" to "Acme"`
- `Given Alice proposed undoing that change` (the latest change set)
- `Given a background agent "Triage" that works on customers`
- `Given Alice proposed ...` also reads `When Alice proposes changing the status of "Acme" to "churned"`
- `Given "Acme" was permanently removed` / `When "Acme" is permanently removed`
- `When Alice confirms the proposal` / `When Alice skips the proposal` (also as Given, past tense)
- `When Alice confirms the proposal in two tabs at once`
- `When Alice lists the proposals`
- `Then the proposal is confirmed by Alice` / `skipped by Alice`, `Then the proposal is still pending`
- `Then the proposal failed with "<part of the error>"`
- `Then the proposal needs a person's approval` / `does not need a person's approval`
- `Then Alice sees only her own proposals` / `Then Alice sees every proposal`

"The proposal" is the latest one filed; it is also the record "Alice's proposal". After a confirm, "that change" (for
the undo steps) is the change the proposal applied.
"""

from django.contrib.contenttypes.models import ContentType
from pytest_bdd import given, then, when
from rest_framework.test import APIRequestFactory

from crudkit.models import ChangeLog, FeedItem
from crudkit_api.services import action_for_label
from crudkit_assistant.models import Agent, AssistantProposal
from crudkit_assistant.proposals import create_proposal
from tests.bdd.world import label_field, phrase


def _propose(world, name, instance, kind, payload, model=None, source="assistant", client=""):
    model = model or type(instance)
    proposal = create_proposal(
        world.user(name), model, instance, kind, f"{kind} proposal", payload, source=source, client=client
    )
    world.proposal = world.add(f"{name}'s proposal", proposal)
    world.proposals = [*getattr(world, "proposals", []), proposal]
    return proposal


def _proposal(world):
    return AssistantProposal.objects.get(pk=world.proposal.pk)


def _patch_payload(world, label, field, value):
    instance = world.records[label]
    name = field.replace(" ", "_")
    return instance, {"fields": {name: world.api_value(type(instance), name, value)}}


def _changes_to(instance):
    return ChangeLog.objects.filter(
        related_content_type=ContentType.objects.get_for_model(instance), related_object_id=instance.pk
    )


# Filing proposals (as setup, the way the assistant, MCP clients and agents do)


@given(phrase('{name:Actor} proposed changing the {field:Words} of "{label:Q}" to "{value:Q}"'))
@when(phrase('{name:Actor} proposes changing the {field:Words} of "{label:Q}" to "{value:Q}"'))
def proposed_patch(world, name, field, label, value):
    instance, payload = _patch_payload(world, label, field, value)
    _propose(world, name, instance, "patch", payload)


@given(
    phrase('{name:Actor}\'s MCP client "{client:Q}" proposed changing the {field:Words} of "{label:Q}" to "{value:Q}"')
)
def mcp_proposed_patch(world, name, client, field, label, value):
    instance, payload = _patch_payload(world, label, field, value)
    _propose(world, name, instance, "patch", payload, source="mcp", client=client)


@given(phrase('{name:Actor} proposed creating a {model:Model} "{label:Q}"'))
def proposed_create(world, name, model, label):
    _propose(world, name, None, "create", {"type": model.TYPE_ID, "fields": {label_field(model): label}}, model=model)


@given(phrase('{name:Actor} proposed running "{action:Q}" on "{label:Q}"'))
def proposed_action(world, name, action, label):
    instance = world.records[label]
    method = action_for_label(type(instance), action)
    assert method, f'"{label}" has no action called "{action}"'
    _propose(world, name, instance, "action", {"action": method})


@given(phrase('{name:Actor} proposed adding the note "{body:Q}" to "{label:Q}"'))
def proposed_note(world, name, body, label):
    _propose(world, name, world.records[label], "note", {"body": body})


@given(phrase("{name:Actor} proposed undoing that change"))
def proposed_revert(world, name):
    entry = ChangeLog.objects.filter(change_set=world.change_set).first()
    _propose(world, name, entry.related_object, "revert", {"change_set": world.change_set})


@given(phrase('a background agent "{label:Q}" that works on customers'))
def an_agent(world, label):
    world.create(Agent, label, {"instructions": "Tidy up.", "model_type": "CUS"})


@given(phrase('"{label:Q}" was permanently removed'))
@when(phrase('"{label:Q}" is permanently removed'))
def permanently_removed(world, label):
    world.record(label).delete()


# Deciding


def _decide(world, name, decision):
    url = f"/api/v1/{AssistantProposal.TYPE_ID}/{world.proposal.pk}/action/"
    world.remember(name, world.api(name).post(url, {"action": decision}, format="json"))
    applied = (_proposal(world).outcome or {}).get("change_set")
    if applied:
        world.change_set = world.change_sets[name] = applied


@given(phrase("{name:Actor} confirmed the proposal"))
@when(phrase("{name:Actor} confirms the proposal"))
def confirm(world, name):
    _decide(world, name, "confirm")


@given(phrase("{name:Actor} skipped the proposal"))
@when(phrase("{name:Actor} skips the proposal"))
def skip(world, name):
    _decide(world, name, "skip")


@when(phrase("{name:Actor} confirms the proposal in two tabs at once"))
def confirm_twice_at_once(world, name):
    """Both tabs loaded the proposal while it was pending; the second Confirm arrives after the first applied it."""
    second_tab = _proposal(world)
    _decide(world, name, "confirm")
    request = APIRequestFactory().post("/")
    request.user = world.user(name)
    world.response = second_tab.confirm(request)


@when(phrase("{name:Actor} lists the proposals"))
def list_proposals(world, name):
    world.remember(name, world.api(name).get(f"/api/v1/{AssistantProposal.TYPE_ID}/"))


# Outcomes


@then(phrase("the proposal is {status:Words} by {name:Actor}"))
def decided_by(world, status, name):
    proposal = _proposal(world)
    assert proposal.status == status, (proposal.status, proposal.outcome)
    assert proposal.confirmed_by == world.user(name)
    assert proposal.confirmed_at is not None


@then(phrase("the proposal is still pending"))
def still_pending(world):
    proposal = _proposal(world)
    assert proposal.status == AssistantProposal.Status.PENDING, proposal.status
    assert proposal.confirmed_by is None


@then(phrase('the proposal failed with "{message:Q}"'))
def failed_with(world, message):
    proposal = _proposal(world)
    assert proposal.status == AssistantProposal.Status.FAILED, proposal.status
    assert message in proposal.outcome["error"], proposal.outcome


@then(phrase('the proposal created the {model:Model} "{label:Q}"'))
def created_the_record(world, model, label):
    created = _proposal(world).target
    assert isinstance(created, model), created
    assert getattr(created, label_field(model)) == label
    world.add(label, created)


@then(phrase('no {model:Model} "{label:Q}" exists'))
def no_such_record(world, model, label):
    assert not model.objects.filter(**{label_field(model): label}).exists()


@then(phrase('the note "{body:Q}" is added to "{label:Q}"'))
def note_added(world, body, label):
    instance = world.records[label]
    notes = FeedItem.objects.filter(
        parent_content_type=ContentType.objects.get_for_model(instance), parent_object_id=instance.pk
    )
    assert list(notes.values_list("body", flat=True)) == [body]


@then(phrase('the change to "{label:Q}" is recorded as made by {name:Actor} through the MCP client "{client:Q}"'))
def recorded_through_client(world, label, name, client):
    entry = _changes_to(world.records[label]).get()
    assert (entry.source, entry.client, entry.created_by) == ("mcp", client, world.user(name))
    assert str(entry.change_set) == _proposal(world).outcome["change_set"]


@then(phrase('"{label:Q}" was changed only once'))
def changed_once(world, label):
    assert _changes_to(world.records[label]).count() == 1


@then(phrase("the proposal needs a person's approval"))
def needs_approval(world):
    assert _proposal(world).needs_approval()


@then(phrase("the proposal does not need a person's approval"))
def does_not_need_approval(world):
    assert not _proposal(world).needs_approval()


def _listed(world):
    assert world.response.status_code == 200, world.response.content
    return {row["id"] for row in world.response.json()["results"]}


@then(phrase("{name:Actor} sees only {whose:Their} own proposals"))
def sees_own_proposals(world, name, whose):
    user = world.user(name)
    own = {p.id for p in world.proposals if p.created_by_id == user.pk}
    assert own, f"{name} has filed no proposals in this scenario"
    assert _listed(world) == own


@then(phrase("{name:Actor} sees every proposal"))
def sees_every_proposal(world, name):
    assert _listed(world) == {p.id for p in world.proposals}
