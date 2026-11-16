# Tracker write port: design

Date: 2026-11-15. Status: draft for review. Plan: `docs/plans/2026-11-15-tracker-write-port.md`.
Source: `~/.local/share/workspace/projects/workspace/audits/2026-11-15-provider-coupling.md`, §1.

## Intent (the user's binding direction)

1. "Everything is provider and technology agnostic." Cards do not depend on Jira. Each concern is
   a neutral port with adapters, and config picks the provider; the vendor name appears only in
   the adapter, its config and `ws` output.
2. "Everything in the workspace works by exchanging JSON contracts", so the tool is as good by hand
   as by AI: the declarative spec idea of AI-made charts (`vega-lite`). The author describes what
   they want in a small, versioned, validated document; deterministic code checks and executes it.

Reads already go through `ws.tracker.port.Tracker`. Writes build Jira REST requests in the core,
`[jira]` is required, `open_tracker()` hardcodes Jira, `cli`/`board_cli` build `JiraClient`,
release texts link `/browse/`, the daily has an ungated MCP path. This step puts writes behind a port.

## Goals, non-goals, anti-goals

- **Goals.** Stage A, no behaviour change: the `card-write`, `card-plan` and `card-result`
  contracts, the `Writer` port, every Jira payload, ADF, transition and REST call under
  `src/ws/tracker/jira/`, `open_tracker()` dispatching on `[tracker] kind`; existing tests pass
  unchanged, approval codes stay byte-identical. Stage B: `[tracker.jira]`, `card_url`, no daily
  MCP fallback, neutral skill words, a boundary test, an in-memory tracker on the contract tests.
- **Non-goals.** A second real tracker; the other ports of the audit; neutral priority names.
- **Anti-goals.** No change to the safety flow (preview with code and pending record, apply behind
  the gate in a separate step, 30-minute window, stop at the first failure, never retry, uncertain
  results kept aside). No Jira write and no real board in tests (`fake_jira` only).

## Approaches

- **Port shape: one `Writer` (picked)**, extending the read `Tracker`, plans a batch and runs it:
  batch rules (a link asked twice across drafts) and the digest need the whole batch, and one
  session serves plan, guard and send. A port per operation would be six classes sharing session,
  project and people, with no home for batch rules.
- **Contract form: JSON Schema files and a small stdlib validator (picked).** Schemas in
  `src/ws/data/contracts/*.schema.json` are readable by people, models and other tools; documents
  are plain dicts at the port. The validator is the shared `ws.contracts` (observe plan, wave 1):
  `validate(document, schema_name) -> list[str]` and `load_schema(name) -> dict`, checking required
  keys, types, enums, `additionalProperties: false` and `version`; no `jsonschema` dependency.
  Dataclasses with a schema exporter would make the schema generated output, make the model read
  Python to learn the shape, and cost more code than the validator.

## The contracts

Every document has `"$schema"` (the schema name) and `"version"` (an integer); a reader refuses a
version it does not know. An added optional key keeps the version; a rename, removal or new meaning
bumps it. `ws card check` runs the same `ws.contracts.validate` the executor runs.

### `card-write` (version 1): one change to one card

