# Board Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cards follow the code: `ws board status` computes, from git, where each open card's code
is (branch, sandbox, master, production tag) and the forward moves it proves; `ws board drafts`
turns them into `/card` move drafts for one preview and one approval; the daily uses the same
moves instead of the old R1 and R2 rules.

**Architecture:** Four small units: `boardconfig` (the `[board]` table), `codeposition` (git only:
fetch, commits by key, environment membership, the rung of each key), `boardrules` (tasks plus
positions give moves, held cards and cards to confirm) and `board_cli` (the two commands). The
standup report takes the board JSON instead of computing suggestions. Writes to Jira stay in the
existing `ws card preview` and `ws card apply`.

**Tech Stack:** Python 3.12 standard library only at runtime (`subprocess`, `tomllib`,
`concurrent.futures`, `dataclasses`); `pytest` and `ruff` through `uv`; git CLI.

**Spec:** `docs/specs/2026-11-05-board-sync-design.md` (read it first; the decisions D1–D11 and
the "holds only as far as it can prove" rule are the contract).

## Global Constraints

- Runtime code uses the standard library only. Run tests with `uv run pytest -q`, lint with
  `uv run ruff check` and `uv run ruff format --check`.
- Every file and identifier name in English; JSON keys in English; texts the user reads in the
  skills are PT-BR.
- A task has as many commits as it has behaviors: one behavior per commit, its tests in the
  same commit, the whole suite passing at each one. The split listed in each task is the
  expected one; a finer split is fine, merging two into one is not.
- Commits: atomic, prefix `feat:`, `fix:`, `test:`, `docs:` or `chore:`, message in PT-BR, at most
  72 characters, no task ID, no `Co-Authored-By`, no "Generated with" line. Run `git diff` before
  each message. `git pull` before starting; push to `main` at the end.
- No real names, hosts or company domains in the repo (the pre-commit hook checks); test fixtures
  use `example.com`, `TS-1xx` keys and repo names like `demo-api`.
- Git calls go through `subprocess.run([...], capture_output=True, text=True, encoding="utf-8",
  errors="replace", check=False)` with `-c core.quotepath=false`, like `ws.standup._git`.
- Canonical statuses are `ws.taskmodel.Status` values; the rungs are `todo` 0, `in_progress` and
  `review` 1, `validation` 2, `ready_deploy` 3, `done` 4.
- `ws board` never writes to Jira, git refs other than remote-tracking ones, or the work tree.

## Review Focus

Each risk has an alternative, a warning or both (spec, "Risks: alternative and warning"). The
warning strings below are exact; the tests assert them.

- A fetch fails: `fetch <repo>: <first stderr line>`; positions with commits there get
  `stale: true`; moves still come. Tests in Task 3 and Task 5.
- A repo without `remote`, not in `ignore_repos`: one warning
  `no remote '<remote>' (only prove in progress): <repo>, <repo>`; repos in `ignore_repos` are
  never read. Tests in Task 3.
- Code only in repos that cannot prove production: in `direct_deploy_repos` the last branch
  environment counts as rung 4; otherwise `Position.limited` and the `limited` list. Tests in
  Task 3 and Task 4.
- Deploy repo missing or with no tag of the repo: `deploy <repo>: <deploy repo> not found` /
  `deploy <repo>: no image tag of this repo in <deploy repo>`, only for repos with commits of the
  given keys; `[board.repos."<repo>"] deploy_repo` overrides the name. Tests in Task 1 and Task 3.
- A key that is the prefix of another: no cross-talk (Task 3). A cards file without `is_epic`:
  epics also come from other cards' `epic_key`, plus the warning
  `cards without is_epic: epics known only as parents; run ws task list again` (Task 4, Task 5).

---

### Task 1: The `[board]` config

**Files:**
- Create: `src/ws/boardconfig.py`
- Modify: `src/ws/taskmodel.py` (add the rung tables)
- Test: `tests/test_boardconfig.py`

