# Neutral tracker vocabulary in `/card` (plan 1 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ws card` writes cards of any type, for any assignee and reporter the user may write, with
or without a sprint, creates epics and initiatives, and adds links, from drafts written in a
tracker-neutral vocabulary, with the tracker chosen in the config.

**Architecture:** The draft format and the config become neutral (`type = "improvement"`, dev ids
for people, `blocks`/`relates`). `[tracker] kind` picks the adapter; today only `jira`, whose
engine stays in `card.py`, `cardrules.py` and `jira.py` (they are the Jira adapter; their module
docstrings say so). A new package `ws.tracker` holds the neutral vocabulary and the kind check.
The neutral port (`Protocol`) and the neutral `Card` arrive in plan 2, where the item commands
need them, together with the `item` key of `create` and the write-back of `card` into the item,
`ws item ...` and `ws task list --role`. Plan 2: items and the `task-shaping` skill. Plan 3:
converting the workspace.

**Tech Stack:** Python 3.12+, standard library only at runtime; `uv`, `pytest`, `ruff`.

**Spec:** `docs/specs/2026-11-13-task-items-design.md` (sections "Neutral vocabulary", "The rules
of a card", "The config", "Whose cards `ws` writes", "`ws card` changes").

## Global Constraints

- Runtime code: standard library only. Run everything with `uv run` (`uv run pytest -q`,
  `uv run ruff check`, `uv run ruff format --check`).
- Names in English (code, flags, messages of the CLI to the model: JSON `problems` in English as
  today); text shown to people in the preview stays PT-BR, like the current preview lines.
- Neutral card types: `task`, `bug`, `hotfix`, `improvement`, `feature`; levels above:
  `epic`, `initiative`. Neutral links: `blocks`, `blocked_by`, `relates`.
- PT-BR labels for the preview: `task` Tarefa, `bug` Bug, `hotfix` HotFix, `improvement` Melhoria,
  `feature` Nova função, `epic` Épico, `initiative` Iniciativa; `blocks` bloqueia, `blocked_by`
  é bloqueado por, `relates` relaciona-se com.
- Required sections: all card types `## Contexto` and `## Pronto quando`; `bug` and `hotfix` also
  `## Como reproduzir` and `## Evidência`; `hotfix` also `## Por que não espera a release`; `epic`
  and `initiative` only `## Contexto`.
- A card is writable when the user is its assignee or its reporter. Anyone else's card is
  refused, for every op. The rule never depends on a local list of people: the repo is shared with another developer.
- No real names in tests or fixtures: fake accounts (`acc-me`, `acc-other`, `acc-ana`) and fake
  titles, as today.
- Commits: prefix `feat:`, `fix:`, `test:`, `docs:` or `chore:`, PT-BR, at most 72 characters, no
  task ID, no `Co-Authored-By`. Run `git diff` before each message. Pull before starting; push to
  `main` at the end.
- `ws` never edits `~/.claude/settings.json` or the user's `config.toml`; it prints what to add.

## Review Focus

1. A `link` draft that names its own card, or the same card in `blocks` and `blocked_by`: refused
   by check, not sent.
2. A link whose opposite already exists (draft "TS-1 blocks TS-2", Jira has "TS-1 is blocked by
   TS-2"): refused as contradictory, not created and not reported as "já existe".
3. A dev id in a draft that is missing from `[people]`, or present without a `jira` id: a clear
   problem naming the id and the `ws people add` hint; an e-mail with spaces or capitals gives
   the same id as its trimmed lowercase form.
4. A type change to a type the card's edit screen does not allow, or an epic `parent` the screen
   does not accept: refused at check with the "à mão" instruction, never a Jira 400 at apply.
5. `sprint` with any value other than `"active"`: refused; a draft with `sprint = "active"` and no
   `due`: refused (the due date is optional only without a sprint).

---

### Task 1: Tracker config: kind, types, links and people

**Files:**
- Create: `src/ws/tracker/__init__.py`, `src/ws/tracker/vocab.py`, `src/ws/identity.py`
  (`def dev_id(email: str) -> str`: `"dev-"` + the first 10 hex characters of the SHA-256 of the
  trimmed, lowercased e-mail)
- Modify: `src/ws/userconfig.py` (`JiraConfig`, `UserConfig`, `load_config`), `src/ws/card.py:166-207`
  (`_needed_keys`, `_session`), `README.md` (section "Local config", the `[jira]` block)
- Test: `tests/test_userconfig.py`, `tests/test_card.py` (fixture `world`)

**Interfaces:**
- Produces, in `ws.tracker.vocab`:
  - `CARD_TYPES = ("task", "bug", "hotfix", "improvement", "feature")`,
    `UPPER_TYPES = ("epic", "initiative")`, `LINK_KINDS = ("blocks", "blocked_by", "relates")`;
  - `TYPE_LABELS: dict[str, str]`, `LINK_LABELS: dict[str, str]` (the PT-BR labels above);
  - `required_sections(type_: str) -> tuple[str, ...]` (the table above).
- Produces, in `ws.tracker`: `KNOWN_KINDS = ("jira",)`; `class UnknownTracker(Exception)`;
  `def require_kind(kind: str) -> None` (raises `UnknownTracker` with
  `"tracker {kind!r} has no adapter yet; known: jira"`).
- Produces, in `ws.userconfig`:
  - `@dataclass(frozen=True) class Person: dev_id: str; ids: dict[str, str]; label: str | None`;
  - `UserConfig` gains `identity_email: str` (`[identity] email`; absent = `[jira] email`);
  - `JiraConfig` loses `issue_type`, gains `types: dict[str, str]` (neutral type → issue type id)
    and `links: dict[str, str]` (`blocks`, `relates` → link type name), both default `{}`;
  - `UserConfig` gains `tracker_kind: str` (from `[tracker] kind`; absent = `"jira"`) and
    `people: dict[str, Person]`.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing tests** in `tests/test_userconfig.py`:
  - `test_tracker_kind_defaults_to_jira` (no `[tracker]` → `"jira"`);
  - `test_tracker_kind_is_read` (`[tracker] kind = "jira"`);
  - `test_jira_types_and_links_are_read` (`[jira.types] task = "10002"`, `improvement = "10010"`;
    `[jira.links] blocks = "Blocks"` → `types == {"task": "10002", "improvement": "10010"}`,
    `links == {"blocks": "Blocks"}`);
  - `test_jira_types_refuse_unknown_neutral_names` (`[jira.types] story = "1"` →
    `ConfigInvalid` naming `story`); same for `[jira.links] duplicates = "Duplicate"`;
  - `test_people_are_read` (`[people."dev-0123456789"] jira = "acc-ana"`, `label = "ana"` →
    `Person("dev-0123456789", {"jira": "acc-ana"}, "ana")`; a key other than tracker kinds
    and `label` → `ConfigInvalid`);
  - `test_dev_id_is_the_hash_of_the_trimmed_lowercase_email` (`dev_id(" Ana@Example.com ")`
    `== dev_id("ana@example.com") == "dev-" + sha256(b"ana@example.com").hexdigest()[:10]`);
  - `test_identity_email_falls_back_to_jira_email`;
  - `test_people_refuse_keys_that_are_not_dev_ids` (`[people.ana]`, `[people.me]`,
    `[people."dev-XYZ"]` → `ConfigInvalid`; keys match `^dev-[0-9a-f]{10}$`);
  - `test_issue_type_key_is_refused_with_the_new_block` (`[jira] issue_type = "Tarefa"` →
    `ConfigInvalid` whose message contains `[jira.types]`).
- [ ] **Step 2: Run** `uv run pytest tests/test_userconfig.py -q` — expected: the new tests FAIL.
- [ ] **Step 3: Implement** `ws.tracker`, `ws.tracker.vocab` and the config reading. `issue_type` in
  `[jira]` raises `ConfigInvalid("[jira] issue_type was replaced by [jira.types]; run `ws tracker discover` and paste its output")`.
- [ ] **Step 4: Update `card._needed_keys` and `card._session`.** A create or an edit with `type`
  needs `types` (missing → `SetupNeeded` with the same message); a `link` needs `links` (missing →
  `SetupNeeded` naming `[jira.links]`); `require_kind(config.tracker_kind)` runs first and its
  error is a `SetupNeeded` (exit 2). The `world` fixture in `tests/test_card.py` writes
  `[jira.types]` (`task = "3"`, `bug = "4"`, `hotfix = "5"`, `improvement = "6"`, `feature = "7"`,
  `epic = "8"`, `initiative = "9"`), `[jira.links]` (`blocks = "Blocks"`, `relates = "Relates"`)
  and `[people."<dev_id('ana@example.com')>"] jira = "acc-ana"`, and drops `issue_type`.
- [ ] **Step 5: Update `README.md`** "Local config": the new tables, with the example of the spec's
  "The config" section (fake ids are fine), and the line on `[tracker] kind`.
- [ ] **Step 6: Run** `uv run pytest -q` — expected: every test passes except the create tests
  that send `"issuetype": {"name": ...}` (fixed in Task 4); note which ones fail.
- [ ] **Step 7: Commit** `feat: config do tracker com tipos, vínculos e pessoas`.

### Task 2: Config helpers: `ws tracker discover` and `ws people`

**Files:**
- Create: `src/ws/tracker/jira_discover.py`
- Modify: `src/ws/cli.py` (new `tracker` group with `discover`; new `people` group with `me` and
  `add`), `src/ws/jira.py` (`JiraClient.issue_types(project) -> list[dict]`,
  `JiraClient.link_types() -> list[dict]`, `JiraClient.user_search(query: str) -> list[dict]`,
  `GET /rest/api/3/user/search?query=`)
- Test: `tests/test_tracker_discover.py`, `tests/test_people_cli.py`

**Interfaces:**
- Produces: `def discover_toml(issue_types: list[dict], link_types: list[dict]) -> str`; CLI
  `ws tracker discover` (read only, exit 0; 2 on setup; 3 when Jira refuses);
  `def people_block(dev_id: str, kind: str, account: str) -> str` (the `[people."dev-…"]` TOML,
  never the e-mail); CLI `ws people me` (prints the user's dev id) and
  `ws people add EMAIL [--account ID]` (read only; prints the block; exit 1 when the search finds
  zero or several accounts, naming `--account`).
- Consumes: `ws.tracker.vocab`, `ws.identity.dev_id`, `userconfig.load_config`.

Tests for `ws people` (in `tests/test_people_cli.py`): `test_people_me_prints_the_users_dev_id`;
`test_people_add_finds_the_account_by_email` (fake search returns one user `acc-ana` → stdout is
`[people."<dev_id('ana@example.com')>"]` and `jira = "acc-ana"`, and does not contain the e-mail);
`test_people_add_with_account_skips_the_search` (no request to `/rest/api/3/user/search`);
`test_people_add_refuses_zero_or_several_matches`.

- [ ] **Step 1: Write the failing tests**:
  - `test_discover_maps_known_names` — types `[{"id": "10002", "name": "Tarefa"}, {"id": "10010", "name": "Melhoria"}, {"id": "10136", "name": "Iniciativa"}, {"id": "10001", "name": "História"}]`
    and links `[{"name": "Blocks"}, {"name": "Relates"}, {"name": "Duplicate"}]` → the output
    contains `task = "10002"`, `improvement = "10010"`, `initiative = "10136"`,
    `# "História" = "10001"` (unmapped, commented), `blocks = "Blocks"`, `relates = "Relates"`,
    `# "Duplicate"`, and parses as TOML;
  - `test_discover_cli_reads_the_project` (fake Jira routes
    `GET /rest/api/3/issue/createmeta/TS/issuetypes` and `GET /rest/api/3/issueLinkType`; exit 0;
    stdout starts with `[jira.types]`).
  - the four `ws people` tests above.
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_discover.py tests/test_people_cli.py -q` —
  expected: FAIL.
- [ ] **Step 3: Implement.** Name → neutral table (case and accents folded with
  `cardrules.fold`): Tarefa/Task → task, Bug → bug, HotFix → hotfix, Melhoria/Improvement →
  improvement, Nova função/New Feature → feature, Epic/Épico → epic, Iniciativa/Initiative →
  initiative; link names Blocks → blocks, Relates → relates.
- [ ] **Step 4: Run** the tests — expected: PASS.
- [ ] **Step 5: Commit** `feat: ws tracker discover e ws people para a config`.

### Task 3: Draft format: neutral keys and the `link` op

**Files:**
- Modify: `src/ws/carddraft.py` (`OPS`, `REQUIRED`, `OPTIONAL`, `_values`)
- Test: `tests/test_card.py` (draft tests near `test_draft_errors`)

**Interfaces:**
- Produces (draft keys; values are strings unless said):
  - `create`: required `type`, `priority`; optional `epic`, `parent`, `assignee`, `reporter`,
    `sprint`, `due` (date);
  - `edit`: required `key`; optional `title`, `priority`, `start`, `due`, `epic`, `type`,
    `assignee`, `reporter`, `parent`;
  - new op `link`: required `key`; optional `blocks`, `blocked_by`, `relates` (lists of strings);
  - `LIST_KEYS = {"blocks", "blocked_by", "relates"}`.
- Consumes: `ws.tracker.vocab.CARD_TYPES`, `UPPER_TYPES`.

- [ ] **Step 1: Write the failing tests** (`parse_draft` only, no Jira):
  - `test_draft_create_needs_a_type` (`missing key 'type' for op create`);
  - `test_draft_create_type_must_be_neutral` (`type = "Melhoria"` →
    `type must be one of task, bug, hotfix, improvement, feature, epic, initiative`);
  - `test_draft_create_card_type_needs_an_epic` (`type = "task"` without `epic` →
    `a task needs an epic`), `test_draft_create_epic_refuses_an_epic_key` (`type = "epic"` with
    `epic` → `an epic has no epic; use parent for its initiative`),
    `test_draft_create_initiative_refuses_parent`;
  - `test_draft_sprint_accepts_only_active` (`sprint = "Sprint 9"` → `sprint must be "active"`);
  - `test_draft_link_lists` (`op = "link"`, `key = "TS-1"`, `blocks = ["TS-2"]` → values
    `{"key": "TS-1", "blocks": ["TS-2"]}`); `test_draft_link_needs_one_list`
    (`a link needs blocks, blocked_by or relates`); `test_draft_link_refuses_its_own_key`
    (`blocks = ["TS-1"]` → `a card cannot link to itself`);
    `test_draft_link_refuses_the_same_card_twice` (`blocks = ["TS-2"]`, `blocked_by = ["TS-2"]` →
    `TS-2 appears in more than one list`); `test_draft_link_has_no_body`;
  - update the existing draft fixtures (`create_draft` gets `type = "task"` by default).
- [ ] **Step 2: Run** `uv run pytest tests/test_card.py -q -k draft` — expected: the new tests FAIL.
- [ ] **Step 3: Implement** the keys, the list parsing (a list of non-empty strings, stripped,
  no duplicates inside one list) and the cross-key rules above inside `_values` (they need no
  Jira).
- [ ] **Step 4: Run** the draft tests — expected: PASS.
- [ ] **Step 5: Commit** `feat: rascunho de card com tipo, pessoas e op link`.

### Task 4: Who can be written, and the create of a card

**Files:**
- Modify: `src/ws/cardrules.py` (`Context.own_card` → `Context.writable_card`, `Context.person`,
  `Context.priorities`, `_create`, `_section_problems`), `src/ws/jira.py`
  (`JiraClient.create_meta(project, type_id)` takes the id; no lookup by name), `src/ws/card.py`
  (`_report_applied`)
- Test: `tests/test_card.py`

**Interfaces:**
- Produces:
  - `Context.writable_card(key: str, verdict: Verdict) -> dict | None` (fields fetched:
    today's plus `reporter`, `issuetype`, `issuelinks`; problem
    `card {key} is not yours: you are neither its assignee nor its reporter`);
    used by `_edit`, `_move`, `_comment`, `_worklog`, `_link`;
  - `Context.person(ref: str, verdict: Verdict) -> str | None` (accountId; `me` → the user, and
    so is the user's own dev id; problems
    `unknown person {ref!r}: run ws people add <e-mail> and paste the block into config.toml` and
    `person {ref!r} has no jira id`); the preview shows the tracker's display name
    (`GET /rest/api/3/user?accountId=`), or `label`, or the id;
  - `_section_problems(text: str, type_: str) -> list[str]` using `vocab.required_sections`;
  - `~/.local/share/workspace/cards/created.tsv`: one line per created card,
    `<draft file name>\t<key>\t<YYYY-MM-DD>`, appended by `_report_applied` (plan 3 and the links
    run read it).
- Consumes: Task 1 (`types`, `people`, `vocab`), Task 3 (draft keys).

- [ ] **Step 1: Write the failing tests**:
  - writable rule: `test_edit_card_where_i_am_reporter_passes` (assignee `acc-other`, reporter
    `acc-me`), `test_edit_card_of_anyone_else_is_refused` (assignee and reporter `acc-other`;
    the problem text above), the same two for `move` and `comment` (parametrize);
  - create: `test_create_sends_the_type_id` (`type = "improvement"` → request body
    `"issuetype": {"id": "6"}`; preview line `Tipo: Melhoria`);
    `test_create_assignee_and_reporter_from_dev_ids` (`assignee = "<ana's dev id>"` →
    `{"accountId": "acc-ana"}`,
    reporter default → `acc-me`; preview `Responsável: ana` and `Relator: Dev Example`);
    `test_create_unknown_dev_id_is_a_problem`; `test_create_dev_id_without_jira_id_is_a_problem`
    (a `[people."dev-…"]` with only `github = "bia"` → `has no jira id`);
    `test_create_without_sprint_sends_no_sprint_and_reads_no_board` (no request to
    `/rest/agile/1.0/board/7/sprint`; no `customfield_10020` in the body; preview
    `Sprint: (nenhuma)`); `test_create_with_sprint_active_keeps_todays_rules` (the existing sprint
    tests, now with `sprint = "active"`); `test_create_due_is_optional_without_sprint` and
    `test_create_due_is_required_with_sprint` (`due is required with sprint = "active"`);
    `test_create_bug_needs_reproduction_and_evidence` (missing `## Como reproduzir` → problem);
    `test_create_hotfix_needs_why_not_the_release`;
    `test_create_priorities_come_from_the_type_id` (route
    `GET /rest/api/3/issue/createmeta/TS/issuetypes/6`);
    `test_created_cards_are_logged` (after apply, `created.tsv` holds `create.md\tTS-200\t2026-10-27`).
- [ ] **Step 2: Run** `uv run pytest tests/test_card.py -q` — expected: the new tests FAIL.
- [ ] **Step 3: Implement.** In `_create`: `issuetype` → `{"id": settings.types[type]}`; `assignee`
  and `reporter` from `ctx.person`; sprint only when `sprint == "active"`; due required only then;
  sections by type; the preview adds `Tipo`, `Responsável`, `Relator`, `Sprint: (nenhuma)` when
  absent, `Prazo: (nenhum)` when absent.
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS (the Task 1 failures included).
- [ ] **Step 5: Commit** `feat: card de qualquer tipo, para outra pessoa e sem sprint`.

### Task 5: Create epics and initiatives

**Files:**
- Modify: `src/ws/cardrules.py` (`_create`, new `_create_upper`), `src/ws/jira.py`
  (`create_meta` already by id)
- Test: `tests/test_card.py`

**Interfaces:**
- Consumes: Task 4 (`_create`, `ctx.person`, `create_meta(project, type_id)`).
- Produces: create of `type = "epic"` / `"initiative"`; `Context.initiative(key, verdict)`
  (the key is in the project, `hierarchyLevel == 2`, not done).

- [ ] **Step 1: Write the failing tests**:
  - `test_create_epic_without_parent` (body `issuetype {"id": "8"}`, no `parent`; title must match
    `^\[[^\]]+\] `; only `## Contexto` required);
  - `test_create_epic_title_needs_a_prefix` (`[X]` missing → `an epic title starts with [PREFIX]`);
  - `test_create_epic_with_parent_when_the_screen_has_it` (createmeta for type `8` lists
    `parent` → body `"parent": {"key": "TS-140"}`; `TS-140` is level 2);
  - `test_create_epic_with_parent_refused_when_the_screen_lacks_it` (createmeta without
    `parent` → problem `the epic create screen has no parent: create it without parent and link it to TS-140 by hand in the tracker`);
  - `test_create_epic_parent_must_be_an_initiative` (level 1 → problem);
  - `test_create_initiative` (body `issuetype {"id": "9"}`, no parent).
- [ ] **Step 2: Run** — expected: FAIL.
- [ ] **Step 3: Implement** `_create_upper`; the "has `parent` on the screen" test reads the same
  create metadata already fetched for the priorities.
- [ ] **Step 4: Run** `uv run pytest -q` — expected: PASS.
- [ ] **Step 5: Commit** `feat: criar épico e iniciativa pelo card`.

### Task 6: Edit type, people and parent

**Files:**
- Modify: `src/ws/cardrules.py` (`_edit`), `src/ws/jira.py` (`JiraClient.edit_meta(key) -> dict`,
  `GET /rest/api/3/issue/{key}/editmeta`)
- Test: `tests/test_card.py`

**Interfaces:**
- Consumes: Task 4 (`writable_card`, `person`), Task 1 (`types`).
- Produces: `edit` with `type`, `assignee`, `reporter`, `parent`.

- [ ] **Step 1: Write the failing tests**:
  - `test_edit_type_sends_the_id_and_shows_labels` (current `issuetype {"id": "3", "name": "Tarefa"}`;
    `type = "improvement"`; editmeta allows id `6` → body `"issuetype": {"id": "6"}`; preview
    `Tipo: Tarefa -> Melhoria`);
  - `test_edit_type_not_allowed_by_the_screen_is_refused` (editmeta without id `6` → problem
    `the card's edit screen does not allow type improvement: change it with the tracker's move, by hand`);
  - `test_edit_assignee_and_reporter` (dev ids → accountIds; `before` keeps the old accountIds;
    preview `Responsável: Dev Example -> ana`);
  - `test_edit_parent_of_an_epic_refused_when_editmeta_lacks_it` (the "à mão" message);
  - `test_edit_same_type_changes_nothing` (the existing "changes nothing" problem).
- [ ] **Step 2: Run** — expected: FAIL.
- [ ] **Step 3: Implement**; editmeta is fetched only when `type` or `parent` is in the draft.
- [ ] **Step 4: Run** `uv run pytest -q` — expected: PASS.
- [ ] **Step 5: Commit** `feat: editar tipo, responsável, relator e pai do card`.

### Task 7: The `link` op

**Files:**
- Modify: `src/ws/cardrules.py` (new `_link`, `check` dispatch), `src/ws/card.py` (`_OPERATIONS`,
  `guard`, `_report_applied`)
- Test: `tests/test_card.py`

**Interfaces:**
- Consumes: Task 3 (`link` draft), Task 4 (`writable_card`), Task 1 (`links`).
- Produces: `link` requests `{"method": "POST", "path": "/rest/api/3/issueLink", "body": {...}}`.

Direction (Jira): for `A blocks B` send
`{"type": {"name": links["blocks"]}, "inwardIssue": {"key": A}, "outwardIssue": {"key": B}}`;
`A blocked_by B` is `B blocks A`; `relates` uses `links["relates"]` with A inward. Reading A's
`issuelinks`: an entry of type Blocks with `outwardIssue.key == B` means "A blocks B"; with
`inwardIssue.key == B` means "A is blocked by B".

- [ ] **Step 1: Write the failing tests**:
  - `test_link_adds_only_missing_links` (TS-101 already blocks TS-120; draft
    `blocks = ["TS-120", "TS-102"]` → one request, for TS-102; preview lines
    `TS-101 bloqueia TS-120: já existe` and `TS-101 bloqueia TS-102`);
  - `test_link_blocked_by_reverses_the_sides` (`blocked_by = ["TS-120"]` → inward `TS-120`,
    outward `TS-101`);
  - `test_link_relates` (type name `Relates`);
  - `test_link_contradicting_an_existing_link_is_refused` (Jira has TS-101 blocked by TS-120;
    draft `blocks = ["TS-120"]` → problem `TS-101 is already blocked by TS-120`);
  - `test_link_target_outside_the_project_is_refused`;
  - `test_link_needs_one_writable_side` (TS-102 of `acc-other` linking TS-103 of nobody →
    refused; TS-102 linking TS-101 (mine) → passes);
  - `test_link_with_everything_existing_changes_nothing` (the "changes nothing" problem);
  - `test_guard_allows_issue_links_only_inside_the_project` (`guard` accepts the POST with two
    `TS-` keys and refuses a body key `OTHER-1`).
- [ ] **Step 2: Run** — expected: FAIL.
- [ ] **Step 3: Implement**; `_OPERATIONS["link"] = "Vincular cards"`; `_report_applied` prints
  `Vinculado: <preview line>` for each request sent.
- [ ] **Step 4: Run** `uv run pytest -q` — expected: PASS.
- [ ] **Step 5: Commit** `feat: op link no card, só vínculos que faltam`.

### Task 8: `ws card epics` sees epics and initiatives the user owns

**Files:**
- Modify: `src/ws/card.py` (`run_epics`)
- Test: `tests/test_card.py`

**Interfaces:**
- Consumes: Task 1 (`types["epic"]`, `types["initiative"]`).
- Produces: `ws card epics` JSON entries `{"key", "title", "prefix", "level", "parent"}`: the epics
  of the user's open cards (today), plus open epics and initiatives where the user is assignee or
  reporter, plus open epics whose parent is one of those initiatives.

- [ ] **Step 1: Write the failing test** `test_epics_lists_owned_epics_and_initiatives` (fake
  search returns an initiative TS-140 of `acc-me` and an epic TS-141 with parent TS-140 → both
  listed, `level` 2 and 1, TS-141 `parent` TS-140; no duplicates with the epics of open cards).
- [ ] **Step 2: Run** — expected: FAIL.
- [ ] **Step 3: Implement** with JQL on `issuetype in (<epic id>, <initiative id>)`, then
  `parent in (<initiative keys>)`.
- [ ] **Step 4: Run** `uv run pytest -q` — expected: PASS.
- [ ] **Step 5: Commit** `feat: ws card epics com iniciativas e épicos próprios`.

### Task 9: Card rules reference and the `/card` skill

**Files:**
- Create: `skills/card/references/card-rules.md`
- Modify: `skills/card/SKILL.md`, `docs/specs/2026-11-13-task-items-design.md` (the rules file
  path and the `link` key name, see below)

**Interfaces:**
- Consumes: the keys of Tasks 3–7.
- Produces: `~/.claude/skills/card/references/card-rules.md`, the one rules file the
  `task-shaping` skill of plan 2 reads.

- [ ] **Step 1: Write `card-rules.md`** from the spec's "The rules of a card" (place, nature with
  the ordered questions, size, links, findings, people, text and sections), neutral words with the
  PT-BR labels, under 120 lines.
- [ ] **Step 2: Update `SKILL.md`:** the description stays "use only when the user types /card";
  the draft table gains `type`, `assignee`, `reporter`, `sprint`, `parent` and the `link` op, with
  one example each for a `bug` create for another person, an epic create and a `link`; Step 1
  ("Understand the request") reads `references/card-rules.md` to choose the type and the sections;
  no sprint unless the user asks (`sprint = "active"`); people by `me` or dev id (`ws` says which ids
  exist when one is unknown); the tracker's name is never written in the skill's text except in
  the Jira-only notes that exist today. Keep it under 500 lines.
- [ ] **Step 3: Fix the spec** in the same commit: the rules file lives in
  `skills/card/references/card-rules.md`; the `link` op uses `key` (like every other op).
- [ ] **Step 4: Check** `uv run pytest -q` and `uv run ruff check` and `uv run ruff format --check`
  — expected: all clean.
- [ ] **Step 5: Commit** `docs: regras de card e skill /card com tipos e vínculos`, then
  `git push`.

---

## After plan 1: applying the board map (runbook, no code)

Before Monday's planning, with plan 1 in `main`:

1. `ws tracker discover >> ~/.config/workspace/config.toml` after reading it (the user runs it, or
   reviews the diff); run `ws people add <the other developer's e-mail>` and paste the block (both
   developers get the same dev id). Change by hand, in Jira, the reporter of the four cards the other
   developer reported (TS-5379, TS-5466, TS-5467, TS-5468).
2. A one-off script in the session's scratchpad turns the reviewed map
   (`~/.local/share/workspace/projects/workspace/board-map/*.tsv`) into drafts, one folder per
   step: epics; edits (epic, type of open cards, reporter); creates (the user's, then the other
   developer's); every draft named after the map's `card` id (`novo-12.md`).
3. Each folder: `ws card preview`, one approval box. Link the two new epics to TS-5645 by hand.
4. **Before the links folder**, send one link alone and read it back on the card in Jira to
   confirm the direction; then the links folder, with the `novo-*` ids replaced by the keys in
   `created.tsv`.
