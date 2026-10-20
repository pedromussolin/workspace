# Acompanhamento do fechamento assíncrono em produção (TS-5377)

Roteiro para conferir, no Datadog, se o fechamento novo está fechando, em
quanto tempo e se algum pedido se perdeu. Base da
[análise de 20/10](../tarefas/03-casos-pos-producao.md).

- **No ar:** cessão e worker desde 19/10 21:45 UTC (`prod-f19ef2c`); BFF
  (`prod-fe2bee2`) e front desde 20/10 ~12:26 UTC (primeira chamada a
  `close/status` às 12:26:39 UTC).
- **Uso até 20/10 12:30 UTC:** nenhum fechamento pelo fluxo novo; uma consulta
  de status.
- Durações do APM vêm em nanossegundos; `duration_ms` do log, em milissegundos.

## Conferência rápida (a cada rodada)

| # | O que | Consulta | Esperado | Alerta |
|---|---|---|---|---|
| 1 | Pedidos | logs `env:production service:platform-cessao "Fechamento de lote fake solicitado"` | um por clique | — |
| 2 | Conclusões | logs `env:production service:platform-cessao-worker "Fechamento de lote fake concluído"`, agrupar por `@status` e `@reason` | 1 para cada pedido | pedidos − conclusões > 0 depois de 10 min = pedido perdido |
| 3 | Duração | mesma consulta, `@duration_ms` (p50, p95, máx.) e `@payments_count` (máx.) | segundos | acima de 300.000 ms (a trava passa a depender só da renovação; o soft limit é 540 s) |
| 4 | Descartes | logs `"Fechamento de lote fake descartado"` | zero | qualquer um: a task chegou sem a trava (fila atrasada ou trava expirada) |
| 5 | Falhas | logs `"Falha no fechamento de lote fake"` (com stack) | zero | qualquer um |
| 6 | Trava | logs `"Falha ao renovar a trava do fechamento de lote fake"` | zero | qualquer um: Redis com problema durante um fechamento |
| 7 | Depois do fechamento | logs `"Falha ao enviar lote real fechado para a esteira de baixa"` e `"Falha ao limpar o cache do lote fake"` | zero | lote fechado e parado |
| 8 | Rotas | APM `env:production service:platform-cessao resource_name:*fake-batches/close*`, por `@http.status_code` | 202 e 200 | 409 frequente (clique repetido), 400 (chave/produto), 5xx |
| 9 | Worker | logs `env:production kube_deployment:*fake-batch-closing*` com `status:error`, e reinícios do pod | sem reinício | reinício = fechamento em andamento perdido |
| 10 | Esteira | APM `operation_name:celery.run resource_name:cessao.tasks.liquidacao_lote.esteira_baixar`, erros | igual aos dias anteriores | erro em lote criado pelo fluxo novo |

Pedido perdido (item 2) se acha cruzando `@job_id` do "solicitado" com o do
"concluído": o `job_id` está nos dois logs.

## Referência do legado (7 dias até 20/10 12:30 UTC)

`POST /liquidacao/` por quem chama:

| Quem | Status | Chamadas | p50 | p95 | Máximo |
|---|---|---|---|---|---|
| BFF | 200 | 201 | 24 s | 6,1 min | 9,7 min |
| BFF | 429 | 18 | 7 ms | 11 ms | 12 ms |
| varredura | 200 | 198 | 4,3 s | 2,9 min | 8,2 min |
| varredura | 400 | 846 | 2,0 s | 5,4 s | 5,2 min |
| Atlas | 200 | 32 | 0,6 s | 12 s | 4,1 min |
| navegador direto | 200 / 500 | 3 / 1 | 9,1 min | — | 14,8 min |

Consultas do legado que equivalem ao UPDATE novo (o novo faz as duas numa
instrução, com um join a mais na cessão do contrato):

| `resource_hash` | O que é | Execuções | p50 | p95 | Máximo |
|---|---|---|---|---|---|
| `af6c090c7fa63323` | SELECT id dos pagamentos de um grupo | 2.495 | 59 ms | 17 s | 5,2 min |
| `45e132ae3d42d03e` | UPDATE `id IN (...)` | 520 | 54 ms | 9,3 s | 2,6 min |

`esteira_baixar` no mesmo período: 846 execuções com trace, p95 11 s, máximo
5,4 min.
