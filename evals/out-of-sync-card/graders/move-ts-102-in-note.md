---
type: regex
pattern: 'Para você:[\s\S]*mover TS-102 para em andamento'
---

TS-102 is "To Do" in the Jira mock, but it has a commit and a branch with its key: rule R1 suggests
moving it to in progress. The short standup lists every suggested move in the "Para você:" note
after the "---", even when `--top 3` cuts the task from the topics.
