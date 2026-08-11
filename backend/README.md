# crudkit

A metadata-driven CRUD framework for Django. Define models; get typed object
IDs, soft delete, merge, change logging, an activity feed, saved views,
AI-populated fields and a generic REST API — without writing per-model
serializers, viewsets or routes.

## Core concepts

Every CrudKit model inherits `BaseCrudKitModel` and declares a 3-letter
`TYPE_ID`. Object IDs are rendered as `<TYPE_ID><pk>` (e.g. `CUS42`) across
the API and UI.

```python
from django.db import models
from crudkit.models import BaseCrudKitModel

class Customer(BaseCrudKitModel):
    TYPE_ID = "CUS"
    name = models.CharField(max_length=255)

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["name"]
```

Included with every model: `created_by`/`updated_by`/`created_at`/`updated_at`
audit columns, a `deleted` soft-delete flag (`soft_delete()`), merge support
(`delete_and_merge_with()`), a change log, an activity feed (`FeedItem`),
external-system sync (`ExternalObject`), saved views/layouts, and optional AI
fields (`AISummaryField`, `AICategoryField`, `AIBooleanField`, `AITagsField`,
`AIForeignKeyField`) populated asynchronously via Celery and pydantic-ai.

## Installation

```
pip install crudkit[api]          # REST API included
pip install crudkit[assistant]    # + per-object AI assistant (Channels)
```

```python
INSTALLED_APPS = [
    ...,
    "rest_framework",
    "crudkit",
    "crudkit_assistant",  # optional
]

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "crudkit_api.pagination.CrudKitPagination",
    "DEFAULT_FILTER_BACKENDS": ["crudkit_api.filters.BasicFilter"],
    "PAGE_SIZE": 50,
}

# urls.py — one include registers a full CRUD API for every TYPE_ID model
urlpatterns = [path("api/v1/", include("crudkit_api.urls"))]
```

## Settings

| Setting | Purpose |
|---|---|
| `CRUDKIT_AI_MODEL` | pydantic-ai model string (e.g. `"mistral:mistral-large-latest"`) enabling AI fields/assistant |
| `CRUDKIT_AI_MODEL_FACTORY` | dotted path to an async context manager yielding a pydantic-ai `Model` (advanced) |
| `CRUDKIT_USER_PROFILE_ADAPTER` | dotted path to a class supplying preferred language + avatar images for users |
| `CRUDKIT_EXTRA_GENERIC_RELATIONS` | project models surfaced as generic relations in object metadata |
| `CRUDKIT_DEFAULT_CURRENCY`, `CRUDKIT_CURRENCY_CHOICES` | currency configuration for `MoneyField` |
| `CRUDKIT_GRAVATAR_FALLBACK_EMAIL` | fallback avatar email (gravatar `mp` default otherwise) |
| `CRUDKIT_DASHBOARD_WIDGETS` | dotted path to a `dashboard_for_user(user)` widget provider |
| `CRUDKIT_ASSISTANT_NAME`, `CRUDKIT_ASSISTANT_SYSTEM_PROMPT`, `CRUDKIT_ASSISTANT_AVATAR_URL` | assistant branding |
| `CRUDKIT_FRONTEND_CONFIG` | dict injected into the bundled SPA at runtime (`app_name`, `logo_url`, ...) |
| `CRUDKIT_FRONTEND_LOGIN_REQUIRED` | redirect anonymous users of the SPA view to `LOGIN_URL` |

## Bundled frontend

The wheel ships the built CrudKit web SPA. To serve it, add the app, the
context processor, a config dict, and a catch-all url include (last!):

```python
INSTALLED_APPS = [..., "crudkit_frontend"]

TEMPLATES = [{
    ...,
    "OPTIONS": {"context_processors": [
        ...,
        "crudkit_frontend.context_processors.crudkit_config",
    ]},
}]

CRUDKIT_FRONTEND_CONFIG = {"app_name": "My App"}  # injected into the SPA at runtime
CRUDKIT_FRONTEND_LOGIN_REQUIRED = False  # True → redirect anonymous users to LOGIN_URL

# urls.py — must be the LAST pattern; everything unmatched serves the SPA
urlpatterns = [..., path("", include("crudkit_frontend.urls"))]
```

Static assets are served by `django.contrib.staticfiles` (or WhiteNoise et
al.) from `crudkit_frontend/static/`, under whatever `STATIC_URL` the project
uses — nothing assumes the default `static/` prefix. Contributors hacking on
the SPA itself
run the Vite dev server from [../frontend](../frontend/) against any CrudKit
backend; `npm run build` there regenerates the bundled assets.

## Running the tests

```
cd backend
uv sync --all-extras
uv run manage.py test crudkit crudkit_api crudkit_assistant crudkit_frontend tests
```

## License

MIT
