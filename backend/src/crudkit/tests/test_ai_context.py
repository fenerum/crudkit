from contextlib import asynccontextmanager
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from crudkit.ai_backend import process
from crudkit.llm import ai_context
from crudkit.models import AIContext


def make_doc(user, name, body, **kwargs):
    return AIContext.objects.create(name=name, body=body, created_by=user, updated_by=user, **kwargs)


class AIContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="agent", password="pw")

    def test_empty(self):
        self.assertEqual(ai_context(), "")

    def test_ordered_by_order_then_name(self):
        make_doc(self.user, "Tone of voice", "Plain and friendly.", order=2)
        make_doc(self.user, "Why customers buy", "Speed.", order=1)
        make_doc(self.user, "Ideal customer", "Small agencies.", order=1)
        self.assertEqual(
            ai_context(),
            "## Ideal customer\nSmall agencies.\n\n## Why customers buy\nSpeed.\n\n## Tone of voice\nPlain and friendly.",
        )

    def test_type_scoping(self):
        make_doc(self.user, "Global", "Everywhere.")
        make_doc(self.user, "Tickets", "Answer within a day.", model_types=["TIC"])
        make_doc(self.user, "Customers", "Churn playbook.", model_types=["CUS", "OPP"])

        self.assertEqual(ai_context(), "## Global\nEverywhere.")
        self.assertEqual(ai_context("CUS"), "## Customers\nChurn playbook.\n\n## Global\nEverywhere.")
        self.assertEqual(ai_context("CUS", include_global=False), "## Customers\nChurn playbook.")
        self.assertEqual(ai_context("XYZ", include_global=False), "")

    def test_inactive_and_deleted_are_left_out(self):
        make_doc(self.user, "Draft", "Not yet.", active=False)
        make_doc(self.user, "Old", "Gone.", deleted=True)
        self.assertEqual(ai_context(), "")

    def test_with_ids(self):
        doc = make_doc(self.user, "Ideal customer", "Small agencies.")
        self.assertEqual(ai_context(with_ids=True), f"## Ideal customer ({doc.pk})\nSmall agencies.")


@override_settings(CRUDKIT_AI_MODEL_FACTORY="tests.testapp.ai.create_model", CRUDKIT_AI_MODEL=None)
class AIFieldPromptTests(TestCase):
    def test_prompt_contains_type_context(self):
        user = User.objects.create_user(username="agent", password="pw")
        make_doc(user, "Ideal customer", "Small agencies.")
        make_doc(user, "Ticket triage", "Billing issues are urgent.", model_types=["TIC"])
        make_doc(user, "Customers", "Not for tickets.", model_types=["CUS"])
        prompts = []

        def model_fn(messages, info):
            prompts.append(messages[-1].parts[-1].content)
            return ModelResponse(parts=[TextPart('{"summary": "ok"}')])

        @asynccontextmanager
        async def create_model():
            yield FunctionModel(model_fn)

        with patch("tests.testapp.ai.create_model", create_model):
            result = process("Subject: refund", {"summary": {"type": "string"}}, "TIC")

        self.assertEqual(result, {"summary": "ok"})
        self.assertIn(
            "## Company context\n## Ideal customer\nSmall agencies.\n\n## Ticket triage\nBilling issues are urgent.\n\n"
            "## Context\nSubject: refund",
            prompts[0],
        )
        self.assertNotIn("Not for tickets.", prompts[0])
