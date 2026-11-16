---
name: daily
description: Builds the user's daily standup grouped by task (yesterday, today, blockers) with suggested card moves, from git, GitHub and the tracker, without writing anywhere. The text is short by default; the detailed one comes on request ("daily detalhado"). Use when the user asks for the daily, the standup or what they have today ("daily", "standup", "o que tenho hoje?"); not on a greeting such as "bom dia", alone or with another request.
---

# Daily standup

## Overview

Reads the user's git, GitHub and tracker activity and writes the standup in the chat, short by default. The text is PT-BR
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
   `cards.json`; a failed run must not leave a `cards.json`. Exit 0: go to step 3b with cards. Exit 2 (no
   `config.toml` or no tracker API key; the user can create the key on the tracker's site and run
   `ws config token <kind>` in their own terminal, outside Claude, since it needs a terminal and the
   key is never pasted in the chat) or exit 1 (tracker error): go to step 3.
3. **Fallback: the tracker's MCP.** Read `[tracker] kind` from `~/.config/workspace/config.toml`;
   an absent kind with an old `[jira]` table means `jira`. Follow `references/<kind>.md`: it names the
   MCP calls and the query, and ends with `~/.local/share/workspace/standup/cards.json` holding
   `{"platform": "<kind>", "cards": [...]}`, written with the Write tool (not an inline shell string,
   so titles need no quoting). When the Write tool is denied, write the same JSON with a quoted
   heredoc (`cat > ~/.local/share/workspace/standup/cards.json <<'EOF'` ... `EOF`): the quotes around
   `EOF` keep the shell from touching the titles. Never drop the fetched cards because Write was
   denied. This step only reads; it never writes to the tracker. With no reference for the kind, or
   that MCP not connected or failing, there are **no cards** (the script and the MCP both failed):
   go to step 4 without `--cards`.
3b. **Board.** Runs after step 2 or step 3, whichever produced `cards.json`; without one, skip it. Run
   `rm -f ~/.local/share/workspace/standup/board.json ~/.local/share/workspace/standup/board.json.tmp`,
   then `ws board status --cards ~/.local/share/workspace/standup/cards.json > ~/.local/share/workspace/standup/board.json.tmp`.
   Only when the exit code is 0, `mv` the `.tmp` file to `board.json`. Exit 2 (no `[board]` table
   or bad input) or exit 1: go on without the board and keep its stderr as one more warning: it counts in
   "N avisos", like the error of step 4's rerun. It reads git and fetches the remotes of the repos, so it can take a while.
3c. **Observations.** Runs after step 3b. Run `ws observe status --json`. Exit 0: read `plans`.
   Exit 1 with JSON on stdout: `plans` still holds every plan that could be read; read it, and
   count each item of `problems` as one warning (it counts in "N avisos"). Exit 2, any other
   exit, no JSON on stdout or a missing command: one more warning; go on without the line. In
   `plans`, a plan with a non-empty `pending`, `missing_days` or `stale`, with `state` `done` or
   with `state` `attention` is one entry for the "observação:" line of the note.
