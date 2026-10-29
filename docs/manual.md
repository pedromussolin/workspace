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
   format (TOML front matter between `+++` lines, then the body) and the user's card style are in
   [skills/card/SKILL.md](../skills/card/SKILL.md), sections "The draft" and "The user's card style". `ws card epics`
   lists the epics for a `create`.
2. `ws card check <draft>` until `ok` is true.
3. `ws card preview <draft or folder>`: nothing is sent; it prints the change and an approval code.
4. `ws card apply <same path> --approve <code>` in your terminal: it re-checks against Jira, shows
   the summary and asks `Gravar no Jira? [s/N]`. Only `s` or `sim` writes. The code lasts 30
   minutes.

A draft whose write failed or is uncertain moves to `~/.local/share/workspace/cards/uncertain/`;
check the card in Jira before trying again.

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

## Approvals the gate would show

By hand there is no gate: you are the one running the command. Before a write that leaves the
machine, read what it sends:

| Write | How to check it first |
|---|---|
| `git push` | `git log --oneline @{u}..HEAD` |
| a PR with `gh pr create` | the title and body you typed; `gh pr view --web` afterwards |
| a Jira card | `ws card preview` (above) |
| content for the personal GitHub | `ws check-secrets <file>` before you paste or push it |
