> Superseded in part by `docs/plans/2026-10-27-daily-by-task.md` (the standup grouped by task).

# Phase A: start of the day (standup and status) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only `daily` skill that builds the user's standup, the status of their tasks against the code, and their open tasks, from git, GitHub and Jira.

**Architecture:** Deterministic work lives in `ws`: `ws standup collect` gathers git, GitHub and project data as JSON; `ws task list` reads Jira through the REST API (main path); `ws task status` maps cards to the neutral task model and applies the three status rules. The skill gets the cards from `ws task list`, falling back to the Atlassian MCP, runs the `ws` commands, and writes the PT-BR text from their output only.

**Tech Stack:** Python 3.12 standard library (`urllib`, `tomllib`, `subprocess`, `getpass`), pytest, ruff, `gh` CLI, `claude plugin eval`.

**Spec:** `docs/specs/2026-10-26-task-driven-work-design.md` (section "Phase A in detail").

**Changes of 27/10 (user):** no repo list and no e-mail in the config. The standup reads every git repo under `~/repos`, and the author is each repo's `git config user.email`. PRs come from one GitHub search. Later idea, not in this plan: each project's `CLAUDE.md` already lists its repos ("Repositórios envolvidos"), which could group the standup by project.

## Global Constraints

- Runtime code uses the standard library only; `uv` only, never `pip`.
- Names (files, folders, functions, CLI) in English; the standup text in PT-BR; CLI messages in English.
- Phase A never writes to Jira or GitHub: no write tool call, no POST/PUT.
- No fixed times in code or config. "Yesterday" is the previous workday: Friday on a Monday (and on Saturday and Sunday).
- Every path comes from `ws.config` (`config_dir()`, `data_dir()`), so tests set `WS_CONFIG_DIR` / `WS_DATA_DIR` and never read the real home.
- The Jira token never passes through the chat: it is typed in a terminal into `~/.config/workspace/credentials` (mode 600, folder 700).
- No real names, company domains or the Jira site URL in the repo; tests use `https://example.atlassian.net`, keys like `TS-101`, fictitious titles.
- Commits: prefix `feat:`, `fix:`, `test:`, `docs:` or `chore:`, PT-BR, at most 72 characters, no Co-Authored-By. `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check` clean before each commit.
- Start after the English-names rename (`docs/plans/2026-10-26-english-names.tsv`) is on `main`; until then, branch from the rename branch and rebase.

## Review Focus

1. A repo root in the config that does not exist: a warning names it, the other roots are still collected; a folder under a root that is not a git repo is skipped silently (Task 4).
2. A card with no parent epic: `epic_key` and `epic_title` are null and the skill groups it under "Sem épico" (Task 3, Task 6).
3. A PR or commit naming several keys, such as `chore(TS-101, TS-102): …`: each key gets the evidence (Task 4, Task 5).
4. A commit by another author does not count; the user's e-mail is each repo's own `git config user.email`, so a repo set to another git account uses that account's e-mail, and a repo with no `user.email` is a warning (Task 4).
5. Jira answers 401 (bad token) or more than one page: a clear one-line error and exit 1 for the first, every page read for the second (Task 3).

---

## Execution

Subagent-driven: one fresh agent per task, a review before the next task starts, and a final review
of the whole branch by the orchestrator (Opus 5.5). Each agent gets the lightest model and effort
that the task allows; the orchestrator raises it for a task that comes back with a defect it should
have caught.

| Task | Model | Effort | Why |
|---|---|---|---|
| 1 Task model and workdays | haiku | medium | short pure code, tests already written here |
| 2 Config and Jira token | sonnet | medium | closed interfaces; care with file modes and the TTY check |
| 3 Jira adapter | sonnet | high | pagination, fake HTTP server, two card shapes |
| 4 Activity collector | sonnet | high | git and `gh` through subprocess, the most edge cases |
| 5 Status rules | sonnet | medium | pure logic, every rule has a firing case and a near-miss |
| 6 `daily` skill | sonnet | high | the description decides when the skill triggers; the live check is the orchestrator's, with the user |
| 7 step 1 (setup reports `bwrap`/`socat`) | haiku | low | one `shutil.which` check and its test |
| 7 steps 3–6 (evals) | sonnet | xhigh | new tool, and cases 3–5 depend on what the probe shows |
| Per-task review | sonnet | medium | diff of one task against its section of this plan |

