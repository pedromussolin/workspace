# Daily by task Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** The daily standup is organized by task (card), not by commit or PR, and a `ws` command does the grouping; the list of every open card leaves the daily (it becomes the future board-review skill, in `docs/backlog.md`).

**Why (user, 2026-10-27, after the first live run):**
- Ontem: one topic per task worked on, with key and title; no commit or PR listed one by one.
- Hoje: one topic per task in progress or named in a project's next step.
- Impedimentos: one topic per possibly stuck task; the skill still asks before calling it a blocker.
- Gone: the commit list, the card-updates lines, the separate PR lines, the **Status** and **Suas tarefas** sections.
- Status suggestions stay, inside the topic of the task they refer to.
- Script first: the grouping is code (`ws standup report`); the skill only writes the text.

**Builds on:** `docs/plans/2026-10-26-daily-standup.md` (merged). Spec: `docs/specs/2026-10-26-task-driven-work-design.md`, updated by Task 2.

## Global Constraints

The same as the phase A plan: standard library only, `uv` only, English names, PT-BR text for
people, every path from `ws.config`, no real names, company domains or Jira site in the repo
(tests use `https://example.atlassian.net`, keys like `TS-101`), commits PT-BR with a prefix and at
most 72 characters, no trailers, `uv run pytest -q`, `uv run ruff check`,
`uv run ruff format --check` clean before each commit. The daily never writes to Jira or GitHub.

## Execution

| Task | Model | Effort | Why |
|---|---|---|---|
| 1 `ws standup report` | sonnet | medium | rules fully specified below, one new module and its CLI |
| 2 Skill, README, spec | sonnet | medium | text against a fixed JSON contract |
| 3 Evals | the evals agent, resumed | — | its cases depend on the old format |
| Reviews | sonnet | medium | |

Tasks 1 and 2 run in parallel (separate worktrees): the contract below is fixed. Task 3 runs after
both are merged.

## The contract: `ws standup report`

`ws standup report --activity FILE [--cards FILE] [--today YYYY-MM-DD]`

- `--activity`: the output of `ws standup collect`.
- `--cards`: the `{"platform": "jira", "cards": [...]}` file (from `ws task list` or the MCP
  fallback). Absent: Jira is unavailable; the report is built from the activity alone.
- With `--cards`, it needs `config.toml` (`[jira] site`, `status_overrides`, `[standup]
  stale_workdays`): missing or invalid → exit 2 with the message. Without `--cards`, no config is
  needed. Malformed input (unreadable file, bad JSON, missing keys, a malformed card) → exit 2
  naming the problem, never a traceback.
- Prints compact JSON (`separators=(",", ":")`, `ensure_ascii=False`):

```text
{"window": <activity.window>,
 "jira": true | false,
 "yesterday": [{"key", "title", "status", "url", "commits", "subjects", "prs", "suggestion"}],
 "today":     [{"key", "title", "status", "url", "next_step", "suggestion"}],
 "next_steps": [{"project", "text"}],
 "blockers":  [{"key", "title", "url", "updated", "workdays"}],
 "keyless":   {"commits": N, "repos": ["..."]},
 "warnings":  [<activity.warnings>]}
```

Rules (the cards are mapped with `jira.task_from_card`; the suggestions and stuck entries come from
`taskstatus.evaluate`, unchanged):

