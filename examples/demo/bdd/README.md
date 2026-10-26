# CrudKit journeys (BDD, in the browser)

The `.feature` files here specify what a person sees and does in the CrudKit
web app: signing in, finding, editing and merging records, saved views and
their layouts, the assistant, approvals. Each scenario drives the built SPA
in a real browser (Playwright) against this demo project.

**The rules for writing features are in
[backend/tests/bdd/README.md](../../../backend/tests/bdd/README.md) and apply
here unchanged.** Selectors (roles, labels, test ids) live in the steps, never
in a feature. This file covers what is specific to the browser suite.

## Layout

```
features/<journey>.feature   one file per journey
steps/common.py              people, records, going somewhere, forms, what is on screen (shared)
steps/<area>.py              the phrases one area adds (lists, records, views, search, ...)
world.py                     the `world` fixture, the REST helper and the step vocabulary
conftest.py                  boots the demo, signs in once, loads every steps/*.py
test_features.py             binds every .feature file
test_coverage.py             the coverage guard
```

## How a scenario runs

- **One server, one seeded database for the whole run.** `conftest.py` boots
  the demo on a throwaway SQLite database (`migrate`, `seed`, `runserver` with
  `DEMO_AI_MODEL=test`, pydantic-ai's offline model, so the assistant works
  without an API key). With `--base-url` or `E2E_BASE_URL` it uses that server
  instead, as CI does.
- **Alice is the seeded administrator** (`admin`/`admin`). The suite signs in
  once through the login page and every scenario starts from that signed-in
  browser state. `Given Alice is not signed in` swaps to a fresh browser.
- **Every scenario creates its own records**, through the REST API, like
  `frontend/e2e/helpers.ts`. A record a feature calls `"Drag me"` is really
  called `"Drag me <token>"`, with one token per scenario, so scenarios never
  see each other's records and a search for the token finds exactly the
  scenario's own. Steps translate with `world.text()`: a label of this
  scenario's records becomes its real name, also inside longer text
  (`"Drag me renamed"`). Text that is not such a label, like the seeded
  records (`"Kindred"`, `"Octavia E. Butler"`) or anything the app says,
  is used as written. Typing a new name into a form names a new record the
  same way.
- Seeded records are shared: read them, never change them.

## Writing steps

Steps use `phrase()` from `world.py`:

| Placeholder | Matches | Becomes |
|---|---|---|
| `{x:Actor}` | `Alice`, `she`, `he`, `they` | the string |
| `{x:Model}` | `book`, `books`, `author`, `reading`, `view` (and plurals) | the type code (`BOK`) |
| `{x:Q}` | the text between double quotes | the string |
| `{x:QList}` | `"a", "b" and "c"` | `["a", "b", "c"]` |
| `{x:Words}` | lowercase words, e.g. `status`, `sort order` | the string |
| `{x:A}` | `a` or `an` | the string |

Fields are named as the screen names them (`name` is a book's title) and
choices by their label (`"To read"`); `world.api` reads the record type's
metadata to translate. Phrases overlap easily in a browser suite ("the
`{field}` shows" would also match "the form shows"), so check a new phrase
against `steps/` before adding it. Assertions use Playwright's `expect`, which
retries; before asserting that something is absent, assert something that
proves the page has loaded.

## Step catalogue (shared phrases)

From `steps/common.py`. Each area's phrases are listed in the docstring at the
top of its `steps/<area>.py`.

**People**
- `Given Alice is signed in` / `Given Alice is not signed in`
- `When Alice signs in` / `When Alice signs in with a wrong password`
- `Then she is asked to sign in` / `Then she is shown as signed in`

**Records** (created through the API as setup)
- `Given a reading "Diary"` / `Given an author "Correspondent"`
- `Given a reading "Drag me" with status "Reading"`
- `Given a reading "Order first" with:` + `| field | value |` rows
- `Given Alice deleted "Diary"`
- `When the name of "Shared" is changed to "Shared, renamed" elsewhere` (also `Given … was changed`, `When … are changed`)

**Going somewhere**
- `Given Alice is on the dashboard` / `When she goes to the dashboard`
- `Given Alice is on the readings list` / `When she opens the readings list`
- `Given Alice is on the page of "Diary"` / `When she opens "Diary"`
- `When she follows the link "Octavia E. Butler"`, `When she reloads the page`
- `When she presses Escape|Enter` (in the innermost open form, if any)
- `Then she is on the dashboard|the books list|the page of "Diary"`

**What is on screen**
- `Then she sees "A" and "B"` / `Then she does not see "A"` (in the page's main area)
- `Then she is told "Note posted"` (anywhere, e.g. a notification)
- `Then the page is titled "…"`

**Forms** (the innermost one: an open dialog, else the page)
- `When she fills in the name "Unwritten"`, `When she picks "Italo Calvino" as the author`
- `When she creates it` / `When she saves it`
- `Then the form has|still has the name "Unwritten"`, `Then the form shows "Ursula K. Le Guin"`

## Coverage tags

| Kind | Names | Comes from |
|---|---|---|
| `@page:<path>` | `/`, `/login`, `/<segment>`, `/<segment>/VIW/<view>`, … and `not-found` | every `<Route>` in `frontend/src/App.tsx`: the index route is `/`, `:param` is written `<param>`, the catch-all `*` is `not-found` |
| `@layout:<value>` | `list`, `kanban`, `gallery`, `swimlane`, `conversation`, `quadrant` | the choices of the saved view's `layout` field (`View.ViewLayoutChoices`) |

`test_coverage.py` fails when a page or layout has no tagged feature, and when
a tag names one that no longer exists.

## Running

```bash
cd frontend && npm install && npm run build   # the SPA, into backend/src/crudkit_frontend/
cd ../examples/demo
uv sync --group dev
uv run playwright install chromium            # once
uv run pytest                                 # every journey + the coverage guard
uv run pytest -k kanban                       # journeys whose name mentions kanban
uv run pytest --headed --slowmo 300           # watch it
uv run pytest --base-url=http://127.0.0.1:8000   # against a server you started
E2E_BASE_URL=http://127.0.0.1:8000 uv run pytest # the same
```

Write `--base-url=URL` with the `=`: pytest-playwright registers the option
late, and a separate `URL` argument is taken for a test path.

The suite boots its own server on port 8766 (`E2E_PORT` to change it), next
to the TypeScript suite's 8765. On failure, `--screenshot only-on-failure` and
`--tracing retain-on-failure` write to `test-results/`.
