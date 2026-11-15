# Card review package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ws review pack TS-N` collects, read-only, each repo's changes of the card's task branch
against the merge base with the remote base (committed, staged, unstaged, untracked), sorted by
kind, with new migrations, env var names, test files and the card context, into a private
`pack.json`; the `card-review` skill turns it into `review.md` (PT-BR) beside it.

**Architecture:** Flat modules, as `cardstart`: `ws.reviewpaths` (pure categories),
`ws.reviewdiff` (git reads: checkout, merge base, files, hunks, commits), `ws.reviewsignals` (pure:
migrations through `ws.release.migrations`, env vars through `ws.envcheck`), `ws.reviewcard`
(card context through the port, which gains `description`), and `ws.reviewpack` (the command and
its CLI `register`). Repo resolution is shared with `ws card start` (`cardstart.repos_for_card`,
`cardstart.locate_repo`). The config gains `[board.repos."<name>"] review_categories`.

**Tech Stack:** Python 3.12+, standard library only at runtime; `uv`, `pytest`, `ruff`.

**Spec:** `docs/specs/2026-11-15-card-review-design.md` (all sections). Starts from `main` with the
card-start plan (2026-11-15) merged.

## Global Constraints

- Runtime code: standard library only. Run everything with `uv run` (`uv run pytest -q`,
  `uv run ruff check`, `uv run ruff format --check`).
- Names in English (modules, flags, JSON keys, `problems`, `warnings` and `flags` texts). PT-BR
  only in the skill's lines to the user and in `review.md`.
- `ws review pack` never writes to the tracker, never commits, pushes, stashes, switches or
  changes a work tree; git only `fetch` and reads. It never runs tests.
- Files only under `config.data_dir()`; never under the workspace repo. Tests set `WS_DATA_DIR`
  to `tmp_path`.
- Tests: fake accounts `acc-me`, `acc-other`; repos `acme-api`, `acme-front` with local bare
  remotes under `tmp_path`; fake titles; `GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`;
  no real Jira, no network, no real names or hosts.
- Commits: prefix `feat:`, `fix:`, `test:`, `docs:` or `chore:`, PT-BR, at most 72 characters, no
  task ID, no `Co-Authored-By`; `git diff` before each message. Each task commits in its own
  worktree branch; the controller merges and pushes.

## Review Focus

