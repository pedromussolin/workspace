---
type: llm
---

The text is a daily standup written from made-up data. Valid Jira keys: TS-101, TS-102, TS-103,
TS-104, TS-105 and TS-106.

PASS if every bullet line under the headings Ontem, Hoje and Impedimentos names a valid key, except
two kinds of line that may have no key: a summary line like "2 commits sem card em demo-notes", and
under Hoje a line that starts with a project name (demo-project), and no bullet names a key that is
not valid.

FAIL if some other bullet line under those headings has no valid key, or some bullet names a key
that is not valid.
