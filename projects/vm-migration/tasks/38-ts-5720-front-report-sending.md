+++
card = "TS-5720"
type = "feature"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5721"]
blocked_by = ["TS-5718"]
docs = ["11-front-report-sending.md"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-25
+++
# 38 — Front: Origem com consulta, filtros e prévias

## Contexto

Painel da Origem com API montado a partir do catálogo, limpeza ao trocar o tipo da conexão e prévias de linhas, contagem e SQL recolhível.

A Origem também aceita arquivo de entrada (SFTP ou download) seguido de uma regra nomeada do catálogo (TS-5712).

## Pronto quando

- Painel monta filtros do catálogo e mostra as duas prévias.
- Origem com arquivo e regra nomeada configurável pela tela, com prévia.
