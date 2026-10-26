# Fechamento assíncrono no Datadog — 20/10/2026 (primeiro dia)

O que rodou pela rota nova (TS-5377) no primeiro dia de uso em produção.
Base: [roteiro de acompanhamento](acompanhamento-fechamento-assincrono.md) e
[casos de 20/10](../tarefas/03-casos-pos-producao.md).

- **Período:** 20/10, 00:00 a 17:55 UTC. Os fechamentos foram de 14:28 a
  17:25 UTC (11:28 a 14:25 em Brasília).
- **Fonte:** `env:production`, com três tipos de log:
  - "Fechamento de lote fake solicitado" (`platform-cessao` e
    `apl-credit-whitelabel-api`);
  - "Fechamento de lote fake concluído" (`platform-cessao-worker`);
  - spans `celery.run` de `close_fake_batch` e `postgres.query` do UPDATE
    (`resource_hash:31fa1a89c021a472`).
- **Unidades:** durações do APM em nanossegundos; `duration_ms` do log em
  milissegundos.

## Resumo

- **25 pedidos, 25 fechados** (`closed`). Zero falhas, descartes, 409, 400,
  5xx, estouro de tempo ou reinício do worker.
- **52.139 pagamentos** em 25 lotes reais.
- O clique responde em 25 ms na cessão e em 248 ms no BFF (p50).
- A espera na fila foi praticamente zero (concorrência 16, R16).
- A task durou 9,8 s no p50 e 27,6 s no máximo. O maior grupo, de 29.792
  pagamentos, levou 27,6 s.
- **Anomalia:** 11 fechamentos do fundo 209 ficaram até 25 s parados no
  UPDATE, à espera de uma trava de outra transação (seção "Espera por trava").
- **Esteira:** 23 de 25 lotes chegaram à atualização de status dos contratos.
  Os 2 de renegociação, fechados às 17:06 UTC, ainda não chegaram.

## Comparação com a rota antiga

Mesmo caminho, a tela via BFF, nas duas colunas:
- **Antes:** `consolidate` no BFF → `POST /liquidacao/` na cessão
  (`@http.useragent:python-httpx*`), 30 dias até a implantação (19/09 21:45
  a 19/10 21:45 UTC).
- **Agora:** `fake-batches/close` → task `close_fake_batch`, em 20/10.

| Métrica | Antes (rota antiga) | Agora (rota nova) | Ganho |
|---|---|---|---|
| Espera do clique no BFF (p50) | 5,0 s, sem confirmar nada | 0,25 s | 20× mais rápido |
| Clique recusado com 429 | 11,7% (95 de 811) | 0% (0 de 25) | eliminado |
| Fechamento que falhou depois do "ok" (500) | 4,9% (21 de 428); a falha chegava em 20 min (p50), até 44 min | 0% | eliminado |
| Duração do fechamento (p50) | 20,6 s | 9,8 s (1,5 s sem a espera por trava) | 2× (14×) |
| Duração do fechamento (p95) | 5,5 min | 25,8 s | 13× |
| Duração do fechamento (máximo) | 9,7 min | 27,6 s | 21× |
| Tempo de servidor por fechamento (média) | 100 s; 179 s contando as falhas | 10,6 s | ~10× (~17×) |
| Usuário vê o resultado | não; só recarregando a lista | sim, na linha ("Fechando…" → fechado/falha) | — |

Como ler:
- **Amostra:** o "Agora" é um dia, 25 fechamentos e só alguns produtos (1901,
  1145, 1143, 713, 449, 1043). O "Antes" são 30 dias com todos os produtos da
  tela. É indicativo; repetir com uma semana de uso.
- **Contagens do APM:** os spans do legado são amostrados (~50%). As
  contagens são limite inferior; as proporções e os percentis valem. Os
  números do "Agora" vêm dos logs (completos).
- **"Duração" no legado** é o tempo da requisição na cessão. Inclui montar a
  resposta depois do commit, que chegava a 99% do tempo nos grupos grandes
  ([evidência de 09/10](fechamento-lote-datadog-2026-10-09.md)). O lote
  ficava pronto antes do fim, mas a cessão seguia ocupada, e é isso que a
  linha mede.
