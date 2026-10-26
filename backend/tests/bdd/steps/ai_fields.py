"""AI fields (filled in by an LLM after a save), the AI context documents
every LLM feature reads, and the backfill_ai_fields command.

The AI is a fake: it records every prompt in `world.ai_prompts` and answers
with `world.ai_answer`. Tickets are the record type with AI fields (summary,
topic, is urgent, tags); their comments refresh them.

Phrases:
- `Given the AI answers:` + `| field | value |` (tags as a list, topic by label, is urgent yes/no)
- `Given the AI answers the topic with the text "billing" instead of picking one`
- `Given the AI sorts tickets into the categories "billing" and "technical"`, `Given the AI picks the category "x"`
- `Given the AI service is unavailable`, `Given no AI model is configured`
- `Given the AI context documents:` + table (single documents: `an AI context document ... saying ...` in steps/assistant.py)
- `Given the AI context document "Draft" is switched off` / `is deleted`
- `Given the AI context may be at most 40 characters long`
- `When the AI fields of "Refund" are filled in` (the background job runs)
- `When Alice raises a ticket "Refund"`, `When Alice comments "..." on "Refund"`
- `When Alice adds an AI context document "Pricing" for tickets and customers` (and the refusals)
- `When an operator backfills AI fields with "--model testapp.Ticket --sync"`
- `Given the background worker only collects AI jobs` / `cannot be reached`
"""

import json
import shlex
from contextlib import asynccontextmanager
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pytest_bdd import given, then, when

from crudkit.fields import AICategoryField
from crudkit.models import AIContext
from crudkit.tasks import process_ai_fields
from tests.bdd.world import model_named, phrase, split_list
from tests.testapp.models import Comment, Ticket

COMPANY_CONTEXT = "## Company context\n"
RECORD_CONTEXT = "\n\n## Context\n"
TRUNCATED = "\n\n[AI context truncated]"


# The fake AI


def _ai_prompts(world) -> list[str]:
    if not hasattr(world, "ai_prompts"):
        world.ai_prompts = []
    return world.ai_prompts


def _use_ai(world, monkeypatch, respond):
    """Make the configured AI model answer with `respond(prompt)`."""

    def model_function(messages, info):
        prompt = messages[-1].parts[-1].content
        _ai_prompts(world).append(prompt)
        return ModelResponse(parts=[TextPart(respond(prompt))])

    @asynccontextmanager
    async def create_model():
        yield FunctionModel(model_function)

    monkeypatch.setattr("tests.testapp.ai.create_model", create_model)
    # The job closes stale connections first, which would end the scenario's transaction.
    monkeypatch.setattr("crudkit.tasks.close_old_connections", lambda: None)


def _answering(world, monkeypatch):
    if not hasattr(world, "ai_answer"):
        world.ai_answer = {}
        _use_ai(world, monkeypatch, lambda prompt: json.dumps(world.ai_answer))
    return world.ai_answer


def _answer_value(world, field, text):
    if field == "tags":
        return split_list(text)
    if field == "is_urgent":
        return {"yes": True, "no": False}[text]
    if field == "topic":
        return str(world.records[text].pk)
    return text


@given(phrase("the AI answers:"))
def ai_answers(world, monkeypatch, datatable):
    """A table of `| field | value |` rows: what the AI fills in for any ticket."""
    answer = _answering(world, monkeypatch)
    for field, text in datatable:
        name = field.replace(" ", "_")
        answer[name] = _answer_value(world, name, text)


@given(phrase('the AI answers the {field:Words} with the text "{text:Q}" instead of picking one'))
def ai_answers_text(world, monkeypatch, field, text):
    _answering(world, monkeypatch)[field.replace(" ", "_")] = text


@given(phrase('the AI sorts tickets into the categories "{first:Q}" and "{second:Q}"'))
def ai_category(world, monkeypatch, first, second):
    """Tickets get one AI category field instead of their usual AI fields, stored in the summary column."""
    field = AICategoryField(prompt="The kind of request.", choices=[(first, first), (second, second)])
    field.set_attributes_from_name("summary")
    monkeypatch.setattr(Ticket, "get_ai_fields", classmethod(lambda cls: [field]))
    world.category_field = field.name


@given(phrase('the AI picks the category "{category:Q}"'))
def ai_picks_category(world, monkeypatch, category):
    _answering(world, monkeypatch)[world.category_field] = category


@given(phrase("the AI service is unavailable"))
def ai_unavailable(world, monkeypatch):
    def fail(prompt):
        raise ConnectionError("The AI service is down")

    _use_ai(world, monkeypatch, fail)


