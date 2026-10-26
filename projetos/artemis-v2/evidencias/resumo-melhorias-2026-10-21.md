# Resumo das melhorias em produção — 21/10/2026

Números para a mensagem aos stakeholders: fechamento de lote fake (TS-5377,
com a fase 1) e listagem de lotes reais (TS-5383). Medição de 21/10, 11h10
de Brasília (14h10 UTC).

- **Fonte:** Datadog, `env:production`. Durações do APM em nanossegundos,
  convertidas.
- **[C]** em tudo abaixo, salvo onde indicado.

## Quando cada versão entrou (spans `flask.request` da cessão, por `@version`)

| Versão da cessão | Desde (UTC) | O que leva |
|---|---|---|
| `prod-f19ef2c` | 19/10 21:45 | TS-5377 (fechamento assíncrono) |
| `prod-2eb8faa` | 20/10 ~23:06 | fase 1 da TS-5377 e TS-5383 |
| `prod-bcf8447` | 21/10 ~00:30 | hotfix do detalhe do lote real pelo `lote_id` |

As consultas novas da TS-5383 (`788d1d5df137d8b`, `db8a1f03fb515cca`,
`4856ef7a427ac6f6`, `9cc782411e60f129`) aparecem a partir das 23h UTC de
20/10, junto com a `prod-2eb8faa`. Isso corrige a "noite de 20/10" da
[evidência da réplica](lotes-reais-replica-2026-10-20.md): o deploy foi com a
fase 1.

## Fechamento de lote fake

Rota nova pela tela desde 20/10 12:26 UTC. "Antes" é a rota antiga pela
tela, 30 dias até 19/10 21:45 UTC, da
[evidência de 20/10](fechamento-assincrono-datadog-2026-10-20.md).

| Métrica | Antes | Agora (20/10 12:26 a 21/10 14:10 UTC) |
|---|---|---|
| Pedidos × fechados | — | **47 × 47**, 57.542 pagamentos, 8 produtos |
| Falhas, descartes, trava perdida, erro na esteira | 500 em 4,9% (21 de 428), chegando em ~20 min | **0** |
| Clique recusado (429) | 11,7% (95 de 811) | **0** |
| Espera do clique no BFF (p50) | 5,0 s, sem confirmar nada | **0,22 s** (10 chamadas amostradas desde 20/10 23:10) |
| Duração (p50) | 20,6 s | **10,6 s** |
| Duração (p95) | 5,5 min | **32,5 s** |
| Duração (máximo) | 9,7 min | **45 s** (maior grupo: 29.792 pagamentos) |
| Tempo de servidor por fechamento (média) | 100 s; 179 s com as falhas | **13 s** (612 s ÷ 47) |
| Reenvio por queda do worker (`attempt > 1`) | — | 0 (desde a fase 1) |
| Espera na fila (`queue_wait_ms`, máximo) | — | 74 ms (desde a fase 1) |

O "Agora" vem dos logs (completos). O "Antes" vem de spans amostrados
(~50%): contagens são limite inferior, proporções e percentis valem.

## Listagem de lotes reais (`GET /liquidacao/lotes/reais`, cessão)

| Métrica | 7 dias antes (13/10 23:05 a 20/10 23:05 UTC) | Depois (20/10 23:10 a 21/10 14:10 UTC) |
|---|---|---|
| Chamadas | 837 | 56 |
| Erro 500 (`statement_timeout`, 120 s) | **180 (21,5%)** | **0** |
| p50 (sucesso) | 0,34 s | **0,19 s** |
| p95 (sucesso) | 50,8 s | **11,1 s** |
| Máximo (sucesso) | 2,9 min | **22,7 s** |
| Tempo de servidor por chamada (média, com erros) | 32,9 s (27.527 s ÷ 837) | **1,8 s** (101 s ÷ 56) |

- Linha de base de 05/10 (antes da V2): 18% de 504 no BFF; p95 de 12,6 min
  e máximo de 2h12 na cessão ([baseline](baseline-datadog-2026-10-05.md)).
- **Amostra pequena:** o "depois" é uma noite e uma manhã. A medição que
  vale é a de dois dias úteis (22–23/10, tarefa 12).
- Réplica, 20/10: a página do fundo 209 que dava 500 passou de mais de 60 s
  para 0,4 s, e os irmãos de mais de 120 s para 0,1 s. O detalhe do lote
  1837116 (1.744 remessas) passou de mais de 60 s (e 414 na tela) para
  34 ms ([evidência](lotes-reais-replica-2026-10-20.md)).

## Pontos a acompanhar

- **CNAB por remessa:** 3 respostas 404 no BFF
  (`GET .../real-batches/cnab?proc_id=…`, navegador) depois do hotfix; nos 7
  dias anteriores, 2 respostas 200. **[H]** Remessa sem arquivo de CNAB
  (remessa por pagamento). Conferir se a tela mostra botão para remessa sem
  arquivo.
- **Pagamentos do lote (`GET /liquidacao/pagamentos/query`):** amostra mista
  por versão (`prod-bcf8447`: 15 chamadas, p50 0,3 s, p95 6,1 s, máximo
  23 s). Sem conclusão; medir junto com a listagem em 22–23/10.

## Consultas para repetir

- Versões: `aggregate_spans` em `env:production service:platform-cessao
  operation_name:flask.request`, agrupado por `@version` com intervalo de
  30 min.
- Fechamentos: `analyze_datadog_logs` com filtro `env:production
  service:platform-cessao-worker "Fechamento de lote fake concluído"` e
  colunas `@status`, `@reason`, `@duration_ms`, `@payments_count`,
  `@attempt`, `@queue_wait_ms`, `@product_id`.
- Pedidos e falhas: `env:production service:(platform-cessao OR
  platform-cessao-worker)` com as mensagens "solicitado", "descartado",
  "Falha no fechamento de lote fake", "Trava do fechamento de lote fake
  perdida", "Falha ao renovar a trava…" e "Falha ao enviar lote real
  fechado para a esteira de baixa", por `service` e `message`.
- Listagem: `aggregate_spans` em `env:production service:platform-cessao
  operation_name:flask.request resource_name:"GET /liquidacao/lotes/reais"`,
  COUNT, P50, P95, MAX e SUM de `@duration`, por `@http.status_code`.
- Visão do usuário: `env:production service:apl-credit-whitelabel-api
  operation_name:fastapi.request resource_name:*liquidation*`, por
  `resource_name` e `@http.status_code`.
