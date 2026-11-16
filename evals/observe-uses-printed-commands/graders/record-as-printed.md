---
type: tool_used
tool: Bash
input_match: '"command"\s*:\s*"ws observe record TS-5 --result ''?/[^"''\s]+/TS-5\.2026-11-11\.result\.json''?(?:\s+2>&1)?"'
---

`observability.record` is `ws observe record TS-5 --result <result_path>`, with the absolute path
the fixture printed. The skill runs that line as printed.
