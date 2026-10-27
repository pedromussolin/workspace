---
name: daily
description: Builds the user's daily standup (yesterday, today, blockers), the status of their tasks against the code, and their open tasks, from git, GitHub and Jira, without writing anywhere. Use when the user asks for the daily, the standup or what they have today ("daily", "standup", "o que tenho hoje?"); not on a greeting such as "bom dia", alone or with another request.
---

# Daily standup

## Overview

Reads the user's git, GitHub and Jira activity and writes the standup in the chat. The text is PT-BR
(the user reads it or pastes it); these instructions are in English. This skill only reads: it never
creates, edits, transitions or comments on anything.

Working files go in `~/.local/share/workspace/standup/`. Run
`mkdir -p ~/.local/share/workspace/standup` first and always use the full path, never a relative
one: card titles must not land in whatever folder the session is in. Never read
`~/.config/workspace/credentials`; `~/.config/workspace/config.toml` may be read.

## Steps

1. **Activity.** Run `ws standup collect > ~/.local/share/workspace/standup/activity.json`. It reads
   every git repo under `repo_roots` and prints `window` (`since` is the previous workday), `commits`,
   `branches`, `prs` (each with `updated_at`), `last_activity`, `next_steps` and `warnings`. If it
   fails, say so and stop.
2. **Cards, through the Atlassian MCP.** First run
   `rm -f ~/.local/share/workspace/standup/cards.json ~/.local/share/workspace/standup/cards.json.tmp`,
   so a card file from an earlier day is never used.
   - Read `[jira] site` from `~/.config/workspace/config.toml`. Call
     `getAccessibleAtlassianResources` and take the `cloudId` of the resource whose `url` equals that
     site. No config file or no matching resource: go to step 3.
   - Call `atlassianUserInfo` for the account id (used only to set `reporter_is_me`).
   - Call `searchJiraIssuesUsingJql` with `cloudId`, `maxResults: 100`,
     `fields: ["summary", "status", "parent", "reporter", "updated"]` and this `jql`, where
     `<since>` is `window.since` from `activity.json`:

     ```text
     assignee = currentUser() AND (statusCategory != Done OR updated >= "<since>") ORDER BY updated DESC
     ```

   - The answer is `issues.nodes[]` and `issues.pageInfo`. While `hasNextPage` is true, call again
     with `nextPageToken` set to `endCursor`.
   - Turn each node into a compact card with exactly these fields: `key`; `title`
     (`fields.summary`); `status_name` (`fields.status.name`); `status_category`
     (`fields.status.statusCategory.key`: `new`, `indeterminate` or `done`); `epic_key` and
     `epic_title` (`fields.parent.key` and `fields.parent.fields.summary`, `null` without a
     parent); `reporter_is_me` (`fields.reporter.accountId` equals the account id);
     `updated` (`fields.updated`, as it came).
   - Create `~/.local/share/workspace/standup/cards.json` with the Write tool (not a shell
     command, so titles need no quoting), containing `{"platform": "jira", "cards": [...]}`.
3. **If the MCP fails, times out or step 2 could not start**, run
   `ws task list --since <since> > ~/.local/share/workspace/standup/cards.json.tmp` and, only when
   the exit code is 0, `mv` the `.tmp` file to `cards.json` (a failed run must not leave an empty
   `cards.json`). Exit 2 means the config or the Jira API key is missing: tell the user to create
   the key on the Atlassian site and run `ws config token jira` in their own terminal, outside
   Claude (it needs a terminal and the key is never pasted in the chat). If this also fails there
   are **no cards**: skip step 4 and write from the activity alone. Start the text with the line
   "Jira indisponível: sem status, tarefas nem cards"; write "indisponível" under **Impedimentos**,
   **Status** and **Suas tarefas**; in **Hoje** keep only the `next_steps` entries.
4. **Status.** Run
   `ws task status --cards ~/.local/share/workspace/standup/cards.json --activity ~/.local/share/workspace/standup/activity.json`.
   It prints `tasks` (neutral cards: `key`, `title`, `url`, `status`, `epic_title`,
   `requested_by_other`, `updated`), `suggestions` (`key`, `from`, `to`, `rule`, `evidence`) and
   `stuck` (`key`, `last_activity` always null, `updated`, `workdays`). If it fails, put its stderr
   in the text and go on from the activity alone, as in step 3 without cards.
5. **Write the text** with the template below, from these JSON files only.

## Output (PT-BR)

Use exactly these five headings, in this order:

```text
**Ontem**
- <what the user did> (<sha> | <repo>#<PR> | <KEY>)

**Hoje**
- <KEY> <title>: <status>, em andamento
- <próximo passo of each project, from next_steps>

**Impedimentos**
- <KEY> sem commit há <workdays> dias úteis; card atualizado em <updated>: possivelmente travado

**Status**
- <KEY>: <from> -> <to> (<evidence>)

**Suas tarefas**
*<epic_title>*
- <KEY> <title> (<status>)
*Sem épico*
- <KEY> <title> (<status>) (pedido de outra pessoa)
```

- **Ontem:** only commits whose `keys` is not empty (one line each, citing sha and key), PRs with
  `updated_at` on or after `window.since` (citing `repo#PR`), and cards whose `updated` is on or
  after `window.since`, with their current status; never say what changed in a card. Commits
  without a key are not listed one by one: at most one line, "N commits sem card em <repos>".
- **Hoje:** tasks whose `status` is `in_progress`, plus each `next_steps` entry.
- **Impedimentos:** list the `stuck` cards as "possibly stuck" and ask the user before calling any
  of them a blocker; a card becomes a blocker only when the user says so. With none, write
  "nenhum".
- **Status:** one line per `suggestions` entry, citing its card key. They are suggestions: say
  nothing moved. With none, write "tudo em dia".
- **Suas tarefas:** every open task (`status` not `done` and not `cancelled`: the list also holds
  cards finished inside the window), grouped by `epic_title`, "Sem épico" last. A task with
  `requested_by_other` true ends with "(pedido de outra pessoa)".

## Rules

- Write only from the JSON. Do not guess a status, a date or a link between a commit and a card.
- Never call a write tool of Jira, GitHub or git. The skill only reads.
- State every `warnings` entry of `activity.json` at the end of the text, as it is.
- Ask before calling a stuck card a blocker.
