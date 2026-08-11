from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from tests.testapp.adapters import InMemoryUserProfileAdapter


class DefaultAdapterUserProfileViewTests(TestCase):
    """Without CRUDKIT_USER_PROFILE_ADAPTER configured, the no-op default
    adapter serves static defaults and PATCH does nothing."""

    def setUp(self):
        self.user = User.objects.create_user(username="agent", password="pw")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_get_returns_defaults(self):
        response = self.client.get("/api/v1/user/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["preferred_language"], "en")
        self.assertEqual(response.data["object_images"], [])
        self.assertIn("assistant", response.data)

    def test_patch_is_noop(self):
        response = self.client.patch("/api/v1/user/me/", {"preferred_language": "da"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["preferred_language"], "en")

        response = self.client.get("/api/v1/user/me/")
        self.assertEqual(response.data["preferred_language"], "en")


@override_settings(CRUDKIT_USER_PROFILE_ADAPTER="tests.testapp.adapters.InMemoryUserProfileAdapter")
class CustomAdapterUserProfileViewTests(TestCase):
    """A project-supplied adapter must receive PATCH language updates and feed
    GET responses (language + object images)."""

    def setUp(self):
        self.user = User.objects.create_user(username="agent", password="pw")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        InMemoryUserProfileAdapter.reset()

    def tearDown(self):
        InMemoryUserProfileAdapter.reset()

    def test_get_without_stored_language_returns_default(self):
        response = self.client.get("/api/v1/user/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["preferred_language"], "en")
        self.assertEqual(response.data["object_images"], [])

    def test_patch_language_stores_via_adapter(self):
        response = self.client.patch("/api/v1/user/me/", {"preferred_language": "da"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["preferred_language"], "da")
        self.assertEqual(InMemoryUserProfileAdapter.languages[self.user.pk], "da")

        response = self.client.get("/api/v1/user/me/")
        self.assertEqual(response.data["preferred_language"], "da")

    def test_object_images_come_from_adapter(self):
        InMemoryUserProfileAdapter.images[self.user.pk] = ["/media/avatar.png"]
        response = self.client.get("/api/v1/user/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["object_images"], ["http://testserver/media/avatar.png"])