Order: Tasks 1 and 2 can run in parallel, and so can 3 and 4 after them; each touches `cli.py` only
in its own `_add_*` function, so the merge is the registration line.

### Task 1: Neutral task model and workday dates

**Files:**
- Create: `src/ws/taskmodel.py`, `src/ws/workdays.py`
- Test: `tests/test_taskmodel.py`, `tests/test_workdays.py`

**Interfaces:**
- Produces:
  - `class Status(StrEnum)`: `TODO="todo"`, `IN_PROGRESS="in_progress"`, `VALIDATION="validation"`, `DONE="done"`, `CANCELLED="cancelled"`.
  - `@dataclass(frozen=True) class Task`: `ref: str` (`"jira:TS-101"`), `key: str`, `title: str`, `url: str`, `status: Status`, `epic_key: str | None`, `epic_title: str | None`, `requested_by_other: bool`, `updated: datetime` (aware).
  - `task_to_json(task: Task) -> dict` (status as its value, `updated` as ISO 8601).
  - `previous_workday(day: date) -> date`; `workdays_before(day: date, n: int) -> date`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 10, 26), date(2026, 10, 23)),  # Monday -> Friday
        (date(2026, 10, 27), date(2026, 10, 26)),  # Tuesday -> Monday
        (date(2026, 10, 24), date(2026, 10, 23)),  # Saturday -> Friday
        (date(2026, 10, 25), date(2026, 10, 23)),  # Sunday -> Friday
    ],
)
def test_previous_workday(day, expected):
    assert previous_workday(day) == expected


def test_workdays_before_skips_weekends():
    assert workdays_before(date(2026, 10, 27), 3) == date(2026, 10, 22)


def test_task_to_json_uses_plain_values():
    task = Task(
        "jira:TS-101",
        "TS-101",
        "[FRONT] Tela",
        "https://example.atlassian.net/browse/TS-101",
        Status.IN_PROGRESS,
        "TS-100",
        "[FRONT] Épico",
        False,
        datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
    )
    data = task_to_json(task)
    assert data["status"] == "in_progress"
    assert data["updated"] == "2026-10-26T09:00:00+00:00"
```

- [ ] **Step 2: Run them and see them fail** — `uv run pytest -q tests/test_workdays.py tests/test_taskmodel.py` → `ModuleNotFoundError`.
- [ ] **Step 3: Implement both modules.** `workdays_before(day, 0) == day`; `n` counts workdays only.
- [ ] **Step 4: Run them and see them pass.**
- [ ] **Step 5: Commit** — `feat: modelo neutro de tarefa e dias úteis`.

### Task 2: Local config and the Jira token

**Files:**
- Create: `src/ws/userconfig.py`
- Modify: `src/ws/cli.py` (new `_add_config`), `src/ws/bootstrap.py` (report a missing `config.toml`)
- Test: `tests/test_userconfig.py`, `tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `ws.config.config_dir()`.
- Produces:
  - `@dataclass(frozen=True) class JiraConfig`: `site: str`, `email: str`, `status_overrides: dict[str, str]`.
  - `@dataclass(frozen=True) class StandupConfig`: `repo_roots: tuple[Path, ...]` (`~` expanded; default `(Path.home() / "repos",)` when absent), `stale_workdays: int` (default 3). No e-mail: the author comes from each repo's git config (Task 4).
  - `@dataclass(frozen=True) class UserConfig`: `jira: JiraConfig`, `standup: StandupConfig`.
  - `load_config() -> UserConfig`; `class ConfigMissing(Exception)` (has `.path`); `class ConfigInvalid(ValueError)`.
  - `load_jira_token() -> str` (raises `ConfigMissing` when the file or key is absent); `save_jira_token(value: str) -> Path`.
  - CLI: `ws config token jira`, reads the token with `getpass` only when stdin is a TTY; otherwise prints `run this in your own terminal: ws config token jira` and exits 2.

