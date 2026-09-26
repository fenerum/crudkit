"""Minimal settings for a CrudKit-based project."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-only-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    # First, so `runserver` serves ASGI (HTTP + the ws/changes/ and ws/assistant/ sockets).
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "crudkit",
    "crudkit_frontend",
    "crudkit_mcp",
    "crudkit_assistant",
    "library",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "demo.urls"
ASGI_APPLICATION = "demo.asgi.application"
# Single process, so in-memory is enough; multi-process deployments need Redis.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "crudkit_frontend.context_processors.crudkit_config",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        # Overridable so the Playwright suite runs against a throwaway DB.
        "NAME": os.environ.get("DEMO_DB_PATH", BASE_DIR / "db.sqlite3"),
        # Parallel e2e writers otherwise hit "database is locked" when a read
        # transaction tries to upgrade to a write.
        "OPTIONS": {"transaction_mode": "IMMEDIATE"},
    }
}

# Overridable so CI can prove the SPA works under any static prefix.
STATIC_URL = os.environ.get("DEMO_STATIC_URL", "static/")
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["crudkit_api.permissions.CrudKitModelPermissions"],
    "DEFAULT_PAGINATION_CLASS": "crudkit_api.pagination.CrudKitPagination",
    "DEFAULT_FILTER_BACKENDS": ["crudkit_api.filters.BasicFilter"],
    "PAGE_SIZE": 50,
}

CELERY_TASK_ALWAYS_EAGER = True
CRUDKIT_DEFAULT_CURRENCY = "EUR"

# The MCP OAuth consent page needs a session login.
LOGIN_URL = "/admin/login/"
CRUDKIT_MCP_SERVER_NAME = "crudkit-demo"

# A pydantic-ai model name (e.g. "anthropic:claude-sonnet-5") enables the
# assistant sidebar and AI fields; without one the assistant is hidden.
CRUDKIT_AI_MODEL = os.environ.get("DEMO_AI_MODEL")

CRUDKIT_FRONTEND_CONFIG = {
    "app_name": "CrudKit Demo",
}