**Interfaces:**
- Produces:
  - `ws.taskmodel.RUNG: dict[Status, int]` (`TODO` 0, `IN_PROGRESS` 1, `REVIEW` 1, `VALIDATION` 2,
    `READY_DEPLOY` 3, `DONE` 4; `BLOCKED` and `CANCELLED` absent) and
    `ws.taskmodel.STATUS_AT_RUNG: dict[int, Status]` (1 `IN_PROGRESS`, 2 `VALIDATION`,
    3 `READY_DEPLOY`, 4 `DONE`).
  - `@dataclass(frozen=True) class Environment: name: str; status: Status; branches: tuple[str, ...];
    deploy_repo: str | None; deploy_branch: str; image_tag: re.Pattern[str] | None` with property
    `rung -> int`.
  - `@dataclass(frozen=True) class BoardConfig: remote: str; lookback_days: int; fetch: bool;
    environments: tuple[Environment, ...]; repo_branches: dict[str, dict[str, tuple[str, ...]]];
    statuses: dict[Status, str]; ignore_repos: tuple[str, ...]; direct_deploy_repos:
    tuple[str, ...]; repo_deploy: dict[str, str]` with methods `branches_for(repo: str, env:
    Environment) -> tuple[str, ...]` (the repo override when present, else `env.branches`),
    `deploy_repo_for(repo: str, env: Environment) -> str` (the repo's `deploy_repo` override,
    else `env.deploy_repo.format(repo=repo)`), `ignored(repo: str) -> bool` and
    `direct_deploy(repo: str) -> bool` (both `fnmatch.fnmatchcase` over the globs).
  - `class BoardMissing(Exception)` (no `[board]` table).
  - `parse_board(table: dict, path: Path) -> BoardConfig` and `load_board() -> BoardConfig`
    (reads `config_dir() / "config.toml"` through `userconfig.load_table("board")`; an empty table
    raises `BoardMissing`; a missing file raises `userconfig.ConfigMissing`).

- [ ] **Step 1: Write the failing tests** in `tests/test_boardconfig.py`, with a `VALID` dict equal
  to the spec's TOML example (parse it with `tomllib.loads` of the example text):
  - `test_valid_example_parses`: 3 environments in order `sandbox`, `master`, `production`;
    `cfg.remote == "origin"`, `cfg.lookback_days == 120`, `cfg.fetch is True`; production has
    `deploy_repo == "{repo}-argocd"`, `deploy_branch == "master"`, `image_tag.pattern ==
    "prod-([0-9a-f]{7,40})"`; `cfg.statuses[Status.DONE] == "Concluído"`;
    `cfg.branches_for("some-repo", sandbox) == ("homolog",)` and
    `cfg.branches_for("other", sandbox) == ("sandbox", "staging")`;
    `cfg.deploy_repo_for("some-repo", production) == "some-deploy-repo"` and
    `cfg.deploy_repo_for("demo-api", production) == "demo-api-argocd"`;
    `cfg.ignored("artemis-workspace")` and not `cfg.ignored("demo-api")`;
    `cfg.direct_deploy("demo-api-argocd")` and not `cfg.direct_deploy("demo-api")`.
  - `test_defaults_when_keys_absent`: a table with only `environments` and `statuses` gives
    `remote "origin"`, `lookback_days 120`, `fetch True`, `deploy_branch "master"`,
    `ignore_repos == ()`, `direct_deploy_repos == ()`.
  - Parametrized `test_invalid_raises_config_invalid` (each must raise `userconfig.ConfigInvalid`
    and the message must name the key path): duplicate environment name; status `"todo"`; statuses
    not strictly rising (`ready_deploy` then `validation`); environment with both `branches` and
    `deploy_repo`; environment with neither; `image_tag` with zero groups (`"prod-[0-9a-f]+"`);
    `image_tag` that does not compile (`"prod-("`); repo override naming an unknown environment;
    `[board.statuses]` missing `in_progress`; missing the name for a status an environment uses;
    `lookback_days = 0`; `fetch = "yes"`; `ignore_repos = "x"` (not a list); a repo
    `deploy_repo` that is not a non-empty string.
  - `test_load_board_without_table_raises_board_missing` (config.toml with only `[jira]`, via the
    `WS_CONFIG_DIR` env var like `tests/test_userconfig.py`).

