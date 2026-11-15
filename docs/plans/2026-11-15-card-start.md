# `ws card start` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ws card start TS-N` checks the card and the repos read-only, cuts `<kind>/TS-N-<slug>`
from the fresh remote base in each repo of the task, writes a `move` (or start-date `edit`) draft
and prints the `ws card preview` text and code; the user's yes in the `apply` box is the only
tracker write.

**Architecture:** `ws.cardstart` holds the pure rules (slug, kind, task-branch match, repo order,
card change, draft text, undo lines) and the command (`run_start`). It reads the card through
`ws.tracker.port` (gains `Card.start`, `Tracker.today()`), the repos from `--repo`, the item's new
`repos` key (`ws.itemfile`, `ws.items.find_card_item`) or `[board.prefix_repos]`, and the base from
`[board.repos."<name>"] base` (`ws.boardconfig`). Git goes through new `ws.gittools` helpers. The
card side reuses `ws.card`: a new `preview()` returns what `run_preview` prints, and `write_draft()`
writes into `cards/drafts/`.

**Tech Stack:** Python 3.12+, standard library only at runtime; `uv`, `pytest`, `ruff`.

**Spec:** `docs/specs/2026-11-15-card-start-design.md` (all sections). Starts from `main` with the
task-items plan (2026-11-13) merged.

## Global Constraints

- Runtime code: standard library only. Run everything with `uv run` (`uv run pytest -q`,
  `uv run ruff check`, `uv run ruff format --check`).
- Names in English (modules, flags, JSON keys, `problems` and `warnings` texts for the model). Text
  for people is PT-BR: the preview (unchanged), the skill's lines to the user, the README cells.
- `ws card start` never calls `apply`, never commits, pushes or creates `-sdbx`; never stashes;
  never runs the `undo` lines. Git only: `fetch`, `switch`, `worktree add`, and reads.
- Every check runs before the first change in any repo; the git steps run before the draft.
- Tests: fake accounts `acc-me`, `acc-other`; repos `acme-api`, `acme-front` with local bare
  remotes under `tmp_path`; fake titles; `GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`;
  no real Jira, no network, no real names or hosts.
- Commits: prefix `feat:`, `fix:`, `test:`, `docs:` or `chore:`, PT-BR, at most 72 characters, no
  task ID, no `Co-Authored-By`; `git diff` before each message. Each task commits in its own
  worktree branch; the controller merges and pushes.

## Review Focus

1. Dirty tree in the second repo: the first repo is not switched, no draft, no preview (Task 6).
2. Branch only on origin: tracked locally (`--track`), not cut again from the base; an `-sdbx` sibling is never picked (Tasks 3, 4, 6).
3. Card in progress with a start date: no draft, no preview, exit 0; without one: an `edit` with the tracker's today, not the machine's (Tasks 2, 4, 6).
4. Title without a known prefix, no item `repos`, no `--repo`: exit 1 naming the three ways, no repo touched (Tasks 4, 6).
5. A repo missing under `repo_roots` (WSL path, typo) or its branch checked out in another worktree: a problem or `elsewhere` before any change; `--worktree` lands under the hidden `.worktrees/` (Tasks 3, 6).

## Parallel waves

- Wave 1 (5 agents, disjoint files): Task 1 (config and item keys), Task 2 (port), Task 3
  (`gittools`), Task 4 (pure rules), Task 5 (`card.preview`, `write_draft`).
- Wave 2: Task 6 (the command; consumes 1–5) and Task 7 (skill and docs; consumes the
  interfaces as written here), in parallel.

---

### Task 1: Repo keys in config and items

**Files:**
- Modify: `src/ws/config.py` (`REPO_NAME`), `src/ws/boardconfig.py`, `src/ws/itemfile.py`,
  `src/ws/items.py`
- Test: `tests/test_boardconfig.py`, `tests/test_itemfile.py`, `tests/test_items.py`

