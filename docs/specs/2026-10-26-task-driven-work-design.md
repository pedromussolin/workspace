# Task-driven work — design

- **Date:** 2026-10-26
- **Status:** v1, approved on 2026-10-26, after agreeing on it section by section.
- **Scope:** subprojects 2 (GMUD) and 3 (Jira board) of the foundation spec, merged into one work
  cycle. The cycle and the platform model are designed here; phase A is designed in detail.
  Phases B, C and D each get their own detailed section or spec before they are built.

## Goal

Work starts from a task and ends with its goal delivered. The AI guides each step: the standup at
the start of the day, the task (found, created or explicitly skipped), the work (days or months,
resumable at any time), the delivery (a PR or another kind of goal) and, when production changes,
the GMUD. Jira is the platform today; the integration is abstracted so a request can also come
from GitHub Issues, Monday.com or another platform later.

## Decisions (2026-10-26)

| Topic | Decision |
|---|---|
| Entry point | The task. The AI asks whether it already exists, needs to be created, or the work goes without one. |
| Without a task | Allowed only by explicit choice, answered each time ("no task, reason: …"). Nothing is stored. |
| Creating a task | The AI drafts it and creates it only after the user approves the draft. Before drafting, it looks for a similar open task. |
| Title prefix | The task's prefix is its epic's prefix (`[FRONT] …` under an epic titled `[FRONT] …`). |
| Scope | Only tasks assigned to the user, on every platform. Requests from other people assigned to the user (INFRA) show up and can start work; the AI never creates tasks in INFRA. |
| Platforms | The interface is designed for any platform; only the Jira adapter is built. |
| How writes work | Plan file as the interface: every write is first a platform-neutral plan; `ws task check` enforces the rules in code; the MCP applies it, `ws` applies it through the REST API as the fallback. This is the foundation spec's "file as contract, two executors". |
| Standup first | The day starts with the standup and the status, before any development. |
| Time | No fixed times in code or config. "Yesterday" is the previous workday (Friday on a Monday). The standup runs on demand. |
| Evals | `claude plugin eval`. Jev is an optional second judge, used only when the user has a key. |

## The work cycle

| Phase | What happens |
|---|---|
| **A. Start of the day** | Standup by task (yesterday, today, blockers) with status suggestions (cards out of sync with the code, each with a suggested move) inside their task. Read-only. |
| **B. Work on a task** | Pick, create or skip the task; start the work (branch named by the company rule, link to the project folder); keep the task record; update the card. Brings the write path, so A's suggested moves can be applied with approval. |
| **C. Deliver the goal** | The goal is set when the task starts: a PR, a script, a message, a document. The task is done when its goal is delivered. |
| **D. GMUD** | Only when the task changes production. At delivery the AI asks whether it does; if so, the `change-request` skill writes the GMUD and it is sent to the service desk after approval. |

### Where a task lives

- One task per file: `projects/<project>/tasks/NN-<english-slug>.md`. Tasks that belong to no
  project go to `projects/standalone/tasks/`.
- The file starts with the task key (`TS-5431`), the goal and the status, and keeps a "Onde parei /
  próximo passo" section that the AI updates at the end of each session. A task that takes months
  resumes from it.
- The project's `CONTINUE.md` lists the open task files instead of repeating their state.
- What never enters git (worktrees, logs, deploy files, evidence with real data) goes to
  `~/.local/share/workspace/projects/<project>/`.

## Platform model

Every task, from any platform, becomes the same record:

| Field | Meaning |
|---|---|
| `ref` | platform and key, e.g. `jira:TS-5431`; later `github:owner/repo#12`, `monday:123456` |
| `title`, `url` | as on the platform |
| `epic` | the parent epic's ref and title prefix, when there is one |
| `status` | neutral: `todo`, `in_progress`, `validation`, `done`, `cancelled` |
| `assigned_to_me`, `requested_by_other` | scope flags |
| `updated` | last change on the platform |

An adapter implements: list my tasks, get one, search, and apply a plan (create, transition,
comment, log work). The Jira adapter maps statuses from Jira's own status category (new,
indeterminate, done) plus named overrides (`In Validation` → `validation`, `Cancelada` →
`cancelled`), so a workflow change does not need code.

### The write path (phase B, outline)

1. The AI writes a plan file, outside the repo, under `~/.local/share/workspace/plans/`: one
   operation per file (create, transition, comment, log work) with its fields.
2. `ws task check PLAN` refuses a plan that breaks a rule: a task not assigned to the user, a
   title prefix that differs from the epic's, a creation in INFRA.
3. The user sees the plan (a dry run) and approves it.
4. The MCP applies it; if the MCP fails, `ws task apply PLAN` does the same through the REST API.
5. A Claude Code gate on the Atlassian write tools blocks any write that has no checked plan
   matching it.

The plan format and the gate are detailed in phase B's spec.

## Phase A in detail

### What the standup shows

