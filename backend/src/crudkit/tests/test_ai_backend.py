from contextlib import asynccontextmanager
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from crudkit.ai_backend import _build_prompt, _build_pydantic_model, process


def _mock_model_context(model_obj):
    entered = MagicMock()

    @asynccontextmanager
    async def fake_model_context():
        entered()
        yield model_obj

    return fake_model_context, entered


class BuildPydanticModelTests(TestCase):
    def test_string_field(self):
        model = _build_pydantic_model({"summary": {"type": "string"}})
        instance = model(summary="hello")
        self.assertEqual(instance.summary, "hello")

    def test_boolean_field(self):
        model = _build_pydantic_model({"is_urgent": {"type": "boolean"}})
        instance = model(is_urgent=True)
        self.assertTrue(instance.is_urgent)

    def test_array_field(self):
        model = _build_pydantic_model({"tags": {"type": "array"}})
        instance = model(tags=["a", "b"])
        self.assertEqual(instance.tags, ["a", "b"])

    def test_optional_defaults_to_none(self):
        model = _build_pydantic_model(
            {
                "summary": {"type": "string"},
                "flag": {"type": "boolean"},
                "tags": {"type": "array"},
            }
        )
        instance = model()
        self.assertIsNone(instance.summary)
        self.assertIsNone(instance.flag)
        self.assertIsNone(instance.tags)

    def test_unknown_type_ignored(self):
        model = _build_pydantic_model({"x": {"type": "integer"}})
        instance = model()
        self.assertFalse(hasattr(instance, "x"))


class BuildPromptTests(TestCase):
    def test_contains_context(self):
        prompt = _build_prompt("my context", {"f": {"type": "string"}})
        self.assertIn("my context", prompt)

    def test_contains_json_schema(self):
        specs = {"summary": {"type": "string", "description": "a summary"}}
        prompt = _build_prompt("ctx", specs)
        self.assertIn('"type": "string"', prompt)
        self.assertIn('"description": "a summary"', prompt)


class ProcessTests(TestCase):
    def test_successful_call(self):
        fake_output = MagicMock()
        fake_output.model_dump.return_value = {"summary": "hello"}
        fake_result = MagicMock()
        fake_result.output = fake_output

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=fake_result)

        model_obj = MagicMock(name="MistralModel")
        fake_model_context, entered = _mock_model_context(model_obj)

        with (
            patch("crudkit.ai_backend.Agent", return_value=mock_agent) as mock_agent_cls,
            patch("crudkit.llm.model_context", fake_model_context),
        ):
            result = process("some context", {"summary": {"type": "string"}})

        self.assertEqual(result, {"summary": "hello"})
        mock_agent.run.assert_awaited_once()
        entered.assert_called_once()
        # Agent must be constructed with the model from model_context()
        self.assertIs(mock_agent_cls.call_args.args[0], model_obj)

    def test_llm_exception_returns_empty_dict(self):
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM down"))

        fake_model_context, _entered = _mock_model_context(MagicMock())

        with (
            patch("crudkit.ai_backend.Agent", return_value=mock_agent),
            patch("crudkit.llm.model_context", fake_model_context),
            self.assertLogs("crudkit.ai_backend", level="ERROR"),
        ):
            result = process("some context", {"summary": {"type": "string"}})
        self.assertEqual(result, {})

    def test_unconfigured_skips(self):
        with (
            patch("crudkit.llm.is_configured", return_value=False),
            self.assertLogs("crudkit.ai_backend", level="INFO"),
        ):
            result = process("some context", {"summary": {"type": "string"}})
        self.assertEqual(result, {})
