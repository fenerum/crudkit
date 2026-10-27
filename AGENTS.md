# Agent instructions

CrudKit turns Django models into a full CRUD app: a model with a three-letter
`TYPE_ID` gets a generic REST API, metadata-driven UI, saved views, and an AI
assistant. Read [docs/concepts.md](docs/concepts.md) before touching
TYPE_IDs, CK-IDs, the metadata endpoint, saved views, or the frontend config
contract. [CONTRIBUTING.md](CONTRIBUTING.md) has the full workflow details.

## Layout

- `backend/` — the `crudkit` Python package (PyPI: `crudkit`). Django apps:
  `crudkit`, `crudkit_api`, `crudkit_assistant`, `crudkit_frontend`,
  `crudkit_mcp`.
- `frontend/` — React SPA source. `npm run build` emits into
  `backend/src/crudkit_frontend/` so the built UI ships inside the wheel.
  Never published to npm.
- `examples/demo/` — minimal consumer project, exercised end-to-end in CI.

## Commands

```bash
# Backend (cd backend; requires uv, Python >= 3.12)
uv sync --all-extras
uv run manage.py test crudkit crudkit_api crudkit_assistant crudkit_frontend crudkit_mcp tests
uv run ruff check src tests
uv run manage.py makemigrations --check --dry-run   # must stay clean
uv run pytest                     # BDD spec (tests/bdd) + its coverage guard

# Frontend (cd frontend; Node 22)
npm install
npm test
npm run lint
npm run build
npm run e2e    # Playwright against the demo + built SPA (build first;
               # `npx playwright install chromium` once)

# Browser BDD journeys (cd examples/demo; build the SPA first)
uv sync --group dev && uv run playwright install chromium   # once
uv run pytest
```

## Behaviour spec (BDD) — mandatory

The Gherkin features in `backend/tests/bdd/` (backend) and
`examples/demo/bdd/` (browser journeys) are the product's spec: together they
cover **every** public behaviour of the codebase, in plain language a
non-developer can read. Read [backend/tests/bdd/README.md](backend/tests/bdd/README.md)
before changing behaviour or writing a scenario. Every PR that adds or changes
behaviour updates the spec in the same PR:

- Add or adjust scenarios for each behaviour touched: the happy path, the
  refusals, the limits.
- Tag new public surface (`@endpoint:`, `@mcp-tool:`, `@page:`, ...); the
  coverage guard (`test_coverage.py`) fails on untagged surface and on stale tags.
- Write steps in product language: people, records by name, outcomes like
  "it is forbidden". URLs, status codes, JSON and IDs live in step code.

## Workflow

- `main` is protected: all changes go through PRs; required checks are
  `backend`, `frontend`, and `e2e`. Never push to `main` directly.
- Releases: tag `vX.Y.Z` on `main` (plain `v` prefix — one version covers
  backend and frontend). The `publish-python` workflow builds the SPA, then
  the wheel, and publishes to PyPI as `crudkit` via Trusted Publishing.
  Before tagging: bump `version` in `backend/pyproject.toml` and stamp the
  `backend/CHANGELOG.md` entry.

## Invariants — never break these

Downstream projects (notably fenerum-crm) depend on them:

- App labels stay `crudkit`, `crudkit_api`, `crudkit_assistant`,
  `crudkit_frontend`, `crudkit_mcp`.
- `crudkit/migrations/0001_squashed.py`: never edit `replaces`, never
  renumber. New schema changes are new migrations, generated under Django 5.1.
- No settings-derived values in migrations (see `CurrencyField.deconstruct()`
  in `backend/src/crudkit/fields.py`).
- Public API symbols are frozen for 0.x unless coordinated with fenerum-crm:
  `BaseCrudKitModel`, `get_system_user`, `get_model_types`, `parse_ck_id`,
  `crm_action`, `crm_id`, the field classes.
- The built `index.html` keeps the `{{ csrf_token }}` and
  `{{ crudkit_config_json }}` placeholders (`frontend/scripts/postbuild.mjs`
  enforces this — keep it).
