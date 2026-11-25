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
due = 2026-11-18
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 27 — Shared: conexão do tipo API para os microsserviços, a GalaPay e a CVM

## Contexto

Tipo de conexão API na tela Envio de Relatórios. Para o platform-cessao e o data-lake-api, usa os clientes HTTP que o shared já tem (src/services/cessao e src/services/data_lake), sem cliente novo.

A mesma conexão passa a cobrir as fontes de fora que os scripts de envio usam:

- GalaPay, com as credenciais por produto: transações pagas e cobranças do vencimento, com os PDFs dos boletos (boletos pagos e boletos mensais da Padtek);
- download público do cadastro de fundos da CVM (relação de fundos ativos).

Timeout, retry em 5xx, paginação, só endpoints do catálogo, e testar conexão.

## Pronto quando

- Conexões do platform-cessao, do data-lake-api, da GalaPay e da CVM criadas e testadas, com testes.
