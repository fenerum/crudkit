# CrudKit concepts

CrudKit turns Django models into a full CRUD application: declare a model with
a three-letter `TYPE_ID`, and you get a REST API, metadata-driven forms and
lists, saved views, and the bundled web UI for free.

## TYPE_IDs and CK-IDs

Every CrudKit model subclasses `BaseCrudKitModel` and declares a unique
three-letter `TYPE_ID`:

```python
class Book(BaseCrudKitModel):
    TYPE_ID = "BOK"
```

Primary keys are exposed as **CK-IDs** — the TYPE_ID followed by the numeric
id, e.g. `BOK123`. `CrudKitIDField` (a `BigAutoField`) does the wrapping and
unwrapping transparently: the database stores plain integers, while Python and
the API see the prefixed string. `get_ck_id(type_id, pk)` and
`parse_ck_id(ck_id)` in `crudkit.models` convert between the two, which makes
any object addressable from just its CK-ID — the basis for generic relations,
global search, and URLs like `/BOK123` in the SPA.

`get_model_types()` (`crudkit.utils`) builds the registry `{TYPE_ID: model}`
from all installed apps. `crudkit_api` registers one generic viewset per entry,
so a new model is fully served at `/api/v1/<TYPE_ID>/` without writing any API
code. TYPE_IDs must be unique across the project — the registry is a dict, so
a duplicate would silently shadow the earlier model.

## CrudKitSettings

Per-model behaviour is configured on an inner class:

```python
class Book(BaseCrudKitModel):
    TYPE_ID = "BOK"

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["title", "author__name"]
        allowed_prefills = ["author"]
```

- `search_fields` — used by list search and the global `/api/v1/search/`.
- `allowed_prefills` — query params accepted by the `/initial/` action to
  prefill create forms (e.g. "new book for author AUT7").
- `ai_trigger_children` — related objects whose changes re-trigger AI fields.
- `assistant_prompt` / `assistant_tools` — configure the per-object AI
  assistant (`crudkit_assistant`).
- `nested_fields` — additional explicitly public fields to include when a
  relation is serialized. Relations otherwise contain only `id`, `label`, and
  `object_images`.

Project-wide configuration lives in ordinary Django settings with the
`CRUDKIT_` prefix (`CRUDKIT_DEFAULT_CURRENCY`, `CRUDKIT_AI_MODEL`,
`CRUDKIT_FRONTEND_CONFIG`, …) — see the table in `backend/README.md`.

## The metadata endpoint

`GET /api/v1/<TYPE_ID>/metadata/` describes a model so clients can render it
without compile-time knowledge: `verbose_name`, the `fields` map (type,
choices, required, editable, related model and its TYPE_ID, …), reverse and
generic `relations`, `allowed_prefills`, and `actions`.

Actions are model methods decorated with `@crm_action("Verbose name")`
(`crudkit.decorators`); they show up as buttons in the UI and are invoked via
`POST /api/v1/<TYPE_ID>/<pk>/action/`.

The SPA is built entirely on this endpoint — every list, detail view, and form
is rendered from metadata at runtime. That is what makes the frontend generic:
it ships in the wheel yet works for any project's models.

## Saved views

A `View` (TYPE_ID `VIW`) is a stored, shareable query over one model type:
which `fields` to show, `filters` as `[field, comparator, value]` triples
(values may use variables like `${user}`), `order_by`/`group_by`/`pivot_by`,
an optional aggregate, and a `layout` (list, kanban, gallery, swimlane,
conversation, quadrant). Views can be `public`, per-user, marked `default`,
or pinned to the menu with `show_in_menu`.

Requests opt in with the `_view` query param: the API's `BasicFilter` loads
the view and applies its filters and ordering server-side. Views are
themselves CrudKit models, so they are managed through the same generic API
(`/api/v1/VIW/`) — the SPA's "save this view" feature is just a POST.

## Workspaces

A `Workspace` (TYPE_ID `WSP`) is a named, switchable bundle of saved views —
like a Salesforce app with its own tabs. Its `views` field is an ordered JSON
list of View CK-IDs (`["VIW3", "VIW1"]`); the list order is the tab order, and
the same view may appear in any number of workspaces. Workspaces can be
`public` or private to their creator, and are themselves CrudKit models
managed through the generic API (`/api/v1/WSP/`) and the generic SPA forms.

Workspaces only shape the sidebar: picking one from the sidebar-header
switcher replaces the shared-views section with that workspace's tabs. Search,
the command palette, "All objects", and direct links are unaffected. The
active workspace is client-side state persisted in localStorage — URLs stay
flat. A deployment with no `Workspace` rows renders the classic sidebar and
never shows the switcher.

## The frontend config contract

The built SPA shell (`index.html`) is served as a Django template by
`crudkit_frontend`. Exactly two placeholders survive the Vite build (enforced
by `frontend/scripts/postbuild.mjs`):

- `{{ csrf_token }}` — rendered into `<meta name="csrf-token">`.
- `{{ crudkit_config_json }}` — the `CRUDKIT_FRONTEND_CONFIG` setting rendered
  as JSON into `<script id="crudkit-config" type="application/json">` by the
  `crudkit_frontend.context_processors.crudkit_config` context processor.

At startup the SPA parses that script tag (`frontend/utils/appConfig.ts`) and
merges it over defaults: `app_name`, `org_name`, `logo_url`, `auth_mode`
(`password` or `saml`), `storage_prefix`, `conversation_link_pattern`.
Branding is therefore a runtime concern of the host project — nothing is
compiled into the bundle.

Set `CRUDKIT_FRONTEND_LOGIN_REQUIRED = True` to redirect anonymous users to
`LOGIN_URL` instead of serving the shell; by default the shell is public and
the SPA authenticates against the API (JWT via `/api/v1/token/`, or session
auth).
