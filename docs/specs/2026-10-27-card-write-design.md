# Card write: design

Phase B, part 1, of `docs/specs/2026-10-26-task-driven-work-design.md`: a skill that creates and
updates the user's Jira cards the way the user fills them by hand, with every write previewed and
approved by the user. Status: design, 2026-10-27, revised after a spec review the same day.

## Goal

The user types `/card` with what the card is ("/card cria um card para ...", "/card move a TS-5431
para validação", "/card comenta na TS-5424 que ...", "/card lança 2h na TS-5429") and gets a card
filled like their own: title with the epic's prefix, description in their sections, every field
they always fill. Nothing is written before the user sees the exact change and approves it in a
prompt of Claude Code itself.

## Decisions (user, 2026-10-27)

- A card always has, besides Jira's required fields (summary, issue type, project, reporter): the
  **parent epic**, the **priority**, the **assignee** (the user), the **sprint**, a **start date**
  and a **due date**.
- The model card is the user's own: type Tarefa; title `[ÁREA] ...` with the epic's prefix;
  description sections `## Contexto`, `## Desenho combinado`, `## A fazer antes de implementar`,
  `## Pronto quando`.
- Script first: the model writes the prose and picks values; `ws` builds the requests, checks the
  rules, converts the description to Jira's document format (ADF) and calls the API.
- Only the user's own cards are written: never another developer's card, never a card without an
  assignee (in code).

## Decisions taken while the user was away (to confirm)

- **Entry is `/card` only** (`disable-model-invocation: true`, root `CLAUDE.md`). The daily's
  "Para você:" note becomes "para aplicar: /card mover TS-5431 para em validação".
- **The approval is a Claude Code prompt, not prose.** `ws setup` checks and prints (it never
  edits `~/.claude/settings.json`) `permissions.ask` rules for `Bash(ws card apply:*)` and for
  every Atlassian MCP write tool (`createJiraIssue`, `editJiraIssue`, `transitionJiraIssue`,
  `addCommentToJiraIssue`, `addOrEditJiraIssueComment`, `addWorklogToJiraIssue`, `executeWrite`,
  `executeDestructive`, `createIssueLink`, on every Atlassian server installed). Until the user adds
  them, `ws setup` reports a "needs you" line. `ask`, not `deny`, so the GMUD skill (which creates
  requests through `executeWrite`) keeps working with a prompt. A rule matches the command text, so
  it alone is not the barrier: a PreToolUse hook (`hooks/ask_card_apply.py`) answers `ask` for any
  Bash command that, with quotes and backslashes removed, has `card` and `apply` as words, or
  `ws.card`, `from ws import card` or `run_apply` (so `uv run ws card apply`, `python -m ws`,
  `bash -c '...'`, an absolute path to `ws`, `--appr$(true)ove` or a variable holding the flag are
  asked too), and also for `ws` or `card` as a word together with a shell expansion or escape (`$`,
  a backtick, `{`, a backslash-newline) or `eval`, `base64`, `xxd`, `printf` (`ws card ap${x}ply`,
  `ws card a{pp,pp}ly`, `ws ca$(true)rd apply`); a plain `preview`, `check` and `epics` stay
  silent. It is a text hook: a script file the command runs, a background process in a new session
  (`setsid`, `nohup`) or an import route outside those patterns is not seen, and there the
  auto-mode classifier and the user's reading of each command remain the barrier. Not depending
  on text: the preview stores the session id of its shell (`os.getsid(0)`) and `ws card apply
  --approve` refuses (exit 1, "a prévia e a aprovação precisam ser passos separados") in the same
  session, so one command line cannot preview and apply (Claude Code runs each Bash call in its
  own session; a user running both by hand in one terminal uses another tab for the apply). `ws card
  apply --approve` itself exits 2 when the Claude settings lack the rule or a real registration of
  the hook (a `PreToolUse` entry whose matcher covers `Bash` and whose command runs the script
  with python). The preview is its own command (`ws card preview`) so the prompt appears only
  at the real write. There is no HMAC or signature on the pending record: the prompt (rule plus
  hook) is the barrier, the record is only checked to be the user's own private file.
- **Writes go only through the REST API** with the user's API key (an unscoped token). No MCP
  write path in this skill. The key goes only to an Atlassian Cloud site: `[jira] site` must match
  `^https://[a-z0-9-]+\.atlassian\.net/?$`, checked when the config is read and again when the
  client is built (exit 2 otherwise), and a `credentials` file that is a symlink or not owned by
  the user is refused. Without the key the skill stops and says to run `ws config token jira`
  in the user's own terminal.
- **Project allow-list:** every key, for every op, belongs to the configured project. A card of
  another project (INFRA included) is refused; such a change is done by hand. This replaces the
  parent spec's "no creation in INFRA" with a stricter rule.
- **Sprint:** the configured board's active sprint; exactly one → used, shown in the preview with
  its name and end date, with a warning when the end date is past (the board keeps one sprint open
  for months); none or several → the check fails and the skill asks.
- **Dates:** "today" is in the user's Jira time zone (`timeZone` of `GET /myself`), not the
  machine's (WSL is often UTC). `start` defaults to today; `due` is always asked.
- **Required sections:** `## Contexto` and `## Pronto quando`, exact level-2 headings, each not
  empty; the other two only when there is something to say.
- **Amends the parent spec:** Jira-specific `ws card` instead of the neutral `ws task check/apply`
  and REST as the main path instead of the MCP; the neutral plan returns when a second platform
  arrives. The parent spec and backlog item 1 point here.

## The draft file (the model's only output)

One operation per file in `~/.local/share/workspace/cards/drafts/` (mode 700), Markdown with a TOML
front matter between `+++` lines, written with the Write tool (a quoted heredoc when Write is
denied). Unknown front-matter keys are an error (a typo never goes silently); TOML dates and
strings are both accepted for dates.

```text
+++
op = "create"
epic = "TS-101"
priority = "High"
start = 2026-10-28
due = 2026-10-31
+++
# [FRONT] Título curto do card

## Contexto
...

## Pronto quando
- ...
```

| `op` | Front matter | Body |
|---|---|---|
| `create` | `epic`, `priority`, `due`; optional `start` | `# <title>` then the sections |
| `edit` | `key`; any of `title`, `priority`, `start`, `due`, `epic` | optional: a new description |
| `move` | `key`, `to` (the target status name) | none |
| `comment` | `key` | the comment, Markdown |
| `worklog` | `key`, `time` (`2h`, `30m`, `1h 30m`: hours and minutes only), optional `day` | optional |

## The commands

Exit codes for all: 0 ok; 1 a rule failed (the JSON lists the problems); 2 setup needed (no
`config.toml` keys, no API key); 3 Jira refused or unreachable (401/403/5xx/timeout).

- `ws card check DRAFT` — reads the draft, fetches what the rules need (the epic, the card, its
  transitions, the active sprint, the user) and prints a JSON verdict: `ok`, `problems`, `warnings`
  and the resolved values (sprint id, name and end date; epic key, title and prefix; the card's
  current status and assignee; the request(s) it would send).
- `ws card epics` — the epics of the user's open cards: search
  `assignee = currentUser() AND project = <project> AND statusCategory != Done` with `parent`,
  keep the parents with `issuetype.hierarchyLevel == 1` that are not done, print key, title,
  prefix and status. Empty → the skill asks the user for an epic key.
- `ws card preview PATH` — PATH is one draft or a folder of drafts (in name order), always under
  `cards/drafts/` (a file outside it, or a symlink, is refused). Runs every check; on success prints
  the PT-BR preview of every change (field by field; for `edit` of a description, the old and the
  new text) and the requests (method, path, body; never the `Authorization` header), and stores a
  pending record `~/.local/share/workspace/cards/pending/<code>.json` (mode 600) with the drafts'
  paths and content hashes, the requests, the "before" state and today's date. `<code>` is the first
  12 hex characters of the SHA-256 of the site, the methods, the paths, the bodies and the "before"
  state (the current values an edit replaces, a move's current status). Prints the code.
- `ws card apply PATH --approve CODE` — the only form of `apply` (without `--approve` it is an
  error; the flag cannot be abbreviated). Refuses unless the Claude settings hold the `ask` rule and
  the hook (exit 2), a pending record with that code exists, is the user's own file with mode 600,
  is under 30 minutes old and not dated in the future, and the drafts are unchanged (same paths,
  same bytes); re-runs every check against live Jira (the card may have been reassigned or moved
  since the preview) and refuses when the requests or the "before" state now differ, saying when it
  is only "today" that rolled over; checks the five request shapes once more; deletes the pending
  record **before** sending (at most once: a second `--approve` with the same code finds nothing);
  sends the requests in order, stopping at the first failure and reporting what was applied; moves
  each applied draft to `cards/done/` and drops the other pending records that mention it. A draft
  whose write failed or is uncertain moves to `cards/uncertain/` (a later preview of the folder
  never takes it again) and the report says where. A timeout, a 5xx or a connection error after
  sending → "resultado incerto: confira no Jira", no retry; for `create`, the JQL to look for the
  title.

## The rules (`ws card check`, again at `--approve`)

- Every op: the key (and the epic) belong to the configured project.
- `create`: the epic exists, `issuetype.hierarchyLevel == 1`, not done; the title is one line, at
  most 255 characters, and starts with the epic's prefix (`^\[[^\]]+\]`, case-sensitive) and a
  space (an epic without a prefix → any title); the two required sections; `priority` is one of
  the project's allowed priorities (create metadata); `start` ≤ `due`, `due` not before today;
  exactly one active sprint.
- `edit`: the card's assignee is the user; the title prefix against the new epic or the current
  one; `start` ≤ `due` merged with the current values; when the description is replaced, the two
  required sections, and a refusal when the current description holds content the converter cannot
  write back (tables, mentions, media, panels, expands, emoji), listing the types.
- `move`: the assignee is the user; the target matches exactly one available transition by its
  `to.name`, compared without case and accents; two matches → refused, listing them; a transition
  with required fields (`expand=transitions.fields`) → refused (done by hand).
- `comment`: the assignee is the user; the body converts.
- `worklog`: the assignee is the user; `time` matches `^\d+[hm](\s+\d+[hm])*$`; `day` not after
  today.

## The requests (REST v3)

- create: `POST /rest/api/3/issue` with `fields`: `project` `{key}`, `issuetype` `{name}`,
  `summary`, `description` (ADF), `parent` `{key}`, `priority` `{name}`, `assignee` `{accountId}`,
  the start-date field (`YYYY-MM-DD`), `duedate` (`YYYY-MM-DD`), the sprint field (the sprint id, a
  number). The fields were checked on the project's create screen on 2026-10-27.
- edit: `PUT /rest/api/3/issue/{key}` with the changed fields only (answers 204).
- move: `POST /rest/api/3/issue/{key}/transitions` with `{"transition": {"id"}}` (answers 204).
- comment: `POST /rest/api/3/issue/{key}/comment` with an ADF `body`.
- worklog: `POST /rest/api/3/issue/{key}/worklog` with the duration, the start (the `day` at 09:00
  in the user's time zone, written as `2026-10-28T09:00:00.000-0300`: offset without a colon) and
  an optional ADF comment.

`JiraClient` gains one `_request(method, path, body=None)` used by every call: JSON
`Content-Type`, a 204 or empty body is success, Jira's `errorMessages` and `errors` are part of
`JiraError`'s message, no retries.

## The ADF converter (`ws.adf`)

Written from scratch with tests (the GMUD converter it generalizes lives outside the repo). It
supports: `##`/`###` headings, paragraphs, bullet and numbered lists (nested by indentation),
checkbox items (`- [ ]`, `- [x]`, written as bullets starting with ☐ or ☑), fenced code blocks
(`codeBlock`), `**bold**`, `` `code` ``, `[text](url)` links. It fails closed: tables, block
quotes, images, raw HTML and any other construct → an error naming the line. It never emits an
empty text node, and never combines `code` with `strong`.

## Local config (`config.toml`, outside the repo)

```toml
[jira]
project = "<PROJECT>"
board_id = <board id>
issue_type = "<issue type name>"
start_date_field = "customfield_<n>"
sprint_field = "customfield_<n>"
```

Missing keys → exit 2, naming them and the README section "Local config".

## The skill `card`

1. Understand the request; ask only what is missing (for `create`: the epic, offering
   `ws card epics`; the priority; the due date). Write the title and the sections in the user's
   style: plain PT-BR, the context and what "done" means.
2. Write the draft(s); run `ws card check`; fix and repeat until `ok`; ask the user about problems
   only they can settle.
3. `ws card preview <draft or folder>`; show the preview as printed, including warnings.
4. `ws card apply ... --approve CODE`: Claude Code asks the user to allow it (the `ask` rule); the
   user's yes in that prompt is the approval. Give the key and the link.
5. Several changes (the daily's "para aplicar"): one folder, one preview, one approval.

## Tests (pytest, a fake Jira server, no real Jira)

The converter (each construct, the refusals, no empty text nodes); every rule with a passing and a
failing case; time zone from `/myself`; `preview` sends no write; `--approve` without a pending
record, with a wrong code, with a changed draft, or twice sends no write; the right code sends
exactly the previewed requests; a 204 answer is success; Jira's error body reaches the message; a
batch stops at the first failure and reports what was applied; another person's card and another
project's key are refused for every op; `ws setup` reports the missing `ask` rules and the hook; the hook asks for every way of writing an approval; the site rule and the `credentials` checks.

## Out of scope

Branch creation and the task records under `projects/<p>/tasks/` (phase B, part 2); writes through
the MCP; GitHub Issues and Monday.