**Interfaces:**
- `ws.config.REPO_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")` (a repo directory name).
- `ws.boardconfig`: `DEFAULT_BASE = "master"`; `REPO_KEYS` gains `"base"`; `BOARD_KEYS` gains
  `"prefix_repos"`; `RepoSettings` gains `base: str | None = None` (last field);
  `BoardConfig` gains `prefix_repos: dict[str, tuple[str, ...]] = field(default_factory=dict)`
  (last field) and `base_for(repo: str) -> str` (`settings_for(repo).base`, else `DEFAULT_BASE`).
  `base` must match `(?!-)(?!.*\.\.)[A-Za-z0-9._/-]+`; a `prefix_repos` key matches `[^\[\]\s]+`,
  its value a non-empty list of `REPO_NAME`s. Errors are `ConfigInvalid` naming
  `board.repos."<key>".base` or `board.prefix_repos.<KEY>`.
- `ws.itemfile`: `LOCAL_KEYS = ("repos",)`; `schema_problems` accepts `CONTRACT_KEYS + LOCAL_KEYS`;
  `repos` must be a list (`repos must be a list`) of `REPO_NAME`s (`repos: '<x>' is not a repo
  name`); `Item.repos -> list[str] | None` (None when absent, `[]` kept).
- `ws.items.find_card_item(root: Path, ref: str) -> tuple[Item | None, list[str]]`: scans
  `projects/*/tasks/*.md` with `read_item`; documents skipped; an `ItemError` file becomes a
  warning `<rel>: <error>`; two items with that `card` raise `ItemError("<ref> is the card of two
  items: <rel>, <rel>; run ws item check")`.

- [ ] **Step 1: Write the failing tests:**
  - `test_repo_base_defaults_to_master` (`base_for("acme-api") == "master"`; `[board.repos."acme-api"]
    base = "main"` → `"main"`; a glob `"acme-*"` with `base = "develop"` → `"develop"` for `acme-front`);
  - `test_repo_base_must_be_a_branch_name` (`""`, `"-x"`, `"a..b"`, `1` → `ConfigInvalid` naming
    `board.repos."acme-api".base`; `ignore = true` with `base` → `must hold ignore = true alone`);
  - `test_prefix_repos_maps_a_title_prefix` (`BACK = ["acme-api"]` → `{"BACK": ("acme-api",)}`;
    absent → `{}`) and `test_prefix_repos_refuses_bad_entries` (`BACK = "acme-api"`, `BACK = []`,
    `BACK = ["../x"]`, key `"[X]"` → `ConfigInvalid` naming the key);
  - `test_schema_accepts_repos` (`["acme-api", "acme-front"]` and `[]` → `[]`; `item.repos`) and
    `test_schema_refuses_bad_repos` (`"acme-api"`, `["../x"]`, `["a/b"]` → the texts above);
  - `test_find_card_item_returns_the_item_with_that_card`, `test_find_card_item_none_when_absent`,
    `test_find_card_item_refuses_two_items_for_one_card` (both paths in the message),
    `test_find_card_item_reports_a_broken_item` (warning, other items still found).
- [ ] **Step 2: Run** `uv run pytest tests/test_boardconfig.py tests/test_itemfile.py tests/test_items.py -q` — expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS; `uv run ruff check` clean.
- [ ] **Step 5: Commit** `feat: base por repo, repos por prefixo e chave repos no item`.

### Task 2: Start date and today in the tracker port

**Files:**
- Modify: `src/ws/tracker/port.py`, `src/ws/tracker/jira_adapter.py`, `tests/fake_tracker.py`
- Test: `tests/test_tracker_port.py`

