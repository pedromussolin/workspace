# Short daily Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** `daily` gives by default a short, friendly text the user can go through in at most 2
minutes; `daily detalhado` gives today's full per-task format.

**Why (user, 2026-10-27):** "preciso de algo mais resumido e curto e talvez ter uma opção verbosa
[...] Tenho no máx 2 min pra falar na daily". Chosen: one friendly line per task, written about the
task (not in the first person: the user reads it in the first person and explains it to the team),
with the key at the end in parentheses; the card moves in a separate note after the text.

**Builds on:** `docs/plans/2026-10-27-daily-by-task.md` (merged). Same Global Constraints.

## Execution

| Task | Model | Effort | Why |
|---|---|---|---|
| 1 `--top` and `moves` in `ws standup report` | sonnet | low | a flag, a slice, two fields and their tests |
| 2 The two modes in the skill | sonnet | medium | friendly PT-BR wording against a fixed contract |
| Reviews | sonnet | low | small diffs |

Tasks 1 and 2 run in parallel (separate worktrees).

## The contract change: `ws standup report`

`ws standup report --activity FILE [--cards FILE] [--today YYYY-MM-DD] [--top N]`

- `--top N` (N ≥ 1): `yesterday` and `today` keep only their first N entries (they are already
  ordered). `next_steps` and `blockers` are never cut.
- New field, always present: `"more": {"yesterday": X, "today": Y}`, the number of entries cut
  from each list (0 without `--top` or when nothing was cut).
- New field, always present: `"moves": [{"key", "from", "to"}]`, every suggestion of the full
  lists (before any cut), in the order yesterday then today; `[]` when there is none.
- Everything else is unchanged.

### Task 1: `--top` and `moves`

Files: `src/ws/standupreport.py`, `src/ws/cli.py`, `tests/test_standupreport.py`.
Tests: `--top 2` on 4 yesterday entries keeps the first 2 and gives `more.yesterday` 2; `moves`
lists a suggestion whose entry was cut; without `--top`, `more` is zeros and the lists are whole;
`--top 0` or a negative value → argparse error (exit 2).
Commit: `feat: report com --top e a lista de cards a mover`.

### Task 2: the two modes in the skill

Files: `skills/daily/SKILL.md`, `README.md` (the `ws standup report` row mentions `--top`),
`docs/specs/2026-10-26-task-driven-work-design.md` ("What the standup shows": the short default and
the detailed mode).

- The mode: **detailed** when the user asks for it ("daily detalhado", "daily completo",
  "standup detalhado", "verboso"); **short** otherwise. The description says the short text is the
  default and the detailed one is on request, with the same triggers as today.
- Short mode runs step 4 with `--top 3`; detailed mode without `--top`.
- Short template (PT-BR; the whole text at most about 120 words):

```text
**Ontem**
- <Task in a few words>: <what moved, in plain words> (<KEY>)
- E mais <more.yesterday> tarefas.

**Hoje**
- <Task in a few words>: <what is next> (<KEY>)
- <Projeto>: <the next step in one short line>

**Impedimentos**
- <Task in a few words>: sem avanço desde <dd/mm> (<KEY>)
Algum desses é impedimento?

---
Para você: mover <KEY> para <status>; ...
```

  - Each line describes the task, never the person: no first person ("fiz", "fechei") and no
    second person. Example: "Release do portal com permissões por área: PRs prontas para o deploy
    (TS-5424)." The user reads it in the first person and explains it to the team.
  - No sha, PR number, repo name, branch or jargon; the line comes from the card title, the commit
    subjects and the PR titles, rewritten for people.
  - "E mais N tarefas." only when the count is above 0 (singular "E mais 1 tarefa.").
  - No blockers: "Nenhum." and no question.
  - The note after `---` starts with "Para você:" and holds, in this order, only what exists: the
    `moves` ("mover TS-5431 para em validação", PT-BR status names); "Jira indisponível" when
    `jira` is false; "N avisos, peça \"daily detalhado\"" when there are warnings. With none of
    them, no note and no `---`.
- Detailed mode: today's template and rules, unchanged, except that its lines also describe the
  task and not the person.
- Commits: `feat: daily curto por padrão e detalhado sob pedido`, `docs: spec e README do daily curto`.
