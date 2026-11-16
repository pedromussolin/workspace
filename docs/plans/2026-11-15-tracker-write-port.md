# Tracker write port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** every tracker write of `ws` goes through a neutral `Writer` port that takes versioned
JSON contracts (`card-write` in, `card-plan` and `card-result` out); Jira becomes one adapter
under `src/ws/tracker/jira/`, picked by `[tracker] kind`; the approval flow is untouched.

**Architecture:** Stage A (Tasks 1–9) moves code with no behaviour change: golden pins first, then
the schemas and the neutral module `ws.tracker.write`, the errors and the port, the Jira modules
moved under `ws/tracker/jira/` with the old paths kept as `sys.modules` aliases, `ws card` on the
port, and the CLI through `ws.tracker`. Stage B (Tasks 10–18) changes behaviour on purpose:
`[tracker.jira]` config, `card_url_template`, the daily without the MCP fallback, neutral skill
words, move by neutral status, JSON drafts, an in-memory tracker on the contract tests, and the
removal of the aliases with a boundary test.

**Tech Stack:** Python 3.12+, standard library only at runtime; `uv`, `pytest`, `ruff`.

**Spec:** `docs/specs/2026-11-15-tracker-write-port-design.md` (all sections). Starts from `main`
after wave 1 of the observe plan is merged: it builds the shared validator this plan consumes,
`ws.contracts.validate(document, schema_name) -> list[str]` and
`ws.contracts.load_schema(name) -> dict`, reading `src/ws/data/contracts/<name>.schema.json`.
This plan never creates or edits `ws.contracts`; it only adds schema files.

## Global Constraints

- Runtime code: standard library only. Run everything with `uv run` (`uv run pytest -q`,
  `uv run ruff check`, `uv run ruff format --check`).
- Names in English (modules, flags, JSON keys, `problems`); PT-BR only in lines shown to people
  (preview, prompts, apply report, the daily). In Stage A every PT-BR line stays byte-identical.
- Stage A changes no behaviour: every existing test passes **unchanged** after each wave merge,
  and the golden file of Task 1 passes unchanged through Tasks 2–9. A Stage A task that needs to
  edit an existing test is wrong: stop and report.
- The safety flow never changes: draft, `ws card preview` (preview, code, pending record),
  `ws card apply --approve CODE` in a separate step behind the gate, 30-minute window, stop at the
  first failure, never retry, uncertain results kept aside.
- Tests: the `fake_jira` HTTP fixture and the `world` fixture of `tests/test_card.py` only; fake
  accounts `acc-me`, `acc-other`; site `https://example.atlassian.net` where no server is needed;
  fake titles; no network, no real Jira, no real names. Never run a Jira write; never read
  `~/.config/workspace/credentials`.
- Moving a file: `git mv` first (history), then edit; the old path becomes an alias module
  (`import sys`; `from ws.tracker.jira import client`; `sys.modules[__name__] = client`, with a
  docstring "Old path of ..., removed in Task 18").
- `src/ws/tracker/jira/__init__.py` imports its submodules lazily, inside its functions:
  `userconfig` reaches `client` through that package (`check_site`), so a top-level import of
  `adapter` there (which imports `userconfig`) is an import cycle.
- Docs, skills and messages add no capitalized word new to the repo (the new-word hook); code
  reuses existing names (`Writer`, `JiraTracker`, `FakeTracker`, `TrackerError`, `TrackerSetup`).
- Commits: prefix `feat:`, `fix:`, `test:`, `docs:` or `chore:`, PT-BR, at most 72 characters, no
  task ID, no `Co-Authored-By`; `git diff` before each message. Each task commits in its own
  worktree branch; the controller merges, runs the full suite and pushes.

## Review Focus

1. The pending record `cards/pending/<code>.json` keeps its nine keys, and the gate's `_pending_summary` still shows its `summary` (Tasks 1, 2, 7).
2. An old `[jira]` config still loads, with exactly one deprecation line per process and no other output change; both tables at once is refused (Task 10).
3. The approval code of the same drafts and the same fake Jira is byte-identical before and after Stage A (golden of Task 1; Tasks 2, 5, 7).
4. ADF round-trips: `render_body` equals `to_adf`, preview lines from `adf_text` are unchanged, and an edit over foreign nodes is still refused (Tasks 4, 5, 7).
5. The daily with a neutral fallback: `ws task list` exit 1 or 2 falls back to the configured tracker's MCP through `references/<kind>.md`; with both failing, a standup without cards and "Tracker indisponível"; no vendor call is named in `SKILL.md` (Task 11, changed by the user on 16/11).