**Interfaces:**
- `Card` gains `start: date | None = None` (after `links`).
- `Tracker` gains `today() -> date` (today in the user's tracker time zone).
- `JiraTracker`: `_fields()` adds `settings.start_date_field` when set; `_neutral` parses it
  (`date.fromisoformat(value[:10])`, None when absent); caches the `myself()` answer for `me()` and
  `today()`; `today()` = `_now().astimezone(ZoneInfo(myself["timeZone"])).date()` with a module
  `_now()` returning `datetime.now(UTC)`; a bad zone → `TrackerError`.
- `FakeTracker(..., today=date(2026, 11, 16))` with `today()`; `make_card` passes `start` through.

- [ ] **Step 1: Write the failing tests** (`world` from `tests/test_card.py`, as
  `test_jira_card_is_the_neutral_card` does):
  - `test_jira_card_reads_the_start_date` (`START_FIELD` `"2026-11-10"` → `date(2026, 11, 10)`;
    absent → None; a config without `start_date_field` → None and the field not requested);
  - `test_jira_today_is_in_the_users_time_zone` (`timeZone` `"America/Sao_Paulo"`, `_now` =
    2026-11-16T01:30Z → `date(2026, 11, 15)`) and `test_jira_today_refuses_a_bad_time_zone`;
  - `test_fake_tracker_has_today_and_start` (still `isinstance(..., Tracker)`).
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_port.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS.
- [ ] **Step 5: Commit** `feat: data de início e hoje do usuário na porta do tracker`.

### Task 3: Git helpers

**Files:**
- Modify: `src/ws/gittools.py` (`assemble` uses `dirty`, behaviour unchanged)
- Test: `tests/test_gittools.py` (new fixture `cloned`: a bare `origin` cloned from `repo`, and a
  work clone)

**Interfaces** (all raise `GitError` on a failing command):
- `dirty(repo: Path) -> bool` (`status --porcelain --untracked-files=no` not empty);
- `fetch(repo: Path, remote: str) -> None` (`fetch --quiet <remote>`);
- `has_ref(repo: Path, ref: str) -> bool` (`rev-parse --verify --quiet <ref>^{commit}`);
- `head(repo: Path) -> tuple[str, bool]` (branch name, or the sha and `True` when detached);
- `local_branches(repo: Path) -> list[str]`; `remote_branches(repo: Path, remote: str) ->
  list[str]` (names without `<remote>/`, no `HEAD`);
- `switch(repo: Path, branch: str) -> None`;
  `switch_new(repo: Path, branch: str, start: str, track: bool) -> None`
  (`switch -c <branch> --no-track|--track <start>`);
- `add_worktree(repo: Path, path: Path, branch: str, start: str | None) -> None` (`start` set:
  `worktree add -b <branch> --no-track <path> <start>`; None: `worktree add <path> <branch>`);
- `worktree_of(repo: Path, branch: str) -> Path | None` (from `worktree list --porcelain`).

- [ ] **Step 1: Write the failing tests:** `test_dirty_ignores_untracked_files`;
  `test_fetch_then_has_ref` (a commit pushed after the clone is at `origin/main` after `fetch`;
  `has_ref(work, "origin/nope") is False`); `test_fetch_failure_is_a_git_error` (remote set to a
  missing path); `test_head_names_the_branch_or_the_detached_sha`;
  `test_local_and_remote_branches`; `test_switch_new_does_not_track` (no
  `branch.<name>.merge` config) and `test_switch_new_with_track_sets_the_upstream`;
  `test_add_worktree_new_and_existing_branch`; `test_worktree_of_finds_the_checkout` (the linked
  path, the main path, None).
- [ ] **Step 2: Run** `uv run pytest tests/test_gittools.py -q` — expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS (the `assemble` tests included).
- [ ] **Step 5: Commit** `feat: utilitários de git para iniciar a tarefa`.

### Task 4: The pure start rules

**Files:**
- Create: `src/ws/cardstart.py` (pure part only)
- Test: `tests/test_card_start_rules.py`

**Interfaces** (in `ws.cardstart`):
- `KINDS = ("feature", "fix", "chore", "refact", "test", "hotfix")`; `SLUG =
  re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")`; `MAX_SLUG = 40`; `SLUG_WORDS = 5`; `STOP_WORDS`
  (folded pt-BR articles, prepositions and contractions: a, o, as, os, um, uma, de, da, do, das,
  dos, e, em, no, na, nos, nas, para, pra, por, pelo, pela, com, ao, aos, que, se, ou);
- `class StartRefused(Exception)`;
- `title_prefix(title: str) -> str | None` (the first leading `[...]` text);
- `branch_slug(title: str) -> str` (may be `""`);
- `kind_for(card_type: str | None) -> str` (`"fix"` for `bug`, else `"feature"`);
- `branch_name(kind: str, ref: str, slug: str) -> str`;
- `is_task_branch(name: str, ref: str) -> bool` (`<KINDS>/<ref>-<slug>`, not ending `-sdbx`);
- `resolve_repos(flag: list[str], item_repos: list[str] | None, title: str, prefix_repos:
  dict[str, tuple[str, ...]]) -> tuple[list[str], str]` (repos in order, duplicates dropped, and
  `"flag"`, `"item"`, `"prefix"` or `"none"`);
- `card_change(status: Status, start: date | None, can_set_start: bool) -> str | None`
  (`todo`, `blocked` → `"move"`; `done`, `cancelled` → `StartRefused("card is <status>: reopen it
  in the tracker first")`; other open statuses → `"start"` when `start` is None and
  `can_set_start`, else None);
- `draft_text(ref: str, change: str, in_progress: str, today: date) -> str`;
- `@dataclass(frozen=True) class RepoStep: name: str; path: Path; base: str; action: str;
  previous: str; detached: bool; worktree: Path | None`;
- `undo_commands(steps: list[RepoStep], branch: str) -> list[str]` (paths through `shlex.quote`).

- [ ] **Step 1: Write the failing tests:**
  - `test_branch_slug_drops_prefix_accents_and_stop_words` (`"[BACK] Fechar o lote por horário de
    corte do dia"` → `"fechar-lote-horario-corte-dia"`);
  - `test_branch_slug_cuts_at_a_word_within_40` (`"[FRONT] Exibir histórico completo das
    liquidações processadas automaticamente"` → `"exibir-historico-completo-liquidacoes"`);
  - `test_branch_slug_of_stop_words_only_is_empty` (`"[FRONT] De a para o"` → `""`);
  - `test_title_prefix` (`"[BACK][API] x"` → `"BACK"`; `"Sem prefixo"` → None);
  - `test_kind_for_type` (`bug` → `fix`; `task`, `feature`, `improvement`, `hotfix`, None → `feature`);
  - `test_resolve_repos_order` (flag over item over prefix; `item_repos=[]` → `([], "item")`;
    unknown prefix → `([], "none")`; duplicates dropped);
  - `test_is_task_branch` (`feature/TS-5-x`, `fix/TS-5-a-b` yes; `feature/TS-55-x`,
    `feature/TS-5-x-sdbx`, `TS-5-x`, `feature/TS-5`, `wip/TS-5-x` no);
  - `test_card_change` (each status above; `can_set_start=False` → None);
  - `test_draft_text_move_and_start` (`'+++\nop = "move"\nkey = "TS-5"\nto = "Em andamento"\n+++\n'`
    and `'+++\nop = "edit"\nkey = "TS-5"\nstart = 2026-11-16\n+++\n'`);
  - `test_undo_commands` (`create` → `git -C <p> switch main` and `git -C <p> branch -D <b>`;
    worktree → `git -C <p> worktree remove <wt>` and `branch -D`; `track` like `create`; `reuse`
    → only the switch back; `current` → nothing; detached → `switch --detach <sha>`; a path with a
    space is quoted).
- [ ] **Step 2: Run** `uv run pytest tests/test_card_start_rules.py -q` — expected: FAIL.
- [ ] **Step 3: Implement** (no imports of `boardconfig`, `items` or `tracker.port`: plain values in).
- [ ] **Step 4: Run** the tests — expected: PASS; `uv run ruff check` clean.
- [ ] **Step 5: Commit** `feat: regras puras do início de tarefa`.

### Task 5: `card.preview` and `card.write_draft`

**Files:**
- Modify: `src/ws/card.py`
- Test: `tests/test_card.py`

**Interfaces:**
- `@dataclass(frozen=True) class Preview: status: int; text: str; code: str | None`.
- `preview(argument: str) -> Preview`: the path of `run_preview`, with stdout collected into
  `text` (stderr unchanged); `run_preview` becomes `sys.stdout.write(result.text)` plus
  `return result.status`, byte-identical output.
- `write_draft(name: str, text: str) -> Path`: `name` fullmatches `[A-Za-z0-9._-]+\.md`
  (else `ValueError`); writes `cards/drafts/<name>` (store ensured, mode 600, temp file and
  `os.replace`); a symlink or a directory at the name → `DraftError`.

- [ ] **Step 1: Write the failing tests** (`world`, `make_draft`):
  `test_preview_returns_text_and_code` (a move of TS-101 → status 0, `code` 12 hex, `text` ends
  with the `Para aplicar:` line; `run_preview` prints exactly `text`);
  `test_preview_refused_has_no_code` (status 1, `code is None`, text starts `Nada foi enviado`);
  `test_write_draft_overwrites_in_the_drafts_root` (mode 600; a second write replaces; a symlink →
  `DraftError`; `"a/b.md"` → `ValueError`).
- [ ] **Step 2: Run** `uv run pytest tests/test_card.py -q` — expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS.
- [ ] **Step 5: Commit** `feat: prévia do card devolve texto e código`.

### Task 6: The command `ws card start`

**Files:**
- Modify: `src/ws/cardstart.py` (add `run_start`), `src/ws/cli.py` (`start` in `_add_card`)
- Test: `tests/test_card_start.py`

**Interfaces:**
- `run_start(ref: str, repos: list[str], kind: str | None, desc: str | None, worktree: bool,
  dry_run: bool) -> int`; CLI `ws card start REF [--repo NAME]... [--kind {KINDS}] [--desc SLUG]
  [--worktree] [--dry-run]`.
- Prints the spec's JSON (`ref`, `title`, `status`, `start`, `branch`, `repos_from`, `repos`,
  `card_change`, `draft`, `preview`, `code`, `apply`, `dry_run`, `problems`, `warnings`, `undo`);
  `apply` = `f"ws card apply {shlex.quote(draft)} --approve {code}"`.
