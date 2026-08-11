from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from crudkit.models import View, parse_ck_id
from crudkit_api.serializers import get_serializer
from tests.testapp.models import Reminder


class ViewGenericRelationTests(TestCase):
    """The View model as the target of a generic relation: the raw integer is
    stored at model level, while serialization formats it with the VIW prefix."""

    def setUp(self):
        self.user = User.objects.create_user(username="taskuser", password="taskpassword")

    def _create_view(self, name):
        return View.objects.create(
            model="TIC",
            name=name,
            fields=["subject", "customer"],
            created_by=self.user,
            updated_by=self.user,
        )

    def test_related_object_id_prefix(self):
        """Test that the generic FK resolves correctly and related_object_id stores raw integer"""
        view = self._create_view("Test View")

        reminder = Reminder.objects.create(
            note="Reminder related to View",
            related_content_type=ContentType.objects.get_for_model(View),
            related_object_id=view.pk,
            created_by=self.user,
            updated_by=self.user,
        )

        reminder.refresh_from_db()

        # The generic FK should correctly resolve to the view
        self.assertEqual(reminder.target, view)

        # At model level, related_object_id stores the raw integer (for Django's GenericFK to work)
        # The formatted version is only in serialization
        _type_id, view_numeric_id = parse_ck_id(view.pk)

        self.assertEqual(
            reminder.related_object_id,
            view_numeric_id,
            f"related_object_id ({reminder.related_object_id}) should be raw integer ({view_numeric_id})",
        )

    def test_related_object_id_serialization(self):
        """Test that related_object_id is correctly serialized in the API"""
        view = self._create_view("Test View for API")

        reminder = Reminder.objects.create(
            note="Reminder for API test",
            related_content_type=ContentType.objects.get_for_model(View),
            related_object_id=view.pk,
            created_by=self.user,
            updated_by=self.user,
        )

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.user

        ReminderSerializer = get_serializer(Reminder, depth=0)
        serializer = ReminderSerializer(reminder, context={"request": request})
        data = serializer.data

        # The serialized generic object id should match the target's formatted pk
        self.assertEqual(
            data["related_object_id"],
            view.pk,
            f"Serialized related_object_id ({data['related_object_id']}) should match view.pk ({view.pk})",
        )

        # And it should start with "VIW"
        self.assertTrue(
            data["related_object_id"].startswith("VIW"),
            f"Serialized related_object_id should start with 'VIW', got: {data['related_object_id']}",
        )
