# Changelog

## 0.2.2 (2026-09-19)

- `crudkit_api`: list endpoints no longer build a serializer per row. `GenericViewSet.list`
  reuses one serializer for the whole page, `GenericSerializer.build_nested_field` caches the
  generated nested field classes per (related model, depth), and the nested serializer behind a
  forward FK is built once per field instead of once per value. A 500-row page of a model with
  11 FKs went from a 216 MB to a 15 MB peak downstream (72 MB to 8.5 MB in the test suite's
  smaller fixtures) and serializes ~2.6x faster; the JSON is unchanged. Worker RSS on gunicorn
  no longer climbs from refetching kanban/swimlane views, which request `page_size=500`.

- Workspaces: new `Workspace` model (TYPE_ID `WSP`) — switchable sidebar
  apps that pin an ordered set of saved views as tabs, picked from a switcher
  in the sidebar header. Purely additive: deployments with no Workspace rows
  render exactly as before.

## 0.2.1 (2026-08-11)

- `crudkit_frontend`: asset URLs are no longer hardcoded to `/static/`. The
  SPA shell references its assets via `{% static %}` tags (so
  `ManifestStaticFilesStorage` users also get hashed, cache-busted URLs), and
  the JS bundle builds asset/chunk URLs at runtime from Django's
  `STATIC_URL`, exposed by the shell as `window.__CRUDKIT_STATIC_URL__` via
  the `crudkit_config` context processor. Projects with a custom
  `STATIC_URL` (e.g. `assets/`) now work out of the box.

- The distribution is published on PyPI as **`crudkit`** (the planned
  `django-crudkit` name was rejected as too similar to an existing project).
  The importable packages (`crudkit`, `crudkit_api`, `crudkit_assistant`,
  `crudkit_frontend`) are unchanged.
- `crudkit_frontend`: new Django app that ships the built CrudKit web SPA
  inside the wheel. The Vite build emits hashed assets into
  `crudkit_frontend/static/` and the SPA shell into
  `crudkit_frontend/templates/crudkit_frontend/index.html`, which is served
  by a catch-all `spa` view (include `crudkit_frontend.urls` last in your
  urlconf). Branding/configuration is injected at runtime via the
  `crudkit_config` context processor from the `CRUDKIT_FRONTEND_CONFIG`
  setting; set `CRUDKIT_FRONTEND_LOGIN_REQUIRED = True` to redirect
  anonymous users to `LOGIN_URL`.
- The React SPA source now lives in `frontend/` in this repository.

## 0.1.0 (unreleased)

Initial extraction of CrudKit from the Fenerum CRM monolith:

- `crudkit`: `BaseCrudKitModel` with typed CK-IDs, audit columns, soft delete,
  merge; `ChangeLog`, `FeedItem`, `ExternalObject`, `View`, `Layout`,
  `WorkLog`, `ExchangeRate`, `Snippet`; `MoneyField`/`CurrencyField`; AI
  fields with Celery processing; dashboard widget base classes.
- `crudkit_api`: generic DRF serializer/viewset/router over the `TYPE_ID`
  registry, metadata endpoints, saved-view filtering, pagination, JWT auth.
- `crudkit_assistant`: per-object AI assistant over Channels WebSockets with
  a Confirm-gated proposal flow.
