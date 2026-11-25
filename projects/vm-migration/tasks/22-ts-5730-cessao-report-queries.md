+++
card = "TS-5730"
type = "feature"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5731"]
blocked_by = ["TS-5726", "TS-5729"]
docs = ["04-cessao-report-queries.md"]

[tracker]
status = "in_progress"
priority = "Medium"
due = 2026-11-25
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-25
+++
# 22 — Rota de consulta de liquidação no platform-cessao

## Contexto

Consulta Liquidação por processo ou pagamento (junta parcela, contrato e lote), com janela, estado, extratos, identificador e agrupar_por.

Também atende os envios de liquidação fora das ondas iniciais:

- janela pelo mês anterior, para o fee mensal do FIDC Fornecedores;
- processos rejeitados com o motivo do último registro do log, para as retiradas de recusados do Mercato Pago (parcial diária, BGT e Fynvest semanais).

## Pronto quando

- Rota com testes cobrindo as duas granularidades e a prévia SQL.
- Janela por mês e filtro por motivo de rejeição cobertos por teste.