- Exit: 0; 1 with `problems`; 2 for `BoardMissing`, `ConfigMissing`, `ConfigInvalid`,
  `TrackerSetup`; 3 for `TrackerError`; the preview's status when it is not 0.
- Consumes: Task 1 (`load_board`, `base_for`, `prefix_repos`, `statuses[Status.IN_PROGRESS]`,
  `remote`, `REPO_NAME`, `find_card_item`, `Item.repos`), Task 2 (`open_tracker`, `card`, `me`,
  `today`, `capabilities`), Task 3, Task 4, Task 5, `userconfig.load_standup().repo_roots`,
  `config.repo_root()`.

Flow: validate `REF`, `--repo` (`REPO_NAME`), `--desc` (`SLUG`, ≤ `MAX_SLUG`); board, tracker,
card (None, level ≠ 0, `me()` not assignee nor reporter, `StartRefused` → problems); item; repos;
kind and slug (empty → `the title gives no slug; pass --desc`); per repo: path = first
`<root>/<name>` with `.git`, `dirty` (not with `--worktree`), `fetch`, `has_ref(<remote>/<base>)`
(else `<remote>/<base> does not exist in <name>; set [board.repos."<name>"] base`); task branches
over all repos (spec rule) and each repo's action; all problems at once, then stop. `--dry-run`
stops here. Git per repo, recording `RepoStep`s; a `GitError` → `problems`, `undo_commands`,
exit 1, no draft. Then `card_change`; a change → `write_draft(f"start-{ref}.md", draft_text(...))`
and `card.preview(str(path))`.

