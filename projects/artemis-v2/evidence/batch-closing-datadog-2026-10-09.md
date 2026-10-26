# Fechamento de lote no Datadog — 09/10/2026

Onde vai o tempo do `POST /liquidacao/` e do que vem depois dele (esteira).
Base da [tarefa 03](../tarefas/03-fechamento-assincrono-e-429.md).

- Ambiente: `env:production`, serviço `platform-cessao`, 30 dias até 09/10.
- Só ~51% das requisições têm span guardado (4.135 spans contra 8.080 logs
  `Criar lote de liquidacoes`). Contagens e somas de spans são limite
  inferior; percentis e proporções valem.
- Nos spans do Postgres não há rota de origem: as somas por `resource_hash`
  juntam o `POST` e as tasks do Celery que usam as mesmas funções.

## Latência do `POST /liquidacao/`

| Status | Chamadas | p50 | p95 | Máximo | % do tempo total |
|---|---|---|---|---|---|
| 200 | 676 | 16,6 s | 7,1 min | 15,5 min | 41% |
| 500 | 71 | 14,2 min | 43,5 min | 1h42 | 47% |
| 400 | 3.299 | 2,0 s | 5,0 s | 8,6 min | 12% |
| 429 | 89 | 10 ms | 14 ms | 151 ms | ~0% |

`DELETE /liquidacao/` não é problema: 24 chamadas com 200, p95 12,5 s, máximo
2,4 min (já enfileira a exclusão no Celery).

## Quem chama

| Origem | Chamadas | Payload | Observação |
|---|---|---|---|
| EC2 de automações (`python-requests`) | 3.447 | só produto + originador (85% dos logs, 78 payloads distintos, cada um ~90–100 vezes) | varredura automática entre 18h e 23h UTC; dona da maioria dos 400 |
| BFF (pods do EKS) | — | produto, originador, fundo e origem | corta em 120 s com `httpx.ReadTimeout` e devolve 202; a cessão segue rodando |
| Navegador | — | idem | navegador chamando direto |

Os casos extremos vêm do BFF e do navegador. **Dono da varredura: Rafael Frankl (identificado depois, em 09/10).**

## Causa dos 500

- **49 de 71 (todos acima de 600 s): `pottery.exceptions.ReleaseUnlockedLock`.**
  A trava do `@max_calls(release_time=600)` (`cessao/cache/decorators.py`)
  expira em 10 min; o `release()` no `finally` falha e vira 500 **mesmo quando
  o lote foi criado e enviado à esteira** (trace `2094615131271245462`) ou
  quando o resultado certo era 400 (trace `6ac78e0f0000000035d9b1d8105ee7bb`).
- ~20 em 06/10, 19:35–19:36: Postgres fora do ar (`Connection refused`).
- Não houve `statement_timeout`, deadlock nem harakiri do uwsgi.
- 6 respostas 200 acima de 600 s ficaram sem explicação.

## Traces

| Trace | Resultado | Divisão do tempo |
|---|---|---|
| `6ac78e0f0000000035d9b1d8105ee7bb` | 500 em 42 min (BFF, produto 713) | GROUP BY dos grupos aptos 92,7%; SELECT id ×5 6,6%; UPDATE com 0 linhas (corrida) |
| `6ac793f40000000036764c7fd6997906` | 500 em 17 min (BFF, produto 713) | GROUP BY 81,7% |
| `2094615131271245462` | 500 em 1h42 (navegador, produto 1802) | SELECT id ×14 71,3% (um com 510.680 linhas, 37 min); GROUP BY 28,3%. **13 dos 14 SELECTs eram de origens descartadas: 56,8% da requisição** |
| `4019562183569338825` | 200 em 14,8 min (varredura, 7 lotes, um com 610.541 pagamentos) | serialização da resposta ~99%: count 45,6%, proc_id 45,4%, soma de valor 7,5% |
| `6ac7d5f100000000df4ac3ff62f4cfd8` | 200 em 6,2 min (BFF, 2 grupos) | GROUP BY 75,6%; UPDATE com `IN` de 76.210 ids 22,9% |

Tempo de Python, Redis (~3 ms) e enfileiramento no Celery (0,5–22 ms) é
desprezível: o tempo é espera de SQL.

## Consultas que somam o tempo (30 dias, `POST` + Celery)

| `resource_hash` | O que é | Execuções | Soma | p95 |
|---|---|---|---|---|
| `253a4f59e2dcb949` | GROUP BY dos grupos aptos, sem fundo | 10.091 | 231 h | 5,6 min |
| `9544189cfdc7d6a9` | GROUP BY dos grupos aptos, com fundo | 971 | 25,5 h | 6,5 min |
| `af6c090c7fa63323` | SELECT id dos pagamentos de um grupo | 24.640 | 501 h | 8,1 min |
| `45e132ae3d42d03e` | UPDATE `id IN (...)` | 12.872 | — | 7,7 s (máx. 297 s) |
| `f9546497087af0c1` | `qtde_parcelas` (resposta) | 7.517 | 2,2 h | máx. 9,5 min |
| `a869cdebee701bb5` | `proc_id` (resposta) | 7.129 | 2,2 h | máx. 7,3 min |

## Concorrência

08/10, 12:33–13:17: ~20 `POST` do BFF em paralelo no produto 713. Consultas
que começaram em horários diferentes terminaram no mesmo milissegundo, em
grupos — espera por recurso comum. `postgresql.activity.waits`: ~140 sessões em
LWLock e ~86 em IO (métrica do servidor, não só do banco da cessão); uma
transação aberta havia ~48 min. Quem bloqueava não dá para ver pelo APM
(precisa de DBM ou `pg_locks`).

## Depois do fechamento (worker)

| Task / consulta | Execuções | p50 | p95 | Máximo | Soma |
|---|---|---|---|---|---|
| `esteira_baixar` | 11.293 | 0,6 s | 4,4 s | 16 min | 8,8 h |
| `375a486f89b0f878` (`lote.pagamentos` só para checar se há pagamento) | — | — | — | 16 min | 4,6 h |
| `2cc7a0b9c1cb80e3` (`atualiza_status_contrato_task`: contratos com parcelas fechadas) | — | — | 9 min | — | 36 h |
| `2abb7bd6a95591b2` (um INSERT em `contrato_transacao` por contrato) | 3,1 mi | — | — | — | 3,7 h |

- No trace `4019562183569338825`, `lote.pagamentos` carregou 610.541 linhas
  em 342 s, 83,5% da task.
- `esteira_baixar` faz ~8 consultas por contrato (parcela, contrato, sacado,
  documento, endereço, metadata): ~6,8 mil consultas para 795 contratos.
- Fila do Celery: em amostra de 08/10, a task começa 3–10 ms após o
  enfileiramento (pior caso 9 s).
