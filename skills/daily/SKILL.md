---
name: daily
description: Builds the user's daily standup grouped by task (yesterday, today, blockers), with status suggestions from the code, from git, GitHub and Jira, without writing anywhere. Use when the user asks for the daily, the standup or what they have today ("daily", "standup", "o que tenho hoje?"); not on a greeting such as "bom dia", alone or with another request.
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
2. **Cards, through the REST script.** Run
   `rm -f ~/.local/share/workspace/standup/cards.json ~/.local/share/workspace/standup/cards.json.tmp`
   (so a card file from an earlier day is never used), then
   `ws task list --since <since> > ~/.local/share/workspace/standup/cards.json.tmp`, where `<since>`
   is `window.since` from `activity.json`. Only when the exit code is 0, `mv` the `.tmp` file to
   `cards.json`; a failed run must not leave a `cards.json`. Exit 0: go to step 4 with cards. Exit 2 (no
   `config.toml` or no Jira API key; the user can create the key on the Atlassian site and run
   `ws config token jira` in their own terminal, outside Claude, since it needs a terminal and the
   key is never pasted in the chat) or exit 1 (Jira error): go to step 3.
3. **Fallback: the Atlassian MCP.**
   - Read `[jira] site` from `~/.config/workspace/config.toml`. Call
     `getAccessibleAtlassianResources` and take the `cloudId` of the resource whose `url` equals that
     site. No config file, no matching resource or an MCP error: there are **no cards**, see the
     end of this step.
   - Call `atlassianUserInfo` for the account id (used only to set `reporter_is_me`).
   - Call `searchJiraIssuesUsingJql` with `cloudId`, `maxResults: 100`,
     `fields: ["summary", "status", "parent", "reporter", "updated"]` and this `jql`:

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
   - **No cards** (the script and the MCP both failed): go to step 4 without `--cards`.
4. **Report.** Run
   `ws standup report --activity ~/.local/share/workspace/standup/activity.json --cards ~/.local/share/workspace/standup/cards.json`
   (without the `--cards` part when there are no cards). It prints one JSON: `jira`, `yesterday`,
   `today`, `next_steps`, `blockers`, `keyless` and `warnings` (the fields are used below). If it
   fails, say so with its stderr and stop: the text comes only from the report.
5. **Write the text** with the template below, from the report only.

## Output (PT-BR)

Use exactly these three headings, in this order:

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

- **Ontem:** one line per `yesterday` entry, in order, naming its key and `title`; the short line
  is built from its `subjects` and `prs` (cite `ref` for a PR), never inventing what changed. The
  "N commits sem card em <repos>" line (`keyless.commits`, `keyless.repos`) only when
  `keyless.commits` is greater than 0. No topic without a key.
- **Hoje:** one line per `today` entry with its `status`; omit ": <next_step>" when it is null.
  Then one line per `next_steps` entry as "<project>: <text>".
- **Impedimentos:** one line per `blockers` entry, then the question "Algum desses é impedimento?"
  once. With none, write "Nenhum." and no question.
- `<suggestion>`: only when the entry's `suggestion` is not null, as "Sugestão: mover de <from>
  para <to> (<evidence>)"; nothing moved. Otherwise nothing.
- Status names in PT-BR: `todo` "a fazer", `in_progress` "em andamento", `validation` "em
  validação", `done` "concluída", `cancelled` "cancelada".
- `jira` false: start the text with "Jira indisponível: sem status nem títulos dos cards"; list
  the `yesterday` topics by key, with the PR title when there is one; under **Hoje** only the
  `next_steps`; under **Impedimentos** write "indisponível".
- End with every `warnings` entry, as it is.

## Rules

- Write only from the report. Do not guess a status, a date or a link between a commit and a card.
- Never call a write tool of Jira, GitHub or git. The skill only reads.
- Ask before calling anything a blocker; a `blockers` entry is only a possibility until the user
  says so.
