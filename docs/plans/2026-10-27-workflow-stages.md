# Workflow stages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** The neutral task model knows the stages of the user's real workflow, so the daily stops
suggesting backward moves (a card in Ready Deploy was told to "move to validation") and shows
blocked cards as blockers.

**Why (user, 2026-10-27, after a live run):** "ready deploy fica após os testes em homologação, a
única coisa pendente é o deploy de fato [...] se tivesse bloqueado, estaria com status Blocked".
The TS project has ten statuses; the model knew five, so every status in Jira's "indeterminate"
category became `in_progress`, and "Block" (category "new") became `todo`.

**Builds on:** `docs/plans/2026-10-27-daily-short.md` (merged). Same Global Constraints.

## The user's workflow (decided 2026-10-27)

| Jira status (TS) | Neutral status | In the daily |
|---|---|---|
| Tarefas pendentes, Em análise | `todo` | R1 may suggest `in_progress` |
| Em andamento | `in_progress` | Hoje; R2, R3 |
| Code Review | `review` (new) | Hoje; R2, R3 |
| In Validation, Verify | `validation` | no suggestion |
| Ready Deploy | `ready_deploy` (new) | Hoje as a pending deploy; never a suggestion, never stuck |
| Block | `blocked` (new) | Impedimentos, a confirmed blocker (no question) |
| Concluído, Cancelada | `done`, `cancelled` | out |

The mapping lives in the user's local `config.toml` (`[jira.status_overrides]`), never in code.

## Execution

| Task | Model | Effort | Why |
|---|---|---|---|
| 1 Stages in the model, the rules and the report | sonnet | medium | three modules, rules fully specified |
| 2 The skill, README and spec | sonnet | low | wording against the contract below |
| Reviews | sonnet | low | small diffs |

Tasks 1 and 2 run in parallel (separate worktrees).

## The contract

- `Status` gains `REVIEW = "review"`, `READY_DEPLOY = "ready_deploy"`, `BLOCKED = "blocked"`;
  override values are validated against `Status`, so the new values are accepted in `config.toml`.
- `taskstatus.evaluate`: R1 unchanged (`todo` only). R2: `in_progress` **or `review`** with a
  merged PR naming the key → suggest `validation` (`from` is the card's own status). R3: `in_progress`
  **or `review`** with no own activity and `updated` before the stale cutoff → stuck. Nothing
  else changes (no suggestion for `validation`, `ready_deploy`, `blocked`, `done`, `cancelled`).
- `ws standup report`:
  - `today`: the cards with status `in_progress`, `review` or `ready_deploy` that are not blockers,
    plus cards named in a next step (unchanged rule), in card order.
  - `blockers`: every entry gains `"kind"`: `"stuck"` for the `evaluate` stuck entries (as today),
    `"blocked"` for cards with status `blocked` (fields `key`, `title`, `url`, `updated`; `workdays`
    null). Blocked cards are not repeated in `today`. Order: blocked first, then stuck, each in card
    order.
- The README `config.toml` example lists the TS mapping above as the example overrides.

### Task 1: stages in the model, the rules and the report

Files: `src/ws/taskmodel.py`, `src/ws/taskstatus.py`, `src/ws/standupreport.py`, their tests
(`tests/test_taskmodel.py`, `tests/test_taskstatus.py`, `tests/test_standupreport.py`,
`tests/test_userconfig.py` for an override to `ready_deploy` being valid).
Tests: R2 from `review`; no R2 from `ready_deploy` with a merged PR (the bug of the live run); R3
from `review`; a `blocked` card with a commit gets no R1 and appears in `blockers` with
`kind: "blocked"` and not in `today`; a `ready_deploy` card is in `today` with no suggestion and is
never stuck; stuck entries carry `kind: "stuck"`.
Commit: `fix: modelo conhece code review, pronto para deploy e bloqueado`.

### Task 2: the skill, README and spec

Files: `skills/daily/SKILL.md`, `skills/daily/references/detailed.md`, `README.md`,
`docs/specs/2026-10-26-task-driven-work-design.md` (the platform model's status list and the
status rules).
- PT-BR names: `review` "em code review", `ready_deploy` "pronto para deploy", `blocked`
  "bloqueado" (with the existing five).
- Hoje: a `ready_deploy` card reads "<Task in a few words>: deploy pendente (<KEY>)".
- Impedimentos: `kind: "blocked"` → "<Task in a few words>: bloqueado (<KEY>)", no question; the
  question "Algum desses é impedimento?" only when there is at least one `kind: "stuck"` line, and
  it refers to those. The 3-line cap counts both kinds.
- README: the `config.toml` example overrides become the TS mapping of the table above.
- Commit: `docs: daily e spec com as etapas do fluxo`.
