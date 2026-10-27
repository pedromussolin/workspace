---
type: regex
pattern: '\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}\b|#\d+|demo-(?:api|front|notes)'
match: not_contains
---

The short standup has no sha, no pull request number and no repository name: the work is told
in plain words, one line per task.
