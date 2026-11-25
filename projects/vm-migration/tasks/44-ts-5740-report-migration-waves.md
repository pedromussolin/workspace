+++
card = "TS-5740"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocked_by = ["TS-5732", "TS-5724"]
docs = ["12-report-migration-waves.md"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-25
+++
# 44 — Onda 3: migrar e desligar Estoque (VLTS I), Base de operações e estoque (FBRX3) e report do OCR

## Contexto

Montar os fluxos de estoque e o do report do OCR, rodar em paralelo, conferir e desativar as linhas do script.

Scripts: estoque diário da VLTS I, base de operações e estoque do FBRX3 e report de processamento do OCR.

## A fazer antes de implementar

- Decidir com a área se o defeito conhecido do relatório do FBRX3 (valor presente, provisão e valor pago inflados pelo join entre contrato e parcela) é corrigido antes da migração ou migra igual.

## Pronto quando

- Anexos e totais batem por uma semana e linhas desativadas.
