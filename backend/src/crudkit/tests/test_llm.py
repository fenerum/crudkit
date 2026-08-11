import asyncio
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from crudkit import llm


async def _enter(cm):
    async with cm as model:
        return model


class ModelContextTests(SimpleTestCase):
    @override_settings(CRUDKIT_AI_MODEL_FACTORY=None, CRUDKIT_AI_MODEL=None)
    def test_unconfigured(self):
        self.assertFalse(llm.is_configured())
        with self.assertRaises(ImproperlyConfigured):
            asyncio.run(_enter(llm.model_context()))

    @override_settings(CRUDKIT_AI_MODEL_FACTORY="tests.testapp.ai.create_model", CRUDKIT_AI_MODEL=None)
    def test_factory_takes_precedence(self):
        self.assertTrue(llm.is_configured())
        with patch("tests.testapp.ai.create_model") as factory:
            factory.return_value.__aenter__.return_value = "the-model"
            factory.return_value.__aexit__.return_value = False
            self.assertEqual(asyncio.run(_enter(llm.model_context())), "the-model")

    @override_settings(CRUDKIT_AI_MODEL_FACTORY=None, CRUDKIT_AI_MODEL="mistral:mistral-large-latest")
    def test_model_string(self):
        self.assertTrue(llm.is_configured())
        sentinel = MagicMock(name="inferred")
        with patch("crudkit.llm.infer_model", return_value=sentinel) as infer:
            self.assertIs(asyncio.run(_enter(llm.model_context())), sentinel)
        infer.assert_called_once_with("mistral:mistral-large-latest")
