---
name: daily
description: Builds the user's daily standup (yesterday, today, blockers), the status of their tasks against the code, and their open tasks, from git, GitHub and Jira, without writing anywhere. Use when the user asks for the daily, the standup or what they have today ("daily", "standup", "o que tenho hoje?"); not on a greeting such as "bom dia", alone or with another request.
---

# Daily standup

## Overview

Reads the user's git, GitHub and Jira activity and writes the standup in the chat. The text is PT-BR
(the user reads it or pastes it); these instructions are in English. This skill only reads: it never
creates, edits, transitions or comments on anything.

Working files go in `~/.local/share/workspace/standup/`. Run `mkdir -p` on it first. Never read
`~/.config/workspace/credentials`; `~/.config/workspace/config.toml` may be read.

## Steps

1. **Activity.** Run `ws standup collect > ~/.local/share/workspace/standup/activity.json`. It reads
   every git repo under `repo_roots` and prints `window` (`since` is the previous workday), `commits`,
   `branches`, `prs`, `last_activity`, `next_steps` and `warnings`.
2. **Cards, through the Atlassian MCP.**
   - Read `[jira] site` from `config.toml`. Call `getAccessibleAtlassianResources` and take the
     `cloudId` of the resource whose `url` equals that site.
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
   - Write `{"platform": "jira", "cards": [...]}` to `standup/cards.json`.
3. **If the MCP fails or times out**, run `ws task list --since <since> > standup/cards.json`. Exit 2
   means the config or the Jira API key is missing: tell the user to create the key on the
   Atlassian site and type `! ws config token jira` (never paste it in the chat). If this also
   fails, go on without cards and say in the text that Jira was unavailable.
4. **Status.** Run
   `ws task status --cards standup/cards.json --activity standup/activity.json`. It prints
   `tasks` (neutral cards: `key`, `title`, `url`, `status`, `epic_title`, `requested_by_other`,
   `updated`), `suggestions` (`key`, `from`, `to`, `rule`, `evidence`) and `stuck` (`key`,
   `last_activity`).
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
- <KEY> sem atividade desde <last_activity>: possivelmente travado

**Status**
- <KEY>: <from> -> <to> (<evidence>)

**Suas tarefas**
*<epic_title>*
- <KEY> <title> (<status>)
*Sem épico*
- <KEY> <title> (<status>) (pedido de outra pessoa)
```

- **Ontem:** commits, PRs and card changes since `window.since`. Every line cites a sha,
  `repo#PR` or a card key; a line that cannot cite one is left out.
- **Hoje:** tasks whose `status` is `in_progress`, plus each `next_steps` entry.
- **Impedimentos:** list the `stuck` cards as "possibly stuck" and ask the user before calling any
  of them a blocker; a card becomes a blocker only when the user says so. With none, write
  "nenhum".
- **Status:** one line per `suggestions` entry, citing its card key. They are suggestions: say
  nothing moved. With none, write "tudo em dia".
- **Suas tarefas:** every open task, grouped by `epic_title`, "Sem épico" last. A task with
  `requested_by_other` true ends with "(pedido de outra pessoa)".

## Rules

- Write only from the JSON. Do not guess a status, a date or a link between a commit and a card.
- Never call a write tool of Jira, GitHub or git. The skill only reads.
- State every `warnings` entry of `activity.json` at the end of the text, as it is.
- If `ws standup collect` fails, say so and stop; there is no standup without activity.
- Ask before calling a stuck card a blocker.
