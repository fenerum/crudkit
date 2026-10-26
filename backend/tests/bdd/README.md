# CrudKit behaviour specification (BDD)

The `.feature` files in this directory are **the specification of everything
CrudKit does**, written so that someone who has never read the code (a
product owner, a support engineer, a new contributor) can read them and know
how the product behaves. They are executed with
[pytest-bdd](https://pytest-bdd.readthedocs.io/), so the specification cannot
drift from the code.

There are two suites with the same rules:

| Suite | Where | What it drives |
|---|---|---|
| Behaviour | `backend/tests/bdd/` (this one) | The backend through the REST API, the MCP server, the assistant and change-stream sockets, management commands and the models, against the fixture app in `backend/tests/testapp` |
| Journeys | `examples/demo/bdd/` | The built SPA in a real browser (Playwright), against the demo project |

## The rules

1. **The suites must cover the entire public behaviour of the codebase.** Every
   change that adds or alters behaviour adds or updates a scenario *in the same
   PR*. The coverage guard (`test_coverage.py`) fails when a public surface has
   no feature (see [Coverage tags](#coverage-tags)), but the guard only sees
   *surfaces*. Covering the behaviours behind each surface (the rules, the
   refusals, the edge cases) is on you.
2. **A non-developer must be able to read every feature.** Write in the
   language of the product, not of the code:
   - No URLs, HTTP verbs, status codes, JSON, CK-IDs (`CUS12`), class,
     function or setting names inside steps. Say *"Then it is forbidden"*, not
     *"Then the response is 403"*. Say *"the customer Acme"*, not *"CUS1"*.
   - Exceptions: the names a user actually sees or types (a field called
     "status", a tool name an MCP client calls, a management command an
     operator runs, an error message that is shown).
3. **Every Feature starts with a 1–3 sentence description** of who benefits
   and why. Read it aloud. It should make sense to someone outside the team.
4. **One behaviour per Scenario.** Name it as a statement of that behaviour:
   *"Undo is blocked when someone changed the same field afterwards"*, not
   *"test undo conflict"*. Aim for no more than ~8 steps.
5. **Declarative, not imperative.** *"Given Alice changed the status of
   "Acme" to "churned""*, not a list of clicks or requests.
6. **Use Gherkin's tools for clarity.** `Background:` for setup every scenario
   shares, `Scenario Outline:` + `Examples:` when only values change, data
   tables for records with several fields.
7. **Name the actors.** People are capitalised first names (Alice, Bob, Carol,
   Dave) introduced by a Given that says what they may do. Software actors are
   named for what they are: "an MCP client", "the assistant", "the agent
   "Triage"".
8. **Reuse step phrases before adding new ones.** Check the catalogue below
   and `steps/*.py`. A new phrase must read naturally in *other* features too.

## Layout

```
features/<area>/<behaviour>.feature   one folder per capability
steps/common.py                       people, records, writing, outcomes (shared)
steps/<area>.py                       the phrases one area adds
world.py                              the `world` fixture and the step vocabulary
conftest.py                           loads every steps/*.py, tag handling
test_features.py                      binds every .feature file
test_coverage.py                      the coverage guard
```

Every module in `steps/` is loaded automatically. Step definitions are global,
so a phrase defined in one area can be used in any feature. Before you add a
phrase, grep `steps/` so two modules never define the same one.

## Writing steps

Steps are written with `phrase()` from `world.py`, which adds the suite's
vocabulary to [parse](https://github.com/r1chardj0n3s/parse) patterns:

| Placeholder | Matches | Becomes |
|---|---|---|
| `{x:Actor}` | `Alice` | the string (look the user up with `world.user(x)`) |
| `{x:Model}` | `customer`, `saved views` | the model class, by verbose name |
| `{x:Q}` | the text between double quotes | the string |
| `{x:Words}` | lowercase words, e.g. `status`, `due date` | the string |
| `{x:List}` | `name, status and email` | `["name", "status", "email"]` |
| `{x:Perms}` | `view, change and delete` (only these four verbs) | `["view", "change", "delete"]` |
| `{x:Their}` | `her`, `his`, `their` | the string |

The `world` fixture is the scenario's memory. It holds:

- **People and their REST clients.**
  - `world.add_user(name)` introduces a person.
  - `world.user(name)` gives them back as a fresh instance, so the permission cache never goes stale.
  - `world.api(name)` is a DRF client acting as that person through the app.
- **Records, by label.**
  - `world.create(model, label, values)` creates a record as setup, not through the API.
  - `world.record(label)` re-reads the record from the database.
  - `world.url(label, action)`, `world.ck_id(label)` and `world.number(label)` give its address.
  - `world.value(...)` and `world.api_value(...)` convert the text written in a step into Python and API values.
- **The latest attempt.** `world.remember(name, response)` stores the response
  and the change set it produced (`world.change_set`, `world.change_sets[name]`).
  The outcome steps in `common.py` read it.

Store any other per-scenario state as an attribute on `world`.

Every scenario runs in a rolled-back transaction. Tag a scenario or feature
`@transactional` when it needs real commits: Channels consumers
(`WebsocketCommunicator`), or code that runs `transaction.on_commit` hooks.
Alternatively, wrap the step in pytest-django's
`django_capture_on_commit_callbacks(execute=True)` fixture. The cache is cleared
around every scenario.

Asynchronous APIs (Channels communicators, the MCP server) are driven from
synchronous steps with `asgiref.sync.async_to_sync`. AI models are faked by
patching `tests.testapp.ai.create_model` with a pydantic-ai `FunctionModel`
(see `steps/assistant.py`). Real LLMs are never called.

## Step catalogue (shared phrases)

The phrases in `steps/common.py`, which every area may use:

**People**
- `Given Alice is a superuser`
- `Given Alice is a user without any permissions`
- `Given Alice can view, change and delete customers`: Django model permissions; can be repeated to add more
- `Given Alice is inactive`

**Records** (created directly as setup)
- `Given a customer "Acme"`
- `Given a customer "Acme" with status "active"`
- `Given a customer "Acme" with:` followed by a `| field | value |` table (relations by label, people by name)
- `Given Alice owns a customer "Acme"`: the record was created by Alice
- `Given the status of "Acme" is "churned"`

**Writing through the app**
- `Given Alice changed the status of "Acme" to "churned"` / `When Alice changes …`
- `Given Alice deleted "Acme"` / `When Alice deletes "Acme"`

**State**
- `Then "Acme" has status "active"` / `Then "Acme" still has status "active"`
- `Then "Acme" is deleted` / `Then "Acme" is not deleted`

**Outcome of the latest attempt**
- `Then it succeeds`
- `Then it is forbidden`
- `Then it requires signing in`
- `Then it is not found`
- `Then it is rejected` / `Then it is rejected with "<part of the message>"`
- `Then it conflicts`

Each area's own phrases are documented in the docstring at the top of its
`steps/<area>.py`.

## Known bugs

A bug found while writing the spec still gets its scenario. Describe the
*intended* behaviour and tag that scenario `@known-bug`. Do not describe what
the code does today. Tagged scenarios run as strict expected failures:

- CI stays green while the bug is open.
- The scenario turns red the moment the bug is fixed. The fix PR then removes
  the tag, so the scenario becomes an ordinary passing one.

Before tagging, check that the scenario fails *because of the bug*. A missing
or broken step does not count. List open known bugs with:

```bash
grep -rn -A1 "@known-bug" tests/bdd/features
```

## Coverage tags

Tag a Feature (or a Scenario) with the surfaces it specifies. A tag is
`@<kind>:<name>`. Coverage tags are only read by the guard; they are not
pytest markers.

| Kind | Names | Comes from |
|---|---|---|
| `@endpoint:records.<action>` | `list`, `create`, `retrieve`, `update`, `partial_update`, `destroy`, `initial`, `metadata`, `history`, `restore`, `merge`, `reorder`, `action` | the generic record API every type gets |
| `@endpoint:<url name>` | e.g. `changeset_revert`, `search-list`, `token_obtain_pair`, `crudkit_mcp` | every other named route |
| `@mcp-tool:<name>` | e.g. `list_records` | the MCP tool registry |
| `@assistant-tool:<name>` | e.g. `propose_patch` | the assistant's tools |
| `@action:<TYPE>.<method>` | e.g. `ASP.confirm` | `@crm_action` methods on CrudKit's own models |
| `@command:<name>` | e.g. `set_exchange_rate` | management commands |
| `@type:<TYPE_ID>` | e.g. `VIW` | CrudKit's own record types |
| `@websocket:<route>` | e.g. `ws/changes/` | Channels routes |
| `@field:<Class>` | e.g. `MoneyField` | public field classes |
| `@check:<id>` | e.g. `crudkit.E001` | system checks |

`test_coverage.py` computes the inventory from the code and fails in two cases:

- a surface that no feature is tagged with;
- a tag that names something which no longer exists.

When you add a surface, add the tag along with the scenarios that specify it.

## Running

```bash
cd backend
uv sync --all-extras
uv run pytest                         # every scenario + the coverage guard
uv run pytest -k undo                 # scenarios whose name mentions undo
uv run pytest tests/bdd/test_coverage.py   # just the guard
```

The unittest suite (`uv run manage.py test …`) still exists for low-level
edge cases. The features here are the readable specification on top.
