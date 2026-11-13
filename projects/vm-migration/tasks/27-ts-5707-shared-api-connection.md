+++
card = "TS-5707"
type = "feature"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5708", "TS-5710", "TS-5711", "TS-5718", "TS-5722"]
blocked_by = ["TS-5717", "TS-5726"]
docs = ["06-shared-api-connection.md"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-13
+++
# 27 — Shared: conexão do tipo API e cliente HTTP dos microsserviços

## Contexto

Tipo de conexão API (migration, prefixo de segredo), cliente HTTP com timeout, retry em 5xx e paginação, só endpoints do catálogo, e testar conexão pelo health.

## Pronto quando

Conexão API criada e testada contra o health de um serviço, com testes.