The draft (`+++` TOML front matter, Markdown body, a create's first `# ` line as title) maps 1:1
onto it; `ws card show DRAFT` prints it. Keys by `op` (required in bold):

| op | keys |
|---|---|
| `create` | **`type`** (`task`, `bug`, `hotfix`, `improvement`, `feature`, `epic`, `initiative`), **`priority`** (a priority name of the tracker), **`title`**, `body`, `epic`, `parent`, `assignee`, `reporter`, `sprint` (`"active"`, `"next"` or the exact name of an open sprint), `due`, `item` |
| `edit` | **`key`**, `title`, `priority`, `start`, `due`, `epic`, `type`, `assignee`, `reporter`, `parent`, `sprint` (`"active"`, `"next"`, `"backlog"` or the exact name of an open sprint), `body` (new description) |
| `move` | **`key`**, `to` (a status name of the tracker); Stage B adds `status` (`todo`, `in_progress`, `review`, `validation`, `ready_deploy`, `blocked`, `done`, `cancelled`); exactly one |
| `comment` | **`key`**, **`body`** |
| `worklog` | **`key`**, **`time`** (`2h`, `30m`, `1h 30m`), `day`, `body` (worklog comment) |
| `link` | **`key`**, at least one of `blocks`, `blocked_by`, `relates` (lists of card keys) |

People are aliases (dev ids of `[people]`), never tracker accounts; dates `YYYY-MM-DD`; bodies Markdown.

`sprint` takes `"active"` (the board's one active sprint), `"next"` (its earliest future sprint),
`"backlog"` (out of every open sprint; edit only, a create without `sprint` already goes there)
or the exact name of an active or future sprint. Task 19 added all but `"active"` at the user's
request on 16/11.

```json
{"$schema": "card-write", "version": 1, "op": "create", "type": "improvement",
 "priority": "Medium", "title": "[FRONT] Tarefa de exemplo", "epic": "TS-100", "assignee": "dev-b",
 "sprint": "next", "due": "2026-11-20", "body": "## Contexto\n...\n\n## Pronto quando\n- ..."}
```

### `card-plan` (version 1): what preview shows, the code digests and apply executes

- `tracker` (kind), `target` (the instance the plan is bound to; Jira: the site, no trailing `/`),
  `today` (the day in the user's tracker time zone, the one the rules used);
- `steps[]`, one per draft in order: `draft` (`path`, `sha256`), `op`, `card` (key or null),
  `title`, `preview` (PT-BR lines), `warnings`, `problems`, `before` (the card state the preview
  showed), `native` (the calls: `method`, `path`, `body`);
- `summary` (the PT-BR lines the person approves) and `code`, both added by the core.

`native` is opaque to the core: it shows, digests and replays it, and the adapter guards it. The
digest material is frozen with today's key names, so codes survive the move: `{"site": target,
"requests": every native call in order, "before": [steps[].before], "summary": summary}` through
`approval.digest`. Changing it is a new contract version.

```json
{"$schema": "card-plan", "version": 1, "tracker": "jira", "target": "https://example.atlassian.net",
 "today": "2026-11-15", "steps": [{"draft": {"path": "<drafts>/m.md", "sha256": "..."}, "op": "move",
 "card": "TS-101", "title": null, "preview": ["Mover o card TS-101", "..."], "warnings": [], "problems": [],
 "before": {"status": "A fazer"}, "native": [{"method": "POST", "path": "/rest/api/3/issue/TS-101/transitions",
 "body": {"transition": {"id": "21"}}}]}], "summary": ["[1/1] Mover card TS-101 (m.md)", "..."], "code": "0123456789ab"}
```

The pending record `cards/pending/<code>.json` keeps its keys and meaning (`code`, `created_at`,
`site`, `today`, `sid`, `drafts`, `requests`, `before`, `summary`), built from the plan by one pure
function; the gate reads only `summary` (non-empty list of strings). `preview --json` prints the plan.

**`card-result` (version 1), what apply did:** `steps[]` with `draft`, `status` (`applied`,
`failed`, `uncertain`, `not_sent`), `sent` (calls of the step that succeeded), `created` (new key
or null), `url` (`card_url` or null), `error`. The core prints its PT-BR lines from it, as today.

## The port

`ws.tracker.port.Writer` extends `Tracker` with `name` (`"Jira"`, for PT-BR lines such as "Gravar
no Jira?"), `target`, `capabilities` (the existing `CAPABILITIES` names) and:
- `plan(entries) -> dict`: each entry `{source, write, problems}` (path and digest, the
  `card-write` document or null, parse problems); returns `card-plan` without `summary` and `code`;
- `guard(calls) -> str | None`, `send(call) -> object`, `created_key(reply) -> str | None`,
  `find_hint(title) -> str` (where to look for an uncertain create; Jira: a JQL line);
- `apply(plan, send=None) -> Iterator[dict]`: `card-result` steps one at a time, stopping at the
  first failure; one shared loop in `ws.tracker.write` gives every tracker the same rules, and the
  core passes its `_send`, the one function every write leaves by;
- `render_body(markdown) -> object` (raises `ValueError` with a `line`), `card_url(key) -> str`.

`open_tracker()` imports the package `ws.tracker.ADAPTERS[kind]` (`{"jira": "ws.tracker.jira"}`):
`open_tracker(config)` plus offline `card_url_template(settings)` and `task_from_listing(card,
settings)`. `ws.tracker.errors`: `TrackerSetup` (exit 2), `TrackerError` (`status`, `uncertain`;
exit 3), which `JiraError` subclasses.

## The Jira adapter

`src/ws/tracker/jira/`: `client.py` (was `ws/jira.py`), `adf.py`, `rules.py` (was `cardrules`),
`discover.py`, `adapter.py` (`JiraTracker`, read and write), `writer.py` (session, plan, guard,
send, `ws card epics`), Stage B `settings.py` (`JiraConfig`). Stage A keeps the old paths as
aliases (`sys.modules[__name__] = new_module`) so tests patching `cardrules.check` still work.

| contract | Jira |
|---|---|
| `type`; `epic`, `parent`; people | type id from `types`, level from `hierarchyLevel`; `fields.parent`; `accountId` from `[people.<dev id>] ids.jira` |
| `sprint`, `start`, `due` | the sprint id in `sprint_field` (`"active"`: the read of active sprints; `"next"` and a name: the board's active and future sprints), `null` for `"backlog"`; `start_date_field`; `duedate` |
| `to` / `status` | the one transition whose destination folds equal / maps to it by `status_overrides`, then category |
| `body` | ADF (`adf.to_adf`); nodes `ws` cannot write back refuse an edit |
| link kinds | link type names from `links`; `blocked_by` is `blocks` reversed |
| `time`, `day`; `card_url` | `timeSpent`, `started` 09:00 in the user's time zone; `{site}/browse/{key}` |

## Config migration (Stage B)

`[tracker] kind = "jira"` and `[tracker.jira]` (was `[jira]`, same keys and subtables). The core
keeps `tracker_kind` and the raw table; the adapter parses it (`check_site` moves along). An old
`[jira]` without `[tracker.jira]` still loads, with one stderr line ("config.toml: [jira] is
deprecated; move it under [tracker.jira]"); both at once is `ConfigInvalid`; `kind` may be absent
only with the old table. Tokens stay `ws config token <kind>`; `[people] ids` are keyed by kind.

## Other Stage B changes

- Release and board use `card_url_template` and `task_from_listing` ("not a card key"). `move`
  takes the neutral `status`; drafts may also be `.json` `card-write` documents.
- The daily uses `ws task list` only: on failure the standup has no cards and says "Tracker
  indisponível". The MCP fallback is deleted; the report key `jira` becomes `tracker`.
- `skills/card/SKILL.md` says "the tracker", quotes `Gravar no <tracker>?` (name from `ws` output);
  Jira specifics (site shape, JQL, token) go to `skills/card/references/jira.md`.
- `tests/test_tracker_boundary.py`: no module of `src/ws` or `hooks` outside `ws/tracker/` imports
  `ws.tracker.jira*`, `adf` or `jira`, or holds `/rest/api` or `/browse/`. `FakeTracker`
  (`tests/fake_tracker.py`) gains a write side, kind `memory`, and passes Jira's contract tests.

## Privacy

Examples and fixtures use placeholders (`example.atlassian.net`, `acc-me`, `dev-b`, `TS-1xx`,
made-up titles); anything copied from a real board goes through `ws mask` first. Plans and pending
records carry account ids and card text: they stay in `~/.local/share/workspace/cards/` (mode 600),
never in the repo; `ws card show` and `--json` print to stdout only.

## Left for later

In the audit's order: 2 code host (`release/github.py`, the standup's GraphQL); 3 gate vendor
registry (`mcp_rules`, `bootstrap` tool lists, the "Grava no Jira" titles of `bash_rules`, which
could read the tracker name from the pending record); 4 config store and deploy manifest; 5
post-deploy probe (Datadog); 6 migration chain (Alembic). Also: the tracker-free card rules (title
prefix, sections, time) out of `jira/rules.py`, and a neutral priority scale.