- **"1,5 s sem a espera por trava":** p50 dos 11 fechamentos que não pegaram
  a espera de 14:28–14:29 (seção abaixo).
- **429 e 500 no legado:**
  - o 429 era o clique repetido, porque a tela não guardava o "em
    andamento";
  - 49 dos 500 de 30 dias até 09/10 eram a trava do `max_calls` expirando
    aos 600 s, com o lote às vezes já criado;
  - o BFF respondia 202 depois de 5 s, então o usuário nunca via esses 500.
- **Tempo de servidor** = soma das durações ÷ fechamentos:
  - antes: 40.765 s ÷ 407 (só os 200), ou (40.765 + 35.660) s ÷ 428
    (contando os 500);
  - agora: 265 s ÷ 25.
- **Não comparável:** pagamentos por segundo. O legado não registra quantos
  pagamentos cada fechamento levou.

## Fechamentos por produto

| Produto | Fundo | Lotes | Pagamentos | Maior grupo | Duração (mín.–máx.) |
|---|---|---|---|---|---|
| 1901 | 26 | 4 | 43.917 | 29.792 | 0,35–27,6 s |
| 1145 | 506 | 3 | 4.198 | 2.974 | 0,56–14,2 s |
| 713 | 209 | 4 | 2.816 | 1.744 | 5,1–9,8 s |
| 1143 | 506 | 3 | 1.180 | 559 | 0,43–3,4 s |
| 449 | 209 | 1 | 16 | 16 | 3,6 s |
| 1043 | 209 | 10 | 12 | 3 | 5,8–25,8 s |

Rajadas (UTC):
- 14:28:41–14:29:07: 15 pedidos em 26 s;
- 14:41:59–14:42:06: 4 pedidos;
- 17:06: 2 pedidos;
- 17:25:05–17:25:13: 4 pedidos.

O pico foi de 13 fechamentos simultâneos, às 14:29.

## Rotas

| Rota | Status | Chamadas | p50 | p95 | Máximo |
|---|---|---|---|---|---|
| cessão `POST /liquidacao/fake-batches/close` | 202 | 25 | 25 ms | 28 ms | 101 ms |
| BFF `POST .../fake-batches/close` | 202 | 20 (amostra) | 248 ms | 335 ms | 343 ms |
| cessão `POST .../close/status` | 200 | 47 | 3,7 ms | 4,9 ms | 5,1 ms |
| BFF `POST .../close/status` | 200 | 30 (amostra) | 225 ms | 349 ms | 375 ms |

- O BFF leva ~220 ms a mais que a cessão nas duas rotas. É a consulta de
  produtos do usuário a cada chamada (sem cache, ver o relatório do BFF em
  [03-casos-pos-producao.md](../tarefas/03-casos-pos-producao.md)).
- Nenhuma chamada ao `consolidate` legado pela tela. O `POST /liquidacao/`
  teve só 4 chamadas, todas do Atlas.

## Tempo do UPDATE

Velocidade nos fechamentos sem espera por trava:

| Grupo | Pagamentos | Duração | Pagamentos por segundo |
|---|---|---|---|
| 1901 / 1513 | 29.792 | 27,6 s | ~1.080 |
| 1901 / 73 | 13.174 | 10,8 s | ~1.220 |
| 1145 / 886 | 2.974 | 14,2 s | ~210 |
| 713 / 1282 | 1.744 | 5,6 s | ~310 |

- A velocidade varia de ~200 a ~1.200 pagamentos por segundo, conforme o
  grupo.
- Extrapolação linear **[H]**: 137 mil pagamentos (maior dia do produto 15)
  levariam 2 a 11 min; 600 mil, 8 a 50 min. O soft limit da task é 540 s
  (9 min). Grupos dessa ordem continuam dependendo do L3 e da D20.

## Espera por trava (14:28:41–14:29:07 UTC)

- **[C]** O que se vê nos spans do UPDATE (`31fa1a89c021a472`):
  - 11 fechamentos do **fundo 209** começaram o UPDATE entre 14:28:41,454 e
    14:29:01. São 10 do produto 1043 (1 a 3 pagamentos cada) e parte dos do
    713.
  - **Todos terminaram entre 14:29:06,880 e 14:29:06,885**, qualquer que
    fosse o início.
  - O primeiro esperou 25,4 s para atualizar 1 linha.
  - Dois do 713, pedidos às 14:28:57 e 14:29:02, terminaram juntos logo
    depois, às 14:29:07,5.
