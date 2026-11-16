---
type: tool_used
tool: Bash
input_match: 'ws task list --since 2026-10-23\b'
---

Reads go through `ws` first: the skill runs `ws task list` with the window's `since` (the Friday
before the fixed Monday) before any MCP call. In the sandbox it exits 2 (no API key).
