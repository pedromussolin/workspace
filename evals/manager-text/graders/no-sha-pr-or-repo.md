---
type: regex
pattern: '\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}\b|#\d+|demo-(?:api|front|notes)'
match: not_contains
---

The manager text has no sha, no pull request number and no repository name.