- [ ] **Step 2: Run** `uv run pytest tests/test_boardconfig.py -q`. Expected: FAIL (module missing).

- [ ] **Step 3: Implement** `src/ws/boardconfig.py` and the two tables in `taskmodel.py`. Reuse
  `userconfig.ConfigInvalid`, `userconfig.ConfigMissing` and `userconfig.load_table`. Error
  messages: `f"{path}: board.environments[{i}].{key} ..."`, `f"{path}: board.statuses ..."`.

- [ ] **Step 4: Run** `uv run pytest tests/test_boardconfig.py -q`. Expected: PASS.

- [ ] **Step 5: Commits:** `feat: etapas do card no modelo de tarefa` (`RUNG`, `STATUS_AT_RUNG`
  and a test of their order in `tests/test_taskmodel.py`), then
  `feat: configuração dos ambientes do board` (`boardconfig.py` and its tests).

### Task 2: Epics flagged on cards

**Files:**
- Modify: `src/ws/jira.py` (`FIELDS`, `card_from_issue`, `task_from_card`)
- Modify: `src/ws/taskmodel.py` (`Task.is_epic: bool = False` as the last field; `task_to_json`
  adds `"is_epic"`)
- Test: `tests/test_jira.py`, `tests/test_taskmodel.py`

**Interfaces:**
- Produces: card JSON key `is_epic: bool`; `Task.is_epic`.

- [ ] **Step 1: Write the failing tests:**
  - `test_fields_ask_for_issuetype`: `"issuetype" in jira.FIELDS`.
  - `test_card_from_issue_flags_epic_by_hierarchy_level`: an issue with
    `fields.issuetype = {"name": "Épico", "hierarchyLevel": 1}` gives `is_epic is True`; with
    `{"name": "Tarefa", "hierarchyLevel": 0}` gives `False`; without `issuetype` gives `False`.
  - `test_task_from_card_without_is_epic_is_not_epic`: a card dict without `is_epic` (the old
    format and the MCP fallback) gives `task.is_epic is False`; with `"is_epic": True` gives True.
  - `test_task_to_json_has_is_epic`.

- [ ] **Step 2: Run** `uv run pytest tests/test_jira.py tests/test_taskmodel.py -q`. Expected: the
  new tests FAIL.

- [ ] **Step 3: Implement.** `is_epic` is not added to `CARD_FIELDS` (it stays optional on input).

- [ ] **Step 4: Run** `uv run pytest -q`. Expected: PASS (whole suite: `Task` gained a defaulted
  field).

- [ ] **Step 5: Commits:** `feat: card do Jira sabe se é épico` (`FIELDS`, `card_from_issue`),
  then `feat: tarefa carrega a marca de épico` (`Task.is_epic`, `task_from_card`, `task_to_json`).

### Task 3: Code positions from git

**Files:**
- Modify: `src/ws/standup.py` (rename `_find_repos` to `find_repos`, update its caller)
- Create: `src/ws/codeposition.py`
- Test: `tests/test_codeposition.py`

