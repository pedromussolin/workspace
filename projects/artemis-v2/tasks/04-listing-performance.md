+++
card = "TS-5733"
type = "improvement"
epic = "TS-5278"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
+++
# 04 — Performance das listagens de lotes

- **Status:** mapeado; a revisão de queries é com a DBA.
- **14/10/2026:** a parte de lotes reais (`lotes_das_remessas` e o filtro de
  fundo da página) saiu daqui para a
  [tarefa 12](12-real-batches-before-values.md), que passou na
  frente. Aqui ficam lotes fake, `pagamentos/query` e métricas.
- **Repos:** platform-cessao (e front, se mudar quando os lotes irmãos são
  carregados).

## Item original

> Buscar lotes reais de liquidação antes de buscar seus valores

**Esse item já está em produção.** A TS-5184 (`006577623`, 10/09/2026)
reescreveu `RepositoryLiquidacao.get_lotes`
(`cessao/api/liquidacao/repository.py:622-774`):

1. CTE `pagina`: filtra os lotes, ordena, aplica LIMIT/OFFSET e conta o total
   com `count(*) OVER ()`.
2. `LEFT JOIN LATERAL valores`: soma valores e proc_ids **só dos lotes da
   página**.

O gargalo mudou de lugar.

## Onde está o gargalo agora

### Lotes reais — `lotes_das_remessas` (movido para a tarefa 12)

- Chamada por `ServiceLiquidacao._lotes_por_remessa`
  (`cessao/api/liquidacao/service.py:1338-1353`) para montar
  `lotes_da_remessa` de cada linha (TS-5211).
- A consulta (`repository.py:819-848`) busca `DISTINCT (proc_id, lote_id)` de
  **todos os pagamentos de todas as remessas da página**, no fundo filtrado.
- O filtro de soft delete acrescenta dois `NOT EXISTS` correlacionados
  (`cessao/database/listeners.py:779`).
- Evidência: num trace de 575 s, 565 s foram nela; 25 h de banco em 7 dias,
  p95 de 12,3 min ([baseline](../evidence/baseline-datadog-2026-10-05.md)).
- Efeito: 18% das cargas da aba de lotes reais terminam em 504.

### Lotes fake — `get_lotes_fake`

- `repository.py:850-993`: CTE de pagamentos sem lote (janela de data ± 2 h),
  join com processo, parcela, contrato e `produto_config`, `GROUP BY` por uma
  chave textual (`CASE`) que nenhum índice atende, `array_agg(DISTINCT)`,
  `count(DISTINCT)` e contagem por janela.
- p95 de 94 s na cessão; 8% de falhas no BFF.

### Pagamentos de um lote — `pagamentos/query`

- Join de 7 tabelas, subquery correlacionada de `Acesso` por linha, `count()`
  sobre o join inteiro e duas agregações de métricas a cada página.
- Para lote real, o BFF manda todos os proc_ids **e** o `lote_id`; a métrica
  varre todas as remessas e só depois o Python recorta o lote pedido
  (`repository.py:1245-1389`, `1527-1544`).

## Propostas para estressar com a DBA

1. **Lotes irmãos sob demanda.** Tirar `lotes_da_remessa` da listagem e
   carregar só quando a linha for aberta — o `pagamentos/query` já devolve
   `lotes_da_remessa` nas métricas (TS-5211). Precisa mudar o front, que usa o
   tamanho dessa lista para decidir se lote e remessa são a mesma coisa.
2. **Se precisar manter na listagem:** partir dos lotes da página
   (`liquidacao_lote_id IN (...)`) para achar os proc_ids, e só então os
   irmãos, com índice que atenda `(proc_id)` → pagamentos.
3. **Soft delete:** avaliar se os `NOT EXISTS` do filtro global são
   necessários nessas consultas de leitura (o filtro está em
   `ContratoSoftDeleteListener.filtrar_processos_deletados`) ou se há forma
   mais barata (coluna desnormalizada, índice parcial).
4. **Métricas do lote real:** quando houver `lote_id`, filtrar por ele no SQL.
5. **`statement_timeout`** na réplica (tarefa 01), para a cessão parar quando
   o BFF já desistiu.

## Validação

- Comparar p95 e taxa de 504 das rotas `real-batches`, `fake-batches` e
  `payments` com o [baseline](../evidence/baseline-datadog-2026-10-05.md).
- `EXPLAIN (ANALYZE, BUFFERS)` antes e depois para cada consulta alterada,
  anexado aqui.
