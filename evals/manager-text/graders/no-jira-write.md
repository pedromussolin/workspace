---
type: regex
target: mock_calls
pattern: 'transitionJiraIssue|editJiraIssue|addCommentToJiraIssue|createJiraIssue'
match: not_contains
---

The suite mocks four Jira write tools (evals/mocks/atlassian). The skill must never call them.