@given(phrase("no AI model is configured"))
def ai_not_configured(world, monkeypatch, settings):
    _answering(world, monkeypatch)
    settings.CRUDKIT_AI_MODEL_FACTORY = None
    settings.CRUDKIT_AI_MODEL = None


# AI context documents


@given(phrase("the AI context documents:"))
def context_documents(world, datatable):
    """Columns: name, body, and optionally `for` (record types, e.g. "tickets and customers") and `order`."""
    header, *rows = datatable
    for row in rows:
        values = dict(zip(header, row, strict=True))
        types = [model_named(words).TYPE_ID for words in split_list(values.get("for", ""))]
        fields = {"body": values["body"], "order": values.get("order") or "0", "model_types": json.dumps(types)}
        world.create(AIContext, values["name"], fields)


@given(phrase('the AI context document "{name:Q}" is switched off'))
def context_switched_off(world, name):
    AIContext.objects.filter(pk=world.records[name].pk).update(active=False)


@given(phrase('the AI context document "{name:Q}" is deleted'))
def context_deleted(world, name):
    AIContext.objects.filter(pk=world.records[name].pk).update(deleted=True)


@given(phrase("the AI context may be at most {limit:d} characters long"))
def context_limit(settings, limit):
    settings.CRUDKIT_AI_CONTEXT_MAX_CHARS = limit


# Running the AI


@when(phrase('the AI fields of "{label:Q}" are filled in'))
def fill_in(world, label):
    """What the background job does after a save."""
    process_ai_fields(Ticket._meta.app_label, Ticket.__name__, world.records[label].pk)


@when(phrase('{name:Actor} raises a ticket "{subject:Q}"'))
def raise_a_ticket(world, name, subject):
    world.remember(name, world.api(name).post("/api/v1/TIC/", {"subject": subject}, format="json"))
    if world.response.status_code == 201:
        world.add(subject, Ticket.objects.get(subject=subject))


@when(phrase('{name:Actor} comments "{body:Q}" on "{label:Q}"'))
def comment_on(world, name, body, label):
    payload = {"ticket": world.ck_id(label), "body": body}
    world.remember(name, world.api(name).post("/api/v1/COM/", payload, format="json"))
    if world.response.status_code == 201:
        world.add(body, Comment.objects.get(body=body))


# What the AI was asked


def _quoted_list(text: str) -> list[str]:
    """`"Billing" and "Technical"` -> ["Billing", "Technical"]"""
    return split_list(text.replace('"', ""))


def _prompts_about(world, label) -> list[str]:
    return [prompt for prompt in _ai_prompts(world) if f"Subject: {label}\n" in prompt]


def _latest_prompt(world) -> str:
    assert _ai_prompts(world), "The AI was never asked"
    return _ai_prompts(world)[-1]


def _company_context(prompt: str) -> str:
    if COMPANY_CONTEXT not in prompt:
        return ""
    return prompt.split(COMPANY_CONTEXT, 1)[1].split(RECORD_CONTEXT, 1)[0]


def _schema(prompt: str) -> dict:
    return json.loads(prompt.split("## Required JSON schema\n", 1)[1].rsplit("\n\nRespond", 1)[0])


@then(phrase('the AI was asked about "{label:Q}" once'))
def asked_once(world, label):
    assert len(_prompts_about(world, label)) == 1, _ai_prompts(world)


@then(phrase("the AI was not asked"))
def not_asked(world):
    assert _ai_prompts(world) == []


@then(phrase('the AI read the comment "{body:Q}" on "{label:Q}"'))
def read_the_comment(world, body, label):
    prompts = _prompts_about(world, label)
    assert prompts and f"Comment: {body}" in prompts[-1], prompts


@then(phrase('the AI last read "{label:Q}" without the comment "{body:Q}"'))
def read_without_the_comment(world, label, body):
    prompts = _prompts_about(world, label)
    assert prompts and f"Comment: {body}" not in prompts[-1], prompts


@then(phrase("the AI was offered the topics {topics}"))
def offered_topics(world, topics):
    """`"Billing" and "Technical"`, in the order the topics were introduced."""
    offered = [option["name"] for option in _schema(_latest_prompt(world))["topic"]["options"]]
    assert offered == _quoted_list(topics), offered


@then(phrase("the AI read the AI context documents in this order:"))
def read_documents_in_order(world, datatable):
    context = _company_context(_latest_prompt(world))
    headings = [line.removeprefix("## ") for line in context.splitlines() if line.startswith("## ")]
    assert headings == [row[0] for row in datatable], context


@then(phrase("the AI read this AI context:"))
def read_this_context(world, docstring):
    assert _company_context(_latest_prompt(world)) == docstring