## Parallel waves

Disjoint files inside a wave; the suite is green after each wave merge.

- Stage A
  - Wave A0 (1 agent): Task 1 (golden pins on current `main`).
  - Wave A1 (3 agents): Task 2 (schemas and `ws.tracker.write`), Task 3 (errors, `Writer`,
    dispatch), Task 4 (leaf modules moved: client, adf, discover).
  - Wave A2 (2 agents): Task 5 (rules moved, `jira/writer.py`), Task 6 (adapter moved, side reads).
  - Wave A3 (2 agents): Task 7 (`ws card` on the port), Task 8 (`ws.tracker` facade, board).
  - Wave A4 (1 agent): Task 9 (CLI through the tracker; `ws card show`, `preview --json`).
- Stage B
  - Wave B1 (4 agents): Task 10 (config), Task 11 (daily), Task 12 (card skill words), Task 13
    (memory tracker and contract tests).
  - Wave B2 (4 agents): Task 14 (release links), Task 15 (callers off `config.jira`), Task 16
    (move by neutral status), Task 17 (JSON drafts).
  - Wave B3 (1 agent): Task 18 (aliases removed, boundary tests).

---

## Stage A: no behaviour change

### Task 1: Golden pins of the approval flow

**Files:**
- Create: `tests/test_card_golden.py`, `tests/golden/card-preview.txt`, `tests/golden/card-pending.json`

**Interfaces:** none new. Import the `world` fixture and the draft helpers from `tests/test_card.py`
(no change to that file). One batch of seven drafts: create, create of an epic, edit (priority and
due), move to "Em Andamento" with an empty start date, comment with a list and code, worklog with a
comment, link (`blocks` and `relates`). Time frozen as the existing tests freeze it. Temporary
paths in the outputs are replaced by `<drafts>` before comparing.

- [ ] **Step 1: Write the tests:**
  - `test_golden_codes_per_operation` (each draft alone and the batch: the code equals a literal);
  - `test_golden_pending_record` (keys exactly `code`, `created_at`, `site`, `today`, `sid`,
    `drafts`, `requests`, `before`, `summary`; `requests`, `before`, `summary`, `site`, `today`
    equal `tests/golden/card-pending.json`);
  - `test_golden_preview_text` (the whole stdout of the batch preview equals `card-preview.txt`);
  - `test_golden_apply_report` (apply of the batch: the PT-BR lines and the writes seen by the fake
    server, in order, equal literals).
