---
type: tool_used
tool: Bash
input_match: '"command"\s*:\s*"[^"]*(?:ws observe run[^"]*(?:&&|\|\||;|\|)|(?:&&|\|\||;|\|)\s*ws observe run)'
min: 0
max: 0
---

No `ws observe run` inside a chain (`&&`, `||`, `;` or a pipe): a chained run hides it from the
approval box.