**Interfaces:**
- Consumes: `BoardConfig`, `Environment` (Task 1); `ws.standup.keys_in`, `ws.standup.find_repos`.
- Produces:
  - `@dataclass(frozen=True) class Holding: repo: str; commit: str (7 chars); subject: str;
    reached: str | None (environment name; None when outside every environment);
    branch: str | None`.
  - `@dataclass(frozen=True) class Position: rung: int; environment: str | None; holding: Holding |
    None; repos: tuple[str, ...]; stale: bool; limited: bool` (`limited`: every commit is at its
    repo's cap and the rung is below 4).
  - `fetch(repos: list[Path], remote: str) -> dict[str, str]`: repo name to error text for each
    failed fetch; repos without `remote` are skipped silently; `git fetch --prune --quiet <remote>`
    in a `ThreadPoolExecutor(max_workers=8)`, `timeout=120` per repo (a timeout is a failure).
  - `positions(repos: list[Path], keys: set[str], cfg: BoardConfig, today: date,
    stale: set[str]) -> tuple[dict[str, Position], list[str]]`: one `Position` per key that has at
    least one commit (keys without commits are absent), and warnings.

- [ ] **Step 1: Write the failing tests.** A fixture builds, under `tmp_path`, a bare remote per
  repo and a clone under `roots` (reuse the `git` fixture of `tests/conftest.py`), with helpers
  `commit(repo, subject, day)` (empty commits, fixed dates like `tests/test_standup.py`),
  `push(repo, branch)` and `merge(repo, source, into)` (`--no-ff`, so a merge commit exists).
  Config: the spec's three environments, `fetch=False` unless the test fetches. Cases (rung,
  environment):
  - `test_branch_commit_only_is_in_progress`: commit `TS-101 x` on `feature/TS-101-x`, pushed →
    rung 1, environment None, `holding.branch` ends with `feature/TS-101-x` (local or remote name).
  - `test_local_only_commit_is_in_progress`: commit never pushed → rung 1.
  - `test_empty_branch_has_no_position`: branch `feature/TS-102-y` with no commit of its own →
    `"TS-102" not in result`.
  - `test_in_sandbox_is_validation`: merged into `sandbox` and pushed → rung 2, `"sandbox"`.
  - `test_in_master_not_deployed_is_ready_deploy`: in `master`, the deploy repo's tag points to an
    older master commit → rung 3, `"master"`.
  - `test_in_every_production_tag_is_done`: deploy repo `demo-api-argocd` with two values files
    both naming the new sha as `prod-<sha7>` → rung 4, `"production"`.
  - `test_one_stale_tag_holds_the_card`: same, one file with the old sha → rung 3, holding
    `reached == "master"`.
  - `test_tag_of_another_app_is_ignored`: a third file with `prod-deadbee` (unknown sha) and the
    two good ones → rung 4.
  - `test_unmerged_commit_holds_the_card`: one commit deployed and another `TS-103` commit only on
    a pushed branch → rung 1, holding branch names that branch.
  - `test_merge_commits_do_not_count`: a merge commit whose subject has `TS-104` and no other
    commit → `"TS-104" not in result`.
  - `test_hotfix_without_sandbox_reaches_master`: commit only in `master` → rung 3.
  - `test_repo_override_branch_name`: `[board.repos."demo-api".branches] sandbox = ["homolog"]`,
    commit merged into `homolog` → rung 2.
  - `test_key_prefix_does_not_match`: commits `TS-150 a` (sandbox) and `TS-15 b` (branch) → TS-150
    rung 2, TS-15 rung 1.
  - `test_personal_repo_commit_only_proves_in_progress`: repo with no remote, commit `TS-105` →
    rung 1; together with a deployed `TS-105` commit in `demo-api` → rung 4.
  - `test_deploy_repo_master_commit_does_not_hold`: `chore(TS-106)` in `demo-api-argocd` master
    and the `demo-api` commit deployed → rung 4.
  - `test_commit_older_than_lookback_is_ignored`: `lookback_days=30`, commit 60 days before
    `today` → absent.
  - `test_fetch_failure_is_reported_and_no_remote_is_silent`: one repo whose remote URL points to
    a missing path, one repo without remote → `fetch()` returns exactly the first repo's name.
  - `test_stale_repo_marks_position_stale`: `positions(..., stale={"demo-api"})` → `stale is True`.
  - `test_repo_without_remote_is_one_warning`: two repos without remote (`notes-a`, `notes-b`)
    → exactly one warning `no remote 'origin' (only prove in progress): notes-a, notes-b`.
  - `test_direct_deploy_repo_master_is_production`: `direct_deploy_repos = ["*-argocd"]`, a
    card whose only commit is `chore(TS-107)` in `demo-api-argocd` master → rung 4; without the
    glob → rung 3 and `limited is True`.
  - `test_missing_deploy_repo_warns_only_for_repos_with_keys`: no `demo-api-argocd` clone,
    `TS-108` deployed-looking in `demo-api` and no key in `other-api` → one warning
    `deploy demo-api: demo-api-argocd not found`, none for `other-api`; and with the deploy repo
    present but only foreign tags → `deploy demo-api: no image tag of this repo in demo-api-argocd`.
  - `test_repo_override_deploy_repo`: `[board.repos."demo-api"] deploy_repo = "deploys"` with the
    tags in `deploys` → rung 4.

