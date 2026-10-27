---
type: regex
pattern: '\[FRONT\]|\[API\]|Sugestão'
match: not_contains
---

With Jira down the skill has no cards: no card title (the mock titles start with [FRONT] or [API])
and no status suggestion may appear.