- **[C]** Terminar no mesmo instante, independentemente do início, é sinal
  de espera por uma trava liberada uma vez só. Não houve espera na fila: o
  pedido mais a duração dão o fim, com folga de ~0,3 s.
- **[C]** Os fechamentos não esperaram uns pelos outros. O primeiro também
  esperou, e as linhas são disjuntas (origens diferentes).
- **[H]** Quem segurava a trava foi uma transação fora do APM. Nenhum span
  com mais de 3 s na cessão no período, além dos nossos. Candidatos:
  - sessão manual no banco;
  - a varredura, que grava direto com usuário próprio;
  - uma transação aberta sem consulta ativa ("idle in transaction").

  **Validar** no Database Monitoring do Datadog: amostras de atividade de
  14:28:40 a 14:29:07 UTC no banco da cessão, coluna de quem bloqueia.
- **Efeito hoje:** só atraso, de até 25 s.
- **Efeito possível:**
  - sem `lock_timeout` (R17), uma trava longa prende o fechamento até o soft
    limit (9 min), que termina em "Erro inesperado";
  - com 2 vagas (R16 corrigido), as duas ficariam presas, e a fila cresceria
    rumo ao `expires` de 300 s (R18).

## Worker

- Pod `platform-cessao-fake-batch-closing-worker-9464c4dd7-2hzkq`, sem
  reinício desde 19/10 21:45 UTC. Concorrência 16 (R16 continua).
- Pico de memória 1,92 GiB de 3 GiB (64%), com 13 fechamentos simultâneos.
  Pico de CPU 0,16 core.
- Cada fechamento abriu uma conexão nova ao banco (primeira task de cada
  processo do Celery).

## Depois do fechamento (esteira)

- 23 dos 25 lotes logaram "Atualização de status de contratos do lote
  liquidação" (fim da esteira), a maioria às 17:15 e 17:30 UTC. Esse é o
  horário em que a conciliação andou, não o do fechamento.
- **Faltam 2** (renegociação, fechados às 17:06 UTC):
  - `84be8528-…` (produto 1145, 1.034 pagamentos);
  - `55c42bc4-…` (produto 1143, 431 pagamentos).

  **[H]** Aguardam conciliação. **Conferir** na tela de lotes reais.
- `esteira_baixar` desde 14:28 UTC: 75 execuções, todas `ok`, p95 5,1 s,
  máximo 60,6 s.

## Fora do fechamento, na mesma tela

`GET /liquidacao/lotes/reais`: 19 respostas 500 hoje, todas em ~120 s
(`statement_timeout`). Quatro delas foram logo depois da primeira rajada,
entre 14:29:48 e 14:31:57 UTC. É o problema da
[tarefa 12](../tarefas/12-lotes-reais-lotes-antes-dos-valores.md), não do
fechamento, mas o usuário cai nele ao conferir o lote que acabou de fechar.

## Consultas para repetir

- Antes (legado pela tela): spans `env:production service:platform-cessao
  resource_name:"POST /liquidacao/" operation_name:flask.request
  @http.useragent:python-httpx*` e `env:production
  service:apl-credit-whitelabel-api resource_name:*fake-batches/consolidate*
  operation_name:fastapi.request`, por `@http.status_code`, com contagem,
  p50, p95, máximo e soma de `@duration`.

- Fechamentos: `analyze_datadog_logs` com filtro
  `env:production service:platform-cessao-worker "Fechamento de lote fake concluído"`
  e colunas `@status`, `@reason`, `@duration_ms`, `@payments_count`,
  `@product_id`, `@fund_id`, `@origin`, `@job_id`, `@batches`.
- Espera na fila: juntar "solicitado" e "concluído" por `@job_id`, usando o
  `@asctime` de cada um.
- Espera por trava: spans `env:production service:postgres
  resource_hash:31fa1a89c021a472`, comparando início e fim.
- Esteira: logs do `platform-cessao-worker` com os identificadores de
  `@batches`, mensagem "Atualização de status de contratos do lote
  liquidação".
