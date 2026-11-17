---
status: accepted
date: 2026-11-16
---

# Epics and initiatives outside sprints, with due dates

## Context and Problem Statement

A card fits one sprint: at most about five working days with AI, with one checkable "Pronto
quando". An epic or an initiative spans many cards and sprints, and `/card` can now move cards
between sprints and to the backlog.

## Decision Outcome

An epic or an initiative stays out of sprints: only its cards go into one. It keeps its due date.
An edit with `"backlog"` takes it out of a sprint. The rule is enforced in code. Rules:
[card rules](../../skills/card/references/card-rules.md), section "Sprint and due date".

## Consequences

- Good: a sprint holds only work that fits it.
- Good: the due date still says when the epic or the initiative should be done.
- Bad: an epic or an initiative already in a sprint needs a `"backlog"` edit to leave it.