- [ ] **Step 2: Run** `uv run pytest tests/test_card_golden.py -q` on current `main`, paste the
  literals and files from the first run, run again — expected: PASS (this pins today's behaviour).
- [ ] **Step 3: Run** `uv run pytest -q`; `uv run ruff check` clean.
- [ ] **Step 4: Commit** `test: fixa códigos de aprovação, prévia e registro do ws card`.

### Task 2: The contracts and the neutral write module

**Files:**
- Create: `src/ws/data/contracts/card-write.schema.json`, `src/ws/data/contracts/card-plan.schema.json`,
  `src/ws/data/contracts/card-result.schema.json`, `src/ws/tracker/write.py`
- Test: `tests/test_tracker_write.py`

**Interfaces:**
- Schemas (draft 2020-12 subset that `ws.contracts` supports): `card-write` keys per `op` as in the
  spec table (one `oneOf` branch per op, `additionalProperties: false`, `version` const 1; `move`
  has `to` only, `status` comes in Task 16); `card-plan` and `card-result` as in the spec.
- `ws.tracker.write.VERSION = 1`; `SCHEMAS = ("card-write", "card-plan", "card-result")`.
- `to_document(draft: Draft) -> dict`: `$schema`, `version`, `op`, every value of `draft.values`
  copied by name (dates as `YYYY-MM-DD`, lists as lists; no per-key code), `title` when the draft
  has one, `body` when it has non-blank text.
- `from_document(document: dict) -> Draft`: the inverse (`sha256` of the canonical JSON).
- `check_document(document: dict) -> list[str]`: unknown `$schema` or `version` first, then
  `ws.contracts.validate(document, document["$schema"])`.
- `digest_material(plan: dict) -> dict` (`site`, `requests`, `before`, `summary`, exactly as
  `card.approval_code` builds them) and `plan_code(plan: dict) -> str` (`approval.digest`).
- `pending_record(plan: dict, *, created_at: str, sid: int) -> dict` (the nine keys).
- `apply_steps(writer, plan: dict, send) -> Iterator[dict]`: for each step, `send(call)` for each
  `native` call; yields one `card-result` step per step; a `TrackerError` yields `failed` (or
  `uncertain` when `error.uncertain`) and stops; any other exception yields `uncertain` with
  `"{type}: {message}"` and stops; `created` is `writer.created_key(first reply)` for `create`.
  Import `TrackerError` from `ws.tracker.port` (Task 3 keeps it there as a re-export).

- [ ] **Step 1: Write the failing tests:** `test_draft_to_document_for_each_op` (parametrized over
  the six ops), `test_document_round_trips_to_the_same_draft_values`,
  `test_documents_of_each_op_validate`, `test_schema_refuses_unknown_key_bad_enum_and_version`,
  `test_digest_material_has_the_frozen_keys`, `test_plan_code_equals_card_approval_code`,
  `test_pending_record_has_the_nine_keys`, `test_apply_steps_stops_at_the_first_failure`,
  `test_apply_steps_marks_other_errors_uncertain`, `test_apply_steps_sends_each_native_call_once`.
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_write.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `feat: contratos card-write, card-plan e card-result`.

### Task 3: Errors, the `Writer` protocol and the dispatch

**Files:**
- Create: `src/ws/tracker/errors.py`
- Modify: `src/ws/tracker/port.py`, `src/ws/tracker/__init__.py`, `src/ws/tracker/jira_adapter.py`
- Test: `tests/test_tracker_port.py` (new tests only)

**Interfaces:**
- `errors.TrackerSetup(Exception)`; `errors.TrackerError(Exception)` with
  `__init__(message, status: int | None = None, uncertain: bool = False)`; `port` re-exports both.
- `port.Writer(Tracker, Protocol)`: `name`, `target`, `plan(entries)`, `guard(calls)`,
  `send(call)`, `apply(plan, send=None)`, `created_key(reply)`, `find_hint(title)`,
  `render_body(markdown)`, `card_url(key)` (spec, "The port").
- `ws.tracker.ADAPTERS = {"jira": "ws.tracker.jira_adapter"}`; `KNOWN_KINDS = tuple(ADAPTERS)`.
- `port.open_tracker()`: config errors and `UnknownTracker` become `TrackerSetup`; then
  `importlib.import_module(ADAPTERS[kind]).open_tracker(config)`.
- `jira_adapter.open_tracker(config) -> JiraTracker`: today's body (`card.session`).

- [ ] **Step 1: Write the failing tests:** `test_open_tracker_dispatches_on_the_configured_kind`
  (a stub module put in `sys.modules` and in `ADAPTERS`), `test_open_tracker_unknown_kind_is_a_setup_problem`,
  `test_tracker_error_keeps_status_and_uncertain`, `test_writer_protocol_lists_the_port_members`.
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_port.py -q` — expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `feat: porta Writer e despacho do tracker pelo kind`.

### Task 4: The leaf Jira modules move under `tracker/jira/`

**Files:**
- Create: `src/ws/tracker/jira/__init__.py` (docstring only), `src/ws/tracker/jira/client.py`
  (from `src/ws/jira.py`), `src/ws/tracker/jira/adf.py` (from `src/ws/adf.py`),
  `src/ws/tracker/jira/discover.py` (from `src/ws/tracker/jira_discover.py`)
- Modify (to aliases): `src/ws/jira.py`, `src/ws/adf.py`, `src/ws/tracker/jira_discover.py`
- Test: `tests/test_tracker_jira_paths.py`

**Interfaces:** the moved modules keep every name; their imports point at the new paths. The old
paths are aliases, so `ws.jira is ws.tracker.jira.client`.

- [ ] **Step 1: Write the failing tests:** `test_old_paths_are_the_moved_modules` (three
  identities), `test_patching_through_an_old_path_reaches_the_new_module` (monkeypatch
  `ws.adf.to_adf`; `ws.tracker.jira.adf.to_adf` is the patch).
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_jira_paths.py -q` — expected: FAIL.
- [ ] **Step 3: Implement** (`git mv`, then the alias files).
- [ ] **Step 4: Run** `uv run pytest -q` (`test_adf.py`, `test_jira.py`, `test_tracker_discover.py`
  unchanged); ruff clean.
- [ ] **Step 5: Commit** `chore: move cliente, ADF e discover do Jira para tracker/jira`.

### Task 5: The card rules move and the Jira writer functions

**Files:**
- Create: `src/ws/tracker/jira/rules.py` (from `src/ws/cardrules.py`), `src/ws/tracker/jira/writer.py`
- Modify: `src/ws/cardrules.py` (alias), `src/ws/card.py` (only: `session` and `SetupNeeded`
  become re-exports of `writer.session` and `TrackerSetup`)
- Test: `tests/test_tracker_jira_writer.py`

**Interfaces** (`writer.py`, functions over `settings` and `client`; messages byte-identical):
- `session(needed: set[str]) -> tuple[JiraConfig, JiraClient]` (moved from `card.session`, raises
  `TrackerSetup`); `needed_keys(writes: list[dict]) -> set[str]` (from `card._needed_keys`, over
  `card-write` documents).
- `plan(client, settings, entries: list[dict], *, people, identity_email, now) -> dict`
  (`entries` as in the spec: `source`, `write`, `problems`): `rules.Context.load`, then
  `rules.check(context, write.from_document(entry["write"]))` per entry (called through the module,
  so a patch of `cardrules.check` applies), the batch link problems (from
  `card._batch_link_problems`), each `Verdict` turned into a `card-plan` step (`native` =
  `requests`, `card` = `resolved["card"]["key"]`, `today` from the first verdict). An entry with no
  `write` becomes a step with its problems only.
- `guard(project: str, calls: list[dict]) -> str | None` (from `card.guard`).
- `send(client, call) -> object`; `created_key(reply) -> str | None`;
  `find_hint(project, title) -> str` (`"use esta JQL: ..."`, from `card._jql_for`).
- `render_body(markdown) -> dict` (`adf.to_adf`); `card_url(site, key) -> str`;
  `card_url_template(settings) -> str` (`"{site}/browse/{key}"` with the site filled in).
- `epics(client, settings) -> list[dict]` (body of `card.run_epics`, same JSON entries).

- [ ] **Step 1: Write the failing tests:** `test_plan_steps_carry_the_rules_requests` (each golden
  draft: `native` equals `rules.check(...).requests`), `test_plan_refuses_a_link_asked_twice_in_a_batch`,
  `test_plan_of_an_unparsed_entry_keeps_its_problems`, `test_guard_accepts_known_shapes_and_refuses_others`,
  `test_find_hint_is_the_old_jql_line`, `test_render_body_is_to_adf`, `test_card_url_and_template`,
  `test_epics_lists_open_epics_and_initiatives`, `test_old_cardrules_path_is_the_rules_module`.
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_jira_writer.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` (golden included); ruff clean.
- [ ] **Step 5: Commit** `feat: regras e escrita do Jira atrás do adaptador`.

### Task 6: The adapter moves; side reads through it

**Files:**
- Create: `src/ws/tracker/jira/adapter.py` (from `src/ws/tracker/jira_adapter.py`)
- Modify: `src/ws/tracker/jira_adapter.py` (alias), `src/ws/tracker/jira/__init__.py`,
  `src/ws/tracker/jira/client.py`, `src/ws/tracker/__init__.py` (`ADAPTERS["jira"] = "ws.tracker.jira"`)
- Test: `tests/test_tracker_jira_adapter.py`

**Interfaces:**
- `client.JiraError` subclasses `TrackerError` (same `status`, `uncertain`).
- `ws.tracker.jira` exports `open_tracker(config)`, `JIRA_CAPABILITIES`,
  `task_from_listing(card: dict, settings) -> Task` (`client.task_from_card` with site and overrides).
- `JiraTracker` gains `list_tasks(since: date, role: str) -> dict` (the exact `ws task list` JSON),
  `discover_toml() -> str`, `account_for(email: str) -> str | None` (today's `ws people add` lookup).

- [ ] **Step 1: Write the failing tests:** `test_jira_error_is_a_tracker_error`,
  `test_open_tracker_returns_a_jira_tracker`, `test_list_tasks_is_the_task_list_json`,
  `test_discover_toml_through_the_adapter`, `test_account_for_an_email`,
  `test_task_from_listing_needs_no_session`, `test_old_jira_adapter_path_is_the_adapter`.
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_jira_adapter.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `chore: adaptador Jira em tracker/jira com leituras auxiliares`.

### Task 7: `ws card` on the port

**Files:**
- Modify: `src/ws/card.py`, `src/ws/tracker/port.py`, `src/ws/tracker/jira/adapter.py`,
  `src/ws/tracker/jira/__init__.py`
- Test: `tests/test_card_port.py`

**Interfaces:**
- `port.open_writer(entries: list[dict]) -> Writer` (dispatch as `open_tracker`; the adapter
  package's `open_writer(config, entries)` computes its own needed config keys).
- `JiraTracker` implements `Writer`: `name = "Jira"`, `target` (site without `/`), and the
  members delegating to `writer.py`; `apply` is `write.apply_steps`.
- `card.py` keeps its public names and test hooks: `Loaded`, `Preview`, `Plan` (now over a
  `card-plan` document), `approval_code`, `guard` and `_needed_keys` (re-exports until Task 18),
  `_send(writer, call)` (returns `writer.send(call)`; the one call site of `send`, passed to
  `writer.apply`). New: `preview_plan(argument) -> dict` (the `card-plan` document with `summary`
  and `code`) and `show(path) -> dict` (the `card-write` document of a draft).
- PT-BR lines take the tracker name from `writer.name` ("nada foi enviado ao Jira", "Gravar no
  Jira? [s/N]", "confira no Jira", "o Jira recusou"), so they stay byte-identical.

- `load` turns each parsed draft into `write.to_document(draft)` and runs `write.check_document`
  on it (the validator the executor uses); a draft `carddraft` accepts always passes, so no
  message changes.

- [ ] **Step 1: Write the failing tests:** `test_every_accepted_draft_validates_as_card_write`
  (the drafts of the existing card tests), `test_preview_plan_validates_as_card_plan`,
  `test_preview_plan_code_is_the_pending_code`, `test_show_prints_the_card_write_of_a_draft`,
  `test_apply_result_validates_as_card_result`, `test_card_core_builds_no_jira_request` (no
  `/rest/api` string left in `card.py`).
- [ ] **Step 2: Run** `uv run pytest tests/test_card_port.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.** Order inside `_approve` stays the same: record, window, code, session
  id, drafts, rebuilt plan, code again, guard, confirm, delete the record, send.
- [ ] **Step 4: Run** `uv run pytest -q` — every `test_card*.py`, `test_card_golden.py` and
  `test_gate_bash.py` unchanged and green; ruff clean.
- [ ] **Step 5: Commit** `feat: ws card usa a porta Writer`.

### Task 8: The `ws.tracker` facade and the board

**Files:**
- Modify: `src/ws/tracker/__init__.py`, `src/ws/board_cli.py`
- Test: `tests/test_tracker_facade.py`

**Interfaces** (dispatch on `config.tracker_kind`, no adapter import at module top):
- `ws.tracker.list_tasks(since, role) -> dict`, `discover_toml() -> str`,
  `account_for(email) -> str | None` (through `port.open_tracker()`);
- `ws.tracker.task_from_listing(card: dict, config) -> Task` and
  `ws.tracker.status_overrides(config) -> dict[str, str]` (offline).
- `board_cli.py` uses them instead of `jira.task_from_card` and `config.jira.status_overrides`;
  its messages stay as they are (Task 15 changes them).

- [ ] **Step 1: Write the failing tests:** `test_facade_dispatches_list_tasks`,
  `test_facade_task_from_listing_is_offline`, `test_facade_unknown_kind_is_a_setup_problem`.
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_facade.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` (`test_board_cli.py` unchanged); ruff clean.
- [ ] **Step 5: Commit** `feat: fachada do tracker para listagens e quadro`.

### Task 9: The CLI through the tracker

**Files:**
- Modify: `src/ws/cli.py`
- Test: `tests/test_cli_tracker.py`

**Interfaces:** `ws task list`, `ws tracker discover` and `ws people add` call the facade of Task 8 and catch `TrackerSetup` (exit 2) and `TrackerError` (exit 1, as today); no
`jira.` name left in `cli.py`. New: `ws card show DRAFT` (prints `card.show`) and
`ws card preview --json` (prints `card.preview_plan`; same pending record and code as without it).

- [ ] **Step 1: Write the failing tests:** `test_task_list_output_unchanged_through_the_facade`,
  `test_card_show_prints_a_valid_card_write`, `test_preview_json_prints_a_valid_card_plan`,
  `test_preview_json_writes_the_same_pending_record`, `test_cli_names_no_jira_module`.
- [ ] **Step 2: Run** `uv run pytest tests/test_cli_tracker.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` (end of Stage A: every old test and the golden green,
  unchanged); ruff clean.
- [ ] **Step 5: Commit** `feat: comandos do ws leem o tracker pela fachada`.

## Stage B: neutral config, links and words

### Task 10: Neutral tracker config

**Files:**
- Create: `src/ws/tracker/jira/settings.py`
- Modify: `src/ws/userconfig.py`, `src/ws/tracker/jira/__init__.py`, `tests/conftest.py`, and the
  tests that write a `[jira]` table, switched to `[tracker.jira]` (`git grep -l '\[jira' tests`:
  `item_helpers.py`, `release_helpers.py`, `test_board_cli.py`, `test_boardconfig.py`,
  `test_bootstrap.py`, `test_card.py`, `test_card_create.py`, `test_card_link.py`,
  `test_deploycheck.py`, `test_deploycheck_cli.py`, `test_jira.py`, `test_people_cli.py`,
  `test_release_settings.py`, `test_standup.py`, `test_taskstatus.py`, `test_tracker_discover.py`,
  `test_tracker_port.py`); not `test_standupreport.py`, which Task 11 owns
- Test: `tests/test_userconfig.py` (its old-table cases stay as the compat tests)

**Interfaces:**
- `jira.settings.JiraConfig` (moved; `userconfig` re-exports it until Task 18) and
  `parse_settings(table: dict, path: Path) -> JiraConfig` (with `check_site` and today's messages,
  `jira.` replaced by `tracker.jira.`).
- `UserConfig` gains `tracker_settings: object` (parsed by `ADAPTERS[kind].parse_settings`);
  `UserConfig.jira` stays as a property returning it when the kind is `jira` (removed in Task 18).
- Old `[jira]` without `[tracker.jira]`: loaded, and one stderr line per process
  `config.toml: [jira] is deprecated; move it under [tracker.jira]`. Both: `ConfigInvalid`.
  No `[tracker] kind` and no `[jira]`: `ConfigInvalid` naming `[tracker] kind`.

- [ ] **Step 1: Write the failing tests:** `test_tracker_jira_table_loads`,
  `test_old_jira_table_loads_with_one_deprecation_line`, `test_both_jira_tables_are_refused`,
  `test_kind_is_required_without_the_old_table`, `test_unknown_kind_is_refused`,
  `test_jira_settings_refuse_a_site_outside_atlassian_cloud`.
- [ ] **Step 2: Run** `uv run pytest tests/test_userconfig.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `feat: config [tracker.jira] com leitura do [jira] antigo`.

### Task 11: The daily without the MCP fallback

**Files:**
- Modify: `skills/daily/SKILL.md`, `skills/daily/references/detailed.md`, `src/ws/standupreport.py`,
  `tests/test_standupreport.py` (also switched to `[tracker.jira]`)
- Test: `tests/test_daily_skill.py`

**Interfaces:** step 3 "Fallback: the Atlassian MCP" is deleted; when `ws task list` exits 1 or 2
the skill goes to the report without `--cards` and says "Tracker indisponível" (setup hint for
exit 2 kept, with `ws config token <kind>`). The report key `jira` becomes `tracker` (bool); the
skill and `references/detailed.md` read `tracker` and say "Tracker indisponível: sem status nem
títulos dos cards". The description says "from git, GitHub and the tracker".

- [ ] **Step 1: Write the failing tests:** `test_daily_names_no_atlassian_tool`
  (no `getAccessibleAtlassianResources`, `searchJiraIssuesUsingJql`, `atlassianUserInfo`, `cloudId`,
  `Atlassian`), `test_daily_reads_the_tracker_key`, `test_report_has_tracker_key_not_jira`.
- [ ] **Step 2: Run** `uv run pytest tests/test_daily_skill.py tests/test_standupreport.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `feat: daily sem fallback do MCP, só pelo ws task list`.

### Task 12: Neutral words in the card skill

**Files:**
- Create: `skills/card/references/jira.md`
- Modify: `skills/card/SKILL.md`, `skills/card/references/card-rules.md`
- Test: `tests/test_card_skill_words.py`

**Interfaces:** `SKILL.md` says "the tracker"; the prompt is quoted as `Gravar no <tracker>? [s/N]`
("the name `ws` prints"); "Nothing is written through a tracker MCP, ever"; exit codes 2 and 3 in
neutral words. Site shape, JQL hint, `ws config token jira`, the epic screen note go to
`references/jira.md`, linked once. Mentions `ws card show`.

- [ ] **Step 1: Write the failing tests:** `test_card_skill_names_no_vendor` (`SKILL.md` and
  `card-rules.md` free of `Jira`, `Atlassian`, `JQL`, `atlassian.net`),
  `test_card_skill_links_the_jira_reference`, `test_card_skill_stays_under_500_lines`.
- [ ] **Step 2: Run** `uv run pytest tests/test_card_skill_words.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `docs: skill /card em palavras neutras do tracker`.

### Task 13: The memory tracker and the contract tests

**Files:**
- Modify: `tests/fake_tracker.py`
- Test: `tests/test_writer_contract.py`

**Interfaces:** `FakeTracker(kind="memory", ...)` keeps its read side and gains the `Writer`
members over its own dict of cards: `plan` builds `native` calls such as
`{"method": "SET", "path": "cards/TS-101", "body": {...}}`, refuses unknown cards and a lacking
capability as `problems`; `send` applies them; `render_body` returns the Markdown; `card_url`
gives `memory://TS-101`. Registered through `monkeypatch.setitem(ADAPTERS, "memory", ...)`.

- [ ] **Step 1: Write the tests** (parametrized over `jira` with the `world` fixture and `memory`):
  `test_plan_is_a_valid_card_plan`, `test_same_entries_give_the_same_code`,
  `test_unknown_card_is_a_problem_not_a_call`, `test_apply_yields_valid_card_result_steps`,
  `test_apply_stops_at_the_first_failure`, `test_render_body_refuses_with_a_line_or_passes`,
  `test_card_url_contains_the_key`, `test_capabilities_are_known_names`, and
  `test_preview_and_apply_run_on_the_memory_tracker` (the CLI flow end to end, kind `memory`).
- [ ] **Step 2: Run** `uv run pytest tests/test_writer_contract.py -q` — expected: the memory
  cases FAIL until the fake gains the write side.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `test: tracker em memória passa nos testes de contrato`.

### Task 14: Release links through `card_url_template`

**Files:**
- Modify: `src/ws/tracker/__init__.py` (`card_url_template(config=None) -> str`, offline),
  `src/ws/release/settings.py`, `src/ws/release/folder.py`, `src/ws/release/rules.py`,
  `tests/release_helpers.py`, `tests/test_release_settings.py`, `tests/test_release_folder.py`,
  `tests/test_release_rules.py`

**Interfaces:** `ReleaseConfig.site` becomes `card_url_template: str` (with `{key}`);
`tasks_block(tasks, template)`; the rules check `template.format(key=key) in body`. The release
reads the tracker through `ws.tracker`, not `load_table("jira")`.

- [ ] **Step 1: Write the failing tests:** `test_release_links_use_the_tracker_template`,
  `test_release_rules_check_the_template_link`, `test_release_config_without_tracker_fails`.
- [ ] **Step 2: Run** `uv run pytest tests/test_release_settings.py tests/test_release_folder.py tests/test_release_rules.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `feat: links da release vêm do tracker, não de /browse/`.

### Task 15: Callers off `config.jira`

**Files:**
- Modify: `src/ws/board_cli.py`, `src/ws/boardconfig.py`, `src/ws/tracker/jira/writer.py`,
  `src/ws/tracker/jira/adapter.py`, `tests/test_board_cli.py`, `tests/test_boardconfig.py`
- Test: `tests/test_tracker_config_reads.py`

**Interfaces:** the adapter reads `config.tracker_settings`; the board says "not a card key" and
points at `[tracker.jira.status_overrides]` through the facade (`ws.tracker.status_overrides`).

- [ ] **Step 1: Write the failing tests:** `test_no_core_module_reads_config_jira` (no `.jira.` or
  `config.jira` in `src/ws` outside `ws/tracker/`), `test_board_names_a_card_key_neutrally`.
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_config_reads.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `fix: quadro e adaptador leem a config neutra do tracker`.

### Task 16: Move by neutral status

**Files:**
- Modify: `src/ws/carddraft.py`, `src/ws/tracker/jira/rules.py`,
  `src/ws/data/contracts/card-write.schema.json`
- Test: `tests/test_card_move_status.py`

**Interfaces:** `move` takes `to` (status name) or `status` (a `Status` value), exactly one
(`carddraft` and the schema). Jira picks the one transition whose destination maps to `status`
through `status_overrides`, then the status category; none or several is a problem naming the
destinations and suggesting `to`. The start date rule is the same as for `to`.

- [ ] **Step 1: Write the failing tests:** `test_move_by_status_picks_the_one_transition`,
  `test_move_by_status_with_two_destinations_names_them`, `test_move_with_to_and_status_is_refused`,
  `test_status_override_wins_over_the_category`, `test_move_by_status_sets_an_empty_start_date`.
- [ ] **Step 2: Run** `uv run pytest tests/test_card_move_status.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `feat: mover card por status neutro`.

### Task 17: JSON drafts

**Files:**
- Modify: `src/ws/card.py`, `src/ws/tracker/write.py`, `skills/card/SKILL.md` (one line)
- Test: `tests/test_card_json_drafts.py`

**Interfaces:** a draft may be `NAME.json`, a `card-write` document; `collect`, `load`,
`write_draft` and `remove_draft` accept it; `load` runs `write.check_document` then
`from_document`. `ws card check FILE.json` validates a `card-write` or a `card-plan` document (the
latter schema only). The pending record keeps the file's `sha256`.

- [ ] **Step 1: Write the failing tests:** `test_json_draft_previews_like_its_markdown_twin` (same
  summary and code), `test_json_draft_with_an_unknown_key_is_refused`,
  `test_check_validates_a_card_plan_document`, `test_a_folder_mixes_md_and_json_drafts`.
- [ ] **Step 2: Run** `uv run pytest tests/test_card_json_drafts.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `feat: rascunhos de card em JSON pelo contrato card-write`.

### Task 18: Aliases removed and the boundary tests

**Files:**
- Delete: `src/ws/jira.py`, `src/ws/adf.py`, `src/ws/cardrules.py`, `src/ws/tracker/jira_adapter.py`,
  `src/ws/tracker/jira_discover.py`
- Modify: `src/ws/card.py` (drops `guard`, `_needed_keys` and every Jira import),
  `src/ws/userconfig.py` (drops the `JiraConfig` re-export and the `jira` property),
  `src/ws/tracker/vocab.py` (gains `fold`), `src/ws/tracker/jira/rules.py`, `src/ws/reviewcard.py`
  (`fold` from `vocab`), and the tests that import the old paths: `tests/test_card.py`,
  `tests/test_card_link.py`, `tests/test_card_epics.py`, `tests/test_adf.py`, `tests/test_jira.py`,
  `tests/fake_tracker.py`, `tests/test_review_card.py`, `tests/test_review_pack.py`,
  `tests/test_tracker_port.py`, `tests/test_tracker_discover.py`, `tests/test_tracker_jira_paths.py`
  (deleted)
- Test: `tests/test_tracker_boundary.py`

**Interfaces:** tests reach `guard`, `needed_keys`, `check` and the client at
`ws.tracker.jira.writer`, `ws.tracker.jira.rules`, `ws.tracker.jira.client`.

- [ ] **Step 1: Write the failing tests:** `test_no_module_outside_tracker_imports_the_jira_adapter`
  (AST over `src/ws/**/*.py` and `hooks/**/*.py` outside `src/ws/tracker/`: no `ws.jira`,
  `ws.adf`, `ws.cardrules`, `ws.tracker.jira*`, `from ws import jira|adf|cardrules`,
  `from ws.tracker import jira`), `test_neutral_tracker_modules_import_no_adapter` (`__init__`,
  `port`, `write`, `errors`, `vocab`: dispatch by string only),
  `test_no_rest_path_or_browse_link_outside_the_adapter`, `test_old_jira_module_paths_are_gone`.
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_boundary.py -q` — expected: FAIL.
- [ ] **Step 3: Implement** (delete, update imports; the golden of Task 1 still passes).
- [ ] **Step 4: Run** `uv run pytest -q`; ruff clean.
- [ ] **Step 5: Commit** `chore: remove caminhos antigos do Jira e testa a fronteira`.
