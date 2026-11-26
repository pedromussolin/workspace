# Listagem de lotes fake na réplica: o peso é a soma dos lotes abertos (26/11/2026)

**Conclusão:** a listagem de lotes fake (L2) passa de 120 s por causa da soma dos lotes abertos, e
não do tamanho das tabelas de pagamento ou de remessa. Para descartar contrato apagado, a soma junta
cada pagamento dos lotes abertos com parcela, contrato e processo do contrato. No maior lote aberto
(73.559 pagamentos) isso levou 50 s com o cache frio; a mesma contagem só pelo índice do lote levou
0,14 s. A busca da remessa pelo número custa 0,01 ms por linha.

## Medição

- **Fonte:** réplica de leitura de produção, `EXPLAIN (ANALYZE, BUFFERS)` e contagens, em 26/11/2026
  de manhã; sessão só leitura, `statement_timeout` de 60 a 120 s, uma consulta por vez.
- **SQL:** escrito à mão a partir de `RefactLiquidacaoRepository.listar_lotes_fake`
  (`cessao/api/liquidacao/refact.py:953`, cessão `origin/master` c6f88ce39), em
  [fake-listing-open-batches-2026-11-26.sql](../attachments/sql/fake-listing-open-batches-2026-11-26.sql).
- **Cenário:** dia 25/11/2026, todos os fundos, sem produto nem status, página 1 de 10, ordem padrão.

| O que | Resultado |
|---|---|
| A listagem inteira | cancelada no limite de 120 s |
| Avulsos do dia (pagamento sem lote, remessa, cadastro) | 67 ms, 9 pagamentos; a remessa sai pelo índice `(uuid, data_criacao)`, 0,010 ms por busca, tudo em cache |
| Lotes abertos (vigente com `fechado = false` e lote `pendente`) | 27.763: 243 de 24 a 26/11/2026, 27.455 de 12 a 29/06/2026 e 65 de 06/2024 a 04/2026 |
| Pagamentos nesses lotes | recentes: 249.196, o maior com 73.559, nenhum vazio; junho: amostra de 300, todos vazios; antigos: 92 ao todo, 61 lotes vazios |
| Soma do maior lote aberto com o filtro de contrato apagado | 50,0 s; 123.759 páginas lidas do disco, 97 s de I/O somando os processos paralelos: parcela 28,7 s, contrato 29,7 s, processo do contrato 38,7 s |
| Contagem do mesmo lote só pelo índice do lote | 0,14 s, tudo em cache |

O plano da listagem inteira (sem executar) estima a parte dos lotes abertos em bilhões de unidades
de custo e a dos avulsos em cerca de 1.500.

## Índices de produção que os modelos não mostram [C]

- `liquidacao_pagamento`: `(data_criacao)` e `(data_criacao) WHERE liquidacao_lote_id IS NULL`.
- `contrato`: `(data_criacao)`.
- `liquidacao_processo`: `(uuid, data_criacao)` e `(uuid, produto_id, estado_atual) INCLUDE (proc_id)`.

O índice parcial do pagamento sem lote leu 270 mil páginas, todas em cache, para achar 9 linhas.
**[H]** são entradas de pagamentos que já ganharam lote, ainda não limpas; a DBA confirma.

## Tamanho (catálogo, 26/11/2026)

| Tabela | Dados | Índices | Linhas (estimativa) |
|---|---|---|---|
| `liquidacao_pagamento` | 134 GB | 216 GB | 780 milhões |
| `liquidacao_processo` | 120 GB | 315 GB | 832 milhões |
| `contrato_parcela` | 123 GB | 160 GB | 835 milhões |
| `contrato` | 83 GB | 73 GB | 337 milhões |
| `contrato_processo` | 40 GB | 138 GB | 341 milhões |

`shared_buffers`, a memória de páginas do Postgres: 41,5 GB.

## Para repetir

Rodar as consultas do anexo uma por vez na réplica, na ordem. A 4 mostra o custo com o cache frio
na primeira execução; repetir para ver com o cache quente.
