# Changelog

## 0.2.0 (2026-08-11)

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