`config.toml` format (documented in README):

```toml
[jira]
site = "https://<site>.atlassian.net"
email = "<you>@<company>"

[jira.status_overrides]
"In Validation" = "validation"
"Cancelada" = "cancelled"

[standup]  # optional, these are the defaults
repo_roots = ["~/repos"]
stale_workdays = 3
```

`credentials` format: `[jira]` / `token = "<token>"`, written with `json.dumps` for the string (valid TOML basic string), file mode 600, folder 700.

- [ ] **Step 1: Write the failing tests:**
  - `test_load_config_reads_every_field`: asserts `repo_roots` expanded from `~`, overrides dict, `stale_workdays` 3 when absent, and `repo_roots` defaults to `~/repos` when `[standup]` is absent;
  - `test_missing_config_raises_config_missing_with_path`;
  - `test_override_to_unknown_status_is_invalid` (`"X" = "doing"` raises `ConfigInvalid`);
  - `test_save_token_writes_600_in_700_folder_and_load_reads_it`;
  - `test_cli_token_refuses_without_tty` (stdin not a TTY → exit 2, message above, no file written);
  - `test_setup_reports_missing_config_toml` (a `needs you:` line naming the path and the README section).
- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement** with `tomllib`; validate types and that every override value is a `Status` value.
- [ ] **Step 4: Run and see them pass.**
- [ ] **Step 5: Commit** — `feat: config local do ws e token do Jira pelo terminal`.

### Task 3: Jira adapter and `ws task list`

**Files:**
- Create: `src/ws/jira.py`
- Modify: `src/ws/cli.py` (new `_add_task` with `list`)
- Test: `tests/test_jira.py`

**Interfaces:**
- Consumes: `Task`, `Status`, `task_to_json` (Task 1); `load_config`, `load_jira_token` (Task 2).
- Produces:
  - `FIELDS = ["summary", "status", "parent", "reporter", "updated"]`.
  - `my_tasks_jql(since: date) -> str` returning `assignee = currentUser() AND (statusCategory != Done OR updated >= "YYYY-MM-DD") ORDER BY updated DESC`.
  - The **compact card**, the input `ws task status` reads, a dict with exactly: `key`, `title`, `status_name`, `status_category` (`new` | `indeterminate` | `done`), `epic_key`, `epic_title` (null without parent), `reporter_is_me` (bool), `updated` (ISO 8601).
  - `card_from_issue(issue: dict, my_account_id: str) -> dict`: accepts a REST issue (`issue["fields"]`) or an MCP node; reads `fields.summary`, `fields.status.name`, `fields.status.statusCategory.key`, `fields.parent.key`, `fields.parent.fields.summary`, `fields.reporter.accountId`, `fields.updated`.
  - `status_of(name: str, category: str, overrides: dict[str, str]) -> Status`: an override by exact name wins; else `new`→`TODO`, `indeterminate`→`IN_PROGRESS`, `done`→`DONE`.
  - `task_from_card(card: dict, site: str, overrides: dict[str, str]) -> Task` (`url = f"{site}/browse/{key}"`, `ref = f"jira:{key}"`, `requested_by_other = not reporter_is_me`); raises `ValueError` naming the missing field.
  - `class JiraClient(site, email, token, timeout=20)`: `myself() -> dict` (`GET /rest/api/3/myself`); `search(jql: str, fields: list[str]) -> list[dict]` (`GET /rest/api/3/search/jql`, `maxResults=100`, follows `nextPageToken` until `isLast`); basic auth; `class JiraError(Exception)` with the HTTP status in the message.
  - CLI: `ws task list [--since YYYY-MM-DD]` (default `previous_workday(today)`), prints `{"platform": "jira", "cards": [compact cards]}`; config or token missing → exit 2; `JiraError` → message on stderr, exit 1.

