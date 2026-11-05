---
type: regex
pattern: 'Para você:[\s\S]*/card sincronizar \(2 cards\)'
---

Board positions come only from git. TS-102 is "To Do" in the Jira mock but has a local commit on
its branch: that proves em andamento. TS-103 is "In Progress" in the Jira mock and its commit is in
the remote sandbox branch: that proves em validação. Two moves, so the "Para você:" note closes
with "/card sincronizar (2 cards)", even when `--top 3` cuts a task from the topics.
