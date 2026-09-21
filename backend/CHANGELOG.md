# Changelog

## Unreleased

- `crudkit_frontend`: feed items whose related object isn't an email (chat messages, calls,
  meetings, ...) show the feed item's `body` instead of an empty frame.

## 0.3.0 (2026-09-21)

- `crudkit_frontend`: related-record pickers offer `+ Create <model> "<typed text>"`, which
  opens the target's create form in a modal (prefilled from the first `search_fields` entry)
  and selects the new record without leaving the form. Modals nest; Esc/Enter only affect the
  topmost one. (#34)
- `crudkit_api`: the metadata endpoint also returns `search_fields`, `can_create` (add
  permission for the requesting user) and `inline_create`. `build_model_metadata` takes an
  optional `user`. (#34)
- `crudkit`: new `CrudKitSettings.inline_create` (default `True`); set `False` to hide the
  inline create option for a model. (#34)
- `crudkit_frontend`: a failed Kanban/Swimlane drop shows the server's validation error
  instead of a generic message. (#31)
- `crudkit_frontend`: inline email images are hidden behind a toggle; image attachments
  preview on hover. (#32)

## 0.2.3 (2026-09-21)

- `crudkit_api`: `GET /api/v1/` no longer returns 403 under `CrudKitModelPermissions`.
  `has_permission` checks authentication first and honours DRF's
  `_ignore_model_permissions`; the API root (`CrudKitRouter`/`CrudKitAPIRootView`) now lists
  only the models the user may view. (#25)
- `crudkit_frontend`: the detail view wraps long (over 60 characters) and multiline text,
  with a Show more/less toggle when it overflows, instead of a single ellipsised line. (#26)
- `crudkit_api`: fix a 500 when listing FeedItem or ExternalObject rows; generic relations
  are no longer included in the list prefetch. (#27)
- `crudkit`: multi-table-inheritance children are reachable by their own CK-ID again; the
  parent's `CrudKitIDField` accepts the TYPE_IDs of its descendants. (#28)

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
