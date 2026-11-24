# Manual mode

Every flow of this repo without any AI: the `ws` commands do the deterministic part, and you write
the prose. A new flow is done only when it has its section here
([approval gates design](specs/2026-10-28-approval-gates-design.md), "Manual mode is a
requirement").

## Once

1. `ws setup --check` and fix what it lists (`ws setup` without `--check` fixes the local part).
2. Jira API key: create it on the Atlassian site, then `ws config token jira` in your terminal.

## Daily standup

```
mkdir -p ~/.local/share/workspace/standup && cd ~/.local/share/workspace/standup
ws standup collect > activity.json
ws task list --since <window.since from activity.json> > cards.json
ws standup report --activity activity.json --cards cards.json --top 3
ws task status --cards cards.json --activity activity.json
```

The report groups the activity by card: `yesterday`, `today`, `blockers` and `moves` (cards whose
status looks behind). Write the standup from it, one line per task, the card key at the end. Without
`--top 3` you get the detailed version.

## Jira card

1. Write a draft in `~/.local/share/workspace/cards/drafts/<name>.md`, one operation per file. The
   format (TOML front matter between `+++` lines, then the body) and the card policy are in
   [skills/card/SKILL.md](../skills/card/SKILL.md), sections "The draft" and "The card policy".
   `ws card policy` prints the rules a card must follow (title, sections, required fields,
   categories); `ws card epics` lists the epics for a `create`. The draft keys for the categories
   and the original estimate are `labels` and `estimate` on a create, `add_labels`,
   `remove_labels` and `estimate` on an edit, and `causes` and `caused_by` on a link.
2. `ws card check <draft>` until `ok` is true.
3. `ws card preview <draft or folder>`: nothing is sent; it prints the change and an approval code.
4. `ws card apply <same path> --approve <code>` in your terminal: it re-checks against Jira, shows
   the summary and asks `Gravar no Jira? [s/N]`. Only `s` or `sim` writes. The code lasts 30
   minutes.

A draft whose write failed or is uncertain moves to `~/.local/share/workspace/cards/uncertain/`;
check the card in Jira before trying again.

## Time spent on a card

Real hours, from evidence only, never from a plan
([design](specs/2026-11-24-time-tracking-design.md)).

1. Mark the work as it happens: `ws time start TS-123` when a card begins, `ws time stop` when you
   stop or switch (`ws time stop TS-123` closes one card). `--at HH:MM` marks today at that local
   time, never in the future. Several cards may be open; `ws time status` prints the open ones and
   today's minutes per card. The session hook also records activity on a card branch, which covers
   what you forget to mark. All of it lives in `~/.local/share/workspace/timelog/<YYYY-MM>.jsonl`
   (private, append-only).
2. Look at a period: `ws time report --week 2026-W48` (or `--from DATE --to DATE`). Per day and
   card it gives the minutes by source (`marked`, `hook`, `commits`, `filled`), what the tracker
   already holds (`logged_minutes`) and what is left to log (`to_log_minutes`). A working day
   closes at the floor (`[time] day_floor`) among the planned cards, by their share of the day's
   commits; an intruder card counts apart. `below_floor` and `no_evidence_minutes` are the hours
   the evidence did not explain: mark them, or tell the model what was done. Today is never filled
   before it is over.
3. When a card is done: `ws time report --card TS-123 --drafts
   ~/.local/share/workspace/cards/drafts/time-ts-123` writes one `worklog` draft per day with
   hours to log (`TS-123-worklog-<day>.md`). A card with an unplanned label, or any card with
   `--unplanned` (no plan came before the work), also gets `TS-123-estimate.md`: its original
   estimate is its real time, with no padding. The folder must be new or empty.
4. Steps 2 to 4 of "Jira card" on that folder: `ws card preview`, then `ws card apply` in your
   terminal. Hours already logged are subtracted, so a second run never logs the same hours twice.

## End of an iteration (checkpoint)

1. Update `projects/<slug>/CONTINUE.md` (`## Onde parei`, `## Próximo passo`), `decisions.md` and
   the task files.
2. `ws checkpoint check <slug>` until it passes.
3. `ws checkpoint diff <slug>` to see what goes in.
4. `ws checkpoint commit <slug> -m "docs: <what changed>"`: commits that folder only, pulls and
   pushes.

## Names and masking

The git hooks run `ws check-secrets` and the new-word check by themselves.

- A blocked commit or push: fix the text, or `ws mask --in-place FILE` to swap real names for
  their analogs.
- New words: `ws names review` asks about each one in the terminal (real name, harmless term,
  skip); `ws names pending` only lists them.

## Classify an MCP server

An MCP server the gate does not know asks before every call, reads included. `ws setup` says
which configured servers are missing (`MCP servers the approval gate does not know: ...`).

1. `ws gate catalog` lists those servers and the tools the gate already asked about, with counts.
   A server's tools show up there after its first calls; until then, read its tool list in Claude
   Code (`/mcp`).
2. Reads and changes that stay on the machine: `ws gate catalog pass SERVER TOOL...`. Writes:
   `ws gate catalog ask SERVER TOOL...`. When unsure, `ask`.
3. Commit `hooks/gate/catalog.json`, then run `ws setup` in your terminal: it updates the
   protected copy the gate reads.

## Approvals the gate would show

By hand there is no gate: you are the one running the command. Before a write that leaves the
machine, read what it sends:

| Write | How to check it first |
|---|---|
| `git push` | `git log --oneline @{u}..HEAD` |
| a PR with `gh pr create` | the title and body you typed; `gh pr view --web` afterwards |
| a Jira card | `ws card preview` (above) |
| content for the personal GitHub | `ws check-secrets <file>` before you paste or push it |
