+++
card = "TS-5725"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocked_by = ["TS-5731", "TS-5724"]
docs = ["12-report-migration-waves.md"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-16
+++
# 43 — Onda 2: migrar e desligar Relação de baixas (Vektor) e os envios de liquidação do Mercato Pago

## Contexto

Montar os fluxos de liquidação, rodar em paralelo, conferir e desativar as linhas do script.

Scripts:

- FIDC Vektor: relação de baixas semanal;
- Mercato Pago: valores processados e liquidações rejeitadas do dia, parcial diária de retirada de recusados, retirada semanal de recusados CITTI e NPL (BGT) e NP (Fynvest).

## A fazer antes de implementar

- Hoje as retiradas mandam um xlsx por fundo num e-mail só. Confirmar com o BGT, a Fynvest e o Mercato Pago o formato novo (um fluxo por fundo ou um arquivo com a coluna do fundo).

## Pronto quando

- Anexos e totais batem por uma semana e linhas desativadas.