1. A rename with edits (`R087`) and a rename made only in the work tree (shows as a deletion plus an untracked file): `status`, `old_path`, category by the new path (Tasks 2, 6).
2. A binary file, committed and untracked: `binary: true`, null counts, no hunks, never decoded as text by the signals (Tasks 2, 3).
3. An untracked new migration: listed with `stages == ["untracked"]`, parsed from the work tree, counted in `heads_after` (Tasks 2, 3, 6).
4. The task branch checked out in another worktree, or nowhere: read from that worktree (never from the main checkout's unrelated changes), or commits only with a warning (Tasks 2, 6).
5. A card with no item and no title prefix (and a card absent from the tracker): exit 1 naming the three ways, project `standalone`, no repo read (Task 6).

## Parallel waves

- Wave 1 (5 agents, disjoint files): Task 1 (categories and config), Task 2 (`reviewdiff`),
  Task 3 (`reviewsignals`), Task 4 (port and card context), Task 5 (skill and docs; consumes the
  interfaces as written here).
- Wave 2: Task 6 (the command; consumes 1–4).

---

### Task 1: Path categories and the config key

**Files:**
- Create: `src/ws/reviewpaths.py`
- Modify: `src/ws/boardconfig.py`, `src/ws/envcheck.py` (rename `_glob_regex` to `glob_regex`,
  its two call sites follow; behaviour unchanged)
- Test: `tests/test_review_paths.py`, `tests/test_boardconfig.py`

**Interfaces:**
- `ws.envcheck.glob_regex(pattern: str) -> re.Pattern[str]`.
- `ws.reviewpaths.CATEGORIES = ("test", "migration", "contract", "model", "config", "front",
  "other")`; `DEFAULT_RULES: tuple[tuple[str, tuple[str, ...]], ...]` (the spec's table, in that
  order, without `other`); `category_for(path: str, overrides: dict[str, tuple[str, ...]] |
  None = None) -> str` (override rules in their order, then `DEFAULT_RULES`, else `"other"`;
  `glob_regex(...).fullmatch`).
- `ws.boardconfig`: `REPO_KEYS` gains `"review_categories"`; `RepoSettings` gains
  `review_categories: dict[str, tuple[str, ...]] | None = None` (last field); `BoardConfig` gains
  `review_categories_for(repo: str) -> dict[str, tuple[str, ...]]` (`{}` when absent). A key must
  be in `CATEGORIES`, a value a non-empty list of non-empty strings; errors are `ConfigInvalid`
  naming `board.repos."<key>".review_categories[.<category>]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_category_defaults` (parametrized: `app/alembic/versions/0003_lote.py` → `migration`;
    `tests/test_lote.py`, `src/app/lote/lote.component.spec.ts` → `test`; `app/api/routes/lote.py`,
    `app/schemas/lote.py` → `contract`; `app/models/lote.py` → `model`; `Dockerfile`,
    `.github/workflows/ci.yml`, `app/core/settings.py` → `config`; `src/app/lote/lote.component.ts`
    → `front`; `app/services/lote.py`, `README.md` → `other`);
  - `test_category_test_wins_over_migration` (`tests/alembic/versions/test_x.py` → `test`);
  - `test_category_override_wins_over_defaults` (`{"front": ("src/app/models/**",)}` →
    `src/app/models/lote.ts` is `front`; without it, `model`);
  - `test_review_categories_for_a_repo` (`[board.repos."acme-front"] review_categories = { front =
    ["src/app/models/**"] }` → that dict with a tuple; absent → `{}`; key `"acme-*"` applies to
    `acme-front`);
  - `test_review_categories_refuses_bad_entries` (`{ nope = ["x"] }`, `{ front = "x" }`,
    `{ front = [] }`, `{ front = [""] }`, `review_categories = 1` → `ConfigInvalid` naming the key).
- [ ] **Step 2: Run** `uv run pytest tests/test_review_paths.py tests/test_boardconfig.py -q` — expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` (the envcheck tests included) — expected: all PASS; `uv run ruff check` clean.
- [ ] **Step 5: Commit** `feat: categorias de arquivo da revisão e chave por repo`.

### Task 2: The diff in git

**Files:**
- Create: `src/ws/reviewdiff.py` (its own `_git` runner returning bytes, `-c core.quotePath=false`,
  `--no-ext-diff --no-color`; failures raise `ws.gittools.GitError`; uses `gittools.head`,
  `local_branches`, `worktree_of` and `cardstart.is_task_branch`)
- Test: `tests/test_review_diff.py` (fixture: a bare `origin` holding `master`, a work clone)

**Interfaces:**
- `MAX_BLOCKS = 20`; `STAGES = ("committed", "staged", "unstaged", "untracked")`;
  `class ReviewRefused(Exception)`.
- `@dataclass(frozen=True) class Checkout: branch: str; worktree: Path | None`.
- `@dataclass(frozen=True) class FileChange: path: str; old_path: str | None; status: str;
  added: int | None; deleted: int | None; binary: bool; stages: tuple[str, ...];
  hunks: tuple[int, ...]` (`status` one of `added`, `modified`, `deleted`, `renamed`, `copied`,
  `type_changed`).
- `@dataclass(frozen=True) class Commit: sha: str; subject: str`;
  `@dataclass(frozen=True) class Collected: merge_base: str; files: tuple[FileChange, ...];
  commits: tuple[Commit, ...]`.
- `find_checkout(repo: Path, ref: str) -> Checkout`: the current branch when it is a task branch;
  else the only local task branch and `worktree_of` it (None when checked out nowhere). Raises
  `ReviewRefused`: `no task branch for <ref> in <repo.name>; run ws card start <ref>`;
  `<ref> has more than one task branch in <repo.name>: <a>, <b>`; `<branch> is checked out in
  <path>, which no longer exists; run git -C <repo> worktree prune`.
- `collect(repo: Path, checkout: Checkout, base_ref: str) -> Collected`: with a worktree, the
  files are `git diff -M <merge_base>` there plus `ls-files --others --exclude-standard`, `stages`
  from `diff <mb> <branch>`, `diff --cached`, `diff`, the untracked list; without one, `diff -M
  <mb> <branch>` and `stages == ("committed",)`. Counts from `--numstat` (`-` → binary); an
  untracked file is binary when its first 8000 bytes hold a NUL, else `added` is its line count and
  `hunks == (1,)`; hunks from `-U0` headers. Files sorted by path; commits `<mb>..<branch>` oldest
  first.
- `diff_command(repo: Path, checkout: Checkout, merge_base: str) -> str` (`git -C <worktree> diff
  -M <mb>` or `git -C <repo> diff -M <mb> <branch>`, through `shlex.quote`).

- [ ] **Step 1: Write the failing tests:**
  - `test_find_checkout_current_branch` (on `feature/TS-5-fechar-lote` → that branch, worktree the
    clone);
  - `test_find_checkout_branch_in_another_worktree` (clone on `master`, branch in a linked worktree
    → its path) and `test_find_checkout_branch_checked_out_nowhere` (worktree None);
  - `test_find_checkout_refuses_none_and_two` (messages as above; a `feature/TS-5-x-sdbx` sibling
    alone counts as none);
  - `test_collect_committed_staged_unstaged_and_untracked` (commit `a.py` on the branch then edit it
    unstaged; stage a new `b.py`; untracked `c.py` → stages `("committed", "unstaged")`,
    `("staged",)`, `("untracked",)`; exact counts);
  - `test_collect_compares_with_the_merge_base` (a commit pushed to `origin/master` after the branch
    point is not listed);
  - `test_collect_rename_keeps_the_old_path` (`git mv x.py y.py` plus one edited line, committed →
    `renamed`, `old_path == "x.py"`);
  - `test_collect_binary_files` (committed and untracked bytes with a NUL → `binary`, counts None,
    `hunks == ()`);
  - `test_collect_hunks_are_new_side_lines` (lines 3 and 10 of a 12-line file changed → `(3, 10)`);
  - `test_collect_reverted_file_is_not_listed` (committed change undone in the work tree);
  - `test_collect_without_worktree_reads_commits_only` and `test_collect_commits_oldest_first`;
  - `test_diff_command_quotes_paths` (a folder with a space).
- [ ] **Step 2: Run** `uv run pytest tests/test_review_diff.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS; `uv run ruff check` clean.
- [ ] **Step 5: Commit** `feat: leitura das mudanças da branch da tarefa para revisão`.

### Task 3: Migrations and env vars from the changes

**Files:**
- Create: `src/ws/reviewsignals.py` (pure but `new_side`, which reads files)
- Test: `tests/test_review_signals.py`

**Interfaces:**
- `migration_report(base: dict[str, str], new: dict[str, str]) -> tuple[dict, list[str],
  list[str]]` (path → source of the migration files at the merge base and in the new tree; returns
  the report `{"added": [{"path", "revision", "down_revision": [...]}], "changed_existing":
  [...], "heads_before": [...], "heads_after": [...]}`, the flags and the warnings). Uses
  `parse_revision`, `revisions`, `heads`; `MigrationUnreadable` → a warning, the file skipped.
  Flags: `existing migration changed: <path>`, `existing migration deleted: <path>`,
  `more than one Alembic head after the change: <a>, <b>`.
- `env_report(base: dict[str, bytes], new: dict[str, bytes], profile: RepoProfile, changed:
  set[str]) -> tuple[dict, list[str], list[str]]`: `scan_python` (and `scan_shell` on
  `profile.shell_files`) over both sides; report `{"added": [{"name", "required", "where":
  [...]}], "removed": [...]}` sorted by name; flag `required env var added: <NAME>; check the
  Parameter Store` per required added name; scan warnings kept only for paths in `changed`.
- `profile_for(name: str, path: Path, settings: EnvCheckSettings | None) -> RepoProfile` (the
  `[env_check.repos.<name>]` profile, else a plain one: `kind="python"`, no helpers, prefixes or
  globs beyond `DEFAULT_EXCLUDE_GLOBS`).
- `new_side(base: dict[str, bytes], root: Path, removed: list[str], present: list[str]) ->
  dict[str, bytes]` (base minus `removed`, each `present` path read from `root`; a missing or
  non-regular file is skipped).

- [ ] **Step 1: Write the failing tests:**
  - `test_migration_report_new_migration_on_the_base_head` (base `b1`←`b2`, new adds `c3` down
    `b2` → `added == [{"path": ..., "revision": "c3", "down_revision": ["b2"]}]`, heads `["b2"]`
    → `["c3"]`, no flags);
  - `test_migration_report_flags_changed_and_deleted_existing` (both flag texts);
  - `test_migration_report_flags_two_heads` (`c3` down `b1` → `heads_after == ["b2", "c3"]` and the
    flag);
  - `test_migration_report_unreadable_is_a_warning` (a syntax error names the path; others read);
  - `test_env_report_added_and_removed` (base reads `A`; new reads `os.environ["B"]` and drops `A`
    → added `B` required, removed `["A"]`, flag for `B`; `os.getenv("C")` → not required, no flag);
  - `test_env_report_settings_base_in_an_unchanged_file` (`class Base(BaseSettings)` in
    `core/base.py` unchanged; `class S(Base): lote_cutoff: str` added → `LOTE_CUTOFF` added);
  - `test_env_report_uses_the_profile_helpers` (`env_str("D")` with `helpers=("env_str",)`);
  - `test_env_report_keeps_warnings_of_changed_paths_only`;
  - `test_new_side_overlays_the_work_tree` and `test_profile_for_falls_back_to_a_plain_profile`.
- [ ] **Step 2: Run** `uv run pytest tests/test_review_signals.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS; `uv run ruff check` clean.
- [ ] **Step 5: Commit** `feat: migrations e variáveis de ambiente das mudanças`.

### Task 4: The card description and the card context

**Files:**
- Modify: `src/ws/tracker/port.py`, `src/ws/tracker/jira_adapter.py`, `tests/fake_tracker.py`
- Create: `src/ws/reviewcard.py`
- Test: `tests/test_tracker_port.py`, `tests/test_review_card.py`

**Interfaces:**
- `CAPABILITIES` and `JIRA_CAPABILITIES` gain `"description"`; `Tracker` gains
  `description(ref: str) -> str | None` (plain text, headings as `## `; None when empty).
- `JiraTracker.description`: `client.issue(ref, ["description"])`, ADF through
  `ws.cardrules.adf_text` (move it to `ws.adf` if the import makes a cycle); 404 → None; other
  `JiraError` → `TrackerError`.
- `FakeTracker(..., descriptions: dict[str, str] | None = None)` with `description(ref)`.
- `ws.reviewcard.done_when(text: str) -> str | None`: the lines under the heading whose
  `cardrules.fold` is `pronto quando` (any `#` level) up to the next heading, stripped; None when
  absent or empty.
- `ws.reviewcard.card_context(tracker: Tracker, ref: str) -> tuple[dict | None, list[str]]`: None
  when the card is absent; else `{"ref", "title", "type", "status", "done_when"}` and warnings:
  `the tracker gives no card description; read Pronto quando in the tracker` (no capability),
  `<ref> has no Pronto quando section` (absent or empty).

- [ ] **Step 1: Write the failing tests:**
  - `test_jira_description_is_plain_text` (ADF heading `Pronto quando` plus a bullet list →
    `"## Pronto quando\n- ..."`; only `description` requested; null → None; 404 → None; 500 →
    `TrackerError`);
  - `test_fake_tracker_has_description` (still `isinstance(..., Tracker)`);
  - update the capability assertions that list `JIRA_CAPABILITIES`;
  - `test_done_when_takes_the_section_until_the_next_heading` (`"## Contexto\nx\n## Pronto quando\n-
    a\n- b\n## Como reproduzir\ny"` → `"- a\n- b"`; `"### pronto QUANDO"` works; absent → None;
    empty → None);
  - `test_card_context_reads_the_card` (status value, type, `done_when`) and
    `test_card_context_without_the_capability_warns` and `test_card_context_absent_card`.
- [ ] **Step 2: Run** `uv run pytest tests/test_tracker_port.py tests/test_review_card.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — expected: all PASS.
- [ ] **Step 5: Commit** `feat: descrição do card na porta e contexto para revisão`.

### Task 5: The skill `card-review` and docs

**Files:**
- Create: `skills/card-review/SKILL.md`, `tests/test_card_review_skill.py`
- Modify: `README.md` (a row for `ws review pack`; under "Local config",
  `[board.repos."<name>"] review_categories`)

**Interfaces:**
- Consumes the command, flags, JSON keys, flags texts and exit codes of Tasks 2–4 and 6, as written
  here and in the spec.

- [ ] **Step 1: Write the failing test** `test_skill_names_the_command_and_the_rules`: front
  matter `name: card-review`, no `disable-model-invocation`; the text has `ws review pack`,
  `diff_command`, `review.md`, `pack.json`, `## Olhar primeiro`, `## Riscos`, `done_when`, `#L`,
  `never commit`; under 500 lines.
- [ ] **Step 2: Write the skill.** Description (third person): builds the local review package of
  a card before its changes are committed; use when the user asks to review a card's changes or
  for its review package ("/card-review TS-5431", "monta a revisão do TS-5431"); read-only, never
  commits. Steps, as the spec's "The skill": run the pack (flags only from the user's words);
  exit 1 → problems in PT-BR, ask only repos or project, rerun; exit 2/3 → show stderr, stop; read
  per file with `diff_command -- <path>` in the spec's order, untracked with Read, lockfiles by
  counts; write `review.md` with Write at `review_path` (the six sections, links
  `[path:line](<abs_path>#L<line>)` from `hunks` or the diff); reply with the path, `code <path>`
  and the top three risks, nothing more. Rules: never commit, push, stash, run tests, write the
  tracker, publish an Artifact, or copy the review into the workspace repo.