- [ ] **Step 2: Run** `uv run pytest tests/test_codeposition.py -q`. Expected: FAIL (module
  missing).

- [ ] **Step 3: Implement `codeposition.py`.** The algorithm the tests do not fully fix:

```text
since = today - lookback_days; walk_since = since - 30 days (tolerates commit-date skew)
for each repo:
  commits = git log --all --exclude=refs/stash --no-merges --since=<since> --format=%H%x1f%s
            keep (sha, subject, keys_in(subject) ∩ keys)
  (repos matching cfg.ignored are never passed in; board_cli filters them before the fetch)
  env_sets = {}                     # environment name -> set of shas, only for available envs
  for env in cfg.environments:
    if env.branches: ref = first existing refs/remotes/<remote>/<b> of cfg.branches_for(repo, env)
                     env_sets[env] = set(rev-list --since=<walk_since> ref)       if ref
    else:            deploy = repo.parent / cfg.deploy_repo_for(repo.name, env)
                     lines = git -C deploy grep -hoE <env.image_tag.pattern> <remote>/<deploy_branch>
                     shas  = [m.group(1) for line in lines if (m := env.image_tag.search(line))]
                     tags  = [full sha for s in shas if rev-parse --verify -q s^{commit} works in repo]
                     env_sets[env] = intersection of rev-list sets of every tag   if tags
  if cfg.direct_deploy(repo.name) and env_sets has a branch env: its last one counts as rung 4
  cap = max(env.rung for env in env_sets) or 0
  for each commit: reached = max(env.rung for env in env_sets if sha in env_sets[env]) or 0
                   value   = inf if reached == cap else reached
per key: low = min(values); rung = max(caps of its commits) if low == inf else low
         rung = max(rung, 1); environment = name of the env whose rung == rung (None for rung 1)
         limited = (low == inf and rung < 4)
         holding = the commit with value == low when low != inf (branch: first of
                   `git branch -a --contains <sha> --format=%(refname:short)` that is not an
                   environment branch, None if none)
```

- [ ] **Step 4: Run** `uv run pytest tests/test_codeposition.py tests/test_standup.py -q`.
  Expected: PASS.

- [ ] **Step 5: Commits:** `chore: coletor da daily expõe a busca de repos` (the rename alone),
  `feat: fetch dos repos em paralelo com aviso por falha` (`fetch` and its test),
  `feat: posição do card pelos ambientes de branch` (commits, branch environments, cap, holding,
  stale; every test without a deploy repo), then `feat: produção provada pelas tags do repo de
  deploy` (the deploy environment and its four tests).

### Task 4: Moves from positions

**Files:**
- Create: `src/ws/boardrules.py`
- Test: `tests/test_boardrules.py`

