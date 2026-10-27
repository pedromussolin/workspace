---
type: regex
pattern: '\[FRONT\]|\[API\]|mover TS-'
match: not_contains
---

With Jira down the skill has no cards: no card title (the mock titles start with [FRONT] or [API])
and no suggested move may appear.
