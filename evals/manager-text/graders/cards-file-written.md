---
type: tool_used
tool: Write
input_match: 'workspace/standup/cards\.json[\s\S]*platform[\s\S]{0,8}jira[\s\S]*TS-104'
---

The fetched cards go to the standup folder's cards.json with the Write tool, as
`{"platform": "jira", "cards": [...]}`, every card included.
