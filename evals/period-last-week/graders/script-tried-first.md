---
type: tool_used
tool: Bash
input_match: 'ws task list --since 2026-10-19\b'
---

Reads go through `ws` first: the skill runs `ws task list` with the period's `since` (Monday
19/10, from `ws standup period`) before any MCP call. In the sandbox it exits 2 (no API key).
