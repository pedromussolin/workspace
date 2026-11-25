# Latência das quatro listagens e volume das tabelas (25/11/2026)

**Conclusão:** três das quatro listagens passam de 5 s com frequência em produção, e as tabelas que
elas varrem têm centenas de GB e crescem cerca de 18 milhões de pagamentos por mês. Os últimos 6
meses são cerca de 1/7 das linhas. Base do item 8.8 do
[desenho](../tasks/04-hot-data-and-config-cache-design.md).

## Latência, 7 dias até 25/11/2026 (Datadog APM, spans indexados, `env:production`)

| Listagem | Rota na cessão | Spans | p95 | p99 | Máximo | Spans acima de 5 s |
|---|---|---|---|---|---|---|
| L1 lotes reais | `GET /liquidacao/lotes/reais` | 695 | 19,1 s | 120 s | 152,6 s | 75 |
| L2 lotes fake | `GET /liquidacao/fake-batches` | 611 | 43,3 s | 165,3 s | 359,8 s | 98 |
| L3 pagamentos de um lote | `GET /liquidacao/pagamentos/query` | 154 | 1,6 s | 4,5 s | um caso isolado muito acima | 2 |
| L4 lotes de cessão | `GET /cessao/query` | 27 | 21,5 s | 22,4 s | 24,9 s | 9 |

- No BFF, `GET /operations/liquidation/fake-batches` chega ao máximo de 120 s, o limite do BFF.
- Spans indexados guardam mais as requisições lentas que as rápidas: os percentis saem puxados para
  cima, e a contagem acima de 5 s é um piso.
- **Para repetir:** `v2.SpansApi.aggregateSpans` com `resource_name:*<rota>* env:production`, 7 dias,
  `pc95`/`pc99`/`max` sobre `@duration` (nanossegundos), agrupado por `service` e `resource_name`; a
  contagem acima de 5 s com `@duration:>5000000000`.

## Volume (Datadog, métricas da integração do Postgres)

| Tabela | Linhas hoje (`postgresql.live_rows`) | Linhas há 6 meses | Crescimento em 6 meses | Tamanho hoje (`postgresql.total_size`) |
|---|---|---|---|---|
| `liquidacao_pagamento` | 786 milhões | 679 milhões | +108 milhões (~14% do total) | 376 GB |
| `liquidacao_processo` | 833 milhões | 708 milhões | +125 milhões (~15%) | 466 GB |
| `contrato_parcela` | 850 milhões | 666 milhões | +184 milhões (~22%) | 304 GB |
| `contrato_processo` | 342 milhões | 283 milhões | +59 milhões (~17%) | 191 GB |
| `contrato` | 342 milhões | 282 milhões | +60 milhões (~18%) | 168 GB |
| `liquidacao_lote_processo` | 1,6 milhão | 1,6 milhão | +36 mil | 0,4 GB |

- O valor de 12 meses atrás veio na casa das centenas de milhares para todas as tabelas: a coleta
  dessas métricas provavelmente começou depois. Não serve para medir o crescimento de um ano.
- **Para repetir:** `v2.MetricsApi.queryScalarData`, `max:postgresql.live_rows{table:<tabela>} by
  {table}` e `max:postgresql.total_size{...}`, agregador `last`, num dia de hoje e num dia de 182
  dias atrás.
