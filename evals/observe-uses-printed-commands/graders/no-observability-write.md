---
type: regex
target: mock_calls
pattern: 'execute_code_write|create_datadog_notebook|edit_datadog_notebook|delete_datadog_notebook|upsert_datadog_dashboard'
match: not_contains
---

The suite mocks the write tools of the observability server (evals/mocks/datadog). The skill only
reads and must never call them.
