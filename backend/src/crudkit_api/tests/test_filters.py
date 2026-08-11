from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from crudkit.models import View
from crudkit_api.filters import BasicFilter


class MockView:
    """Mock view for testing the filter backend."""

    def __init__(self):
        self.request = None


class TestBasicFilter(TestCase):
    """Tests for the BasicFilter class."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.filter = BasicFilter()
        self.view = MockView()

        # Create test user
        self.user = User.objects.create_user(username="testuser", password="password")

        # Create test views with different ordering configurations
        self.view_with_order_by = View.objects.create(
            name="Test View with Order By",
            model="TST",  # Test model
            order_by="name",
            created_by=self.user,
            updated_by=self.user,
            fields=["id", "name", "status"],  # Required field
        )

        self.view_with_group_by = View.objects.create(
            name="Test View with Group By",
            model="TST",  # Test model
            group_by="status",
            created_by=self.user,
            updated_by=self.user,
            fields=["id", "name", "status"],  # Required field
        )

        self.view_with_pivot_by = View.objects.create(
            name="Test View with Pivot By",
            model="TST",  # Test model
            pivot_by="category",
            created_by=self.user,
            updated_by=self.user,
            fields=["id", "name", "status", "category"],  # Required field
        )

        self.view_with_all = View.objects.create(
            name="Test View with All",
            model="TST",  # Test model
            order_by="name",
            group_by="status",
            pivot_by="category",
            created_by=self.user,
            updated_by=self.user,
            fields=["id", "name", "status", "category"],  # Required field
        )

    def test_filter_with_api_order_by(self):
        """Test filtering with _order_by parameter from API."""
        # Create a mock request with _order_by parameter
        django_request = self.factory.get("/", {"_order_by": "name"})
        request = Request(django_request)
        self.view.request = request

        # Mock queryset with order_by method
        class MockQuerySet:
            def __init__(self):
                self.applied_order_by = None
                self.model = type("Model", (), {"_meta": type("_meta", (), {"get_fields": lambda: []})})

            def order_by(self, *fields):
                self.applied_order_by = fields
                return self

            def filter(self, **kwargs):
                return self

        queryset = MockQuerySet()

        # Apply the filter
        result = self.filter.filter_queryset(request, queryset, self.view)

        # Check that order_by was applied with case-insensitive ordering for text fields
        # For 'name', we should apply Lower() for case-insensitivity
        self.assertEqual(len(result.applied_order_by), 1)
        self.assertIn("name", str(result.applied_order_by[0]))
        self.assertIn("Lower", str(result.applied_order_by[0]))

    def test_filter_with_view_ordering(self):
        """Test filtering with a view that has ordering configured."""
        # Create a mock request with _view parameter
        django_request = self.factory.get("/", {"_view": self.view_with_order_by.id})
        request = Request(django_request)
        self.view.request = request

        # Mock queryset with order_by method
        class MockQuerySet:
            def __init__(self):
                self.applied_order_by = None
                self.model = type("Model", (), {"_meta": type("_meta", (), {"get_fields": lambda: []})})

            def order_by(self, *fields):
                self.applied_order_by = fields
                return self

            def filter(self, **kwargs):
                return self

        queryset = MockQuerySet()

        # Apply the filter
        result = self.filter.filter_queryset(request, queryset, self.view)

        # Check that order_by was applied with case-insensitive ordering for the 'name' field
        self.assertEqual(len(result.applied_order_by), 1)
        self.assertIn("name", str(result.applied_order_by[0]))
        self.assertIn("Lower", str(result.applied_order_by[0]))

    def test_filter_with_all_ordering_fields(self):
        """Test filtering with a view that has all ordering fields configured."""
        # Create a mock request with _view parameter
        django_request = self.factory.get("/", {"_view": self.view_with_all.id})
        request = Request(django_request)
        self.view.request = request

        # Mock queryset with order_by method
        class MockQuerySet:
            def __init__(self):
                self.applied_order_by = None
                self.model = type("Model", (), {"_meta": type("_meta", (), {"get_fields": lambda: []})})

            def order_by(self, *fields):
                self.applied_order_by = fields
                return self

            def filter(self, **kwargs):
                return self

        queryset = MockQuerySet()

        # Apply the filter
        result = self.filter.filter_queryset(request, queryset, self.view)

        # Check that order_by was applied with all fields in the correct order:
        # pivot_by, group_by, order_by (with case-insensitive name)
        self.assertEqual(len(result.applied_order_by), 3)
        # First field should be category
        self.assertEqual(result.applied_order_by[0], "category")
        # Second field should be status
        self.assertEqual(result.applied_order_by[1], "status")
        # Third field should be case-insensitive name
        self.assertIn("name", str(result.applied_order_by[2]))
        self.assertIn("Lower", str(result.applied_order_by[2]))

    def test_api_order_by_overrides_view_order_by(self):
        """Test that _order_by parameter from API overrides view's order_by."""
        # Create a mock request with both _view and _order_by parameters
        django_request = self.factory.get("/", {"_view": self.view_with_all.id, "_order_by": "updated_at"})
        request = Request(django_request)
        self.view.request = request

        # Mock queryset with order_by method
        class MockQuerySet:
            def __init__(self):
                self.applied_order_by = None
                self.model = type("Model", (), {"_meta": type("_meta", (), {"get_fields": lambda: []})})

            def order_by(self, *fields):
                self.applied_order_by = fields
                return self

            def filter(self, **kwargs):
                return self

        queryset = MockQuerySet()

        # Apply the filter
        result = self.filter.filter_queryset(request, queryset, self.view)

        # Check that order_by was applied with API parameter overriding view's order_by
        # but still including pivot_by and group_by from view
        self.assertEqual(len(result.applied_order_by), 3)
        # First field should be category
        self.assertEqual(result.applied_order_by[0], "category")
        # Second field should be status
        self.assertEqual(result.applied_order_by[1], "status")
        # Third field should be updated_at (not a text field, so no Lower())
        self.assertEqual(result.applied_order_by[2], "updated_at")

    def test_multiple_order_by_fields(self):
        """Test that multiple comma-separated order_by fields are handled correctly."""
        # Create a mock request with _order_by parameter containing multiple fields
        django_request = self.factory.get("/", {"_order_by": "name,created_at,-updated_at"})
        request = Request(django_request)
        self.view.request = request

        # Mock queryset with order_by method
        class MockQuerySet:
            def __init__(self):
                self.applied_order_by = None
                self.model = type("Model", (), {"_meta": type("_meta", (), {"get_fields": lambda: []})})

            def order_by(self, *fields):
                self.applied_order_by = fields
                return self

            def filter(self, **kwargs):
                return self

        queryset = MockQuerySet()

        # Apply the filter
        result = self.filter.filter_queryset(request, queryset, self.view)

        # Check that order_by was applied with all fields in correct order
        # With case-insensitive ordering for text field 'name'
        self.assertEqual(len(result.applied_order_by), 3)
        # First field should be case-insensitive name
        self.assertIn("name", str(result.applied_order_by[0]))
        self.assertIn("Lower", str(result.applied_order_by[0]))
        # Second field should be created_at
        self.assertEqual(result.applied_order_by[1], "created_at")
        # Third field should be -updated_at
        self.assertEqual(result.applied_order_by[2], "-updated_at")
