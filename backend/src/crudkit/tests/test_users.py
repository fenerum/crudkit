from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from crudkit.utils import get_system_user


class ServiceUserTests(SimpleTestCase):
    def test_service_user_uses_configured_username_field(self):
        manager = Mock()
        expected_user = object()
        manager.get_or_create.return_value = (expected_user, True)
        user_model = SimpleNamespace(
            USERNAME_FIELD="email",
            _default_manager=manager,
            _meta=SimpleNamespace(fields=[SimpleNamespace(name="email")]),
        )

        with patch("crudkit.utils.get_user_model", return_value=user_model):
            user = get_system_user()

        self.assertIs(user, expected_user)
        manager.get_or_create.assert_called_once_with(email="system", defaults={})
