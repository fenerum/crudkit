from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase

from crudkit.models import CrudKitIDField, CrudKitPositiveIntegerField, parse_ck_id
from tests.testapp.models import Comment, Ticket, UrgentComment


class TestModel:
    """Mock model class for testing CrudKitIDField"""

    TYPE_ID = "TST"


class CrudKitIDFieldTests(TestCase):
    def setUp(self):
        self.field = CrudKitIDField()
        self.field.model = TestModel

    def test_get_prep_value_with_integer(self):
        """Test that an integer value is returned as is"""
        value = 42
        self.assertEqual(self.field.get_prep_value(value), value)

    def test_get_prep_value_with_none(self):
        """Test that None is returned as None"""
        self.assertIsNone(self.field.get_prep_value(None))

    def test_get_prep_value_with_empty_string(self):
        """Test that an empty string is converted to None"""
        self.assertIsNone(self.field.get_prep_value(""))

    def test_get_prep_value_with_valid_ck_id(self):
        """Test that a valid CK ID is properly parsed"""
        value = "TST123"
        _, expected_pk = parse_ck_id(value)
        self.assertEqual(self.field.get_prep_value(value), expected_pk)

    def test_get_db_prep_value_with_integer(self):
        """Test get_db_prep_value with an integer"""
        value = 42
        result = self.field.get_db_prep_value(value, connection)
        self.assertEqual(result, value)

    def test_get_db_prep_value_with_none(self):
        """Test get_db_prep_value with None"""
        result = self.field.get_db_prep_value(None, connection)
        self.assertIsNone(result)

    def test_get_db_prep_value_with_empty_string(self):
        """Test get_db_prep_value with empty string"""
        result = self.field.get_db_prep_value("", connection)
        self.assertIsNone(result)

    def test_get_db_prep_value_with_valid_ck_id(self):
        """Test get_db_prep_value with a valid CK ID"""
        value = "TST123"
        _, expected_pk = parse_ck_id(value)
        result = self.field.get_db_prep_value(value, connection)
        self.assertEqual(result, expected_pk)


class CrudKitPositiveIntegerFieldTests(TestCase):
    def setUp(self):
        self.field = CrudKitPositiveIntegerField()
        self.field.model = TestModel

    def test_get_prep_value_with_integer(self):
        """Test that an integer value is returned as is"""
        value = 42
        self.assertEqual(self.field.get_prep_value(value), value)

    def test_get_prep_value_with_none(self):
        """Test that None is returned as None"""
        self.assertIsNone(self.field.get_prep_value(None))

    def test_get_prep_value_with_empty_string(self):
        """Test that an empty string is converted to None"""
        self.assertIsNone(self.field.get_prep_value(""))

    def test_get_prep_value_with_valid_ck_id(self):
        """Test that a valid CK ID is properly parsed"""
        value = "TST123"
        _, expected_pk = parse_ck_id(value)
        self.assertEqual(self.field.get_prep_value(value), expected_pk)

    def test_get_db_prep_value_with_integer(self):
        """Test get_db_prep_value with an integer"""
        value = 42
        result = self.field.get_db_prep_value(value, connection)
        self.assertEqual(result, value)

    def test_get_db_prep_value_with_none(self):
        """Test get_db_prep_value with None"""
        result = self.field.get_db_prep_value(None, connection)
        self.assertIsNone(result)

    def test_get_db_prep_value_with_empty_string(self):
        """Test get_db_prep_value with empty string"""
        result = self.field.get_db_prep_value("", connection)
        self.assertIsNone(result)

    def test_get_db_prep_value_with_valid_ck_id(self):
        """Test get_db_prep_value with a valid CK ID"""
        value = "TST123"
        _, expected_pk = parse_ck_id(value)
        result = self.field.get_db_prep_value(value, connection)
        self.assertEqual(result, expected_pk)

    def test_get_db_prep_value_with_model_instance(self):
        """A FK default callable may return a model instance (e.g.
        CaseReason.get_default-style defaults); schema-time evaluation then
        passes the instance itself down to the target field."""

        class _FakeInstance:
            pk = "TST123"

        result = self.field.get_db_prep_value(_FakeInstance(), connection)
        self.assertEqual(result, 123)

    def test_get_prep_value_with_model_instance_int_pk(self):
        class _FakeInstance:
            pk = 42

        self.assertEqual(self.field.get_prep_value(_FakeInstance()), 42)


class SubclassCkIdLookupTests(TestCase):
    """A multi-table-inheritance child shares the parent's pk column, so both the
    parent's and the child's TYPE_ID address the same row."""

    def setUp(self):
        self.user = User.objects.create_user(username="fielduser", password="pw")
        self.ticket = Ticket.objects.create(subject="Broken invoice", created_by=self.user, updated_by=self.user)
        self.comment = UrgentComment.objects.create(
            ticket=self.ticket,
            body="Test content",
            created_by=self.user,
            updated_by=self.user,
        )
        self.pk = int(str(self.comment.pk).removeprefix("COM").removeprefix("URG"))

    def test_lookup_by_child_type_id(self):
        self.assertEqual(UrgentComment.objects.get(pk=f"URG{self.pk}"), self.comment)

    def test_lookup_by_parent_type_id(self):
        self.assertEqual(UrgentComment.objects.get(pk=f"COM{self.pk}"), self.comment)

    def test_parent_queryset_accepts_child_type_id(self):
        self.assertEqual(Comment.objects.get(pk=f"URG{self.pk}").pk, self.comment.pk)

    def test_unrelated_type_id_still_rejected(self):
        with self.assertRaises(ValueError):
            UrgentComment.objects.get(pk=f"TIC{self.pk}")
