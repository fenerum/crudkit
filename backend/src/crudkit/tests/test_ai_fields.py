from unittest import TestCase

from crudkit.fields import AIBooleanField, AICategoryField, AIForeignKeyField, AISummaryField, AITagsField


class AISummaryFieldTests(TestCase):
    def test_defaults(self):
        field = AISummaryField(prompt="test desc")
        self.assertTrue(field.blank)
        self.assertTrue(field.null)
        self.assertFalse(field.editable)
        self.assertEqual(field.ai_prompt, "test desc")

    def test_ai_field_marker(self):
        self.assertTrue(AISummaryField.ai_field)

    def test_deconstruct_round_trip(self):
        field = AISummaryField(prompt="summarize it")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "crudkit.fields.AISummaryField")
        self.assertEqual(kwargs["prompt"], "summarize it")
        reconstructed = AISummaryField(*args, **kwargs)
        self.assertEqual(reconstructed.ai_prompt, "summarize it")

    def test_deconstruct_omits_empty_description(self):
        field = AISummaryField()
        _, _, _, kwargs = field.deconstruct()
        self.assertNotIn("prompt", kwargs)


class AICategoryFieldTests(TestCase):
    def test_defaults(self):
        field = AICategoryField(prompt="cat")
        self.assertEqual(field.max_length, 64)
        self.assertTrue(field.blank)
        self.assertTrue(field.null)
        self.assertFalse(field.editable)

    def test_custom_max_length(self):
        field = AICategoryField(max_length=20)
        self.assertEqual(field.max_length, 20)

    def test_choices_preserved(self):
        choices = [("a", "A"), ("b", "B")]
        field = AICategoryField(choices=choices)
        self.assertEqual(field.choices, choices)

    def test_ai_field_marker(self):
        self.assertTrue(AICategoryField.ai_field)

    def test_deconstruct(self):
        field = AICategoryField(prompt="categorize", max_length=32)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "crudkit.fields.AICategoryField")
        self.assertEqual(kwargs["prompt"], "categorize")
        self.assertEqual(kwargs["max_length"], 32)


class AIBooleanFieldTests(TestCase):
    def test_defaults(self):
        field = AIBooleanField(prompt="is spam?")
        self.assertTrue(field.null)
        self.assertFalse(field.editable)
        self.assertEqual(field.ai_prompt, "is spam?")

    def test_ai_field_marker(self):
        self.assertTrue(AIBooleanField.ai_field)

    def test_deconstruct(self):
        field = AIBooleanField(prompt="is urgent")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "crudkit.fields.AIBooleanField")
        self.assertEqual(kwargs["prompt"], "is urgent")


class AITagsFieldTests(TestCase):
    def test_defaults(self):
        field = AITagsField(prompt="tags")
        self.assertEqual(field.max_tags, 10)
        self.assertTrue(field.blank)
        self.assertFalse(field.editable)
        self.assertEqual(field.default, list)

    def test_custom_max_tags(self):
        field = AITagsField(max_tags=5)
        self.assertEqual(field.max_tags, 5)

    def test_ai_field_marker(self):
        self.assertTrue(AITagsField.ai_field)

    def test_deconstruct_default_max_tags_omitted(self):
        field = AITagsField(prompt="tags")
        _, _, _, kwargs = field.deconstruct()
        self.assertNotIn("max_tags", kwargs)

    def test_deconstruct_non_default_max_tags_included(self):
        field = AITagsField(prompt="tags", max_tags=5)
        _, _, _, kwargs = field.deconstruct()
        self.assertEqual(kwargs["max_tags"], 5)

    def test_deconstruct_round_trip(self):
        field = AITagsField(prompt="keywords", max_tags=3)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "crudkit.fields.AITagsField")
        reconstructed = AITagsField(*args, **kwargs)
        self.assertEqual(reconstructed.ai_prompt, "keywords")
        self.assertEqual(reconstructed.max_tags, 3)


class AIForeignKeyFieldTests(TestCase):
    def test_defaults(self):
        field = AIForeignKeyField("crm.Topic", prompt="pick topic")
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertFalse(field.editable)
        self.assertEqual(field.ai_prompt, "pick topic")

    def test_ai_field_marker(self):
        self.assertTrue(AIForeignKeyField.ai_field)

    def test_deconstruct(self):
        field = AIForeignKeyField("crm.Topic", prompt="pick topic")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "crudkit.fields.AIForeignKeyField")
        self.assertEqual(kwargs["prompt"], "pick topic")