- [ ] **Step 1: Write the failing tests:**
  - `test_status_of` parametrized: override `"In Validation"` (category `indeterminate`) → `VALIDATION`; `"Cancelada"` (category `done`) → `CANCELLED`; `"Em andamento"` → `IN_PROGRESS`; `"To Do"` (`new`) → `TODO`; `"Concluído"` (`done`) → `DONE`.
  - `test_card_from_issue_rest_and_mcp_shapes_are_equal`.
  - `test_card_without_parent_has_null_epic` (Review Focus 2).
  - `test_task_from_card_names_the_missing_field`.
  - `test_client_reads_every_page` (Review Focus 5): fake server with 2 pages, 150 issues.
  - `test_client_401_raises_jira_error_with_status`.
  - The fake Jira is an `http.server.ThreadingHTTPServer` on `127.0.0.1:0` in a fixture, asserting the basic-auth header and the `jql` and `fields` query values.
- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement** with `urllib.request`; no retries.
- [ ] **Step 4: Run and see them pass.**
- [ ] **Step 5: Commit** — `feat: adaptador do Jira e ws task list pela API REST`.

### Task 4: Activity collector and `ws standup collect`

**Files:**
- Create: `src/ws/standup.py`
- Modify: `src/ws/cli.py` (new `_add_standup` with `collect`)
- Test: `tests/test_standup.py`

**Interfaces:**
- Consumes: `previous_workday`, `workdays_before` (Task 1); `StandupConfig` (Task 2); `ws.config.repo_root()`.
- Produces:
  - `KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")`; `keys_in(text: str) -> list[str]` (in order, no repeats).
  - `collect(cfg: StandupConfig, today: date, workspace: Path, gh: str = "gh") -> dict`, returning:

```text
{"window": {"since": "YYYY-MM-DD", "until": "YYYY-MM-DD"},
 "commits":  [{"repo", "sha", "date", "subject", "keys"}],
 "branches": [{"repo", "name", "keys"}],
 "prs":      [{"repo", "number", "title", "state", "merged_at", "url", "keys"}],
 "last_activity": {"<KEY>": "<ISO date of the latest own commit>"},
 "next_steps": [{"project", "text"}],
 "warnings": ["..."]}
```

  - Repos: every direct child folder of each `repo_roots` entry that is a git repo (has a `.git` folder or file), hidden folders skipped, and the workspace repo itself (`repo_root()`) skipped, since its planning reaches the standup through `CONTINUE.md`; sorted by name. A root that does not exist adds a warning naming it.
  - Commits: per repo, the author is `git -C REPO config user.email` (the effective value, so `includeIf` and per-repo accounts work); unset adds a warning naming the repo and its commits are skipped. `git -C REPO log --all --since=<since> --author=<email> --fixed-strings`, deduplicated by sha. `last_activity` uses the same query from `workdays_before(today, stale_workdays)`.
  - Branches: local branches (`refs/heads`) whose name has a key.
  - PRs: one call for every repo of the user's GitHub account: `gh api graphql` with the search `is:pr author:@me updated:>=<since>` (`type: ISSUE`, `first: 100`), reading `number`, `title`, `state` (lowercased), `mergedAt`, `headRefName`, `url` and `repository.name` (the `repo` field). Keys come from the title and `headRefName`. If `gh` fails, add one warning `gh: PRs left out (<first stderr line>)`; if `issueCount` is over 100, a warning says only the first 100 were read.
  - Next steps: for each `projects/*/CONTINUE.md` under `workspace`, the text under the heading `## Próximo passo` until the next `## `; a file without it adds a warning naming the project.
  - CLI: `ws standup collect [--today YYYY-MM-DD]` prints the JSON.

