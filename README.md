# CrudKit

An open-source, metadata-driven CRUD application framework:

- **[backend/](backend/)** — `django-crudkit` (PyPI): Django models, generic REST API and AI assistant. Typed object IDs, soft delete, merge, change log, activity feed, saved views, AI fields.
- **[frontend/](frontend/)** — the metadata-driven React SPA. Built with Vite and bundled into the `django-crudkit` wheel, served by the `crudkit_frontend` Django app.

## Bundled frontend

The wheel ships the built SPA — consumers get a full web UI without touching
Node:

```python
INSTALLED_APPS = [..., "crudkit_frontend"]

TEMPLATES[0]["OPTIONS"]["context_processors"] += [
    "crudkit_frontend.context_processors.crudkit_config",
]

CRUDKIT_FRONTEND_CONFIG = {"app_name": "My App"}

# urls.py — catch-all, must be the LAST pattern
urlpatterns = [..., path("", include("crudkit_frontend.urls"))]
```

Contributors work on the SPA with the Vite dev server (`cd frontend && npm
install && npm run dev`) pointed at any CrudKit backend; `npm run build`
emits the production bundle into `backend/src/crudkit_frontend/` (gitignored,
built in CI for releases).

Built and maintained by [Fenerum](https://github.com/fenerum). MIT licensed.