- **yesterday:** one entry per key that has at least one own commit in the activity (`commits`
  are already the window's) or a PR with `updated_at` on or after `window.since`. `commits` is the
  count; `subjects` the commit subjects naming the key, newest first, at most 5; `prs` the PRs
  naming the key with `updated_at` on or after `window.since`, as `{"ref": "<repo>#<number>",
  "state", "title"}`. Order: latest activity first (the newest commit date or PR `updated_at` of
  the key). `title`, `status` (the neutral value) and `url` come from the card; without a card,
  `title` is the title of the first PR naming the key, else null, and `status`/`url` are null.
- **today:** the cards with status `in_progress` that are not blockers, plus any card named (by
  key) in a project's next step whatever its status; `next_step` is that project's next-step text
  when it names the key, else null. Order: the order of the cards. Without cards: empty.
- **next_steps:** the activity's `next_steps` entries that name no key of a `today` entry.
- **blockers:** the `stuck` entries of `evaluate`, with the card's `title` and `url`. A blocker is
  not repeated in `today`.
- **suggestion:** each `evaluate` suggestion, as `{"from", "to", "rule", "evidence"}`, goes on the
  `yesterday` entry of its key when there is one, else on its `today` entry; when the key is in
  neither, a `today` entry is added for it (its card's fields, `next_step` null). Every other
  entry has `suggestion: null`.
- **keyless:** the count of activity commits whose `keys` is empty, and their repos, sorted, no
  repeats.
- **jira:** true when `--cards` was given and read.

### Task 1: `ws standup report`

**Files:** create `src/ws/standupreport.py` (`build_report(activity: dict, tasks: list[Task] | None,
today: date, stale_workdays: int) -> dict`); modify `src/ws/cli.py` (`report` under `_add_standup`);
test `tests/test_standupreport.py`.

Tests (pure dicts for `build_report`, plus CLI tests through `main`):
- a key with commits and a merged PR in the window: one `yesterday` entry with the count, subjects
  newest first (cap 5) and the PR ref; the R2 suggestion on it;
- a key with only a PR updated in the window (no commit) is in `yesterday`; a PR updated before
  `window.since` is not;
- a key with no card takes the PR title; with neither, title null;
- `today`: an in-progress card; a todo card named in a next step gets that `next_step` and the step
  leaves `next_steps`; a stuck card is in `blockers` and not in `today`;
- an R1 suggestion through a branch only (no commit) adds a `today` entry;
- `keyless` counts and repos;
- no `--cards`: `jira` false, `today` and `blockers` empty, `yesterday` from the activity, and no
  config needed;
- CLI: `--cards` with no `config.toml` → exit 2; malformed activity → exit 2 without a traceback;
  compact output.

Commit: `feat: ws standup report agrupa a atividade por tarefa`.

### Task 2: the skill, the README and the spec

**Files:** `skills/daily/SKILL.md`, `README.md`, `docs/specs/2026-10-26-task-driven-work-design.md`,
`docs/plans/2026-10-26-daily-standup.md` (one line at the top: superseded in part by this plan).

- Description: the standup grouped by task (yesterday, today, blockers) with status suggestions,
  from git, GitHub and Jira, read-only; same triggers ("daily", "standup", "o que tenho hoje?";
  not "bom dia").
- Steps 1–3 stay (collect; `ws task list` into `.tmp`, moved on exit 0; the MCP fallback with the
  Write tool). Step 4 becomes `ws standup report --activity <activity.json> [--cards <cards.json>]`
  (without `--cards` when there are no cards). Step 5 writes the text from the report only.
- Template (PT-BR), three headings:

```text
**Ontem**
- <KEY> — <title>: <one short line on what was done, from subjects and prs>. <suggestion>
- <N> commits sem card em <repos>

**Hoje**
- <KEY> — <title> (<status>): <next_step>. <suggestion>
- <project>: <next step text>

**Impedimentos**
- <KEY> — <title>: sem commit há pelo menos <workdays> dias úteis; card atualizado em <updated>.
Algum desses é impedimento?
```

  - `<suggestion>`: "Sugestão: mover de <from> para <to> (<evidence>)", only when present; nothing
    moved.
  - Status names in PT-BR: todo "a fazer", in_progress "em andamento", validation "em validação",
    done "concluída", cancelled "cancelada".
  - The keyless line only when `keyless.commits` > 0. No topic without a key.
  - No blockers: "Nenhum." and no question.
  - `jira` false: start with "Jira indisponível: sem status nem títulos dos cards"; topics by key,
    with the PR title when there is one; Hoje only the `next_steps`; Impedimentos "indisponível".
  - The `warnings` at the end, as they are.
- Rules stay: write only from the report, never a write tool, ask before calling a blocker.
- README: a row for `ws standup report` in the command table.
- Spec: "What the standup shows" becomes the three parts by task, suggestions inside the topic; the
  open-card list moves to the board-review skill (backlog); "How it runs" step 4 is
  `ws standup report`; the evals table: case 4 "every topic names a card key present in the data",
  case 5 "the suggestion appears in its task's topic".

Commits: `feat: skill daily organizada por tarefa`, `docs: spec e README do daily por tarefa`.

### Task 3: evals

After Tasks 1 and 2 are on `main`: the evals agent rebases its branch and adapts the cases and
graders to the three headings and the topic format (case 3: Friday's key in Ontem; case 4: every
topic names a key from the data; case 5: the suggestion inside its topic and "Jira indisponível"),
then the validation runs (`--runs 1 --ablation none`).
