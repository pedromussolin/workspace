# Baseline de produção — 05/10/2026

Números do Datadog APM antes de qualquer mudança da V2. Toda tarefa que
promete ganho de performance deve ser medida de novo com as mesmas consultas
e comparada com esta página.

- Ambiente: `env:production` (asgard).
- Janelas: últimos 7 dias, salvo quando indicado 30 dias.
- Durações do Datadog vêm em nanossegundos; aqui estão convertidas.

## Como a tela chega até o banco

```
front (/liquidation-batches)
  └─ BFF apl-credit-whitelabel-api (FastAPI, limite de 120 s para a cessão)
       └─ platform-cessao (uwsgi: 4 processos × 1 thread por pod, 18 pods)
            └─ Postgres asgard-postgres-production-cessao (banco platform-cessao)
```

Quando o BFF desiste (504), a cessão **continua** a requisição até o fim,
ocupando um dos 4 processos do pod e uma conexão do banco.

## Experiência do usuário (BFF, 7 dias)

| Rota do BFF | Sucesso | Falhas | p50 | p95 |
|---|---|---|---|---|
| `GET /operations/liquidation/real-batches` | 491 | **110 × 504 (18%)** | 1,2 s | 47,8 s |
| `GET /operations/liquidation/fake-batches` | 599 | **50 × 504 + 3 × 502 (8%)** | 1,1 s | 51,8 s |
| `GET /operations/liquidation/payments` | 270 | 4 × 504 | 0,6 s | 18,3 s |
| `GET /operations/liquidation/real-batches/balance` | 229 | — | 1,0 s | 2,0 s |
| `POST /operations/liquidation/fake-batches/consolidate` | 179 × 202 | 29 × 429, 4 × 400 | 5,0 s | 5,0 s |

O 202 em exatos 5 s é proposital: o BFF espera no máximo 5 s por um erro e
devolve 202 (`ESPERA_DE_ERRO`, `business.py:361`).

## Cessão (7 dias)

| Rota | Chamadas | p50 | p75 | p95 | Máximo |
|---|---|---|---|---|---|
| `GET /liquidacao/lotes/reais` | 872 | 0,8 s | 8,2 s | **12,6 min** | **2h12** |
| `GET /liquidacao/lotes/fake` | 1.130 | 0,8 s | 4,3 s | 94 s | 41 min |
| `GET /liquidacao/pagamentos/query` | 400 | 0,3 s | 0,7 s | 17 s | 4 min |
| `GET /liquidacao/` (legado) | 206 | 7,9 s | 13,8 s | 98 s | 16 min |
| `GET /cessao/` | 167 | 61 s | 8,3 min | 33 min | 62 min |

### `POST /liquidacao/` (fechar lote), 30 dias

| Status | Chamadas | p50 | p95 | Máximo |
|---|---|---|---|---|
| 200 | 616 | 17 s | 7,2 min | 19 min |
| 400 | 3.231 | 1,9 s | 4,7 s | — |
| 429 | 60 | 8 ms | 12 ms | — |
| 500 | 30 | 14 min | 59 min | 1h42 |

## Um trace típico da aba de lotes reais

Trace `6ac3b76400000000872e3f22990ee83f` (05/10, 14:42):

| Trecho | Tempo |
|---|---|
| BFF (`http.request` para a cessão) | 120 s → 504 |
| Cessão, requisição inteira | 575 s |
| Consulta da página (CTE `pagina` + LATERAL dos valores) | 9,4 s |
| `lotes_das_remessas` (lotes irmãos da remessa) | **565 s**, 2.445 linhas |

## Consultas que mais somam tempo de banco (7 dias)

| `resource_hash` | Consulta | De onde vem | Execuções | Tempo total | p95 |
|---|---|---|---|---|---|
| `23ea4ea711b38532` | `SELECT estado_atual, originador_id ... WHERE proc_id = ? GROUP BY ...` | `_processos_agrupados_por_proc_id` (fechamento automático, a cada pagamento) | 12.724 | **88 h** | 2,8 min |
| `8579040160ac6c61` | `INSERT INTO liquidacao_processo` | entrada de pagamentos | 174.106 | 55 h (1,1 s por insert) | 0,4 s |
| `3afbd330f1bd4d7f` | `SELECT DISTINCT proc_id, liquidacao_lote_id ...` | `lotes_das_remessas` (`GET /lotes/reais`) | 429 | 25 h | 12,3 min |
| `e0b37d0a5f2865d4` | agregado de contratos sem lote | `GET /cessao/` | 255 | 10 h | 19 min |
| `af6c090c7fa63323` | `SELECT liquidacao_pagamento.id ... WHERE liquidacao_lote_id IS NULL ...` | `create_by_originador` (`POST /liquidacao/`) | 4.232 | 11 h | 16 s |

Os `NOT EXISTS (... data_delete IS NOT NULL)` que aparecem nessas consultas são
injetados pelo filtro global de soft delete (`cessao/database/listeners.py:779`).

## Logs relevantes (30 dias)

| Mensagem | Ocorrências | Serviço |
|---|---|---|
| `Corrida detectada: 0 pagamentos atualizados, lote descartado` | 3.939 (+181 em padrões vizinhos) | worker |
| `Tentativa de criar lote sem pagamentos ...` | ~770 | api e worker |
| `Falha ao enviar arquivo para o SFTP da genius` | 68 (23 com `size mismatch in put! 0 != N`) | worker |
| `Retorno da Genius nao e utf-8 valido; lendo como cp1252` | 4.863 | worker |
| `event=lote_ctrl_sem_registro` / `backstop_sem_registro` | 0 | — |

## Consultas para medir de novo

Datadog APM (`aggregate_spans` ou Trace Explorer):

- Latência por rota da cessão:
  `service:platform-cessao env:production operation_name:flask.request resource_name:"GET /liquidacao/lotes/reais"`
  com P50/P95/MAX de `@duration`, agrupado por `@http.status_code`.
- Visão do usuário:
  `env:production service:apl-credit-whitelabel-api resource_name:*liquidation*`
  agrupado por `resource_name` e `@http.status_code`.
- Tempo de banco por consulta:
  `service:postgres env:production @db.instance:platform-cessao operation_name:postgres.query`
  com SUM de `@duration`, agrupado por `resource_hash`.
- 429 em todo o ambiente: `@http.status_code:429`, agrupado por `service` e
  `resource_name`.
