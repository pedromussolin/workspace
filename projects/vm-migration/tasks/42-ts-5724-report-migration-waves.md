+++
card = "TS-5724"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5725", "TS-5740", "TS-5741"]
blocked_by = ["TS-5731", "TS-5713", "TS-5716", "TS-5721", "TS-5722", "TS-5723"]
docs = ["12-report-migration-waves.md"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-16
+++
# 42 — Onda 1: migrar e desligar os envios do FIDC Fornecedores e o aviso do Jurídico

## Contexto

Montar os fluxos, rodar em paralelo com os scripts por pelo menos uma semana, conferir anexos, totais e destinatários e desativar as linhas na mv_schedule_reports.

Scripts:

- FIDC Fornecedores: cessões diárias, cessões mensais, pendura a acrescer, vencimentos atualizados, cobrança diária (valores a pagar) e fee mensal;
- Jurídico: aviso mensal do controle processual aos escritórios (modelo fixo, cópia oculta).

## Pronto quando

- Anexos e totais batem por uma semana (no mensal, uma execução), fluxos ligados e linhas dos scripts desativadas.
