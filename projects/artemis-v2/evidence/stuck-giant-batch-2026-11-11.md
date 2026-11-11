# Lote gigante parado na esteira de baixa — 07/11 a 11/11/2026

Base da [tarefa 14](../tasks/14-giant-batch-pipeline.md).

- **Fontes:** Datadog (APM, logs, eventos do Kubernetes e `kubernetes.memory.usage`), `env:production`;
  réplica de leitura da cessão.
- **Consulta feita em:** 11/11/2026, ~17h UTC. Horários em UTC; Brasília é UTC−3.

## Linha do tempo do lote 1841860 [C]

| UTC | O quê | Fonte |
|---|---|---|
| 07/11 11:10 | abre o vigente (produto 80, originador 80, fundo 36, origem `consumer_baixa_ordinaria_padrao`) | réplica |
| 07/11 11:10 → 09/11 14:03 | acumula 1.003.192 pagamentos | réplica |
| 09/11 20:19:48 | a varredura (`POST /liquidacao/`) fecha o lote e o manda para a `esteira_baixar`; a chamada dura 690 s | logs e APM |
| 09/11 20:26:34 | o worker avisa que não registrou o compromisso de saldo (fundo sem conta de conciliação; tolerado), lote em `pendente` | logs |
| 09/11 20:26:49 | o contêiner do worker é recriado; o pod foi de ~7,56 GB (20:00) para ≥10,58 GB (amostra) e voltou a ~2,67 GB | eventos do Kubernetes e métrica |
| 09/11 21:47 | deploy da release de 09/11 recria os pods (sem relação com o lote) | eventos |
| 11/11 | o lote segue `pendente`; o vigente da chave já é o 1843210, com 285.653 pagamentos | réplica |

O evento do Kubernetes traz a recriação, não o motivo: falta de memória é a hipótese mais forte **[H]**.
Um lote de 1.039.324 pagamentos do mesmo produto (30/10) concluiu.

## Reenvio manual em 11/11 [C]

| UTC | O quê |
|---|---|
| 17:49:25 | `POST /liquidacao/reenviar` com o identificador do lote: 200 em 11 ms |
| 17:49–17:53 | `reenviar_lote_liquidacao_task` roda (1 execução, sem erro) e dispara a `esteira_baixar` |
| 17:54:13 | o worker carrega o lote (~4,5 min) e repete o aviso do compromisso de saldo |
| 17:54:27 | lote em `concluido` |
| 17:54:28 | começa a `atualiza_status_contrato_task` do lote |

- Memória do pod que processou: 4,41 GB antes, 9,06 GB no pico (amostra de 10 s), 3,47 GB depois, sem
  reinício. O lote de 1 milhão pediu **pelo menos +4,7 GB**. Em 09/11 o pod partiu de ~7,5 GB: com o
  limite de 12 GiB (~12,9 GB), não havia espaço. Isso reforça a falta de memória como causa **[H forte]**.
- Os 15 pods do worker estavam entre 3,4 e 4,8 GB antes do reenvio.

## Varredura, `POST /liquidacao/` vindo da EC2 de automações [C]

| Dia | 200 | 400 | 429 | 500 | Duração máxima |
|---|---|---|---|---|---|
| 30/10 | 52 | 115 | — | 1 | 4.682 s |
| 03/11 a 06/11 | 46 a 51 | 48 a 60 | — | — | 192 a 419 s |
| 09/11 | 52 | 102 | — | — | 690 s |
| 10/11 | 48 | 113 | 9 | 1 | 744 s |

- O 400 é "nenhum pagamento apto para liquidar", resposta normal de chave sem nada a fechar.
- Desde 09/11 há rodadas também às 21h e às 23h30 UTC, além das 20h.
- 10/11, 20:43: o 500 é `ReleaseUnlockedLock` da trava `max_calls` (600 s): a chamada do produto
  581 durou 744 s, 439 s e 297 s nas duas buscas de pagamentos aptos do legado.
- 10/11, 21:06: os 9 × 429 são a mesma trava recusando chamadas. A varredura não lê a resposta,
  mas os lotes do 581 desse dia concluíram.

## Lotes dos produtos do Mercato Libero desde 03/11 [C]

Fora o 1841860, todos os lotes de dias anteriores estão `concluido`; os 37 vigentes abertos são de 11/11.

## Consultas para medir de novo

- **APM:** `service:platform-cessao env:production operation_name:flask.request
  @http.client_ip:<IP da EC2 de automações> resource_name:"POST /liquidacao/"`, COUNT por
  `@http.status_code` em intervalos de 1 dia, MAX de `@duration` (nanossegundos).
- **Logs de um lote:** `env:production @lote_identificador:<identificador do lote>`.
- **Memória do worker:** `max:kubernetes.memory.usage{kube_deployment:platform-cessao-worker-worker,env:production} by {pod_name}`.
- **Réplica, lotes por dia e estado:**

```sql
select l.produto_id, l.data_criacao::date as criado, l.estado_atual,
       coalesce(v.fechado::text, 'sem_vigente') as vigente_fechado, count(*) as lotes
from liquidacao_lote_processo l
left join liquidacao_lote_vigente v on v.liquidacao_lote_id = l.id
where l.produto_id in (4, 80, 81, 1406, 581, 15)
  and l.data_criacao >= date '2026-11-03'
group by 1, 2, 3, 4
order by 1, 2, 3;
```

- **Réplica, tamanho de um lote:** `select count(*) from liquidacao_pagamento where liquidacao_lote_id = <id>;`
  (cruzar os pagamentos de um lote de 1 milhão com `liquidacao_processo` estoura 120 s).
