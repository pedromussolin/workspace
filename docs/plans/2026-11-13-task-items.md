# Task items and the `task-shaping` skill (plan 2 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each task file under `projects/<slug>/tasks/` carries its card's contract fields in a TOML
front matter; `ws item` creates, checks and compares these items with the tracker, turns the
differences into `ws card` drafts, and `ws card apply` writes the new card's ref back into the item.

**Architecture:** `ws.itemfile` reads and rewrites one item (text level, byte-preserving);
`ws.items` loads a project (`project.toml` + items) and checks it offline; `ws.itemtracker` and
`ws.itemsync` compare and copy through the neutral port `ws.tracker.port` (a read-only `Protocol`:
who the user is, cards by ref and by query, capabilities), whose only adapter wraps today's
`JiraClient`. Writes keep going through `ws card` drafts, preview and approval; the port gains
plan/send only when a second adapter needs them. Plan 3 (`scripts/adopt-items.py`) calls
`ws item new` and expects `ws item check` (offline) to pass.

**Tech Stack:** Python 3.12+, standard library only at runtime; `uv`, `pytest`, `ruff`.

**Spec:** `docs/specs/2026-11-13-task-items-design.md` (sections "The item file", "The tracker
port", "`ws card` changes" (`item`, write-back), "New `ws item` commands", "Skills").
Starts from `feat/tracker-neutral-card` with plan 1 merged (Tasks 5–7 included).

## Global Constraints

- Runtime code: standard library only. Run everything with `uv run` (`uv run pytest -q`,
  `uv run ruff check`, `uv run ruff format --check`).
- Names in English (modules, flags, JSON keys, `problems` texts for the model). Text for people is
  PT-BR: `ws card apply` lines, the README table headers and status labels.
- Item contract keys, exactly: `card`, `type`, `epic`, `assignee`, `reporter`, `blocks`,
  `blocked_by`, `relates`, `docs`, `tracker` (only `false`), `status` (only with `tracker = false`).
  Cache table `[tracker]` keys, exactly: `status`, `priority`, `due`, `sprint`, `synced`.
- An item's `type` is one of `task`, `bug`, `hotfix`, `improvement`, `feature`; epics and
  initiatives are not items (they live in `project.toml` and in plain `/card` drafts).
- Items name people by dev id (`^dev-[0-9a-f]{10}$`), never `me`; `me` exists only in local card
  drafts and on the `ws item new` command line (written as the runner's dev id). Nothing in an item
  depends on who runs `ws`.
- Commands rewrite only the keys they own: `ws card apply` and `ws item set-card` the `card` line,
  `ws item pull` the pulled keys, `ws item sync` the `[tracker]` table. Every other byte stays.
- `ws item` commands never write to the tracker; the only writer is `ws card apply`.
- Nothing from the tracker's site enters the repo: no URLs in tables, only refs and dev ids.
- Tests: fake accounts `acc-me`, `acc-other`, `acc-ana`, e-mails `dev@example.com` and
  `ana@example.com`, fake titles; no real Jira.
- Commits: prefix `feat:`, `fix:`, `test:`, `docs:` or `chore:`, PT-BR, at most 72 characters, no
  task ID, no `Co-Authored-By`; `git diff` before each message. Each task commits in its own
  worktree branch; the controller merges and pushes.

## Review Focus

1. A second create for the same item: two create drafts naming one `item` in a batch, or a create
   for an item that already has `card`: refused at check, never a duplicate card (Task 4).
2. A create with `item` whose apply result is uncertain (5xx, timeout): the item is recorded with
   ref `?`, `ws item drafts` refuses to draft it again, and `ws item set-card` (ref or `--none`)
   releases it (Tasks 4, 5, 6).
3. A link declared on one side only (item A: `blocks = ["TS-2"]`; card TS-2 shows "blocked by A"):
   not drift on TS-2's item (Task 5).
4. One card in two items (D18: one item, one card): an offline problem naming both paths (Task 3).
5. A hand-written front matter (comments, a multi-line list, keys in any order, a `[tracker]`
   table) keeps every byte outside the rewritten entry after write-back, pull and sync (Task 1).

## Parallel waves

- Wave 1: Task 1 (item file) and Task 2 (port, Jira adapter, `ws task list --role`).
- Wave 2: Task 3 (projects offline: `new`, `check`, `table`) and Task 4 (`item` key, write-back).
- Wave 3: Task 5 (`check --tracker`, `drafts`) and Task 7 (skills, README).
- Wave 4: Task 6 (`pull`, `sync`, `set-card`); it shares `item_cli.py` with Tasks 3 and 5.

---

### Task 1: The item file

**Files:**
- Create: `src/ws/itemfile.py`
- Modify: `src/ws/tracker/vocab.py` (add `REF`)
- Test: `tests/test_itemfile.py`

**Interfaces:**
- Produces, in `ws.tracker.vocab`: `REF = re.compile(r"[A-Z][A-Z0-9_]*-[1-9]\d*")` (a card ref).
- Produces, in `ws.itemfile`:
  - `CONTRACT_KEYS`, `CACHE_KEYS` (the Global Constraints lists, in that order);
    `ITEM_PATH = re.compile(r"projects/[a-z0-9]+(?:-[a-z0-9]+)*/tasks/[A-Za-z0-9._-]+\.md")`;
  - `class ItemError(Exception)`;
  - `@dataclass(frozen=True) class Item: path: Path; front: dict; heading: str` (absolute path, the
    parsed front matter, the text of the first `# ` line of the body or `""`), with properties
    `card -> str | None`, `tracked -> bool` (`front.get("tracker") is not False`),
    `links -> dict[str, list[str]]` (each of `LINK_KINDS`, `[]` when absent),
    `cache -> dict` (the `[tracker]` table, `{}` when absent);
  - `read_item(path: Path) -> Item | None` (None: no front matter, a document; `ItemError`: not
    UTF-8, front matter not closed, invalid TOML);
  - `schema_problems(item: Item) -> list[str]` (one item, no project context; a tracked item
    needs `type`, `epic`, `assignee`, `reporter`; with `tracker = false`, `status` is required,
    `card` refused and the other contract keys optional);
  - `set_keys(text: str, values: dict[str, object]) -> str` and
    `set_cache(text: str, table: dict) -> str` (raise `ItemError` when the front matter does not
    parse, before or after);
  - `item_path(root: Path, rel: str) -> Path` (`rel` must fullmatch `ITEM_PATH`; the resolved path
    stays under `root/projects`, is not a symlink; else `ItemError`);
  - `write_text(path: Path, text: str) -> None` (temp file in the same folder, `os.replace`, mode
    kept).
- Consumes: `vocab.CARD_TYPES`, `vocab.LINK_KINDS`, `identity.DEV_ID`, `taskmodel.Status`,
  `userconfig.toml_string`.

- [ ] **Step 1: Write the failing tests** (pure text, `tmp_path` files):
  - `test_a_file_without_front_matter_is_a_document` (`read_item` → `None`);
  - `test_reads_the_contract_fields` (the spec's example with dev ids: `card == "TS-5570"`,
    `links["blocked_by"] == ["TS-5569", "tasks/13-plan-ts-5567.md"]`, `cache["due"] ==
    date(2026, 11, 20)`, `heading == "13 — Fechamento automático"`);
  - `test_schema_refuses_unknown_keys` (`title = "x"` → `unknown key 'title'`; `[tracker]`
    `colour = "x"` → `unknown key 'colour' in [tracker]`);
  - `test_schema_refuses_me` (`assignee = "me"` →
    `assignee must be a dev id, not me: the repo is shared; ws people me prints yours`) and a
    malformed id (`dev-XYZ` → `assignee must be a dev id (dev- and 10 hex digits)`);
  - `test_schema_type_is_a_card_type` (`type = "epic"` →
    `type must be one of task, bug, hotfix, improvement, feature`);
  - `test_schema_requires_type_epic_and_people` (missing `epic` → `missing key 'epic'`);
  - `test_schema_card_and_links_are_refs_or_paths` (`card = "ts 1"` → `card must be a card ref`;
    `blocks = ["x.md"]` → `blocks: 'x.md' is neither a card ref nor tasks/<file>.md`);
  - `test_tracker_false_needs_a_status_and_no_card` (`tracker = false` without `status` →
    `tracker = false needs a status`; with `card` → `tracker = false has no card`;
    `status = "doing"` → `status must be one of todo, in_progress, ...`; `tracker = true` →
    `tracker is either false or the [tracker] table`);
  - `test_a_broken_tracker_table` (`due = "soon"` → `[tracker] due must be a date`);
  - `test_set_keys_inserts_card_as_the_first_key` (result `== text.replace("+++\n",
    '+++\ncard = "TS-9"\n', 1)` on a file with comments and a `[tracker]` table);
  - `test_set_keys_replaces_a_multiline_list` (`blocks = [\n  "TS-1",\n]  # x` →
    `blocks = ["TS-2"]`; every other line identical);
  - `test_set_keys_refuses_a_broken_front_matter` (`ItemError`);
  - `test_set_cache_rewrites_only_the_table` (contract lines and body identical; the table lists
    the keys in `CACHE_KEYS` order) and `test_set_cache_appends_a_missing_table`;
  - `test_item_path_refuses_what_is_not_an_item_path` (`../x.md`, `projects/a/notes/x.md`,
    `/abs/x.md`, `projects/a/tasks/sub/x.md`, a symlink).
- [ ] **Step 2: Run** `uv run pytest tests/test_itemfile.py -q` — expected: FAIL (no module).
- [ ] **Step 3: Implement.** Work on `text.splitlines(keepends=True)`. A key's entry starts at its
  top-level `key =` line (before the first `[` header) and ends at the first line where
  `tomllib.loads` of the gathered lines succeeds; a missing key goes right after the opening
  `+++`. `set_cache` replaces from `[tracker]` to the next header or the closing `+++`, or inserts
  the table before the closing `+++` after a blank line. Both re-parse the result and raise
  `ItemError` unless it equals the old front matter with only those keys changed. Values: strings
  through `toml_string`, dates `isoformat()`, lists `["a", "b"]`, bools `false`.
- [ ] **Step 4: Run** the tests — expected: PASS; `uv run ruff check` clean.
- [ ] **Step 5: Commit** `feat: arquivo de item com front matter e reescrita fiel`.

### Task 2: Tracker port, Jira adapter and `ws task list --role`

**Files:**
- Create: `src/ws/tracker/port.py`, `src/ws/tracker/jira_adapter.py`, `tests/fake_tracker.py`
- Modify: `src/ws/card.py` (rename `_session` to `session`; callers updated), `src/ws/jira.py`
  (`ROLES`, `role_jql`, `tasks_jql`, `FIELDS` gains `assignee`, `card_from_issue` gains
  `assignee_name`), `src/ws/cli.py` (`_add_task`, `_cmd_task_list`)
- Test: `tests/test_tracker_port.py`, `tests/test_jira.py`

**Interfaces:**
- Produces, in `ws.tracker.port` (`ws/tracker/__init__.py` stays as it is: `userconfig` imports
  it, so it must not import the port):
  - `CAPABILITIES = ("worklog", "sprint", "start_date", "initiative", "epic_parent",
    "set_reporter", "change_type", "link_types")`;
  - `@dataclass(frozen=True) class Link: kind: str; ref: str`;
  - `@dataclass(frozen=True) class Card: ref: str; title: str; type: str | None; level: int;
    parent: str | None; assignee: str | None; reporter: str | None; status: Status;
    due: date | None; priority: str | None; sprint: str | None; links: tuple[Link, ...] = ()`
    (`type` neutral, None when unmapped; people are tracker account ids);
  - `@dataclass(frozen=True) class CardQuery: parent_in: tuple[str, ...]; role: str = "all";
    open_only: bool = True` (`role` one of `jira.ROLES`);
  - `@runtime_checkable class Tracker(Protocol)`: `kind: str`, `capabilities: frozenset[str]`,
    `me() -> str`, `card(ref: str) -> Card | None` (None: absent from the configured project),
    `cards(query: CardQuery) -> list[Card]`, `display_name(account: str) -> str`;
  - `class TrackerSetup(Exception)` (exit 2), `class TrackerError(Exception)` (exit 3);
  - `class People`: `People(people: dict[str, Person], kind: str, own_dev_id: str,
    own_account: str)`, `People.from_config(config: UserConfig, own_account: str) -> People`,
    `account(dev_id: str) -> str | None`, `dev_id(account: str) -> str | None`,
    `problem(dev_id: str) -> str | None` (the texts of `cardrules.Context.person`:
    `unknown person 'dev-…': run ws people add <e-mail> and paste the block into config.toml`,
    `person 'dev-…' has no jira id`; the own dev id is always known);
  - `open_tracker() -> Tracker` (imports the adapter inside the function; `UnknownTracker` and
    `card.SetupNeeded` become `TrackerSetup`).
- Produces, in `ws.tracker.jira_adapter`: `JIRA_CAPABILITIES` (all but `epic_parent`);
  `class JiraTracker(client: JiraClient, settings: JiraConfig)`, built by `open_tracker` from
  `card.session({"project", "types"})`; caches `me()` and `card()` per ref; wraps `JiraError`,
  `KeyError`, `TypeError`, `ValueError` into `TrackerError`.
- Produces, in `ws.jira`: `ROLES = ("mine", "following", "all")`; `role_jql(role) -> str`
  (`assignee = currentUser()`; `reporter = currentUser() AND assignee != currentUser()`;
  `(assignee = currentUser() OR reporter = currentUser())`); `tasks_jql(since, role="mine")`,
  with `my_tasks_jql(since) == tasks_jql(since, "mine")` (text unchanged).
- Produces, in `tests/fake_tracker.py`: `make_card(ref: str, **fields) -> Card` (defaults: title
  `f"[FRONT] {ref}"`, type `task`, level 0, parent `TS-100`, assignee and reporter `acc-me`,
  status `Status.TODO`, priority `Medium`, the rest empty) and `class FakeTracker(cards=(), *,
  account="acc-me", capabilities=frozenset(JIRA_CAPABILITIES), names=None)` with
  `kind = "jira"`, `me()` returning `account`, `reads: list[str]`, `cards()` filtering parent,
  role (against `account`) and open (not `DONE` or `CANCELLED`).
- Consumes: plan 1's `JiraConfig.types` and `links`, `userconfig.Person`, `identity.dev_id`.

Jira mapping: type by `issuetype.id` reversed from `settings.types`; `level` from
`issuetype.hierarchyLevel` (0 when absent); status by `jira.status_of(name, category,
settings.status_overrides)`; `sprint`: the sprint field's entry with `state == "active"`, else the
last entry's `name`, else None; links as plan 1 reads them (`_existing_link`): type
`links["blocks"]` with `outwardIssue` → `Link("blocks", key)`, with `inwardIssue` →
`Link("blocked_by", key)`, type `links["relates"]` either side → `Link("relates", key)`.
`cards()` JQL: `project = "TS" AND parent in (TS-100, TS-111) AND <role_jql> AND statusCategory != Done`
(the last clause only with `open_only`); an empty `parent_in` sends nothing.

- [ ] **Step 1: Write the failing tests** (`world` fixture imported from `tests/test_card.py` as
  `tests/test_card_create.py` does):
  - `test_jira_card_is_the_neutral_card` (issuetype id `6`, sprint field
    `[{"name": "Sprint 54", "state": "closed"}, {"name": "Sprint 55", "state": "active"}]`, the
    three link shapes above → `Card("TS-104", ..., type="improvement", level=0, parent="TS-100",
    reporter="acc-other", status=Status.IN_PROGRESS, due=date(2026, 11, 5), sprint="Sprint 55",
    links=(Link("blocks", "TS-120"), Link("blocked_by", "TS-121"), Link("relates", "TS-122")))`);
  - `test_jira_card_absent_or_of_another_project_is_none` (404; `TS-130` of `OTHER`);
  - `test_jira_unmapped_type_is_none` (issuetype id `10001`);
  - `test_jira_cards_query_by_parent_and_role` (the JQL above, `role="all"`; empty `parent_in` →
    no request);
  - `test_jira_errors_are_tracker_errors` (`fake.status = 500` → `TrackerError`);
  - `test_jira_capabilities_lack_only_epic_parent`;
  - `test_open_tracker_refuses_an_unknown_kind` (`[tracker] kind = "monday"` → `TrackerSetup`
    containing `has no adapter yet`);
  - `test_people_resolve_both_ways` (own dev id ↔ `acc-me`; ana's ↔ `acc-ana`; unknown → None and
    the `ws people add` problem);
  - `test_fake_tracker_is_a_tracker` (`isinstance(FakeTracker(), Tracker)`);
  - in `tests/test_jira.py`: `test_task_list_role_following` (`ws task list --role following` →
    JQL starts `reporter = currentUser() AND assignee != currentUser() AND (`; JSON
    `"role": "following"`), `test_task_list_cards_carry_the_assignee_name`,
    `test_task_list_default_role_keeps_the_jql` (`== my_tasks_jql(...)`), and `--role boss` →
    exit 2 (argparse).
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_port.py tests/test_jira.py -q` — expected:
  the new tests FAIL.
- [ ] **Step 3: Implement** the port, the adapter, the fake, the rename and the role.
  `ws task list` prints `{"platform": "jira", "role": ..., "cards": [...]}`.
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS.
- [ ] **Step 5: Commit** `feat: porta neutra do tracker e papel no ws task list`.

### Task 3: Project items offline: `ws item new`, `ws item check`, `ws item table`

**Files:**
- Create: `src/ws/items.py`, `src/ws/item_cli.py`,
  `templates/item/{task,bug,hotfix,improvement,feature}.md`,
  `templates/project/project.toml` (`epics = []`), `tests/item_helpers.py`
- Modify: `src/ws/cli.py` (import `item_cli`; `item_cli.register(subparsers)` in `build_parser`),
  `src/ws/tracker/vocab.py` (`STATUS_LABELS`), `templates/project/README.md` (the table between
  the markers)
- Test: `tests/test_items.py`

**Interfaces:**
- Produces, in `ws.items`:
  - `TABLE_START = "<!-- ws:items -->"`, `TABLE_END = "<!-- /ws:items -->"`;
  - `class ProjectMissing(Exception)`;
  - `@dataclass class Project: slug: str; folder: Path; epics: tuple[str, ...];
    initiative: str | None; prefixes: dict[str, str]; items: list[Item]; problems: list[dict]`
    (items sorted by file name; `problems` from `project.toml` and unreadable items);
  - `project_slugs(root: Path) -> list[str]` (every `projects/<slug>` with a `project.toml`);
  - `load_project(root: Path, slug: str) -> Project` (`ProjectMissing` without `project.toml`);
  - `rel(root: Path, path: Path) -> str` (repo-relative, `/`-separated);
  - `link_ref(project: Project, target: str) -> str | None` (a ref returns itself; `tasks/<f>.md`
    returns that item's `card`, None when it has none yet; `ItemError` when not an item of the
    project or `tracker = false`);
  - `check_offline(projects: list[Project], root: Path, people: People) -> list[dict]`
    (`{"path": rel, "problem": text}`);
  - `new_item(root: Path, slug: str, *, type_: str, epic: str, assignee: str, reporter: str,
    heading: str, name: str | None = None) -> Path`;
  - `table_block(project: Project) -> str`, `write_table(project: Project) -> bool` (changed).
- Produces, in `ws.tracker.vocab`: `STATUS_LABELS` (`todo` a fazer, `in_progress` em andamento,
  `review` em code review, `validation` em validação, `ready_deploy` pronto para deploy, `blocked`
  bloqueado, `done` concluída, `cancelled` cancelada).
- Produces, in `ws.item_cli`: `register(subparsers)` with the `item` group and
  `_projects(names: list[str], root: Path) -> list[Project]` (empty → `project_slugs`); offline
  commands build `People.from_config(load_config(), own_account="")`; and:
  - `ws item new <project> --type T --epic K [--assignee A] [--reporter R] --heading "..."
    [--slug S]`: prints the repo-relative path; exit 1 on a bad value, 2 on setup;
  - `ws item check [projects...]`: prints `{"problems", "drift", "pending", "orphans"}` (offline:
    the last three empty); exit 1 with problems, 2 on setup or an unknown project;
  - `ws item table <project>`: prints `{"path", "rows", "changed"}`; exit 1 without markers.
- Produces, in `tests/item_helpers.py`: `ME = dev_id("dev@example.com")`,
  `ANA = dev_id("ana@example.com")`; fixture `item_repo(tmp_path, ws_config, monkeypatch) -> Path`
  (sets `WS_REPO_ROOT`; copies `templates/item`; `projects/demo/` with
  `project.toml` `epics = ["TS-100", "TS-111"]`, a README with the markers, `tasks/`; when
  absent (a test that also uses `world` lists it first), a `config.toml` with site `https://example.atlassian.net`, e-mail `dev@example.com`, project `TS`,
  the `[jira.types]`/`[jira.links]` of `tests/test_card.py` and ana in `[people]`);
  `write_item(root: Path, name: str, front: str, body: str = "# 01 — Algo\n") -> Path` (under
  `projects/demo/tasks/`).
- Consumes: Task 1 (`read_item`, `schema_problems`, `Item`, `ItemError`, `write_text`,
  `vocab.REF`), Task 2 (`People`).

`project.toml`: `epics` (list of refs, required), `initiative` (ref, optional), `prefixes`
(table epic → prefix, keys among `epics`); other keys are problems. `check_offline` adds to each
item's `schema_problems`: the `epic` is in `epics` (`epic TS-9 is not in project.toml`); each dev
id passes `people.problem`; each `docs` entry exists under `tasks/` with no `..`; each link
target resolves with `link_ref`; an item does not link to itself, nor name one target in two
lists; one `card` in two items is a problem on both (`TS-5 is also the card of <path>`).

`new_item`: the project folder must exist (not `project.toml`: plan 3 may write it later; the
epic's membership is `check`'s job); `type_` in `CARD_TYPES`, `epic` matches `REF`, people match
`DEV_ID`; `NN` = highest `^\d+` prefix in `tasks/` plus one, two digits; file
`tasks/NN-<name>.md`, `name` validated by `project.SLUG_PATTERN`, else the heading folded (accents
off, lowercase, non-alphanumerics to `-`, first six words). Content: `+++`, the four keys in the
order type, epic, assignee, reporter, `+++`, `# NN — <heading>`, a blank line, the template.
On the command line `me` and the defaults become the runner's dev id.

Table: rows by file name, columns `| # | Tarefa | Card | Tipo | Responsável | Status |`: the `NN`
prefix; `[heading without "NN — "](tasks/<file>)` with `|` escaped; the ref or `—`; the PT-BR type
label; the assignee dev id; `STATUS_LABELS` of `[tracker] status`, or of `status` when
`tracker = false`, or `—`.

- [ ] **Step 1: Write the failing tests** in `tests/test_items.py` (through `main([...])`):
  - `test_check_passes_a_clean_project` (exit 0, `problems == []`);
  - `test_check_epic_must_be_in_project_toml`;
  - `test_check_unknown_dev_id_names_ws_people_add`;
  - `test_check_docs_must_exist`;
  - `test_check_link_paths_resolve` (to a document → problem; to an item with no card → no problem);
  - `test_check_refuses_one_card_in_two_items` (both paths in `problems`);
  - `test_check_refuses_a_self_link_and_one_target_twice`;
  - `test_check_reports_a_broken_project_toml` (`epics = "TS-1"`, `colour = 1`);
  - `test_check_unknown_project_exits_2`;
  - `test_new_writes_the_next_number_with_the_template` (tasks `07-a.md` and `13-b.md` → stdout
    `projects/demo/tasks/14-closing-by-time.md`; the file starts
    `+++\ntype = "bug"\nepic = "TS-100"\nassignee = "<ME>"\nreporter = "<ME>"\n+++\n# 14 — Fechamento automático\n`
    and holds the four `##` headings of `required_sections("bug")`; then `ws item check` exits 0);
  - `test_new_without_slug_folds_the_heading` (`14-fechamento-automatico.md`);
  - `test_new_refuses_an_epic_type_and_a_bad_dev_id`;
  - `test_item_templates_hold_the_required_sections` (each `templates/item/<type>.md`'s `## `
    headings `== required_sections(type)`);
  - `test_table_rewrites_only_between_the_markers` (text before and after byte-identical; a row
    `| 14 | [Fechamento automático](tasks/14-closing-by-time.md) | TS-5 | Bug | <ME> | em andamento |`);
  - `test_table_without_markers_exits_1`.
- [ ] **Step 2: Run** `uv run pytest tests/test_items.py -q` — expected: FAIL.
- [ ] **Step 3: Implement** `ws.items`, `ws.item_cli`, the templates (PT-BR, the required
  sections only, each heading followed by a blank line) and the project template.
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS (`tests/test_project.py` included).
- [ ] **Step 5: Commit** `feat: ws item new, check e table nos projetos`.

### Task 4: The `item` key of a create and the write-back

**Files:**
- Create: `src/ws/itemrecord.py`
- Modify: `src/ws/carddraft.py` (`OPTIONAL["create"]`, `_create_rules`), `src/ws/card.py`
  (`build_plan`, `_send_all`, `_report_failure`)
- Test: `tests/test_card_item.py`

**Interfaces:**
- Produces, in `ws.itemrecord` (the record is `data_dir()/cards/uncertain/items.tsv`, one line per
  item: `<rel>\t<ref or ?>\t<YYYY-MM-DD>`):
  - `record(rel: str, ref: str | None) -> None` (replaces the item's older line);
  - `recorded(rel: str) -> str | None` (the ref, `"?"`, or None);
  - `clear(rel: str) -> None`;
  - `write_back(root: Path, rel: str, ref: str) -> None` (`set_keys({"card": ref})` +
    `write_text`; the same ref is a no-op; `ItemError` when the file is gone, the front matter does
    not parse or another `card` is there);
  - `create_problems(root: Path, values: dict, own_dev_id: str) -> list[str]`.
- Produces: draft key `item` (create only, card types only; must fullmatch `ITEM_PATH`):
  `item must be a path like projects/<slug>/tasks/NN-name.md`,
  `item is only for a card; an epic or an initiative has no item`.
- Consumes: Task 1 (`item_path`, `read_item`, `set_keys`, `write_text`, `ITEM_PATH`), plan 1
  (`created.tsv`, `_report_applied`).

`create_problems` texts: `item <rel> is not an item`; `item <rel> already has card TS-5: a second
create would duplicate it`; `item <rel> has tracker = false`; `<field> differs from the item <rel>
(<value>)` for `type`, `epic`, `assignee`, `reporter` (a draft's absent or `me` person is the own
dev id); `item <rel> has an uncertain create (<ref or ?>): check the tracker, then run ws item
set-card <rel> <ref> (or --none)`. `build_plan` adds them to the create's verdict (requests
cleared), and `two drafts create a card for item <rel>` to every draft of a pair.

After `_report_applied` of a create with `item`: `write_back(repo_root(), rel, key)`, then print
`Item atualizado: <rel> (card = "<key>")`. On `ItemError`: print
`Card <key> criado, mas o item <rel> não foi atualizado (<reason>); rode ws item set-card <rel> <key>`,
`record(rel, key)`, go on with the batch; `_send_all` returns 1 at the end (3 still wins on a
Jira failure). `_report_failure` of an uncertain create with `item` calls `record(rel, None)`.

- [ ] **Step 1: Write the failing tests** (`world` from `tests/test_card.py`; `WS_REPO_ROOT` in
  `tmp_path` with `projects/demo/tasks/01-a.md`: type `task`, epic `TS-100`, people the own dev id
  and a comment line):
  - `test_draft_item_key_shape` (`item = "../x.md"` and `type = "epic"` with `item` → the texts);
  - `test_create_with_item_writes_the_card_back` (apply exit 0; the item `==` the original with
    `card = "TS-200"` as the first key; stdout has `Item atualizado`; `created.tsv` has the line);
  - `test_create_for_an_item_with_a_card_is_refused`;
  - `test_create_whose_fields_differ_from_the_item_is_refused` (`type = "improvement"`);
  - `test_two_creates_for_one_item_are_refused` (no POST sent);
  - `test_create_for_a_recorded_item_is_refused`;
  - `test_write_back_failure_records_and_finishes_the_batch` (wrap `card._send` to break the
    item's TOML after the POST; a second draft, an `edit` of TS-101, is still sent; exit 1; the
    broken item untouched; stdout has `TS-200`, the path and `ws item set-card`;
    `recorded(rel) == "TS-200"`);
  - `test_uncertain_create_records_the_item` (POST answers 500 → exit 3, `recorded(rel) == "?"`).
- [ ] **Step 2: Run** `uv run pytest tests/test_card_item.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS.
- [ ] **Step 5: Commit** `feat: card criado grava a chave no item, com registro incerto`.

### Task 5: `ws item check --tracker` and `ws item drafts`

**Files:**
- Create: `src/ws/itemtracker.py`
- Modify: `src/ws/item_cli.py` (`--tracker` on `check`; new `drafts`)
- Test: `tests/test_item_tracker.py`

**Interfaces:**
- Produces, in `ws.itemtracker`:
  - `@dataclass class Report: problems: list[dict]; drift: list[dict]; pending: list[dict];
    orphans: list[dict]` with `to_json() -> dict`;
  - `compare(projects: list[Project], root: Path, tracker: Tracker, people: People) -> Report`;
  - `write_drafts(report: Report, projects: list[Project], root: Path, tracker: Tracker,
    only: set[str] | None, now: datetime) -> dict` (`{"folder", "count", "need_text",
    "waiting", "by_hand"}`; `ItemError` when it refuses, nothing written);
  - `DEFAULT_PRIORITY = "Medium"`.
- Produces, CLI: `ws item check [projects] --tracker` (same JSON, filled; exit 1 on problems, 2
  `TrackerSetup`, 3 `TrackerError`); `ws item drafts [projects] [--only REFS]` (`REFS`: commas,
  each a card ref or a repo-relative item path as `check` prints them). Tracker commands build
  `People.from_config(config, tracker.me())`.
- Consumes: Task 2 (`port.open_tracker`, `Tracker`, `CardQuery`, `People`, `Link`), Task 3
  (`Project`, `check_offline`, `link_ref`, `rel`), Task 4 (`itemrecord.recorded`),
  `card.drafts_folder`, `vocab.required_sections`.

JSON entries: problem `{"path", "problem"}`; drift `{"path", "card", "field", "item", "tracker"}`
(people as dev ids, plus `"names": {"item", "tracker"}` from `display_name`); pending
`{"path", "card": null, "op": "create"}` or `{"path", "card", "op": "link", "kind", "to",
"waits"}`; orphan `{"card", "title", "epic"}`.

`compare`: offline problems first; an item with offline problems or `tracker = false` is not
compared. An item with no card → pending create. Else `tracker.card(ref)`: None →
`card TS-5 was not found in the tracker's project`; `level != 0` → `TS-5 is not a card (level 1)`;
drift when `type`, `epic` (vs `parent`), `assignee`, `reporter` (via `people.account`) differ. Each
link target: a ref the tracker lacks → problem; a path whose item has no card → pending with
`waits: true`; an existing target missing from the card's links → pending `waits: false`. A link on
the card counts as declared when its item lists it or the other card's item lists the inverse
(`blocks` ↔ `blocked_by`, `relates` ↔ `relates`); an undeclared one is drift on that kind
(`item`: the item's list, `tracker`: the card's). Orphans: `tracker.cards(CardQuery(project.epics))`
whose ref no item holds.

`write_drafts` refuses on any problem, and on a create for an item `recorded` (the Task 4
message). Selected (all, or `only`): one `edit-<ref>.md` per card with drift in
`type`/`epic`/`assignee`/`reporter` (the item's values); one `link-<ref>.md` per card with pending
links not waiting; one `create-<slug>-<file stem>.md` per item with no card: `type`, `epic`,
`priority = "Medium"`, `assignee`, `reporter`, `item = "<rel>"`, body `# ` and the empty
`## <section>` headings of `required_sections(type)`; its path goes to `need_text`. A drift field
whose capability is missing (`type` → `change_type`, `reporter` → `set_reporter`, links →
`link_types`) and every undeclared tracker link go to `by_hand` as text
(`change the type of TS-5 by hand in the tracker`; `remove the link TS-5 blocks TS-7 by hand, or
ws item pull <path> --fields blocks`); waiting links go to `waiting`. Folder
`drafts_folder(f"items-{now:%Y%m%d-%H%M%S}")`; no draft → `{"folder": null, "count": 0, ...}`.

- [ ] **Step 1: Write the failing tests** (`item_repo`, `FakeTracker` through
  `monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: fake)`):
  - `test_check_tracker_reports_each_drift_kind` (four fields, both values, names);
  - `test_check_tracker_missing_card_is_a_problem` (exit 1);
  - `test_check_tracker_pending_creates_and_links` (a missing link `waits: false`, a link to a
    cardless item `waits: true`, a cardless item `op: create`);
  - `test_check_tracker_link_declared_on_the_other_side_is_not_drift`;
  - `test_check_tracker_undeclared_tracker_link_is_drift`;
  - `test_check_tracker_orphans` (an open card of `acc-me` under TS-100 with no item is listed; a
    done one and one of `acc-other` are not);
  - `test_drafts_writes_edit_link_and_create` (count 3; `parse_draft` accepts the edit and the
    link; the create fails to parse on the `# ` title; `need_text` lists it);
  - `test_drafts_only_selects_refs_and_paths`;
  - `test_drafts_refuses_an_item_recorded_uncertain` (exit 1, no folder under `cards/drafts/`);
  - `test_drafts_refuses_when_check_has_problems`;
  - `test_drafts_missing_capability_goes_to_by_hand` (no `change_type` → no edit draft for the
    type);
  - `test_check_tracker_through_the_jira_adapter` (`world` then `item_repo`; TS-101 set with
    `issuetype {"id": "3", "hierarchyLevel": 0}` and reporter `acc-me`; its item (task, TS-100,
    `ME`, `ME`) → exit 0, no drift).
- [ ] **Step 2: Run** `uv run pytest tests/test_item_tracker.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS.
- [ ] **Step 5: Commit** `feat: ws item check --tracker e ws item drafts`.

### Task 6: `ws item pull`, `ws item sync`, `ws item set-card`

**Files:**
- Create: `src/ws/itemsync.py`
- Modify: `src/ws/item_cli.py` (commands `pull`, `sync`, `set-card`)
- Test: `tests/test_item_sync.py`

**Interfaces:**
- Produces, in `ws.itemsync`:
  - `PULL_FIELDS = ("type", "epic", "assignee", "reporter", "blocks", "blocked_by", "relates")`;
  - `pull(root: Path, rel: str, fields: list[str], tracker: Tracker, people: People) -> dict`
    (`{"path", "changed": {field: {"item": old, "tracker": new}}}`; `ItemError` refusals);
  - `sync(projects: list[Project], root: Path, tracker: Tracker, today: date) -> dict`
    (`{"updated": [rel], "problems": [{"path", "problem"}]}`).
- Produces, CLI: `ws item pull <item> --fields F,...`; `ws item sync [projects]`;
  `ws item set-card <item> (<ref> | --none)` (`<item>` repo-relative, an absolute path inside the
  repo accepted). Exit 1 on a refusal or a problem, 2 on setup, 3 on a tracker error.
- Consumes: Task 1 (`set_keys`, `set_cache`, `item_path`, `write_text`), Task 2 (port), Task 3
  (`_projects`, `Project`), Task 4 (`write_back`, `recorded`, `clear`).

`pull` refuses: a field outside `PULL_FIELDS`; an item with no card or `tracker = false`; a card
the tracker lacks; an unmapped type; a person whose account has no dev id
(`the tracker's assignee acc-x has no dev id: run ws people add <e-mail>`). Links come as sorted
refs. `sync` writes, for each tracked item with a card, `{"status": card.status.value,
"priority": ..., "due": ..., "sprint": card.sprint or "", "synced": today}` (`priority` and `due`
left out when None); a card the tracker lacks is a problem and the item stays. `set-card <ref>`:
`write_back` then `clear`; `--none`: `clear` only, refused when nothing is recorded.

- [ ] **Step 1: Write the failing tests** (`item_repo`, `FakeTracker`):
  - `test_pull_copies_the_tracker_values` (`--fields type,assignee`; the two lines change, every
    other byte stays; JSON `changed`);
  - `test_pull_refuses_an_account_without_dev_id` and `test_pull_refuses_an_unknown_field`;
  - `test_sync_rewrites_only_the_tracker_table` (body and contract lines byte-identical; table
    values; `synced` today);
  - `test_sync_skips_untracked_and_cardless_items`;
  - `test_sync_missing_card_is_a_problem_and_leaves_the_item` (exit 1);
  - `test_set_card_writes_and_clears_the_record` (`record(rel, "TS-200")` first);
  - `test_set_card_refuses_another_card` (exit 1, the item unchanged);
  - `test_set_card_none_clears_only_a_recorded_item`.
- [ ] **Step 2: Run** `uv run pytest tests/test_item_sync.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS.
- [ ] **Step 5: Commit** `feat: ws item pull, sync e set-card`.

### Task 7: The `task-shaping` skill, `/card` and `checkpoint`

**Files:**
- Create: `skills/task-shaping/SKILL.md`
- Modify: `skills/card/SKILL.md`, `skills/checkpoint/SKILL.md`, `README.md` (command table,
  section "Projects"), `CLAUDE.md` (layout row of `projects/<slug>/` gains `project.toml`)

**Interfaces:**
- Consumes: the commands, flags and JSON keys of Tasks 2–6, as written in their Interfaces.
- Produces: `~/.claude/skills/task-shaping` once `ws setup` links it (the user runs it after the
  merge).

- [ ] **Step 1: Write `skills/task-shaping/SKILL.md`** (under 120 lines, neutral words, no
  `disable-model-invocation`). Description, third person: helps decide a task's nature (card
  type), size, epic, people and links, splits work that does not fit a sprint, and turns findings
  made during a task into proposed cards for the next sprint; use when the user plans, scopes or
  iterates on a task, or a finding appears mid-task. It writes only item files, never the tracker.
  Steps: read the item (if any) and `~/.claude/skills/card/references/card-rules.md`; propose type
  (the ordered questions), epic (from `project.toml`), size (split or not), people (dev ids,
  `ws people me`) and links, one-line reason each; on the user's yes, `ws item new <slug> ...
  --slug <english-slug>` or edit the front matter's contract keys (never `[tracker]`, never `me`);
  `ws item check <slug>` until no problems; offer `/card` (the user types it). A finding becomes a
  new item for the next sprint, never extra scope, unless the user says to include it.
- [ ] **Step 2: Update `skills/card/SKILL.md`:** the `create` row gains `item` (the item's
  repo-relative path; its `card` is written back after the apply); the description adds the
  example "/card reorganizar"; a "Reorganize" section: `ws item check --tracker`; show `problems`
  and each `drift` field in PT-BR with both values (names, not ids); ask, per field, which side is
  right; `ws item pull <path> --fields ...` for the tracker's side; `ws item drafts --only ...` for
  the item's side; write the title and sections of each `need_text` draft (real names, outside the
  repo) and `ws card check` each; one preview, one approval; show `waiting` and `by_hand`; after
  the apply `ws item sync` and `ws item table <slug>`. A write-back failure or an uncertain create
  names `ws item set-card`. Links to cards created in the same batch: a second `ws item drafts` run.
- [ ] **Step 3: Update `skills/checkpoint/SKILL.md`:** in "Check", when `projects/<slug>/project.toml`
  exists, run `ws item check <slug>` (offline) and fix the item files until it exits 0.
- [ ] **Step 4: Update `README.md`:** rows for `ws item new|check|drafts|pull|sync|table|set-card`
  and `ws task list [--since ...] [--role mine|following|all]`, in the table's style; under
  "Projects", one paragraph on `project.toml` and the item front matter, pointing to the spec.
- [ ] **Step 5: Check** `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`, and
  `wc -l skills/*/SKILL.md` (each under 500) — expected: clean.
- [ ] **Step 6: Commit** `docs: skill task-shaping, reorganizar no /card e itens no checkpoint`.