- [ ] **Step 3: README** rows as above.
- [ ] **Step 4: Run** `uv run pytest tests/test_card_review_skill.py -q` — expected: PASS.
- [ ] **Step 5: Commit** `docs: skill card-review e comando ws review pack no README`.

### Task 6: The command `ws review pack`

**Files:**
- Create: `src/ws/reviewpack.py`
- Modify: `src/ws/cardstart.py` (extract, behaviour unchanged), `src/ws/cli.py`
  (`reviewpack.register(subparsers)`)
- Test: `tests/test_review_pack.py`

**Interfaces:**
- `ws.cardstart`: `locate_repo(name: str, roots: tuple[Path, ...]) -> Path | None` (used by
  `_locate`); `@dataclass(frozen=True) class RepoChoice: names: list[str]; source: str; item: Item
  | None; problems: list[str]; warnings: list[str]` and `repos_for_card(root: Path, ref: str,
  title: str, flag: list[str], prefix_repos: dict[str, tuple[str, ...]]) -> RepoChoice` (the body
  of `_repo_names`, which now wraps it).
- `ws.reviewpack`: `DEFAULT_PROJECT = "standalone"`; `review_folder(project: str, ref: str) ->
  Path`; `write_pack(folder: Path, data: dict) -> Path` (folders 700 from `data_dir()/projects`
  down, `pack.json` 600 by temp file and `os.replace`, an earlier `review.md` deleted);
  `run_pack(ref: str, repos: list[str], project: str | None) -> int`; `register(subparsers)` for
  `ws review pack REF [--repo NAME]... [--project SLUG]`.
