# Contributing

## Repository layout

- `backend/` — the `django-crudkit` Python package: `crudkit` (models, fields,
  registry), `crudkit_api` (generic DRF API), `crudkit_assistant` (AI assistant
  over WebSockets), `crudkit_frontend` (serves the bundled SPA; has no models).
- `frontend/` — the React SPA source. `npm run build` emits the built app
  straight into `backend/src/crudkit_frontend/`, so it ships inside the wheel.
  It is not a separate package and is never published to npm.
- `examples/demo/` — a minimal Django project built on the package; exercised
  end-to-end in CI.

See [docs/concepts.md](docs/concepts.md) for the core concepts (TYPE_IDs,
saved views, the metadata endpoint, the frontend config contract).

## Development setup

Backend (Python ≥ 3.12, [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
uv sync --all-extras
uv run manage.py test crudkit crudkit_api crudkit_assistant crudkit_frontend tests
uv run ruff check src tests
```

Frontend (Node 22):

```bash
cd frontend
npm install
npm run dev    # Vite dev server on :8100, proxies /api to :8000
npm test
npm run lint
npm run build  # builds into backend/src/crudkit_frontend/
```

## Workflow

`main` is protected: every change goes through a pull request, and the
`backend`, `frontend`, and `demo` checks must pass before merging. There are
no direct pushes.

CI runs the backend suite on a Python × Django matrix (plus a fresh-migrate
Postgres job and a migration-drift check), the frontend vitest suite and
production build, and an end-to-end job that installs the built wheel into a
clean venv and boots `examples/demo` against it.

## Releasing

1. Ensure `version` in `backend/pyproject.toml` and the `backend/CHANGELOG.md`
   entry (with date) are in place on `main`.
2. Tag the release commit `vX.Y.Z` and push the tag.
3. The `publish-python` workflow builds the SPA, then the sdist and wheel, and
   publishes to [PyPI](https://pypi.org/project/django-crudkit/) via Trusted
   Publishing (no tokens; the `pypi` GitHub environment provides the OIDC
   identity).

## Invariants

These hold for every change; they exist so downstream projects (notably
fenerum-crm) can upgrade safely:

- App labels stay `crudkit`, `crudkit_api`, `crudkit_assistant`, and
  `crudkit_frontend`.
- `crudkit/migrations/0001_squashed.py`: never edit `replaces`, never
  renumber. New schema changes are new migrations, generated under Django 5.1.
- No settings-derived values in migrations — see `CurrencyField.deconstruct()`
  in `backend/src/crudkit/fields.py` for the pattern.
- Public API symbols are frozen for 0.x unless coordinated with fenerum-crm:
  `BaseCrudKitModel`, `get_system_user`, `get_model_types`, `parse_ck_id`,
  `crm_action`, `crm_id`, the field classes, and friends.
- The built `index.html` must keep the `{{ csrf_token }}` and
  `{{ crudkit_config_json }}` placeholders. `frontend/scripts/postbuild.mjs`
  enforces this at build time and CI re-asserts it.
