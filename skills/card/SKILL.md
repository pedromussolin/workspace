---
name: card
description: Creates and updates the user's own Jira cards (create, edit, move to a status, comment, log work) in the user's card style, with a preview and an approval prompt before any write, through the `ws card` commands. Use only when the user types /card, for example "/card cria um card para ...", "/card mover TS-5431 para em validação" or the daily's "para aplicar".
disable-model-invocation: true
---

# Card

Writes to Jira, so the order is fixed: draft, check, preview, approval (the apply). The model writes
the prose and picks values; `ws card` builds the requests, checks the rules and calls the REST API.
Nothing is written through the Atlassian MCP, ever.

## Steps

1. **Understand the request.** Ask only what is missing. For `create`: the epic (run
   `ws card epics` and offer the list; empty, ask for an epic key), the priority and the due date
   (`start` defaults to today). Write the title and sections in the user's style (below).
2. **Write the draft** with the Write tool in `~/.local/share/workspace/cards/drafts/` (one
   operation per file; `cat > <path> <<'EOF'` with the delimiter quoted, if Write is denied). Run `ws card check <draft>`; fix the
   draft and repeat until `ok` is true. Ask the user only about problems that only they can settle.
3. **Preview:** `ws card preview <draft or folder>`. It writes nothing to Jira. Show the preview
   exactly as printed, warnings included, and the code. Never run `apply` before this was shown.
4. **Apply:** `ws card apply <same path> --approve <CODE>`. This is the only command that writes,
   and the Claude Code prompt on it is the approval (the `permissions.ask` rule plus the
   `hooks/ask_card_apply.py` hook, which asks for any command that names `card` with `apply` or
   imports `ws.card`, or that combines `ws`/`card` with a shell expansion; it reads text, so a
   script file, a `setsid`/`nohup` background process or an odd import is not seen). Never ask the user
   to type the code or to say "ok" in chat instead, and never wrap or disguise the command to avoid
   the prompt, and never run the preview and the apply in one command line: `apply` refuses when it
   shares the shell session with the preview. If it exits 2 with a settings message, tell the user to run `ws setup`. Afterwards
   give the key and the card link. A draft that failed or is uncertain is in
   `~/.local/share/workspace/cards/uncertain/`; say where and ask the user to check Jira.
5. **Several changes** (the daily's "para aplicar: /card mover ...; ..."): one draft per change
   in one folder, one preview, one approval.

## The draft

A Markdown file with TOML front matter between `+++` lines. Unknown keys are an error. Dates are
`YYYY-MM-DD`.

| `op` | Front matter | Body |
|---|---|---|
| `create` | `epic`, `priority`, `due`; optional `start` | `# <title>` then the sections |
| `edit` | `key`; any of `title`, `priority`, `start`, `due`, `epic` | optional new description |
| `move` | `key`, `to` (target status name) | none |
| `comment` | `key` | the comment, Markdown |
| `worklog` | `key`, `time` (`2h`, `30m`, `1h 30m`), optional `day` | optional comment |

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
Por que existe e o que muda, em texto simples.

## Pronto quando
- O que precisa estar valendo para fechar o card.
```

```text
+++
op = "move"
key = "TS-5431"
to = "Em validação"
+++
```

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
  required and not empty; the other two only when there is something to say.
- Plain PT-BR describing the task, not the person. Only headings, paragraphs, lists, fenced code,
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

Only the user's own cards, in the configured project, are written; a refusal for another person's
card or another project is final: tell the user to do it by hand.
