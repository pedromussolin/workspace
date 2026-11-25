+++
card = "TS-5741"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocked_by = ["TS-5732", "TS-5712", "TS-5724"]
docs = ["12-report-migration-waves.md"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-16
+++
# 45 — Onda 4: migrar e desligar os envios com regra em código e fontes externas

## Contexto

Montar os fluxos com as regras nomeadas e as fontes de fora, rodar em paralelo, conferir e desativar as linhas do script.

Scripts:

- VLTS I: projeção de valor presente e ganhos semanais (pedido de transferência);
- Equimedix (administrador Dayvale): renegociações e régua de PDD;
- Mercato Pago: write-off mensal e estornos (valores negativos) do mês;
- Padtek: boletos pagos do dia e boletos mensais;
- relação mensal de fundos ativos (CVM).

A emissão dos boletos da Padtek na GalaPay fica fora deste card: aqui entra só o envio.

## Pronto quando

- Anexos e totais batem por uma semana (nos mensais, uma execução) e linhas desativadas.