- JSON and exit codes: the spec's "Output" and "Exit codes"; `flags` prefixed `<repo>: `, plus
  `<repo>: code changed with no test file changed` (a non-test file changed, no test file did).

Flow: validate `REF` (`vocab.REF`), `--repo` (`REPO_NAME`), `--project` (`project.SLUG_PATTERN`);
`load_board`, `repo_roots`, `open_tracker`, `card_context` (None → `<ref> was not found in the
tracker's project`); `repos_for_card` (title `""` when the card is absent); project; per repo:
`locate_repo`, `fetch` (a `GitError` → warning, `fetched: false`), `has_ref(base_ref)`,
`find_checkout`, `collect`, `category_for` with `review_categories_for`, migrations (`files_at` of
the migration paths at the merge base; new side by `new_side`, or `files_at(branch)` without a
worktree), env only when a `.py` or shell file changed (`load_settings()`, `profile_for`), tests,
`by_category`; a `ReviewRefused`, `GitError` or `SetupError` → a problem for that repo. Then
`write_pack`, print, exit.

- [ ] **Step 1: Write the failing tests** (fixture like `tests/test_card_start.py`'s: `roots/acme-api`
  and `roots/acme-front` with bare remotes on `master`, `[board.prefix_repos] BACK = ["acme-api"]`,
  `FRONT = ["acme-front"]`; item `projects/demo/tasks/01-lote.md` with `card = "TS-5"`, `repos =
  ["acme-api"]`; `FakeTracker` with TS-5 and a description holding `## Pronto quando\n- lote fecha
  às 18h`; `WS_DATA_DIR` under `tmp_path`):
  - `test_pack_collects_the_task_branch` (acme-api on `feature/TS-5-fechar-lote`: committed
    `app/alembic/versions/0003_lote.py` (`c3` down `b2`), unstaged `app/api/routes/lote.py`,
    untracked `tests/test_lote.py` → exit 0; categories `migration`, `contract`, `test`;
    `migrations.added`; `tests.added == ["tests/test_lote.py"]`; `card.done_when == "- lote fecha
    às 18h"`; `project == "demo"`; `repos_from == "item"`);
  - `test_pack_writes_private_files_and_overwrites` (folder 0o700, `pack.json` 0o600, file JSON ==
    stdout JSON; second run replaces; an earlier `review.md` is gone);
  - `test_pack_env_var_added` (`os.getenv("LOTE_CUTOFF_HOUR")` added → in `env.added` with `where`);
  - `test_pack_untracked_new_migration` (stages `["untracked"]`, `heads_after == ["c3"]`);
  - `test_pack_reads_the_branch_in_another_worktree` (main checkout on `master` with an unrelated
    dirty file; branch in `roots/.worktrees/acme-api-TS-5` with an unstaged change → `worktree` that
    path; the unrelated file absent);
  - `test_pack_branch_checked_out_nowhere_warns` (commits only, a warning);
  - `test_pack_repo_without_task_branch_is_a_problem` (`--repo acme-front` on `master` → exit 1,
    the problem names acme-front and `ws card start TS-5`; pack written with it);
  - `test_pack_without_repos_names_the_three_ways` (no item, `"Sem prefixo"` → exit 1; `--repo`,
    `repos = [...]`, `[board.prefix_repos]`; `project == "standalone"`);
  - `test_pack_prefix_and_flag_resolution`; `test_pack_project_flag_wins`;
  - `test_pack_category_override_from_config` (`review_categories = { front =
    ["src/app/models/**"] }` → `front`);
  - `test_pack_flags_a_changed_existing_migration` and `test_pack_flags_code_without_tests`;
  - `test_pack_fetch_failure_is_a_warning` (remote URL to a missing path, `origin/master` fetched
    before → exit 0, `fetched: false`);
  - `test_pack_missing_base_names_the_config_key` (`base = "main"`);
  - `test_pack_card_without_description_capability_warns`;
  - `test_pack_never_changes_the_repos` (HEAD, `status --porcelain`, `stash list` equal before and
    after);
  - `test_pack_without_board_exits_2` and `test_pack_tracker_error_exits_3` (nothing written).
- [ ] **Step 2: Run** `uv run pytest tests/test_review_pack.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` (`tests/test_card_start.py` unchanged and passing),
  `uv run ruff check`, `uv run ruff format --check` — expected: clean.
- [ ] **Step 5: Commit** `feat: ws review pack monta o pacote de revisão do card`.
