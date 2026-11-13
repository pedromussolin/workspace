---
name: card
description: Creates and updates Jira cards the user can write (the user is the card's assignee or reporter) (create, edit, move to a status, comment, log work, link two cards) in the user's card style, with a preview and an approval prompt before any write, through the `ws card` commands. Use only when the user types /card, for example "/card cria um card para ...", "/card mover TS-5431 para em validação", "/card sincronizar", "/card reorganizar" (align the project items with the tracker) or the daily's "para aplicar".
disable-model-invocation: true
---

# Card

Writes to Jira, so the order is fixed: draft, check, preview, approval (the apply). The model writes
the prose and picks values; `ws card` builds the requests, checks the rules and calls the REST API.
Nothing is written through the Atlassian MCP, ever.

## Steps

1. **Understand the request.** Read `references/card-rules.md` (next to this file) to choose the
   type, the epic, the links and the sections. Ask only what is missing. For `create`: the type
   (propose one from the rules' ordered questions, with a one-line reason), the epic (run
   `ws card epics` and offer the list; empty, ask for an epic key; an epic or an initiative takes no
   epic), the priority and, only when there is a sprint, the due date (a create has no start date:
   it is set when the task starts). No sprint unless the user asks for one (`sprint = "active"`).
   The assignee and the reporter are the user (`me`) unless the user names someone else, by dev id
   (`ws people me` prints the user's id; `ws people add EMAIL` prints the config block of a
   colleague; when an id is unknown, `ws card check` says which). Leave `reporter` out when it is
   the user: the tracker makes the creator the reporter, and a `reporter` key is sent only when
   written (the type's create screen must have the field). Write the title and sections in
   the user's style (below).
2. **Write the draft** with the Write tool in `~/.local/share/workspace/cards/drafts/` (one
   operation per file; `cat > <path> <<'EOF'` with the delimiter quoted, if Write is denied). Run `ws card check <draft>`; fix the
   draft and repeat until `ok` is true. Ask the user only about problems that only they can settle.
3. **Preview:** `ws card preview <draft or folder>`. It writes nothing to Jira. Show the preview
   exactly as printed, warnings included, and the code. Never run `apply` before this was shown.
4. **Apply:** `ws card apply <same path> --approve <CODE>`. This is the only command that writes,
   and the Claude Code prompt on it is the approval: the approval gate (`hooks/approval_gate.py`)
   stops the command and shows the user the preview's summary, and the user's yes in that box
   approves exactly that. The gate reads the command text, so a script file or a
   `setsid`/`nohup` background process is not seen. The user can also run the same command by hand
   in their own terminal: it prints the summary and asks `Gravar no Jira? [s/N]`. Never ask the user
   to type the code or to say "ok" in chat instead, and never wrap or disguise the command to avoid
   the prompt, and never run the preview and the apply in one command line: `apply` refuses when it
   shares the shell session with the preview. If it exits 2 with a settings message, tell the user to run `ws setup`. Afterwards
   give the key and the card link. A draft that failed or is uncertain is in
   `~/.local/share/workspace/cards/uncertain/`; say where and ask the user to check Jira.
5. **Several changes**: one draft per change in one folder, one preview, one approval.
6. **Sync** (`/card sincronizar`, the daily's "para aplicar /card sincronizar"): moves the cards
   to the status the code proves. Work in `~/.local/share/workspace/board/` (`mkdir -p` first).
   - Run `rm -f ~/.local/share/workspace/board/cards.json ~/.local/share/workspace/board/cards.json.tmp ~/.local/share/workspace/board/board.json ~/.local/share/workspace/board/board.json.tmp`
     first, so a file from an earlier run is never used. Then
     `ws task list > ~/.local/share/workspace/board/cards.json.tmp` and, only on exit 0, `mv` it to
     `cards.json`; then
     `ws board status --cards ~/.local/share/workspace/board/cards.json > ~/.local/share/workspace/board/board.json.tmp`
     and, only on exit 0, `mv` it to `board.json`. When `ws task list` or `ws board status` fails,
     stop and say why, in PT-BR, from its stderr. Exit 2 from `ws board status` with the `[board]`
     message: tell the user to add `[board]` to `config.toml` (README, "Local config").
   - Show the user, in PT-BR and short: each `moves` entry ("TS-1: em andamento → concluído (em
     produção)", with `environment` in plain words, or without it when null); each `held` card
     with its reason, the first case that applies (`<status>` in PT-BR, so no "fica em em"):
     `holding.tag` set, "TS-2 (<status>): o commit <holding.commit> de <holding.repo> ainda não
     está na tag de produção <holding.tag>"; else `holding.reached` set, "TS-2 (<status>): o
     commit <holding.commit> de <holding.repo> só chegou a <holding.reached>"; else "TS-2
     (<status>): o commit <holding.commit> de <holding.repo> está só na branch <holding.branch>"
     (or "está fora dos ambientes" when `holding.branch` is null); each `limited` card ("o git só prova até
     <status>"); and the `warnings`: one starting with `fetch <repo>:` is written "dados de <repo>
     podem estar desatualizados" instead of the raw text (`stale` on a move is only a bool, the
     repo name exists only there); the others as they are. Status names in PT-BR:
     `todo` "a fazer", `in_progress` "em andamento", `review` "em code review", `validation` "em validação", `ready_deploy` "pronto para deploy", `blocked` "bloqueado", `done`
     "concluída", `cancelled` "cancelada".
   - No `moves`: say so and stop.
   - Otherwise run `ws board drafts --board ~/.local/share/workspace/board/board.json`; it prints
     `{"folder", "count"}`. Then steps 3 (preview of that `folder`) and 4 (apply it): one preview,
     one approval box for all moves. When the preview exits 1, it lists the failing drafts by file
     name: `mv` exactly those files to `<folder>-refused/` (next to the sync folder, inside
     `~/.local/share/workspace/cards/drafts/`; `mkdir -p` first), tell the user, in PT-BR, which
     cards to move by hand and why (the problem the preview printed), and preview the folder again
     with the rest. If no draft is left, stop.
     When the preview names no failing file (one `ws card preview: ...` line on stderr, a draft
     that did not load), show that message and ask the user; do not guess which drafts to move.

## Reorganize (`/card reorganizar`)

Aligns the project items (`projects/<slug>/tasks/*.md`) with the tracker. The item files are
written by `ws item` commands, never by hand here; the tracker is written only by the apply.

1. Run `ws item check --tracker [projects...]`. It prints `problems`, `drift`, `pending` and
   `orphans`. Exit 1: show each `problems` entry in PT-BR and stop for the user to fix the item.
   Exit 2 is setup, 3 is the tracker refusing or unreachable: show the message.
2. Show each `drift` entry (`path`, `card`, `field`) in PT-BR with both values; for people use
   `names`, not ids. Ask, per field, which side is right.
3. Where the tracker's side is right: `ws item pull <path> --fields f1,f2` (it changes only those
   keys of the item).
4. Where the item's side is right, and for `pending` entries: `ws item drafts [--only REFS]`
   (`REFS`: commas, card refs or item paths as `check` printed them). It prints `{"folder",
   "count", "need_text", "waiting", "by_hand"}`. For each path in `need_text` write the `# <title>`
   and the sections (the real names, in a draft outside the repo) and run `ws card check` on each.
5. One preview of the `folder` and one approval (steps 3 and 4 above).
6. Tell the user, in PT-BR, what is in `waiting` (links whose other card is not created yet: run
   `ws item drafts` again after this apply, a second batch) and in `by_hand` (what only the user
   can do in the tracker).
7. After the apply: `ws item sync [projects...]` (refreshes each item's `[tracker]` table) and
   `ws item table <slug>` (the README table).

A write-back failure after a create, or an uncertain create, leaves the item recorded as pending:
name `ws item set-card <item> <ref>` (the card exists) or `ws item set-card <item> --none` (it does
not), then draft again if needed. `ws item drafts` refuses to draft that item until then.
Items without an epic are not drafted: `by_hand` says so; set `epic` in the item first (the
`task-shaping` skill helps).

## The draft

A Markdown file with TOML front matter between `+++` lines. Unknown keys are an error. Dates are
`YYYY-MM-DD`.

| `op` | Front matter | Body |
|---|---|---|
| `create` | `item` (the item's repo-relative path; its `card` is written back after the apply); `type`, `priority`; `epic` (card types; refused for `epic`/`initiative`); `parent` (an epic only: its initiative, and only when the epic create screen has it); `assignee`, `reporter` (`me` or `dev-` + 10 hex, default `me`); `sprint` (absent = none, only `"active"`); `due` (optional, required with a sprint); no `start` | `# <title>` then the sections |
| `edit` | `key`; any of `title`, `type` (one of the five card types, on a card), `priority`, `start`, `due`, `epic` (on a card), `parent` (on an epic; never with `epic`), `assignee`, `reporter` | optional new description |
| `link` | `key`; any of `blocks`, `blocked_by`, `relates` (lists of keys) | none |
| `move` | `key`, `to` (target status name) | none |
| `comment` | `key` | the comment, Markdown |
| `worklog` | `key`, `time` (`2h`, `30m`, `1h 30m`), optional `day` | optional comment |

```text
+++
op = "create"
type = "task"
epic = "TS-101"
priority = "High"
+++
# [FRONT] Título curto do card

## Contexto
Por que existe e o que muda, em texto simples.

## Pronto quando
- O que precisa estar valendo para fechar o card.
```

A `bug` for another developer (a dev id; `reporter` stays the user), in the active sprint, so with a
`due`:

```text
+++
op = "create"
type = "bug"
epic = "TS-101"
priority = "High"
assignee = "dev-0123456789"
sprint = "active"
due = 2026-11-20
+++
# [FRONT] Tela fecha sem salvar o filtro

## Contexto
O filtro some ao trocar de aba.

## Como reproduzir
1. Aplicar um filtro e trocar de aba.

## Evidência
Trecho do log do erro, sem dado de cliente.

## Pronto quando
- O filtro continua aplicado ao voltar para a aba.
```

An epic: the title starts with its prefix and a space, and only `## Contexto` is required. This
Jira's epic create and edit screens have no `parent`, so leave it out: after the epic is created,
the user links it to its initiative by hand in the tracker (say so in the answer).

```text
+++
op = "create"
type = "epic"
priority = "Medium"
+++
# [FRONT] Nome do épico

## Contexto
O sistema ou objetivo que o épico cobre.
```

A link: `TS-102` blocks `TS-103` and relates to `TS-104`. Both cards must exist, so a card created
in the same batch is linked in a later run, and at least one of the two must be writable. A link
already in Jira is skipped; its opposite, or the same link twice (or both ways) in one batch, is
refused.

```text
+++
op = "link"
key = "TS-102"
blocks = ["TS-103"]
relates = ["TS-104"]
+++
```

```text
+++
op = "move"
key = "TS-5431"
to = "Em validação"
+++
```

Moving to "Em andamento" (any status that counts as in progress) also sets the start date to today
when the card has none: the preview shows "Data de início: hoje, dd/mm" and two requests, both
under the one approval. Do not ask for a start date or write one in a draft; use `edit` with
`start` only when the user asks for a specific date.

```text
+++
op = "edit"
key = "TS-5431"
due = 2026-11-03
+++
```

```text
+++
op = "comment"
key = "TS-5424"
+++
Texto do comentário.
```

```text
+++
op = "worklog"
key = "TS-5429"
time = "2h"
day = 2026-10-28
+++
```

## The user's card style

- Title `[ÁREA] ...`: the epic's prefix (as `ws card epics` prints it), a space, then a short
  description. An epic with no prefix takes any title. One line, up to 255 characters.
- Description sections, level-2 headings exactly: `## Contexto`, `## Desenho combinado`,
  `## A fazer antes de implementar`, `## Pronto quando`. `## Contexto` and `## Pronto quando` are
  required and not empty; the other two only when there is something to say. A `bug` and a
  `hotfix` also need `## Como reproduzir` and `## Evidência`, a `hotfix` also
  `## Por que não espera a release`, and an `epic` or `initiative` only `## Contexto`
  (`references/card-rules.md`).
- Plain PT-BR describing the task and only the task: no mention of the user, the AI, the
  conversation or agreements between them. Bad: "Validar a estrutura do documento com <o usuário>."
  Good: "Validar a estrutura do documento." Valid for create, edit (title and description) and
  comment. Citing the user or Claude stays when it is part of the task itself, and other people stay
  when the task depends on them.
- Only headings, paragraphs, lists, fenced code,
  `**bold**`, `` `code` `` and links; no tables, quotes, images or HTML (the converter refuses).

## Exit codes

- **0:** ok, go on.
- **1:** a rule failed; the JSON lists `problems`. Fix the draft, or ask the user when only they
  can decide (which epic, which date).
- **2:** setup needed (a `[jira]` key missing in `config.toml`, or no API key). Say so: run
  `ws config token jira` in the user's own terminal, outside Claude, or fill `config.toml` (README,
  "Local config"; the site must be `https://<name>.atlassian.net`), or the Claude settings lack
  the `ask` rule or the hook (`ws setup`). Stop.
- **3:** Jira refused or is unreachable. Show the message as is. Never retry a write: an uncertain
  result ("resultado incerto") means the user checks Jira; for a `create`, offer the JQL to look
  for the title.

Only cards where the user is the assignee or the reporter, in the configured project, are written
(a link needs one of its two cards to be writable); a refusal for another person's card or another
project is final: tell the user to do it by hand. A type change only goes between the five card
types; changing a card's level (to or from epic or initiative) is done by hand in the tracker. When
a field is not on the type's create screen or the card's edit screen, the check names it: drop it
from the draft, or the user sets it by hand in the tracker.