4. **Report.** Run
   `ws standup report --activity ~/.local/share/workspace/standup/activity.json --cards ~/.local/share/workspace/standup/cards.json --board ~/.local/share/workspace/standup/board.json --top 3`
   (without the `--cards` part when there are no cards; without the `--board` part when there is
   no `board.json`; without `--top 3` in detailed mode, see Modes). It prints one JSON: `tracker`, `yesterday`, `today`, `next_steps`, `blockers`, `keyless`,
   `more` (`yesterday` and `today`: entries cut by `--top`), `moves` (every card move the board
   found, `{key, from, to}`, before any cut), `to_confirm` (cards to ask about, see below) and
   `warnings` (the board's warnings included; the fields are used below). Without `--board` there
   are no suggestions, no `moves` and no `to_confirm`. If the
   run with `--cards` fails (a malformed `cards.json` or a rejected config), run it again with only
   `--activity`, write the standup from that report (`tracker` false) and add the first run's stderr
   to the final warnings line. If the run without `--cards` fails, say so with its stderr and
   stop: the text comes only from the report.
5. **Write the text** in the mode chosen, from the report only.

## Modes

- **Detailed** when the user asks for it ("daily detalhado", "daily completo", "standup
  detalhado", "verboso"): run step 4 without `--top` and follow `references/detailed.md`.
- **Short** otherwise: run step 4 with `--top 3` and follow the template below.

## Short output (PT-BR)

About 120 words in all. Friendly, plain words. No sha, PR number, repo, branch or jargon: rewrite
the card title, commit subjects and PR titles for people.

```text
**Ontem**
- <Task in a few words>: <what moved, in plain words> (<KEY>)
- E mais <more.yesterday> tarefas.

**Hoje**
- <Task in a few words>: <what is next> (<KEY>)
- <Task in a few words>: deploy pendente (<KEY>)
- <Projeto>: <the next step in one short line>

**Impedimentos**
- <Task in a few words>: bloqueado (<KEY>)
- <Task in a few words>: sem avanço desde <dd/mm> (<KEY>)
Algum desses é impedimento?

---
Para você: para aplicar /card sincronizar (N cards); testado em homologação? <KEY> (última atualização <dd/mm>);
Tracker indisponível; N avisos, peça "daily detalhado"
```

- **Describe the task, never the person.** No first person ("fiz", "fechei", "ajustei") and no
  second person. The user reads the text as their own and explains it to the team.
  Good: "Release do portal com permissões por área: PRs prontas para o deploy (TS-5424)."
  Bad: "Fechei as PRs do release do portal (TS-5424)."
- "E mais N tarefas." only when `more.yesterday` is above 0 (singular "E mais 1 tarefa."); the same
  for `more.today` under **Hoje**. Under **Hoje**, at most 2 lines from `next_steps`, each rewritten
  like the others: one short line about the task, no first person, no jargon (detailed mode keeps
  them as given).
- A `today` entry with status `ready_deploy` reads "<Task in a few words>: deploy pendente (<KEY>)".
- **Impedimentos:** at most 3 lines from `blockers` (both kinds count), then "E mais N." when more
  were cut. `kind: "blocked"` reads "<Task in a few words>: bloqueado (<KEY>)", is already confirmed
  and gets no question. `kind: "stuck"` reads "sem avanço desde <dd/mm> (<KEY>)" with its `updated`
  date. Ask "Algum desses é impedimento?" once, only when at least one `stuck` line is shown; it
  refers to those. With none, "Nenhum." and no question.
- The note after `---` starts with "Para você:" and holds, in this order, only what exists: the
  `moves`, as one "para aplicar /card sincronizar (N cards)" with N = the number of `moves` (the
  user types `/card`; nothing moves before); then, when `to_confirm` is not empty, "testado em
  homologação? TS-5537 (última atualização 03/11); ..." with each card's `key` and `since` as dd/mm;
  then, when step 3c found entries, one "observação: TS-5738 dia 3 de 5 (pendente), TS-5753 pode
  desligar de vez; peça /observe" (`dia` and N are the plan's `day` and `days`; `atenção em dd/mm`
  for `attention`, from `attention_days`; "pode desligar de vez" for `done`; `faltam dd/mm` from
  `missing_days`, and `desatualizado` when `stale` is not empty);
  "Tracker indisponível" when `tracker` is false; "N
  avisos, peça \"daily detalhado\"" when `warnings` is not empty (when the report was rerun without cards, the first run's error counts as one more warning). With none of them, no note and
  no `---`.
- Status names in PT-BR: `todo` "a fazer", `in_progress` "em andamento", `review` "em code review", `validation` "em
  validação", `ready_deploy` "pronto para deploy", `blocked` "bloqueado", `done` "concluída", `cancelled` "cancelada".
- `tracker` false: titles are missing, so name each task by key and the PR or commit wording, and
  write "indisponível" under **Impedimentos**.

## Rules

- Write only from the report. Do not guess a status, a date or a link between a commit and a card.
- Never call a write tool of the tracker, GitHub or git. The skill only reads.
- Ask before calling a `stuck` entry a blocker; it is only a possibility until the user says so.
  A `blocked` entry is already confirmed by its tracker status.
