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

- `search_fields` — used by list search and the global `/api/v1/search/`. The
  CK-ID is always searchable too (exact, case-insensitive), with or without them.
- `allowed_prefills` — query params accepted by the `/initial/` action to
  prefill create forms (e.g. "new book for author AUT7").
- `inline_create` — set to `False` to hide the "Create new…" option in
  related-object pickers that target this model (default `True`).
- `ai_trigger_children` — related objects whose changes re-trigger AI fields.
- `assistant_prompt` / `assistant_tools` — the playbook and extra tools the AI
  assistant (`crudkit_assistant`) gets while a record or list of this model is
  on screen.
- `mcp_exclude` — set to `True` to leave the model out of the MCP server's
  generated tools (`crudkit_mcp`).
- `approval_fields` — fields MCP clients and agents may only propose changes
  to (see [Approvals](#approvals)).
- `default_inlines` — related lists the detail page shows when no `Layout`
  row exists for the type, in the same `[[TYPE_ID, [field, …]], …]` form as
  `Layout.inlines`.
- `owner_access` — set to `True` to let any signed-in user view and change the
  rows they created without the Django model permission (others' rows stay
  hidden unless the user has the permission; delete still needs it).
- `celebrate` — values worth a confetti burst in the SPA, e.g.
  `{"stage": ["won"], "status": ["closed"]}`. When a write moves a record into
  one of them, the response carries `X-CrudKit-Celebrate: 1`. That covers an
  edit, a board drag, a bulk edit, an import, or an action that sets the field.
  Values are as stored: choice values, or related record IDs. Saving a record
  that is already there, and undo, never celebrate. A `@crm_action` can also
  celebrate by answering `Response({"celebrate": True, ...})`. The SPA skips
  the animation for people who prefer reduced motion.
- `feed_entry` — a `FeedEntry` that makes the model a kind of entry people add
  to other records' feeds, like a logged call or a sent email (see
  [Feed entries](#feed-entries)).

Project-wide configuration lives in ordinary Django settings with the
`CRUDKIT_` prefix (`CRUDKIT_DEFAULT_CURRENCY`, `CRUDKIT_AI_MODEL`,
`CRUDKIT_FRONTEND_CONFIG`, …) — see the table in `backend/README.md`.

## The metadata endpoint

`GET /api/v1/<TYPE_ID>/metadata/` describes a model so clients can render it
without compile-time knowledge: `verbose_name`, the `fields` map (type,
choices, required, editable, related model and its TYPE_ID, …), reverse and
generic `relations`, `allowed_prefills`, `search_fields`, `actions`,
`feed_entry` (how the type shows in feeds, if it is a kind of feed entry), and
for the requesting user `can_create`, `can_change` and `can_delete` (the
model permissions), `inline_create`, and `feed_entries` (the kinds of entry
they may add to the feed of a record of this type).

Actions are model methods decorated with `@crm_action("Verbose name")`
(`crudkit.decorators`); they show up as buttons in the UI and are invoked via
`POST /api/v1/<TYPE_ID>/<pk>/action/`. Each action in the metadata carries
`requires_approval` (see [Approvals](#approvals)).

### Progress of long-running actions

An action that takes a while reports how far it got with `crudkit.jobs`. The
person who ran it sees a progress bar in a task tray that stays on screen as
they move around, and on the record while it runs:

```python
from crudkit import jobs

@crm_action("Recalculate invoices")
def recalculate(self, request):
    for i, invoice in enumerate(invoices, 1):
        invoice.recalculate()
        jobs.progress(i, total=len(invoices), message=invoice.number)
```

The first `progress()` call creates a task, a `Job` (TYPE_ID `JOB`), labelled
with the action's name and pointing at the record. The task succeeds when the
action returns and fails, with the reason, if it raises or answers with an
error status. An action that never calls `progress()` creates no task. `total`
may be left out while unknown; the bar then sweeps.

To carry on after the click, `hand_off()` the task to a Celery task and finish
it there under `resume()`, which marks it succeeded or failed when the block
exits:

```python
@crm_action("Import contacts")
def import_contacts(self, request):
    import_contacts_task.delay(jobs.hand_off().pk)

@shared_task
def import_contacts_task(job_id):
    with jobs.resume(job_id):
        for i, row in enumerate(rows, 1):
            ...
            jobs.progress(i, total=len(rows))
```

`progress()` looks global but isn't: the current task lives in a ContextVar,
as the [audit context](#history-and-undo) does, so each thread, asyncio task
and Celery task reports into its own. `jobs.current()` returns it. Outside an
action or `resume()`, `progress()` does nothing, so shared helpers can call it.

Progress is pushed over the `ws/changes/` socket to the person who started the
task only, at most four times a second, and saved at most once a second, so
reloads and polling clients catch up. People only ever see their own tasks.
The action's response carries the task's id as `job`. Progress pushed from a
Celery worker needs a channel layer shared between processes (e.g.
`channels_redis`).

### Changing many records at once

`POST /api/v1/<TYPE_ID>/bulk/` changes up to 500 records of one type in one
request: `{"ids": [...], "operation": "update", "fields": {...}}` sets the
same fields on each, `"operation": "delete"` soft-deletes them and
`"operation": "action", "action": "<name>"` runs a `@crm_action` on each. The
values are checked once up front, so a value no record could take is refused
before anything changes. After that each record is changed in its own
savepoint: a record the person may not change (or delete), or that fails its
own validation or the action's checks, is skipped and listed with the reason
under `skipped`, and the rest are kept. The answer is
`{"done": n, "skipped": [{id, label, reason}]}`, plus `job` for actions.
Everything one request changed is one change set, so one undo reverses it. An
action run on many records shows one progress bar, a step per record; the
action's own `progress()` calls are ignored inside it, while `hand_off()`
still gives the action a task of its own. The list's selection bar in the SPA
uses this endpoint for Edit field, Run action and Delete.

The SPA is built entirely on this endpoint — every list, detail view, and form
is rendered from metadata at runtime. That is what makes the frontend generic:
it ships in the wheel yet works for any project's models.

## Feed entries

A record's feed holds notes (`FeedItem`) and whatever kinds of entries the
project declares, such as a logged call, a meeting or a sent email. Each kind is
a model of its own, made one by `CrudKitSettings.feed_entry`:

```python
from crudkit.models import FeedEntry

class Email(BaseCrudKitModel):
    TYPE_ID = "EML"
    ...
    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        allowed_prefills = ["author", "to", "subject", "body"]
        feed_entry = FeedEntry(
            fields=["to", "cc", "subject", "status", "body"],
            icon="mail",
            verb="emailed",
            action="send",
            reply=True,
            attachments="EMA",
            on=["AUT"],
        )
```

- `fields` — the composer's form and what the feed shows, in order. The form
  leaves out fields that can't be edited (a status, say); the feed shows them.
  Rich text gets a block of its own: a `WYSIWYGEditorField` shows inline like
  a note, an `EmailWYSIWYGEditorField` in a sandboxed frame, for HTML that
  comes from outside.
- `icon` — a name from the SPA's icon map (`frontend/components/ui/iconMap.js`).
- `verb` — how the feed tells it ("Alice emailed"). Default "added a <verbose name>".
- `action` — a `@crm_action` the composer runs right after creating the record,
  such as sending the email. Its name labels the composer's button.
- `on` — the TYPE_IDs whose feeds offer the kind. Default: every type.
- `compose=False` — for entries that only arrive from elsewhere (an
  integration, a sync): the feed shows them, the composer doesn't offer them.
- `reply` — the feed offers Reply on the kind's entries, which opens its
  composer with `reply_to` set to the entry.
- `attachments` — the TYPE_ID of a model that holds an entry's files: a foreign
  key to the entry and a `FileField`. The composer uploads each file as one,
  filling in `filename` and `content_type` when the model has them (its other
  required fields need defaults), before it runs `action`. The feed lists
  them; one whose `content_id` the entry's HTML references as `cid:` shows
  inline instead.

The composer has a tab for Note and one for each kind the person may add there
(`feed_entries` in the record type's metadata). A kind's form is its create
form: `/initial/?from_object=<CK-ID>` prefills it, along with the kind's
foreign key to the record when that is in `allowed_prefills`, and
`POST /api/v1/<TYPE_ID>/?from_object=<CK-ID>` creates it. `from_object`, and
`reply_to` for a reply, must name records the person can see; the model's
`from_query_params` then gets them, to prefill a reply's subject and quote,
say. Once the record is created, CrudKit puts it on the feed of the
`from_object` record: a `FeedItem` whose `related_object` is the new record,
unless the project's own code already made that one. A kind whose `on` leaves
out that record's type is refused.

A feed row follows its record. Its Edit and Delete act on the record; undoing
the creation or deleting the record takes the row out of the feed, and
restoring it brings it back. Entries that come from elsewhere go on a feed the
same way: `FeedItem.objects.create(parent_object=customer,
related_object=call, ...)`. The system check `crudkit.E003` reports a
`feed_entry` naming fields, an action, record types or attachments that don't
exist.

## Saved views

A `View` (TYPE_ID `VIW`) is a stored, shareable query over one model type:
which `fields` to show, `filters` as `[field, comparator, value]` triples
(values may use variables like `${user}`), `order_by`/`group_by`/`pivot_by`,
an optional aggregate, and a `layout` (list, kanban, gallery, swimlane,
conversation, quadrant). Views can be `public`, per-user, marked `default`,
or pinned to the menu with `show_in_menu`. `show_badge_in_menu` adds a count
next to the menu item and in the browser tab title. By default it counts every
row in the view. `badge_filters` (same triple format) narrows the count further,
e.g. a view of open chats whose badge counts only the unread ones.

Requests opt in with the `_view` query param: the API's `BasicFilter` loads
the view and applies its filters and ordering server-side; adding `_badge`
also applies its `badge_filters` (this is how the badge count is fetched). Views are
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

## AI context

`AIContext` (TYPE_ID `AIC`) documents are markdown the users maintain in the
UI: who the ideal customer is, why customers buy, tone of voice, playbooks.
Each has a `name`, a markdown `body`, `model_types` (a list of TYPE_IDs; empty
means global, as for snippets), `active` and an `order`. They are ordinary
CrudKit records, so they get the REST API (`/api/v1/AIC/`), list and detail
pages, history and undo at `/AIC`. Add a saved view to the menu to link it.

`crudkit.llm.ai_context(type_id=None)` renders the active documents that apply
(the global ones plus those listing `type_id`), ordered by `order` then
`name`, each under a `## <name>` heading. Every LLM feature reads it:

- the assistant's instructions carry the global documents and those for the
  type of the open record or list (not the `[Screen]` block, which is stored
  with each user turn and would repeat them on every later turn);
- AI fields get a `## Company context` section with the global documents and
  those for the record's type.

The documents are shown to every assistant user, whatever their permissions on
`AIC`, so keep secrets out of them. Editing them is effectively privileged:
their text reaches every user's assistant, every agent and every AI field.
`model_types` must list known TYPE_IDs, and the rendered context is capped at
`CRUDKIT_AI_CONTEXT_MAX_CHARS` (default 20,000) so it fits a small model's
window. When a user teaches the sidebar something durable about the company,
it proposes an edit to the relevant document (`propose_patch` with the `AIC`
id), which waits for Confirm like any other proposal. Agents aren't asked to,
and all of an `AIC`'s fields are `approval_fields`, so MCP clients and agents
can only propose edits.

## History and undo

Every write through the REST API, MCP, the assistant or a `@crm_action` (and
every note added through them) is
logged as a `ChangeLog` entry with the old and new value of each changed field,
the user, and where it came from: `source` (`ui`, `api`, `mcp`, `assistant`,
`agent`, `revert`, `system`) and `client` (an API `Client-Id` or MCP OAuth
client name). `source` and `client` are attribution, not authorization: an API
client can present itself as the UI, so nothing grants or denies access based
on them. Many-to-many fields are logged too, as the sorted related ids before
and after (changes made from the reverse side, `topic.ticket_set.add(...)`,
aren't). Entry points wrap their work in `crudkit.audit.audit(source, ...)`;
all entries written inside share one `change_set` UUID, so one request, tool
call or confirmed proposal is one change set — even when it touched several
records.

A change set can be reverted as a whole
(`POST /api/v1/changesets/<uuid>/revert/`, the MCP `undo` tool, the
assistant's `propose_revert`, or Revert in a record's History tab). Reverting
restores the logged old values, soft-deletes created records and restores
deleted ones, all in one transaction and itself logged as a new change set. It
refuses merges and change sets already reverted, checks the user may change
every record, and reports conflicts instead of overwriting values that were
changed again since, unless forced. Undoing an action needs permission to run
it (an action renamed or removed since can't be undone), and only restores the
fields the action changed on its record: side effects such as sent emails or
external calls are not undone. Reverts run the model's `clean()`, as a PATCH
does. Deleted records can also be restored directly
(`POST /api/v1/<TYPE>/<pk>/restore/`).

A record's change history (`GET /api/v1/<TYPE>/<pk>/history/`, the History
tab, MCP `get_record`'s `changelog`, the assistant's `get_changelog`) needs the
`view_changelog` permission as well as seeing the record: it shows old values
and who changed what. Syncs through `update_or_create_external` log only
when something changed.

## Importing from a spreadsheet

Every list's actions menu offers **Import…** (`/<TYPE>/import`): upload an
Excel workbook (`.xlsx`, first sheet) or a CSV file whose first row names the
columns. Columns go into the field with that name or label. The person can
change that and preview the result before anything is saved. The page
re-runs the same `POST /api/v1/<TYPE>/import/` with `dry_run` on every change.

Each row goes through the same serializer, `clean()` and permission checks as a
REST create or PATCH (`crudkit_api.imports`, on top of
`crudkit_api.services`). Cells are read the way a person would type them:

- Linked records: give the ID (`AUT7`) or, when the type has a name field, the
  name. Only records the person may view are found.
- Choices: give the value or its label.
- Yes/no fields: `yes`/`no`, `true`/`false`, `1`/`0` or `x`.
- Dates: Excel dates or ISO text.

The whole import runs in one transaction. A preview rolls back and so does an
import with any bad row, so nothing is half imported. The person sees every
problem by row and column first. A successful import is one change set
labelled "Imported from <file>", so it can be undone in one go, and agents
react to it as to any other write. The commit is reported as a task with a
progress bar (see [Progress of long-running actions](#progress-of-long-running-actions)).
`CRUDKIT_IMPORT_MAX_ROWS` caps the rows (default 5000).

Existing records can be updated instead of duplicated. An import can match
rows on:

- the record's ID;
- any unique field;
- the fields a model lists for this:

```python
class Lead(BaseCrudKitModel):
    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        import_match_fields = ["email"]
```

Text is matched ignoring case. A key that matches several records is an
error. The import can update matches and create the rest, only update matches,
or skip matches. An update writes only the cells that are filled in, so a blank
cell never clears a value, and a row that changes nothing is not logged.
Importing needs the add permission, and updating also needs the change
permission on each matched record. The metadata endpoint lists a type's
`import_match_fields`.

## Approvals

Some changes should only happen once a person has agreed to them. A model
declares which:

```python
class Invoice(BaseCrudKitModel):
    @crm_action("Send reminder", requires_approval=True)
    def send_reminder(self, request): ...

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        approval_fields = ["amount", "due_date"]
```

`crudkit.authorization.requires_approval(model, action=None, fields=None)`
answers whether running `action`, or writing any of `fields`, needs approval.
The rule binds MCP clients and agents only: people using the UI or the REST
API are the approvers, so they run these actions and edit these fields
directly (the UI marks such actions with a shield). Over MCP with the `write`
scope, such a write is filed as a proposal instead of made; with the
`propose` scope every write is. Undoing a change set is held to the same rule:
if it touches an approval field or the effects of an approval-required action,
`undo` and agents only propose it
(`crudkit_api.services.revert_requires_approval`). `describe_types` reports
`requires_approval` per action and the type's `approval_fields`. The assistant
sidebar already proposes every change. Agents running without a person (source
`agent`) must call `requires_approval()` before writing and propose instead.

A proposal is an `AssistantProposal` (TYPE_ID `ASP`, in `crudkit_assistant`):
its `kind` (`action`, `patch`, `create`, `note`, `revert`), a `payload`, the
`target` record (for a create, the new record once confirmed), `source`
(`assistant`, `mcp`, `agent`) and `client`, and `status` (`pending`,
`confirmed`, `skipped`, `failed`). Users see and decide the proposals they
created, whether or not they have the Django permissions on `ASP`
(`owner_access`); superusers see all. A proposal can't be edited once filed
(its `clean()` refuses), and its target must be a record its creator can see. The Inbox's Proposals tab lists the
pending ones, sidebar and MCP alike, and the Inbox menu item counts them.

Confirm and Skip are the `confirm` and `skip` actions
(`POST /api/v1/ASP/<pk>/action/`), and the sidebar's buttons call the same
code, so a proposal decided in one place is decided everywhere; deciding is
atomic, so two Confirms (two tabs, the Inbox and the sidebar) apply it once
and the second gets 409. Confirming checks that both the confirming user and
the proposal's creator may make the change (add permission for a create,
change permission on the target otherwise), so a proposal never does more
than whoever filed it could. It runs through the same services as the REST
API and is logged as its own change set attributed to the proposal's `source`
and `client`, so it can be undone like any other change. Proposals may only
target types exposed to the assistant: not CrudKit's own proposals, runs,
change log or notes.

## Forms and the assistant

When the user has a create or edit form open (the `/<TYPE>/create` and
`/<CK-ID>/edit` pages, or an inline-create modal over them), the sidebar
reports it in the `[Screen]` block as `Open form`, with the values typed so
far; with nested modals it is the innermost one. Instead of proposing, the
assistant can then fill it in: `fill_form(fields)` sets fields in that form
and `open_create_form(type, fields)` opens a new create form, pre-filled (or
fills the create form of that type already open). Both validate like the
propose tools (field names, choices, foreign keys the user can see, add or
change permission), then send `form_fill` / `form_open` over the socket; the
browser applies the values through react-hook-form and outlines the filled
fields for a moment. Nothing is saved: the user reviews the form and clicks
Save or Create, which is an ordinary REST write. These tools are chat-only;
background agents don't get them. Opening a form over one with unsaved
changes asks the user first.

## Agents

An `Agent` (TYPE_ID `AGT`, in `crudkit_assistant`) is a set of saved
instructions that the assistant carries out in the background. Its `trigger` is
one of:

- `record_created`: a record of `model_type` was created.
- `record_changed`: a record was changed. When `watch_fields` is set, only
  changes to those fields count.
- `schedule`: `hourly`, `daily` or `weekly` after its last scheduled start (an
  interval, not a day or time of day), over the records of its view. Capped
  runs take the records the agent worked on longest ago first.
- `manual`: only when started by hand.

A `view` limits the agent to the records in that saved view, resolved as
`run_as`, the user whose permissions the agent has.

Triggers come from `ChangeLog` entries, so an agent reacts to every logged
write: the REST API, MCP, the assistant, actions and external syncs. Plain ORM
saves in project code are not logged, and so do not trigger agents. A record
with a run already queued isn't queued again, and a failing trigger is logged
without failing the write. Changes made by agents (source `agent`) never
trigger agents, and starting runs ("Run now", "Dry run") and "Revert this run"
are approval-required actions, so agents can't set each other off. Agents only
work on types exposed to the assistant, and get CrudKit's own tools only, not
a model's `assistant_tools`. Scheduled agents need the host's Celery beat to run
`crudkit_assistant.tasks.run_scheduled_agents`; see `backend/README.md`.

Each run is an `AgentRun` (`AGR`) on one record. The assistant reads the
record with its usual tools, together with the AI context for the type and the
agent's instructions, and acts only through proposals:

- **Propose mode** (the default) files the proposals with source `agent` and
  the agent's name as client. They wait in their owner's Inbox.
- **Auto mode** applies right away, as `run_as`, every proposal that doesn't
  need approval (see [Approvals](#approvals)), all in the run's change set.
  "Revert this run" undoes that change set, notes included.
- **Dry run** ("Dry run on latest matching record") saves nothing. The run's
  preview lists what the agent would have proposed.

Two guards cap the work: `max_records_per_run` and `max_runs_per_day`. After 3
failed runs in a row, the agent disables itself and says so on its feed;
re-enabling it resets the count.

Agents and runs belong to whoever created the agent: others don't see them,
and superusers see all of them. `run_as` defaults to the creator, and only
superusers may change it, or change what an agent that runs as someone else
does (its owner may still disable it); edits, merges and reverts are all held
to this. The agent's behaviour fields are `approval_fields`,
so MCP clients and other agents can only propose them. Users can ask the
sidebar for an agent ("every week, flag at-risk customers"): it proposes
creating one.

## The frontend config contract

The built SPA shell (`index.html`) is served as a Django template by
`crudkit_frontend`. Exactly two placeholders survive the Vite build (enforced
by `frontend/scripts/postbuild.mjs`):

- `{{ csrf_token }}` — rendered into `<meta name="csrf-token">`.
- `{{ crudkit_config_json }}` — the `CRUDKIT_FRONTEND_CONFIG` setting, plus
  `default_currency` from `CRUDKIT_DEFAULT_CURRENCY` and `crudkit_version`
  (the installed package version), rendered as JSON into `<script id="crudkit-config" type="application/json">` by the
  `crudkit_frontend.context_processors.crudkit_config` context processor.

At startup the SPA parses that script tag (`frontend/utils/appConfig.ts`) and
merges it over defaults: `app_name`, `org_name`, `logo_url`, `brand_color`
(any CSS color; replaces the indigo accent — buttons, selection, focus rings —
in both themes), `auth_mode` (`password` or `saml`), `storage_prefix`,
`conversation_link_pattern`, `default_currency`, `crudkit_version` (shown at
the bottom of the sidebar).
Branding is therefore a runtime concern of the host project — nothing is
compiled into the bundle.

Set `CRUDKIT_FRONTEND_LOGIN_REQUIRED = True` to redirect anonymous users to
`LOGIN_URL` instead of serving the shell; by default the shell is public and
the SPA authenticates against the API (JWT via `/api/v1/token/`, or session
auth).
