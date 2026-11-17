---
status: accepted
date: 2026-10-27
---

# Tracker writes limited to the user's cards

## Context and Problem Statement

`/card` writes to the team's tracker: it creates cards, moves them, comments, logs work and links
them. A wrong key in a draft could change a card that belongs to someone else.

## Decision Outcome

The tracker writes only cards where the user is the assignee or the reporter. The October design
said "only the user's own cards: never another developer's card, never a card without an
assignee", enforced in code. On 2026-11-16 the user confirmed it as "the assignee or the
reporter", also for sprint and due-date changes. Rules: [safety](../conventions/safety.md).

## Consequences

- Good: a mistake can only reach the user's own cards; the check refuses the rest before the
  preview.
- Bad: a colleague's card is changed by hand in the tracker.
