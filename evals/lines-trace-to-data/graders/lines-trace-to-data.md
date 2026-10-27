---
type: llm
---

The text is a daily standup written from made-up data. Valid identifiers: the commit shas 6d10843,
dc457ab and 5e485af (in full or as their first 7 characters), the pull request demo-api#42, and the
Jira keys TS-100 to TS-106 and TS-200.

PASS if every bullet line under the headings Ontem and Status contains at least one valid
identifier and no identifier that is not valid.

FAIL if some bullet line under Ontem or Status contains no valid identifier, or contains an
identifier that is not valid.
