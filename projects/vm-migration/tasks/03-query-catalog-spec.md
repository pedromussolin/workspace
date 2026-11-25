+++
card = "TS-5726"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5729", "TS-5730", "TS-5742", "TS-5707", "TS-5708"]
blocked_by = ["TS-5717"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-18
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 03 — Especificação do catálogo de consultas

## Contexto

Contrato de cada consulta que a tela Envio de Relatórios oferece: filtros, colunas, paginação, prévia SQL e tipos de campo do formulário. Cobre os 25 scripts de envio de relatórios da VM, não só as quatro ondas iniciais.

Consultas e filtros:

- Contratos (platform-cessao): cessões diárias e mensais, pendura e vencimentos; mais o filtro por vencimento da parcela, para a cobrança diária do FIDC Fornecedores.
- Liquidação (platform-cessao), por processo ou pagamento: relação de baixas, valores processados e rejeitados; mais a janela por mês (fee mensal do FIDC Fornecedores) e os rejeitados com o motivo do log (retiradas parcial, BGT e Fynvest do Mercato Pago).
- Posição de ativos (data-lake-api): estoques, projeção de valor presente, renegociações e a base do write-off mensal.
- Consulta do OCR (data-lake-api): report de processamento de CCBs e invoices.
- GalaPay: transações pagas e cobranças do vencimento, com os PDFs dos boletos (Padtek).
- Cadastro de fundos da CVM: download público do arquivo.
- Regras nomeadas em código que aparecem no catálogo (TS-5712).

## Pronto quando

- Contrato revisado por quem mantém platform-cessao e data-lake-api.
- Cada um dos 25 scripts tem a consulta ou a regra que o substitui indicada no contrato.