**Interfaces:**
- Consumes: `Task` (with `is_epic`), `RUNG`, `STATUS_AT_RUNG`, `BoardConfig.statuses`, `Position`.
- Produces: `plan_moves(tasks: list[Task], positions: dict[str, Position], cfg: BoardConfig,
  today: date) -> dict` with:
  - `moves`: `[{"key", "title", "from", "to", "to_name", "environment", "stale"}]` (`from`/`to`
    canonical values, `to_name` from `cfg.statuses`), in the order of `tasks`;
  - `held`: `[{"key", "title", "status", "holding": {...Holding as dict}}]` for open cards not
    moved whose position has a `holding`;
  - `limited`: `[{"key", "title", "status", "proves", "repos"}]` for open cards whose
    position is `limited` (`proves` = canonical status of the rung), moved or not;
  - epics: `task.is_epic` or the key is the `epic_key` of another task in `tasks`;
  - `to_confirm`: `[{"key", "title", "since"}]` for cards in `validation` with
    `task.updated.date() <= workdays.previous_workday(today)` (`since` = that date, ISO).

- [ ] **Step 1: Write the failing tests:** todo + rung 1 → move to `in_progress` with
  `to_name "Em andamento"`; in_progress + rung 4 → `done`; review + rung 2 → `validation`;
  validation + rung 2 → no move; ready_deploy + rung 2 → no move (never back); blocked, cancelled,
  done and `is_epic=True` cards with rung 4 → no move; a key without position → no move; held entry
  for in_progress + rung 1 with holding; `to_confirm` lists a validation card updated on the
  previous workday and not one updated today; `stale` copied from the position; a card that is
  the `epic_key` of another task, with `is_epic=False`, gets no move; a `limited` position lists
  the card in `limited` with `proves == "ready_deploy"`.

- [ ] **Step 2: Run** `uv run pytest tests/test_boardrules.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement `plan_moves`.**

- [ ] **Step 4: Run** `uv run pytest tests/test_boardrules.py -q`. Expected: PASS.

- [ ] **Step 5: Commits:** `feat: movimentos dos cards a partir da posição do código` (`moves`,
  `held`), then `feat: card em validação pede confirmação do teste` (`to_confirm`).

### Task 5: `ws board status` and `ws board drafts`

**Files:**
- Create: `src/ws/board_cli.py` (`register(subparsers)`, like `src/ws/handoff_cli.py`)
- Modify: `src/ws/cli.py` (call `board_cli.register(subparsers)` in `build_parser`)
- Modify: `src/ws/card.py` (public `drafts_folder(name: str) -> Path`: ensures the store, creates
  `drafts/<name>` with mode 0o700, raises `FileExistsError` if it exists)
- Modify: `src/ws/userconfig.py` (rename `_toml_string` to `toml_string`; update the caller)
- Test: `tests/test_board_cli.py`

**Interfaces:**
- Consumes: Tasks 1–4; `jira.task_from_card`, `userconfig.load_config`, `standup.find_repos`,
  `ws.config.repo_root`.
- Produces:
  - `ws board status --cards FILE [--today YYYY-MM-DD]`: stdout JSON `{"moves", "held",
    "limited", "to_confirm", "warnings"}`; repos matching `cfg.ignored` are dropped before the
    fetch; the `is_epic` warning when any card lacks the key; exit 0; exit 2 on `ConfigMissing`, `ConfigInvalid`,
    `BoardMissing` (message says to add `[board]`, see the spec) or unreadable cards file.
    Warnings: `f"fetch {repo}: {error}"` per failed fetch.
  - `ws board drafts --board FILE`: writes `move-<KEY>.md` per move into
    `drafts_folder(f"sync-{datetime.now():%Y%m%d-%H%M%S}")`, front matter `op = "move"`,
    `key = "<KEY>"`, `to = <toml_string(to_name)>`; stdout JSON `{"folder": str | None,
    "count": int}` (`None`, 0 and no folder when there are no moves); exit 2 on invalid input
    (a key not matching `[A-Z][A-Z0-9]+-\d+`).

- [ ] **Step 1: Write the failing tests** (config through `WS_CONFIG_DIR`, `HOME` and the data dir
  in `tmp_path`, `fetch = false`, one repo built as in Task 3 with a deployed `TS-101` commit, a
  cards file with TS-101 in "Em andamento" and TS-102 an epic): `status` prints one move TS-101
  `in_progress → done` with `to_name "Concluído"` and nothing for the epic; without `[board]` exit 2
  and stderr mentions `[board]`; a cards file without `is_epic` gives the exact warning of the
  Review Focus; a repo whose remote URL is a missing path gives `fetch <repo>: ...` and the move
  still comes with `stale: true` (`fetch = true` in this one test); `drafts` writes `move-TS-101.md` that `ws.carddraft` parses as a
  `move` to `Concluído`; `drafts` with no moves prints `{"folder": null, "count": 0}`.

- [ ] **Step 2: Run** `uv run pytest tests/test_board_cli.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement.** `status` keeps only open cards (`RUNG` has their status) for the
  keys; calls `fetch` only when `cfg.fetch`.

