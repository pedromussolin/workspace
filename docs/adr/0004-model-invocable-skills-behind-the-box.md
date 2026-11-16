---
status: accepted
date: 2026-11-16
---

# Model-invocable skills behind the approval box

## Context and Problem Statement

The earlier rule: a skill that writes outside the repo (tracker, GMUD, GitHub) set
`disable-model-invocation: true`, so only the user could start it. `/card` was "entry by `/card`
only" from 2026-10-27, and the first ruling of the observe skill did the same. The model could not
start a card move from the daily's suggestions or a release from the conversation, even though
each write already waited for the Claude Code box (an `ask` rule or the approval gate).

## Considered Options

1. Keep `disable-model-invocation` on every skill that writes outside the repo.
2. Let the model start every skill, and keep every external write behind the approval box.

## Decision Outcome

Option 2. On 2026-11-15 the observe skill became model-invocable, with every replica query behind
the box on `ws observe run`; on 2026-11-16 `/card` and `/release` followed, and the rule became
general. The model never answers the box for the user. `disable-model-invocation` stays only for a
skill whose writes are not all behind a box; today none has it. Rules:
[skills](../conventions/skills.md), [safety](../conventions/safety.md).

## Consequences

- Good: the model can start a skill from context; the user still approves each write, with the
  real content in the box.
- Bad: the box is the only stop, so a write outside every `ask` rule and gate family would go
  through.
- Bad: the box cannot see a script file that runs `ws card apply` or `ws observe run`.