| Part | Source |
|---|---|
| **Ontem** | One topic per task key with own commits or PRs in the window (since the previous workday), with its title from the card and a short line from the commit subjects and PRs. Commits without a key are one count line. A suggested status move appears inside its task's topic. |
| **Hoje** | Cards in progress that are not blockers, and the cards a project's "Próximo passo" names, with the next step; then the next steps that name no card. Suggestions go inside the task's topic. |
| **Impedimentos** | Cards in progress with no commit for N workdays, offered as possibly stuck; the AI asks before calling anything a blocker. |

The standup has two modes. **Short** is the default: `--top 3`, about 120 words, friendly, with
"E mais N tarefas." for what was cut, and a closing "Para você:" note holding the suggested card
moves (and the Jira or warning notices). **Detailed** comes on request ("daily detalhado",
"daily completo", "standup detalhado", "verboso"): no `--top`, every topic, suggestions inside it.
In both, each line describes the task and never the person (no first or second person), because
the user reads it as their own and explains it to the team; the short one also has no sha, PR
number, repo, branch or jargon.

The list of the user's open tasks, grouped by epic, is no longer part of the standup: it moves to
the board-review skill (backlog).

The text is PT-BR and stays in the chat; the user reads it or pastes it.

### Status rules (code, in `taskstatus.evaluate`, used by `ws task status` and `ws standup report`)

1. Commits or a branch exist for the task, and the card is still `todo`: suggest `in_progress`.
2. The task's PR is merged, and the card is still `in_progress`: suggest `validation`.
3. A card is `in_progress` with no commit or card change for N workdays: flag it as possibly stuck.

N lives in the local config.

### How it runs

1. The skill `daily` (read-only, so the model may invoke it) triggers on "daily", "standup",
   "o que tenho hoje?" and similar explicit asks; a greeting such as "bom dia" does not trigger it.
2. `ws standup collect` gathers the local data as JSON: commits and branches of the user since the
   previous workday in the repos listed in `~/.config/workspace/config.toml`, the user's PRs
   through `gh`, and the "Próximo passo" of each project's `CONTINUE.md`.
3. The cards come from `ws task list`, through the REST API with a personal Jira API token (a
   script: same result every time, fewer tokens); the fallback is the Atlassian MCP. The user creates the token on the Atlassian site and saves it
   with a `ws` command that reads it from the terminal into `~/.config/workspace/credentials`
   (mode 600); it never passes through the chat.
4. `ws standup report` groups the git and card data by task and applies the status rules.
5. The AI writes the standup from that report only.

### When something fails

| Failure | Behavior |
|---|---|
| `ws task list` fails (no config or API key, or a Jira error) | the Atlassian MCP fallback |
| Both fail | the standup from git alone, with a line saying Jira was unavailable |
| `ws standup report` fails with the cards | the standup from the activity alone, with the error |
| `gh` is not authenticated | PRs left out, with a line saying so |
| Any other gap | stated in the text, never filled in |

### Tests (pytest, no real Jira or GitHub)

- `ws standup collect` on throwaway repos: the window (a Monday covers Friday), only the user's
  commits, the repos from the config.
- Each status rule, with test cards and commits.
- The Jira adapter's status mapping, overrides included.
- The REST fallback against a fake Jira server.

### Evals of the `daily` skill

The suite runs with `claude plugin eval`, with `skills/` as a skills-directory plugin and the
Atlassian MCP replaced by mocks (`evals/mocks/`). All data is made up.

| # | Case | Passes when |
|---|---|---|
| 1 | "daily" or "standup" | the standup comes out (`tool_used: Skill`) |
| 2 | "bom dia, me ajuda com esse bug"; and a plain "bom dia" | no standup; the answer is about the bug, or just a greeting |
| 3 | a Monday | Friday's work is included |
| 4 | made-up data | every topic names a card key present in the data |
| 5a | a card out of sync, Jira works (the MCP mocks answer) | the suggestion appears inside that card's topic, and no write tool is called |
| 5b | Jira down (the MCP mocks fail) | the text starts with "Jira indisponível", and no write tool is called |

- Each case runs 3 times; cases 5a and 5b must pass all 3 (a write path needs every run right).
- Mechanical checks use the free graders (`regex`, `tool_used`). The judgment checks ("is every
  line supported by the data?", "is the text short and in PT-BR?") use the `llm` grader, whose
  judge is a Claude model (`--judge-model`, on the user's Claude plan).
- **Jev is optional.** `claude plugin eval` cannot call it: its graders are `regex`, `tool_used`,
  `tool_order`, `file_exists`, `llm` and `baseline`, and the `llm` judge is always a Claude model
  (checked in the Claude Code docs on 2026-10-26). When the user has a Jev key, `ws` re-grades the
  judgment checks from the run's `--json` result with Jev and reports both verdicts; without a key
  this step is skipped.

## Out of scope

- The GitHub Issues and Monday.com adapters (interface only).
- A scheduled standup without an open session.
- Posting the standup anywhere: the Microsoft 365 connector here only reads.
- Jev anywhere other than the evals.

## Next

After this spec is approved: the implementation plan for phase A. Phases B, C and D get their
detailed design before each is built, in this order.
