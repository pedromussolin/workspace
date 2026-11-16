---
type: tool_used
tool: Bash
input_match: '"command"\s*:\s*"ws observe request TS-5 --day 2026-11-11(?:\s+[12]?>[^"&|;]*)?"'
---

`observability.next` is `ws observe request TS-5 --day 2026-11-11`. The skill runs it as printed
(its stdout may go to a file), never a line rebuilt by hand.
