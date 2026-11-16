---
status: accepted
date: 2026-11-16
---

# Architecture decision records

## Context and Problem Statement

Decisions were written per feature, in `docs/plans/*-rulings.md` (release, card review, card
start, observe, tracker write port), mixed with follow-ups and execution notes. The rules that
crossed features (provider-agnostic ports, the approval box, script first) lived as prose in the
root `CLAUDE.md`. People, Claude, its subagents and other AI tools kept re-explaining the same
decisions, and the reason behind a rule was hard to find.

## Decision Outcome

Each architecture decision gets a record in `docs/adr/`, named by a four-digit number in order
and a short title, in the common Markdown format for decision records: front matter with `status`
and `date`, then the sections of [the index](README.md). `docs/adr/README.md` is the index. A
record that a later one replaces keeps its file, and its status names the new record.

The normative rule goes to `docs/conventions/`; the record keeps the why. The older
`docs/plans/*-rulings.md` files stay as history, and the index links them.

## Consequences

- Good: one place for the why of each rule; a convention links to its record.
- Good: any AI tool finds the decisions from `AGENTS.md`, without the chat that made them.
- Bad: one more file per decision, kept short to stay read.
- Bad: the decisions inside the older rulings files are not migrated; they stay where they are.
