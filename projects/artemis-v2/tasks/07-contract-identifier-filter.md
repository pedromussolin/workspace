+++
card = "TS-5736"
type = "improvement"
epic = "TS-5278"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-24
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-23
+++
# 07 — Filtro por identificador de contrato

- **Status:** mapeado, aguardando D5.
- **Repos:** platform-cessao, BFF, front.
- **Decisão:** [D5](../decisions.md) — igualdade, prefixo ou "contém".

## Como está hoje

- **Listagem de lotes (fake e real): não existe.** Nem a cessão
  (`GET /lotes/reais` e `/lotes/fake`) nem o BFF (`viewer.py:221-236`,
  `371-395`) aceitam o filtro.
- **Dentro de um lote fake aberto:** existe como filtro da coluna
  "Identificador" (`close-batches/payments-table/payments-table.ts:72-116`).
  O BFF manda `identificador` e a cessão faz `ilike '%x%'` em
  `contrato_processo.identificador` (`repository.py:1088`).
- **Dentro de um lote real aberto:** a cessão aceita, mas o front deixa a
  coluna como não filtrável (`manual-reconciliation/payments-table/payments-table.ts:138`).

## Proposta

1. Cessão: parâmetro `identificador` em `/lotes/reais` e `/lotes/fake`, como
   `EXISTS` de pagamento → parcela → contrato → `contrato_processo.identificador`.
2. BFF: aceitar e repassar nas duas listagens.
3. Front: campo no toolbar de filtros (`batches-filters-toolbar`).
4. Habilitar o filtro da coluna também no lote real.

## Pontos para estressar

- **Índice:** `contrato_processo.identificador` tem índice btree; ele serve
  para igualdade e prefixo (`LIKE 'x%'`), **não** para `ilike '%x%'`. Nas
  listagens, que já são lentas, "contém" pode piorar muito.
- **Qual identificador a operação procura?** Há outros candidatos:
  `contrato.num_controle` (indexado), `contrato_parcela.num_controle` ("seu
  número") e `contrato_extensao.num_controle_externo`.
- Para lote real, o filtro precisa olhar só pagamentos daquele lote;
  rejeitados não têm pagamento (só `data_raw`).
- Combinar com a data obrigatória da listagem ou permitir busca sem data?

## Validação

- Teste de repositório: filtro encontra o lote que contém o contrato e não
  traz os outros.
- `EXPLAIN` mostrando uso do índice.
