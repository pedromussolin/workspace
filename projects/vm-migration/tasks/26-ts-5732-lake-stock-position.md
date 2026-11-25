+++
card = "TS-5732"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5740", "TS-5741"]
blocked_by = ["TS-5742", "TS-5743"]
docs = ["05-lake-stock-position.md"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-27
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-25
+++
# 26 — Validar as rotas do data-lake-api contra o SQL dos scripts

## Contexto

Comparar as rotas do data-lake-api com o SQL atual dos scripts na mesma data, conferindo antes qual valor presente o cliente recebe.

Entram os quatro relatórios de estoque (estoque e projeção da VLTS I, base do FBRX3, renegociações do Equimedix), o report do OCR e a base do write-off mensal.

## Pronto quando

- Comparação bate para os quatro relatórios de estoque, o report do OCR e o write-off mensal.
