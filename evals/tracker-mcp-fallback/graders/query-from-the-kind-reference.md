---
type: regex
target: mock_calls
pattern: 'searchJiraIssuesUsingJql[^\n]*assignee = currentUser\(\) AND \(statusCategory != Done OR updated >= \\?"2026-10-23\\?"\)'
---

The query is written only in references/jira.md, the reference that `[tracker] kind = "jira"`
selects. Finding it in the mocked call, with the window's `since`, shows the fallback read the kind
and followed its reference.