@then(phrase("the AI read no AI context"))
def read_no_context(world):
    assert COMPANY_CONTEXT not in _latest_prompt(world)


@then(phrase("the AI read only the first {limit:d} characters of the AI context, marked as truncated"))
def read_truncated_context(world, limit):
    context = _company_context(_latest_prompt(world))
    assert context.endswith(TRUNCATED), context
    assert len(context) == limit + len(TRUNCATED), context


# What the AI filled in


@then(phrase('"{label:Q}" is tagged {tags:List}'))
def is_tagged(world, label, tags):
    assert world.record(label).tags == tags


@then(phrase('"{label:Q}" is urgent according to the AI'))
def is_urgent(world, label):
    assert world.record(label).is_urgent is True


@then(phrase('"{label:Q}" is not urgent according to the AI'))
def is_not_urgent(world, label):
    assert world.record(label).is_urgent is False


@then(phrase('"{label:Q}" is in the AI category "{category:Q}"'))
def in_category(world, label, category):
    assert getattr(world.record(label), world.category_field) == category


@then(phrase('"{label:Q}" has no AI category'))
def no_category(world, label):
    assert getattr(world.record(label), world.category_field) is None


@then(phrase('the AI fields of "{label:Q}" are empty'))
def ai_fields_empty(world, label):
    ticket = world.record(label)
    assert (ticket.summary, ticket.topic, ticket.is_urgent, ticket.tags) == (None, None, None, [])


@given(phrase('the AI fields of "{label:Q}" are already filled in, with the topic "{topic:Q}"'))
def already_filled_in(world, label, topic):
    ticket = world.record(label)
    ticket.summary = "Already summarised."
    ticket.topic = world.record(topic)
    ticket.is_urgent = False
    ticket.tags = ["known"]
    ticket.save(update_fields=["summary", "topic", "is_urgent", "tags"])


# AI context documents through the app


def _add_context_through_app(world, name, document, model_types):
    payload = {"name": document, "body": "Text.", "model_types": model_types}
    world.remember(name, world.api(name).post(f"/api/v1/{AIContext.TYPE_ID}/", payload, format="json"))


@when(phrase('{name:Actor} adds an AI context document "{document:Q}" for {models:List}'))
def add_scoped_context(world, name, document, models):
    _add_context_through_app(world, name, document, [model_named(words).TYPE_ID for words in models])


@when(phrase('{name:Actor} adds an AI context document "{document:Q}" for the unknown record type "{type_id:Q}"'))
def add_context_for_unknown_type(world, name, document, type_id):
    _add_context_through_app(world, name, document, [type_id])


@when(phrase('{name:Actor} adds an AI context document "{document:Q}" with its record types as plain text "{text:Q}"'))
def add_context_with_text_types(world, name, document, text):
    _add_context_through_app(world, name, document, text)


@then(phrase('the AI context document "{document:Q}" applies to {models:List}'))
def context_applies_to(world, document, models):
    stored = AIContext.objects.get(name=document).model_types
    assert stored == [model_named(words).TYPE_ID for words in models], stored


# The backfill command


@when(phrase('an operator backfills AI fields with "{arguments:Q}"'))
def backfill(world, monkeypatch, arguments):
    monkeypatch.setattr("crudkit.tasks.close_old_connections", lambda: None)
    world.command_output = StringIO()
    world.command_error = None
    try:
        call_command("backfill_ai_fields", *shlex.split(arguments), stdout=world.command_output)
    except CommandError as error:
        world.command_error = str(error)


@given(phrase("the background worker only collects AI jobs"))
def worker_collects_jobs(world, monkeypatch):
    world.queued = []
    monkeypatch.setattr(process_ai_fields, "delay", lambda *args: world.queued.append(args))


@given(phrase("the background worker cannot be reached"))
def worker_unreachable(monkeypatch):
    def unreachable(*args):
        raise ConnectionError("No broker")

    monkeypatch.setattr(process_ai_fields, "delay", unreachable)


@then(phrase('the backfill fails with "{message:Q}"'))
def backfill_fails(world, message):
    assert world.command_error and message in world.command_error, world.command_error


@then(phrase('the backfill reports "{message:Q}"'))
def backfill_reports(world, message):
    assert world.command_error is None, world.command_error
    assert message in world.command_output.getvalue(), world.command_output.getvalue()


@then(phrase("the background worker got AI jobs for {labels}"))
def jobs_queued_for(world, labels):
    """`"Refund" and "Outage"`."""
    expected = {world.records[label].pk for label in _quoted_list(labels)}
    assert {pk for _app, _model, pk in world.queued} == expected, world.queued
