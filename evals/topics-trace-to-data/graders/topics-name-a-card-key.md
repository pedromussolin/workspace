---
type: llm
---

The text is a short daily standup written from made-up data. Valid Jira keys: TS-101, TS-102,
TS-103, TS-104, TS-105 and TS-106.

PASS if every bullet line under the headings Ontem, Hoje and Impedimentos ends with a valid key in
parentheses, except lines like "E mais 1 tarefa." or "E mais 2.", and, under Hoje, a line that
starts with a project name (demo-project) instead of ending with a key; and no bullet names a key
that is not valid. The question "Algum desses é impedimento?" and the note after "---" ("Para
você: ...") are not bullets and are not judged.

FAIL if some other bullet line under those headings does not end with a valid key, or some bullet
names a key that is not valid.