- [ ] **Step 4: Run** `uv run pytest -q && uv run ruff check && uv run ruff format --check`.
  Expected: PASS and clean.

- [ ] **Step 5: Commits:** `chore: escape de texto TOML com nome público`,
  `feat: pasta de rascunhos de card criada pelo ws` (`drafts_folder` and a test in
  `tests/test_card.py`), `feat: comando ws board status`, then `feat: comando ws board drafts`.

### Task 6: The standup report uses the board

**Files:**
- Modify: `src/ws/taskstatus.py` (remove R1, R2, `_first_evidence`, `_merged_pr_evidence`;
  `evaluate(tasks, activity, today, stale_workdays, moving: frozenset[str] = frozenset()) ->
  {"stuck": [...]}`; a key in `moving` is never stuck)
- Modify: `src/ws/standupreport.py` (`build_report(..., top=None, board: dict | None = None)`:
  suggestions from `board["moves"]` as `{"from", "to", "rule": "board", "evidence":
  environment or "commit"}`; new top-level `to_confirm` copied from the board, `[]` without it)
- Modify: `src/ws/cli.py` (`ws standup report --board FILE`; `ws task status` prints `tasks` and
  `stuck` only; help texts)
- Test: `tests/test_taskstatus.py`, `tests/test_standupreport.py`

- [ ] **Step 1: Update the tests:** delete the R1/R2 tests in `tests/test_taskstatus.py`
  (`test_todo_with_commit_suggests_in_progress` through `test_one_merged_pr_with_two_keys_
  suggests_both`), keep the stuck tests, add `test_moving_card_is_not_stuck`; in
  `tests/test_standupreport.py`, suggestions and `moves` come only from a board dict, a report
  without `board` has `moves == []` and `to_confirm == []`, and `to_confirm` passes through.

- [ ] **Step 2: Run** `uv run pytest tests/test_taskstatus.py tests/test_standupreport.py -q`.
  Expected: FAIL.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** `uv run pytest -q && uv run ruff check`. Expected: PASS.

- [ ] **Step 5: Commits:** `feat: daily usa os movimentos do board` (`--board`, suggestions and
  `to_confirm` from the board, R1 and R2 still in place), then
  `feat: sugestões da daily só pela posição do código` (R1 and R2 removed, `moving`, `ws task
  status` output).

### Task 7: Skills and README

