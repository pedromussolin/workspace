---
type: regex
target: mock_calls
pattern: '__execute_code[^\n]*const P = \{\\"version\\": 1, \\"task\\": \\"TS-5\\", \\"day\\": \\"2026-11-11\\", \\"counts\\": \[\{\\"check\\": \\"chamadas-rota\\"[^\n]*\\"hash\\": \\"ac1a935c81bf\\"[^\n]*\\"hash\\": \\"0cbe962dcc6c\\"[^\n]*// ws:entry[^\n]*return await run\('
---

The counts come from the mocked observability tool (`observability.tool` is `execute_code`), and
its input is the program `ws observe request` printed, verbatim: the parameters line with both
hashes, the entry marker and the call that runs it.
