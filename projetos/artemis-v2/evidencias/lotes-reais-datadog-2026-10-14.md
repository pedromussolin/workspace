# Lotes reais em produção — 14/10/2026

Medição da aba de lotes reais depois da réplica (TS-5279, 07/10) e do
`statement_timeout` de 120 s por consulta (hotfix `0ef1d4f`, 06/10). Base da
[tarefa 12](../tarefas/12-lotes-reais-lotes-antes-dos-valores.md).

- Ambiente: `env:production`. Janela: 6 dias até 14/10/2026, 19h40 UTC.
- Durações convertidas de nanossegundos.

## Rota da cessão `GET /liquidacao/lotes/reais`

| Status | Chamadas | p50 | p95 | Máximo |
|---|---|---|---|---|
| 200 | 603 | 0,28 s | 36,9 s | 2,7 min |
| 500 | **146 (19,5%)** | 120 s | 135 s | 3,8 min |

Os 500 são `QueryCanceled: canceling statement due to statement timeout`:
o limite de 120 s cancela a consulta e a rota responde erro. Em 30 dias, as
2.198 chamadas vieram todas de `python-httpx/0.28.1` (o BFF); nenhum outro
cliente usa a rota.

## Consultas da listagem (tempo de banco)

| `resource_hash` | Consulta | Execuções | Canceladas em 120 s | p50 | p95 | Tempo total |
|---|---|---|---|---|---|---|
| `3afbd330f1bd4d7f` | `lotes_das_remessas` (lotes irmãos) | 342 | **126 (37%)** | 39 ms (ok) | 11,1 s (ok) | **4,3 h** |
| `44a7a7211a2af67b` | página **sem** filtro de produto | 85 | 15 | 4,4 s (ok) | 94 s (ok) | 1,0 h |
| `35a91cd19cdc2168` | página **com** filtro de produto | 293 | 3 | 0,39 s (ok) | 14,7 s (ok) | 0,5 h |

`lotes_das_remessas` responde por ~74% do tempo de banco da listagem e pela
maior parte dos 500.

## Um trace típico

Trace `6acfda6000000000951f20fe386b54eb` (14/10, 19h39 UTC), 120,6 s → 500:

| Trecho | Tempo |
|---|---|
| `SET LOCAL statement_timeout` | 2 ms |
| Página (CTE `pagina` + LATERAL dos valores), 5 linhas | **0,48 s** |
| `lotes_das_remessas` | **120 s**, cancelada |

A consulta de `lotes_das_remessas` que chega ao banco carrega **dois**
`NOT EXISTS` de soft delete: um porque a query tem `Parcela` e outro porque
tem `LiquidacaoPagamento` (`cessao/database/listeners.py:731`). Os dois
fazem a mesma checagem (parcela → contrato → processo deletado).

## Consultas para medir de novo

- Rota: `service:platform-cessao env:production operation_name:flask.request
  resource_name:"GET /liquidacao/lotes/reais"`, P50/P95/MAX de `@duration`
  agrupado por `@http.status_code`.
- Banco: `service:postgres env:production @db.instance:platform-cessao
  operation_name:postgres.query (resource_name:*liquidacao_lote_processo* OR
  resource_name:*DISTINCT*liquidacao_lote_id*)`, SUM/COUNT/P95 de
  `@duration` agrupado por `resource_hash` e `status`. Depois do deploy as
  consultas mudam de texto e ganham `resource_hash` novos.

## Atualização de 20/10/2026

Mesmas consultas, de 14/10 19h40 a 20/10 18h50 UTC. Usada na
[análise do PR de lotes reais](../tarefas/12-analise-pr-lotes-reais.md).

| Status da rota | Chamadas | p50 | p95 | Máximo |
|---|---|---|---|---|
| 200 | 473 | 0,36 s | 35,4 s | 2,9 min |
| 500 | **124 (20,8%)** | 120 s | 150 s | 3,3 min |

| Consulta | Execuções | Canceladas em 120 s | p95 (ok) | Tempo total |
|---|---|---|---|---|
| `lotes_das_remessas` (`3afbd330f1bd4d7f`) | 267 | **100** | 17,2 s | **3,5 h** |
| página sem produto (`44a7a7211a2af67b`) | 103 | 23 | 92,5 s | 1,3 h |
| página com produto (`35a91cd19cdc2168`) | 265 | 0 | 16,6 s | 0,3 h |

Dos 124 erros, 100 (81%) são dos irmãos e 23 (19%) da página sem produto.
Os irmãos seguem com ~70% do tempo de banco da listagem.