**Files:**
- Modify: `skills/daily/SKILL.md`, `skills/daily/references/detailed.md`
- Modify: `skills/card/SKILL.md`
- Modify: `README.md` (command table: `ws board status`, `ws board drafts`; local config:
  `[board]` with the spec's example)

- [ ] **Step 1: `daily`.** New step 3b after the cards: `ws board status --cards <cards.json> >
  ~/.local/share/workspace/standup/board.json` (only with cards; exit 2 or 1: go on without it,
  its stderr counts as a warning). Step 4 adds `--board <board.json>` when it exists. The MCP
  fallback adds `issuetype` to `fields` and `is_epic` (`fields.issuetype.hierarchyLevel >= 1`) to
  each card. Short output note: replace the `/card mover` list with
  "para aplicar /card sincronizar (N cards)" (N = `len(moves)`), then, when `to_confirm` is not
  empty, "testado na sandbox? TS-5537 (desde 03/11); ...". The board warnings join the report
  warnings (counted in "N avisos"). Detailed reference: the same, plus `held` and `limited`
  in plain words.
- [ ] **Step 2: `card`.** Description adds "/card sincronizar". New section "Sync" (step 6):
  `ws task list > <tmp>/cards.json`, `ws board status --cards ... > <tmp>/board.json`, show
  `moves`, `held`, `limited` ("o git só prova até <status>") and `warnings` (stale repos as
  "dados de <repo> podem estar desatualizados") in PT-BR in a short list, then `ws board drafts --board ...` and
  the usual steps 3 and 4 on the printed folder. No moves: say so and stop.
- [ ] **Step 3: README.**
- [ ] **Step 4: Commits:** `docs: daily com a sincronização do board`,
  `docs: /card sincronizar`, then `docs: comandos ws board e a tabela [board] no README`.

### Task 8: Evals of the daily

**Files:**
- Modify: `evals/lib/fixture.sh` (`[board]` in the config: `sandbox` environment on branch
  `sandbox` with status `validation`, `master` on `main` with `ready_deploy`, `fetch = false`,
  `[board.statuses]` with `in_progress = "Em andamento"`, `validation = "Em validação"`,
  `ready_deploy = "Ready Deploy"`)
- Modify: `evals/out-of-sync-card/scaffold.sh` (after `build_fixture`: a bare remote for
  `demo-api`, `main` pushed, branch `sandbox` with the `TS-103` commit pushed; TS-102 stays a local
  branch)
- Modify: `evals/out-of-sync-card/graders/move-ts-102-in-note.md` and `move-ts-103-in-note.md`
  (pattern: `Para você:[\s\S]*/card sincronizar \(2 cards\)`; explanation updated to the board
  rules: TS-102 local commit → em andamento, TS-103 in the sandbox → em validação)

- [ ] **Step 1: Make the changes.**
- [ ] **Step 2: Run** `scripts/run-evals out-of-sync-card` (see `scripts/run-evals --help` for the
  exact flags; if it refuses because of hard links in `.venv`, run
  `rm -rf .venv && UV_LINK_MODE=copy uv sync` first, as its message says). Expected: every grader passes in 3 of 3 runs. The full round (~US$ 6–7.5) runs
  only with the user's ok.
- [ ] **Step 3: Commit** `git commit -m "test: evals da daily com a posição do código"` and
  `git push origin main`.

### Task 9: Turn it on locally (outside the repo)

- [ ] **Step 1:** Add the spec's `[board]` table to `~/.config/workspace/config.toml` (the real
  status names: "Em andamento", "In Validation", "Ready Deploy", "Concluído";
  `ignore_repos = ["*-workspace"]`, `direct_deploy_repos = ["*-argocd"]`).
- [ ] **Step 2:** Run `ws task list > <scratch>/cards.json` and
  `ws board status --cards <scratch>/cards.json`. Expected after the 05/11 manual moves: no move
  for TS-5537 (validation), TS-5465 and TS-5518 (in progress, held by their branches); report any
  other move to the user instead of applying it.
- [ ] **Step 3:** Save the memory "mergeei/subiu → oferecer e rodar a sincronização do board, a
  caixa de aprovação continua" (`~/.claude/projects/-home-pnetto-repos/memory/`, linked in
  `MEMORY.md`).
