# Changelog

## Unreleased

- `crudkit_mcp`: `list_records` takes a saved `view` (VIW CK-ID) and returns its rows with the
  view's filters, ordering and columns applied; `describe_types` lists a type's views. Access
  follows the REST API's `_view`: the view must be public or the user's own, and the user must
  be able to view its type.
- `crudkit_api`: saved-view ordering moved out of `BasicFilter` into `get_order_fields` and
  `order_queryset` in `crudkit_api.filters`.
- `crudkit_frontend`: saved views get a visual filter editor instead of the raw JSON
  textarea — per-field value pickers (choices, yes/no, numbers, dates, related records),
  variables like "Current user" (`${user}`), and invalid filters highlighted in red and
  editable instead of breaking the form.
- `crudkit`: `View.clean()` rejects unknown filter comparators and entries that aren't
  exactly `[field, comparator, value]`, so they fail on save (400) instead of when the view
  is applied (500).

## 0.4.0 (2026-09-24)

- `crudkit_mcp` (new app, `crudkit[mcp]`): remote MCP server + OAuth 2.1 provider, moved from
  fenerum-crm. A fixed, type-parameterised tool set addressing records by TYPE_ID/CK-ID —
  `describe_types`, `search`, `list_records`, `get_record`, and — with
  `CRUDKIT_MCP_WRITE_ENABLED` and the `write` scope — `create_record`, `update_record`,
  `run_action`, `add_note`; all respecting model/row/action permissions. New settings `CRUDKIT_MCP_SERVER_NAME`, `CRUDKIT_MCP_WRITE_ENABLED`,
  `CRUDKIT_MCP_EXTRA_TOOLS`, `CRUDKIT_MCP_MODELS`, `CRUDKIT_MCP_BASE_URL`; new
  `CrudKitSettings.mcp_exclude`. The consent page always grants `read` and offers `write`
  as a checkbox. (#39)
- `crudkit`: `get_authorized_instance` moved from `crudkit_assistant.utils` to
  `crudkit.authorization`. (#39)
- `crudkit_api`: new `crudkit_api.services` with the search, feed, change log and mutation
  helpers shared by the REST API, the assistant and the MCP server. (#39)

## 0.3.1 (2026-09-22)

- `crudkit_frontend`: feed items whose related object isn't an email (chat messages, calls,
  meetings, ...) show the feed item's `body` instead of an empty frame. (#36)
- `crudkit_frontend`: views only appear in menus (sidebar, workspace tabs, command palette)
  when `show_in_menu` is set. The shared Workspace section and workspace tabs only list public
  views; per-type view tabs, the default-view pick and the command palette only list public or
  own views, so superusers no longer see other users' private views there. (#37)

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