- [ ] **Step 1: Write the failing tests** (throwaway repos through the `repo`/`git` fixtures; a fake `gh` script on `PATH` that prints fixed JSON or exits 1):
  - `test_window_on_monday_starts_friday`;
  - `test_author_is_each_repos_git_email` (Review Focus 4: two repos with different `user.email`, each counts its own; another author's commit does not; a repo without `user.email` is a warning);
  - `test_keys_from_subject_and_branch`, `test_several_keys_in_one_title` (Review Focus 3: `chore(TS-101, TS-102): x` → `["TS-101", "TS-102"]`);
  - `test_repos_found_under_roots_and_missing_root_is_a_warning` (Review Focus 1: a non-git folder and a hidden folder are skipped);
  - `test_gh_failure_is_one_warning`;
  - `test_next_steps_from_continue_and_warning_without_section`;
  - `test_last_activity_uses_the_stale_window`.
- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement**, with every git call through one helper that passes `-c core.quotepath=false` and raises on non-zero exit, as `ws.secrets._git` does.
- [ ] **Step 4: Run and see them pass.**
- [ ] **Step 5: Commit** — `feat: ws standup collect junta commits, PRs e próximos passos`.

### Task 5: Status rules and `ws task status`

**Files:**
- Create: `src/ws/taskstatus.py`
- Modify: `src/ws/cli.py` (`status` under `_add_task`)
- Test: `tests/test_taskstatus.py`

**Interfaces:**
- Consumes: `task_from_card` (Task 3), `workdays_before` (Task 1), the collect JSON (Task 4), `load_config` (Task 2).
- Produces:
  - `evaluate(tasks: list[Task], activity: dict, today: date, stale_workdays: int) -> dict`, returning `{"suggestions": [{"key", "from", "to", "rule", "evidence"}], "stuck": [{"key", "last_activity"}]}`.
  - The rules:
    - **R1:** `TODO` with a commit or branch for its key → `IN_PROGRESS`; evidence is the first commit sha or branch name.
    - **R2:** `IN_PROGRESS` with a merged PR (`merged_at` not null) naming its key → `VALIDATION`; evidence is `repo#number`.
    - **R3:** `IN_PROGRESS` with no `last_activity` for its key and `updated` before `workdays_before(today, stale_workdays)` → `stuck`.
  - CLI: `ws task status --cards FILE --activity FILE [--today YYYY-MM-DD]` prints `{"tasks": [task_to_json…], "suggestions": […], "stuck": […]}`. A malformed card → exit 2 naming the field.

- [ ] **Step 1: Write the failing tests:**
  - one test per rule, each with a firing case and a near-miss (R1 with only another key's commit; R2 with an open PR; R3 with a commit inside the window);
  - `test_one_merged_pr_with_two_keys_suggests_both` (Review Focus 3);
  - `test_cli_maps_overrides_from_config` (`"In Validation"` card comes out `validation`);
  - `test_cli_malformed_card_exits_2`.
- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run and see them pass.**
- [ ] **Step 5: Commit** — `feat: regras de status das tarefas e ws task status`.

### Task 6: The `daily` skill and the docs

**Files:**
- Create: `skills/daily/SKILL.md`
- Modify: `README.md` (command table, `config.toml` section, the token command), root `CLAUDE.md` (one line under Layout if needed, staying under 200 lines)

**Interfaces:**
- Consumes: `ws standup collect`, `ws task list`, `ws task status` (Tasks 3–5).

`SKILL.md` content:
- Frontmatter:
  - `name: daily`;
  - `description:` "Builds the user's daily standup (yesterday, today, blockers), the status of their tasks against the code, and their open tasks, from git, GitHub and Jira, without writing anywhere. Use when the user asks for the daily, the standup or what they have today ("daily", "standup", "o que tenho hoje?"); not on a greeting such as "bom dia", alone or with another request."
  - No `disable-model-invocation` (it only reads).
- Steps:
  1. `ws standup collect` into `~/.local/share/workspace/standup/activity.json`.
  2. `ws task list --since <since> > standup/cards.json.tmp`, moved to `cards.json` only on exit 0 (main path: a script).
  3. Only when that exits non-zero (2: no config or API key; 1: Jira error): the Atlassian MCP as the fallback: the user's account id (`atlassianUserInfo`), then `searchJiraIssuesUsingJql` with the JQL of `my_tasks_jql` and the fields in `FIELDS`; write the compact cards (the exact field list from Task 3) to `standup/cards.json` as `{"platform": "jira", "cards": [...]}`. If that also fails: no cards, and the text says Jira was unavailable.
  4. `ws task status --cards … --activity …`.
  5. Write the text.
- Output template in PT-BR, with these exact headings:
  - `**Ontem**`, `**Hoje**`, `**Impedimentos**`, `**Status**`, `**Suas tarefas**`;
  - every line in Ontem and Status cites a sha, `repo#PR` or card key;
  - Suas tarefas is grouped by `epic_title`, with "Sem épico" last;
  - requests from others are marked "(pedido de outra pessoa)".
- Rules: write only from the JSON; never call a write tool; state every warning; ask before calling a stuck card a blocker.

- [ ] **Step 1: Write `SKILL.md`** (under 150 lines) and the README rows and section.
- [ ] **Step 2: Live check.** Create `config.toml` with the user's values (the Jira site and e-mail; repos and git e-mails come from `~/repos` and git config), then say "daily" in a new session. Expected: the five headings, every Ontem line traceable, no Jira write.
- [ ] **Step 3: Commit** — `feat: skill daily com standup, status e tarefas abertas`, then `docs: README com config.toml e os comandos do standup`.

### Task 7: Eval suite

> **27/10:** only step 1 runs now; steps 2–6 wait for a later session (the user's call: the standup first, the evals after).

**Files:**
- Create: `.claude-plugin/plugin.json` (`{"name": "workspace", "mcpServers": {"atlassian": {"command": "false"}}}`; the server exists only so its tools can be mocked), `evals/` (five cases, mocks, a probe case)
- Modify: `src/ws/bootstrap.py` (report missing `bwrap`/`socat`), `tests/test_bootstrap.py`, `README.md` (how to run the suite)

**Interfaces:**
- Consumes: the skill (Task 6), the CLI (Tasks 3–5).

- [ ] **Step 1: Setup reports the sandbox tools.**
  - Test: `test_setup_reports_missing_sandbox_tools`, a `needs you:` line containing `sudo apt-get install -y bubblewrap socat` and "only to run the evals".
  - Implement it with `shutil.which`.
  - Commit: `feat: ws setup avisa das ferramentas do sandbox das evals`.
- [ ] **Step 2: The user installs `bubblewrap` and `socat`** (admin password, once).
- [ ] **Step 3: Probe the eval environment** with a throwaway case:
  - `scaffold_script` writes `$HOME/.config/workspace/config.toml` and a git repo in the workspace;
  - the prompt asks Claude to run `ws standup collect`;
  - command: `claude plugin eval . --case probe --scaffold --allow-tools "Bash(ws:*)" Write --runs 1 --ablation none --no-publish`.

  Decide from the result:
  - (a) `ws` runs and reads the fixture config: cases 3–5 use scaffold fixtures and mocks;
  - (b) otherwise: cases 3–5 resume a `context.history_file` transcript whose `ws` tool results carry the fixture JSON, and the graders judge only the text.

  Delete the probe case.
- [ ] **Step 4: Write the five cases of the spec's eval table:**
  - mocks under `evals/mocks/atlassian/` (`atlassianUserInfo`, `searchJiraIssuesUsingJql` returning made-up cards);
  - case 5 overrides `searchJiraIssuesUsingJql` with an error in its own `mocks/`;
  - graders:
    - cases 1 and 2: `tool_used: Skill`, negated for case 2;
    - case 3: `regex` on a Friday commit's sha;
    - case 4: an `llm` rubric "every line in Ontem and Status names a sha, repo#PR or key present in the data";
    - case 5: `tool_used` with no Atlassian write tool and `regex` on "Jira" + "indisponível";
  - `runs: 3` on every case.
- [ ] **Step 5: Run the suite** — `claude plugin eval . --scaffold --allow-tools "Bash(ws:*)" Write --no-publish`. Expected: every case at 1.0, and the Δ (score change against the run without the skill) positive on cases 1, 3 and 4.
- [ ] **Step 6: Commit** — `test: evals da skill daily com mocks do Jira`.

### Deferred: Jev re-grade

Not built until the user has a Jev key, since its API cannot be tested without one. When it is: `ws eval jev RESULT.json` reads the `--json` result of `claude plugin eval`, sends case 4's rubric to Jev for each run, and prints both verdicts side by side. The key goes to `credentials` the same way as the Jira token.