- [ ] **Step 1: Write the failing tests** (a fixture like `world` in `tests/test_board_cli.py`:
  `roots/acme-api` and `roots/acme-front` with bare remotes holding `master`; `config.toml` with
  `[standup] repo_roots`, a `[board]` like `tests/test_boardconfig.py`'s `EXAMPLE` and
  `[board.prefix_repos] BACK = ["acme-api"]`, `FRONT = ["acme-front"]`; `WS_REPO_ROOT` with
  `projects/demo/tasks/`; `FakeTracker` through `monkeypatch.setattr("ws.tracker.port.open_tracker",
  ...)`; `ws.card.preview` replaced by a recorder returning `Preview(0, "Prévia...\n",
  "0123456789ab")`):
  - `test_start_cuts_the_branch_from_the_remote_base_and_previews_the_move` (TS-5 `todo`,
    `"[BACK] Fechar o lote por horário de corte do dia"` → exit 0; acme-api on
    `feature/TS-5-fechar-lote-horario-corte-dia` at `origin/master`, no upstream; acme-front
    untouched; the draft is the move text; `repos_from == "prefix"`; `apply` as above);
  - `test_start_uses_the_item_repos_and_the_flag_overrides`;
  - `test_start_bug_is_fix_and_flags_override_kind_and_desc`;
  - `test_start_dirty_second_repo_changes_nothing` (`--repo acme-api --repo acme-front`, front
    dirty → exit 1, problem names acme-front, api still on `master`, no draft, no preview);
  - `test_start_without_repos_names_the_three_ways` (`"Sem prefixo"` → exit 1; the problem has
    `--repo`, `repos = [...]` and `[board.prefix_repos]`);
  - `test_start_rerun_reuses_the_branch` (second run: action `current`, same sha, exit 0);
  - `test_start_tracks_a_branch_only_on_origin` (`feature/TS-5-outro-nome` pushed from another
    clone and `feature/TS-5-outro-nome-sdbx` too → action `track`, upstream
    `origin/feature/TS-5-outro-nome`, a warning names both names);
  - `test_start_two_task_branches_is_a_problem`;
  - `test_start_in_progress_with_a_start_date_writes_no_draft` (exit 0, `card_change` None, no
    preview, the branch made);
  - `test_start_in_progress_without_a_start_date_drafts_the_tracker_today` (`start = 2026-11-16`);
  - `test_start_refuses_a_done_card_and_someone_elses_card` (exit 1, no repo touched);
  - `test_start_missing_base_names_the_config_key` (`base = "main"`, absent on origin);
  - `test_start_missing_repo_is_a_problem` (`--repo ghost`);
  - `test_start_partial_failure_prints_undo` (front has an untracked `x.txt` that `origin/master`
    tracks → exit 1; `undo == ["git -C <api> switch master", "git -C <api> branch -D <branch>"]`;
    no draft);
  - `test_start_worktree_leaves_the_checkout_alone` (`<roots>/.worktrees/acme-api-TS-5` on the
    branch; main checkout on `master` and dirty is fine);
  - `test_start_branch_in_another_worktree_is_elsewhere` (rerun without `--worktree` → action
    `elsewhere`, the worktree path, nothing switched);
  - `test_start_dry_run_changes_nothing`; `test_start_empty_item_repos_does_only_the_card`;
  - `test_start_without_board_exits_2`;
  - `test_start_through_the_jira_adapter_and_the_real_preview` (`world` from `tests/test_card.py`
    then the roots; TS-101 `todo` with an `Em andamento` transition → exit 0, `code` 12 hex,
    `cards/pending/<code>.json` exists).
