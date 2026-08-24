from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from crudkit_api.serializers import get_serializer
from tests.testapp.models import Ticket, UrgentComment


class SubclassIDSerializationTest(TestCase):
    """CK-ID (TYPE_ID-prefixed) serialization for a multi-table-inheritance
    child model: UrgentComment (URG) inherits Comment (COM), and must be
    serialized with the URG prefix, not the parent's COM prefix."""

    def setUp(self):
        self.user = User.objects.create_superuser(username="testuser", password="testpass")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.ticket = Ticket.objects.create(
            subject="Broken invoice",
            created_by=self.user,
            updated_by=self.user,
        )

    def _create_comment(self, body="Test content"):
        return UrgentComment.objects.create(
            ticket=self.ticket,
            body=body,
            escalation_reason="production down",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_subclass_id_prefix_in_api_response(self):
        """Test that UrgentComment objects are serialized with URG prefix, not COM prefix"""
        comment = self._create_comment()

        # Get the numeric ID - since pk might already be formatted, extract it
        if isinstance(comment.pk, str) and len(comment.pk) > 3:
            numeric_id = comment.pk[3:]  # Remove prefix
        else:
            numeric_id = comment.pk

        # Test API response with correct URL structure
        response = self.client.get(f"/api/v1/URG/{comment.pk}/")
        self.assertEqual(response.status_code, 200, f"Failed to retrieve comment with ID {comment.pk}")

        # Check the ID in the response
        response_id = response.data.get("id")
        self.assertEqual(
            response_id,
            f"URG{numeric_id}",
            f"API response ID should be URG{numeric_id}, but got {response_id}",
        )

        # Test serializer directly
        UrgentCommentSerializer = get_serializer(UrgentComment)
        serializer = UrgentCommentSerializer(comment)
        serialized_id = serializer.data.get("id")
        self.assertEqual(
            serialized_id,
            f"URG{numeric_id}",
            f"Serialized ID should be URG{numeric_id}, but got {serialized_id}",
        )

    def test_fk_id_prefix_in_api_response(self):
        """Test that a FK to another CrudKit model serializes with the related model's prefix"""
        comment = self._create_comment()

        response = self.client.get(f"/api/v1/URG/{comment.pk}/")
        self.assertEqual(response.status_code, 200)

        # depth=1 nests the ticket; its id must carry the TIC prefix
        ticket_data = response.data.get("ticket")
        self.assertTrue(
            ticket_data["id"].startswith("TIC"),
            f"Nested ticket ID should start with TIC, but got {ticket_data['id']}",
        )

    def test_subclass_list_endpoint_id_prefix(self):
        """Test that UrgentComment objects in list view have URG prefix"""
        for i in range(3):
            self._create_comment(body=f"Test content {i}")

        response = self.client.get("/api/v1/URG/")
        self.assertEqual(response.status_code, 200)

        comments = response.data if isinstance(response.data, list) else response.data.get("results", [])
        self.assertEqual(len(comments), 3)
        for comment_data in comments:
            comment_id = comment_data.get("id")
            self.assertTrue(
                comment_id.startswith("URG"),
                f"Comment ID should start with URG, but got {comment_id}",
            )
