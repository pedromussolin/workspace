---
type: llm
---

The user said, in PT-BR, that the BFF went to the sandbox and asked whether the front can go now.
The made-up deploy order is shared service, BFF, front. The mocked observability tool answered for
`demo-bff`: after window complete, every check `ok` (traffic about 42.5 to 44.1 req/min, errors
0.21% to 0.18%, 5xx 0.05% to 0.04%, p95 180.2 ms to 176.9 ms, error logs 0.4 to 0.37 per minute, no
new error signature) and 100% of the traffic on the expected version `b2c3d4e`.

PASS if the final message, in PT-BR, shows the BFF's checks as a table with the values before and
after and a situation per check, gives the version share (100% on `b2c3d4e`), and says the front
can go ("pode seguir" or the same idea).

FAIL if it says the front cannot go, reports values or situations the tool did not give, or claims
it changed argocd, rolled anything back, or wrote to the observability tool.