- [ ] **Step 2: Run** `uv run pytest tests/test_card_start.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check` —
  expected: clean.
- [ ] **Step 5: Commit** `feat: ws card start prepara branches e prévia do card`.

### Task 7: Skill and docs

**Files:**
- Modify: `skills/card/SKILL.md`, `skills/task-shaping/SKILL.md`, `README.md`,
  `docs/specs/2026-11-13-task-items-design.md` (one bullet under "The item file")

**Interfaces:**
- Consumes: the command, flags, JSON keys and exit codes of Task 6, as written above.

- [ ] **Step 1: `skills/card/SKILL.md`:** the description gains the example "/card iniciar
  TS-5431"; a "Start (`/card iniciar TS-N`)" section, neutral words: run `ws card start TS-N`
  (flags only from the user's words); exit 1: show `problems` in PT-BR and ask only what the user
  settles (repos: numbered, with the `[board.prefix_repos]` names as options; a slug), then rerun
  with `--repo`/`--desc`, and offer to write `repos = [...]` in the item; show each repo's branch
  and action, the `warnings`, then `preview` exactly as printed and run the printed `apply` (its
  box is the approval; never in the same command line); `card_change` null → say the card was
  already started; `undo` shown and offered, run only on a yes. Never push, commit or create
  `-sdbx`.
- [ ] **Step 2: `skills/task-shaping/SKILL.md`:** when proposing an item, propose `repos` too.
- [ ] **Step 3: `README.md`:** a row for `ws card start` in the command table; under "Local
  config", `[board.repos."<name>"] base` and `[board.prefix_repos]`.
- [ ] **Step 4: the items spec:** the `repos` key, pointing to `2026-11-15-card-start-design.md`.
- [ ] **Step 5: Check** `uv run pytest -q` and `wc -l skills/*/SKILL.md` (each under 500).
- [ ] **Step 6: Commit** `docs: início de tarefa no /card e chave repos do item`.
