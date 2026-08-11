"""Tests for the crudkit_frontend context processor and SPA view.

These run against a stub index.html template (tests/templates/) so the suite
never needs the Vite-built SPA. The stub dir is placed in TEMPLATES DIRS,
which Django checks before app template dirs, so a locally built index.html
cannot shadow it.
"""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from crudkit_frontend.context_processors import crudkit_config

STUB_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [Path(__file__).resolve().parent / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "crudkit_frontend.context_processors.crudkit_config",
            ],
        },
    },
]

User = get_user_model()


@override_settings(TEMPLATES=STUB_TEMPLATES, ROOT_URLCONF="crudkit_frontend.tests.urls")
class CrudkitConfigContextProcessorTests(TestCase):
    @override_settings(CRUDKIT_FRONTEND_CONFIG={"app_name": "Acme CRM", "note": "</script><b>"})
    def test_config_json_is_rendered_with_lt_escaped(self):
        context = crudkit_config(request=None)
        self.assertNotIn("<", context["crudkit_config_json"])
        self.assertIn("\\u003c/script>\\u003cb>", context["crudkit_config_json"])
        self.assertEqual(context["crudkit_app_name"], "Acme CRM")

        response = self.client.get("/")
        self.assertContains(response, '"app_name": "Acme CRM"')
        self.assertContains(response, "\\u003c/script>\\u003cb>")
        self.assertContains(response, "<title>Acme CRM</title>", html=False)
        self.assertNotContains(response, "</script><b>")

    def test_defaults_without_setting(self):
        context = crudkit_config(request=None)
        self.assertEqual(context["crudkit_config_json"], "{}")
        self.assertEqual(context["crudkit_app_name"], "CrudKit")

        response = self.client.get("/")
        self.assertContains(response, "<title>CrudKit</title>", html=False)


@override_settings(TEMPLATES=STUB_TEMPLATES, ROOT_URLCONF="crudkit_frontend.tests.urls")
class SpaViewTests(TestCase):
    def test_anonymous_gets_spa_by_default(self):
        response = self.client.get("/some/spa/route")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crudkit_frontend/index.html")

    @override_settings(CRUDKIT_FRONTEND_LOGIN_REQUIRED=True)
    def test_anonymous_is_redirected_to_login_when_required(self):
        response = self.client.get("/some/spa/route")
        self.assertRedirects(
            response,
            "/accounts/login/?next=/some/spa/route",
            fetch_redirect_response=False,
        )

    @override_settings(CRUDKIT_FRONTEND_LOGIN_REQUIRED=True)
    def test_authenticated_user_gets_spa_when_login_required(self):
        user = User.objects.create_user(username="alice", password="pw")
        self.client.force_login(user)
        response = self.client.get("/some/spa/route")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crudkit_frontend/index.html")
