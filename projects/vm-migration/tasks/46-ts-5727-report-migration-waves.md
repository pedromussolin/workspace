+++
card = "TS-5727"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocked_by = ["TS-5712"]
docs = ["12-report-migration-waves.md"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-16
+++
# 46 — Migrar e desligar Valor conciliado e Resultado do processamento (Mercato Pago)

## Contexto

Os dois envios usam o esperado do dia, que hoje vem da planilha analítica gravada na pasta local da VM. O esperado passa a ser calculado direto dos File 4 no SFTP do Mercato Pago, por regra nomeada (TS-5712), sem depender da planilha. Depois, montar os fluxos, rodar em paralelo e desligar.

## Pronto quando

- Esperado calculado bate com a planilha analítica por uma semana.
- Anexos e totais batem e linhas desativadas.
