from unittest import mock

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.test import TestCase
from rest_framework.test import APIClient

from crudkit.models import FeedItem
from tests.testapp.models import Call, Customer


class AddToFeedTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="alice")
        cls.customer = Customer.objects.create(name="Acme", created_by=cls.user, updated_by=cls.user)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _log_call(self):
        url = f"/api/v1/CAL/?from_object={self.customer.pk}"
        response = self.client.post(url, {"subject": "Hi"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.data["id"]

    def test_links_the_new_entry_once(self):
        self._log_call()
        self.assertEqual(
            FeedItem.objects.filter(related_content_type=ContentType.objects.get_for_model(Call)).count(), 1
        )

    def test_keeps_the_row_a_project_already_made(self):
        """Projects that put their entries on the feed themselves (in a post_save)
        don't get a second row."""

        def link_it(sender, instance, created, **kwargs):
            if created:
                FeedItem.objects.create(
                    parent_object=self.customer,
                    related_object=instance,
                    body="made by the project",
                    created_by=self.user,
                    updated_by=self.user,
                )

        post_save.connect(link_it, sender=Call)
        self.addCleanup(post_save.disconnect, link_it, sender=Call)
        self._log_call()
        rows = FeedItem.objects.filter(related_content_type=ContentType.objects.get_for_model(Call))
        self.assertEqual([row.body for row in rows], ["made by the project"])


class GetContentTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="alice")
        cls.audit = {"created_by": cls.user, "updated_by": cls.user}
        cls.customer = Customer.objects.create(name="Acme", **cls.audit)

    def test_uses_the_body_of_a_note(self):
        note = FeedItem.objects.create(parent_object=self.customer, body="<p>Hi</p>", **self.audit)
        self.assertEqual(note.get_content(), {"text": "<p>Hi</p>", "html": "<p>Hi</p>"})

    def test_asks_the_related_record_when_it_can_tell(self):
        call = Call.objects.create(subject="Renewal", **self.audit)
        entry = FeedItem.objects.create(parent_object=self.customer, related_object=call, **self.audit)
        content = {"text": "Renewal", "html": "<b>Renewal</b>"}
        with mock.patch.object(Call, "get_content", create=True, return_value=content):
            self.assertEqual(entry.get_content(), content)
