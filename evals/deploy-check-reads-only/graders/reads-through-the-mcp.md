---
type: regex
target: mock_calls
pattern: '__execute_code[^\n]*const P = \{\\"service\\": \\"demo-bff\\", \\"env_tag\\": \\"sandbox\\"[^\n]*\\"expected_version\\": \\"b2c3d4e\\"[^\n]*// ws:entry[^\n]*return await run\('
---

The BFF is read through the mocked `execute_code`, with the program `ws deploy-check script`
printed, verbatim: its parameters line (service, env, expected version) and its entry.
