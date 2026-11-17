---
type: tool_used
tool: Bash
input_match: '"command"\s*:\s*"ws observe run TS-5(?:\s+--(?:project\s+demo|day\s+2026-11-11))*(?:\s+2>&1)?"'
---

`ws observe run` queries the replica, so the `ask` rule `Bash(ws observe run:*)` makes Claude Code
ask the user first. The box sees the command only when it starts the Bash call and nothing is
chained to it: the whole command is `ws observe run TS-5`, with at most `--project demo` or
`--day 2026-11-11` (and a `2>&1`).
