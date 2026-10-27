# Card write: design

Phase B, part 1, of `docs/specs/2026-10-26-task-driven-work-design.md`: a skill that creates and
updates the user's Jira cards the way the user fills them by hand, with every write previewed and
approved. Status: design, 2026-10-27.

## Goal

The user says what the card is ("cria um card para ...", "move a TS-5431 para validação",
"comenta na TS-5424 que ...", "lança 2h na TS-5429") and gets a card filled like their own:
title with the epic's prefix, description in their four sections, every field they always fill.
Nothing is written before the user sees the exact change and says yes.

## Decisions (user, 2026-10-27)

- A card always has, besides Jira's required fields (summary, issue type, project, reporter): the
  **parent epic**, the **priority**, the **assignee** (the user), the **sprint**, a **start date**
  and a **due date**.
- The model card is the user's TS-5431: type Tarefa; title `[ÁREA] ...` with the epic's prefix;
  description sections `## Contexto`, `## Desenho combinado`, `## A fazer antes de implementar`,
  `## Pronto quando`.
- Script first (root `CLAUDE.md`): the model writes the prose and picks values; `ws` builds the
  payloads, checks the rules, converts the description to Jira's document format (ADF) and calls
  the API.
- Only the user's own cards are written: never another developer's card, never a card without an
  assignee (the rule is in code).

## Decisions taken while the user was away (to confirm)

- **The sprint is the board's active sprint.** Board 358 has one active sprint ("Sprint 16.6.40",
  open since July): the team keeps a single open sprint. `ws` reads the active sprints of the
  configured board; exactly one → used; none or several → the check fails and the skill asks.
- **Start date defaults to today; the due date is always asked** (no default). The priority and
  the epic are asked when the user did not say them.
- **Required sections:** `## Contexto` and `## Pronto quando`; the other two are optional (a small
  card may not need a design). The check rejects a description without the two.
- **Writes go only through the REST API** (`ws`, with the user's API key). No MCP write fallback
  in this part: an MCP write would skip the checks. Without the key, the skill stops and tells the
  user to run `ws config token jira` in their own terminal. A Claude Code hook that blocks the
  Atlassian MCP write tools is in the backlog.
- **The skill is `card`**, invoked only by the user (`/card ...`), since it writes outside the repo
  (`disable-model-invocation: true`, root `CLAUDE.md`).

## The draft file (the model's only output)

One operation per file, under `~/.local/share/workspace/cards/drafts/`, Markdown with a TOML front
matter between `+++` lines. The model writes it with the Write tool (or a quoted heredoc when Write
is denied).

```text
+++
op = "create"
epic = "TS-5357"
priority = "High"
start = "2026-10-28"
due = "2026-10-31"
+++
# [FRONT] Permissões atômicas por ação

## Contexto
...

## Pronto quando
- ...
```

| `op` | Front matter | Body |
|---|---|---|
| `create` | `epic`, `priority`, `due`; optional `start` (default today) | `# <title>` then the sections |
| `edit` | `key`; any of `title`, `priority`, `start`, `due`, `epic` | optional: a new description (the sections) |
| `move` | `key`, `to` (a Jira status name, e.g. "In Validation") | none |
| `comment` | `key` | the comment, Markdown |
| `worklog` | `key`, `time` (Jira format: `2h`, `30m`, `1h 30m`), optional `day` (default today) | optional: what was done |

## The commands

- `ws card check DRAFT` — reads the draft, fetches what the rules need (the epic, the card, the
  active sprint, the user's account) and prints a JSON verdict: `ok`, the problems found, the
  resolved values (sprint id and name, epic title, the card's current status and assignee).
- `ws card apply DRAFT --dry-run` — runs the check; on success prints the PT-BR preview (what will
  change, field by field) and the exact request(s), and an approval code: the first 12 characters
  of the SHA-256 of the requests. Nothing is written.
- `ws card apply DRAFT --approve CODE` — recomputes the requests; refuses unless the code matches
  (so the draft cannot change between the preview and the write, and a write without a preview is
  impossible); then sends them and prints the card key and link.
- `ws card epics` — the epics of the user's open cards (key and title), for the model to offer
  when the user did not say the epic.

## The rules (`ws card check`)

- `create`: the epic exists, is an Epic of the configured project, and the title starts with the
  epic's prefix (the leading `[...]` of the epic's title; an epic without a prefix → any title);
  the description has `## Contexto` and `## Pronto quando`; `priority` is one of the project's
  priorities; `start` ≤ `due`, both ISO dates, `due` not in the past; exactly one active sprint on
  the board.
- `edit`, `move`, `comment`, `worklog`: the card's assignee is the user (by account id). An
  unassigned card or another person's card → refused.
- `move`: the target is one of the card's available transitions (`GET .../transitions`), matched
  by the target status name; refused otherwise, listing the available ones.
- `worklog`: `time` matches Jira's duration format; `day` not in the future.
- Never in the INFRA project (spec rule), whatever the op.

## The requests (REST v3)

- create: `POST /rest/api/3/issue` with `project`, `issuetype` (configured name), `summary`,
  `description` (ADF), `parent` (epic key), `priority` (`{name}`), `assignee` (the user's account
  id), the start-date field (configured id, `YYYY-MM-DD`), `duedate`, the sprint field (configured
  id, the sprint id as a number).
- edit: `PUT /rest/api/3/issue/{key}` with the changed fields only.
- move: `POST /rest/api/3/issue/{key}/transitions` with the transition id.
- comment: `POST /rest/api/3/issue/{key}/comment` with an ADF body.
- worklog: `POST /rest/api/3/issue/{key}/worklog` with the duration (`time`), the start (`day` at
  09:00 local time, with the offset, in Jira's timestamp format) and an optional ADF comment.

The Markdown → ADF conversion becomes `ws.adf` (headings, paragraphs, bullet and numbered lists,
nested lists, `**bold**`, `` `code` ``, links), generalized from the GMUD converter
(`gmud-adf.py`, own code); ADF never combines `code` with `strong`.

## Local config (`config.toml`, never in the repo)

```toml
[jira]
project = "TS"
board_id = 358
issue_type = "Tarefa"
start_date_field = "customfield_10015"
sprint_field = "customfield_10020"
```

Missing keys → `ws card check` names them and points to the README section "Local config".

## The skill `card`

1. Understand the request; ask only what is missing (for `create`: epic — offer `ws card epics`;
   priority; due date). Write the title and the sections in the user's style: plain PT-BR, the
   context and what "done" means; `Desenho combinado` and `A fazer antes de implementar` only when
   there is something to say.
2. Write the draft; run `ws card check`; fix and repeat until `ok` (problems that need the user →
   ask).
3. Run `ws card apply --dry-run`; show the preview to the user, as is, and ask for a yes.
4. Only on an explicit yes: `ws card apply --approve CODE`; give the key and the link.
5. Several operations (for example the daily's "mover TS-5431, TS-5424 para ..."): one draft per
   card, one preview listing all of them, one yes, then one apply per draft.

## Tests (pytest, a fake Jira server, no real Jira)

The ADF conversion; every check rule with a passing and a failing case; the dry-run makes no
write request; `--approve` with a wrong code makes no write request; the right code sends exactly
the previewed requests; transitions by name; worklog `started` format; a card of another person is
refused for every op.

## Out of scope

Branch creation and the task records under `projects/<p>/tasks/` (phase B, part 2); writes through
the MCP; the hook on the MCP write tools; GitHub Issues and Monday.
