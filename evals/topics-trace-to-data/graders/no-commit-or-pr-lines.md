---
type: regex
pattern: '^\s*[-*]\s*`?(?:[0-9a-f]{7,40}|[\w.-]+#\d+)\b'
flags: m
match: not_contains
---

No bullet starts with a commit sha or a `repo#PR` reference: commits and pull requests are not
listed one by one. A topic line may cite a PR inside its text.
