---
status: accepted
date: 2026-11-16
---

# Epic-to-initiative link without the premium plan

## Context and Problem Statement

An epic belongs to an initiative. Without the tracker's premium plan, an epic cannot have an
initiative as its parent, so the `parent` of an epic draft had no field to go to.

## Considered Options

1. The parent field, which needs the premium plan.
2. A link between the epic and the initiative.

## Decision Outcome

Both, chosen by a capability flag: `[tracker.jira] premium` (default `false`). With it, `parent`
sets the parent field. Without it, `parent` on an epic `edit` adds the link that
`[tracker.jira] initiative_link` names (default `relates`), shown in the preview as
`Iniciativa: TS-N (por link Relates)`; a link already there changes nothing. That edit holds
`parent` alone, and a new epic takes two steps: create it without `parent`, then edit it with
`parent`. Rules: [providers](../conventions/providers.md).

## Consequences

- Good: the same draft key works on both plans; the adapter derives the request from the flag.
- Bad: a new epic with an initiative needs two drafts, and the `parent` edit cannot carry other
  changes.
