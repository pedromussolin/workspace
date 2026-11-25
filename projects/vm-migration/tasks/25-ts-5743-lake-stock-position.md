+++
card = "TS-5743"
type = "improvement"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5732"]
blocked_by = ["TS-5742"]
docs = ["05-lake-stock-position.md"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-25
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 25 — Posição de ativos e consulta do OCR no data-lake-api: ramos Dayvale e FBRX3

## Contexto

Ramo do administrador Dayvale e do FBRX3 na posição de ativos (ramo da rota ou consulta dedicada, a definir na especificação).

Consulta nova do OCR para o report de processamento: CCBs e invoices processados no dia útil anterior, com o acumulado do mês e dos últimos 12 dias, lidos do espelho do OCR no Lake. Substitui o SQL do script de report do OCR.

## Pronto quando

- Ramos Dayvale e FBRX3 com testes e SQL em src/infra/redshift/queries.
- Consulta do OCR com testes e SQL em src/infra/redshift/queries.
