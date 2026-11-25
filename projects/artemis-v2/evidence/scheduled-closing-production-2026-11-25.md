# Fechamento por horário em produção — 25/11/2026

Acompanhamento da B1 do [guia da release de 24/11](../tasks/13-post-deploy-switch-on-guide.md)
(fechamento por horário, TS-5570) nos produtos 15 e 1604, ligados em 24/11.

- **Fontes:** Datadog (logs e APM), `env:production`; código da cessão no commit `d28b83a`, o que
  está em produção.
- **Consulta feita em:** 25/11/2026, ~19:10 UTC. Horários em UTC; Brasília é UTC−3.
- **Atualizar:** a cada rodada do produto 15 (17:00, 18:00 e 20:45 de Brasília), na tabela das
  rodadas e nos pendentes.

## Versão em produção [C]

Cessão `prod-d28b83a` desde 25/11 00:46 UTC (argocd `d389626`): a release de 24/11 mais a TS-5773
(`851e7f3cf`, fila `liquidacao.atraso` declarada no consumer; `90817566f`, pagamento parcial de
parcela fechada).

## Rodadas [C]

Fonte: `"Fechamento de lotes por horário concluído"`. "Consulta das chaves" é o span `postgres` da
consulta que lista os pagamentos sem lote aptos (ver o ponto de atenção).

| Brasília | Produto | Chaves | Com lote aberto | Pagamentos sem lote | Fechadas | Falhas | Duração | Consulta das chaves |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 24/11 20:45 | 15 | 0 | 0 | 0 | 0 | 0 | 1,9 s | — |
| 25/11 16:00 | 1604 | 0 | 0 | 0 | 0 | 0 | 0,05 s | — |
| 25/11 16:00 | 15 | 1 | 1 | 0 | 1 | 0 | 281 s | 255 s |

Agendador (`"Agendamentos despachados"`), 25/11 19:00:01 UTC: 3 disparos (1604, 15 e o backstop,
que roda a cada :00 e :30), 0 falhas, 0 perdidos, 0 presos.

## Antes: fechamento pela VM (rota antiga), 11/11 a 24/11

Linha de base dos produtos do Mercato Libero para comparar com o fechamento por horário.

- **Fonte [C]:** spans do APM `flask.request` `POST /liquidacao/` vindos da EC2 de automações,
  `env:production`, de 11/11 03:00 UTC a 25/11 19:25 UTC. São 9 dias úteis: 11, 12, 13, 16, 17,
  18, 19, 23 e 24/11; 20/11 foi feriado, e em 25/11 a VM ainda não tinha rodado.
- **Por que a chamada mede o fechamento [C]:** a rota antiga fecha o vigente e cria os lotes dentro
  da própria chamada e só responde no fim (`cessao/api/liquidacao/viewer.py:463`, commit `d28b83a`).
- **Produto de cada chamada [C]:** sai do log `"Criar lote de liquidacoes - payload"`. O log da API
  não traz `trace_id`, então a junção é pelo servidor e pelo horário: o log sai ~1 s depois do
  início da chamada. Das 1.292 chamadas, 1.258 casaram (4 só pelo horário) e 34 ficaram sem log.
- **Rodada:** as chamadas de um produto com menos de 20 min entre uma e a próxima. **Relógio** é do
  início da primeira chamada ao fim da última; **servidor** é a soma das durações. A soma passa do
  relógio quando há chamadas em paralelo.
- **[H] Cobertura:** o APM guarda só os spans que o filtro de retenção indexa. Uma chamada curta
  descartada na borda da rodada encurta o relógio e a soma. Validar contra `trace.flask.request`
  se a diferença com o fechamento novo for pequena.

| Produto | Rodadas | Início (Brasília) | Chamadas por rodada (p50) | Lotes criados | Relógio por rodada: p50 / máx | Servidor por rodada: p50 / máx | Maior chamada |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 9 | 17h | 28 | 239 | 6,9 / 12,4 min | 6,7 / 12,0 min | 261 s |
| 15 | 9 | 17h | 25 | 20 | 5,9 / 9,8 min | 5,7 / 9,7 min | 234 s |
| 80 | 18 | 17h, 18h e 20h | 14 | 81 | 6,8 / 18,4 min | 5,1 / 8,9 min | 424 s |
| 81 | 9 | 17h | 4 | 38 | 1,0 / 3,0 min | 1,0 / 2,7 min | 50 s |
| 581 | 9 | 17h | 24 | 16 | 5,6 / 6,7 min | 5,4 / 7,3 min | 222 s |
| 1406 | 9 | 17h e 18h | 6 | 54 | 2,7 / 8,2 min | 1,8 / 8,0 min | 233 s |

Servidor somado de todas as rodadas por dia: 21 a 42 min. Nenhum 5xx nem 429 no período.

Produto 15, rodada a rodada:

| Início (Brasília) | Chamadas | Lotes | Relógio | Maior chamada |
| --- | --- | --- | --- | --- |
| 11/11 17:07 | 23 | 2 | 5,9 min | 155 s |
| 12/11 17:08 | 39 | 3 | 6,7 min | 142 s |
| 13/11 17:08 | 25 | 2 | 5,2 min | 140 s |
| 16/11 17:13 | 23 | 2 | 4,3 min | 179 s |
| 17/11 17:08 | 23 | 2 | 4,8 min | 153 s |
| 18/11 17:07 | 26 | 2 | 4,9 min | 150 s |
| 19/11 17:06 | 38 | 3 | 6,7 min | 151 s |
| 23/11 17:09 | 24 | 2 | 9,8 min | 234 s |
| 24/11 17:08 | 25 | 2 | 6,4 min | 215 s |

**Comparação do produto 15 [C]:** pela VM, 4,3 a 9,8 min por rodada (p50 5,9 min), em ~25
chamadas. Pelo horário, em 25/11 16:00: 4,7 min numa execução só, dos quais 255 s procurando as
chaves e 23 s fechando. O tempo total ficou na mesma faixa; o que mudou foi onde ele é gasto.
Uma rodada só não basta para concluir.

- **[C]** O fechamento em si caiu: 23 s para fechar o lote, contra 140 a 234 s da maior chamada de
  cada rodada da VM. É o efeito do lote aberto (TS-5567): o pagamento entra no lote quando chega, e
  fechar vira atualizar o vigente.
- **[C]** O ganho foi consumido pela consulta das chaves (255 s sem achar nenhum pagamento sem
  lote). Em 24/11 20:45 ela respondeu em menos de 2 s.
- **[H]** Com a consulta das chaves rápida, a rodada do 15 ficaria perto de 30 s.
- **Em porcentagem (uma rodada só):**
  - **[C]** Rodada inteira: 281 s contra a mediana de 354 s, 21% a menos. Dentro da variação da
    VM: 9% mais lenta que a melhor rodada (258 s) e 52% mais rápida que a pior (588 s).
  - **[C]** Fechamento em si: 23 s contra a mediana de 153 s da maior chamada por rodada, 85% a
    menos (84% a 90% na faixa de 140 a 234 s). A VM criava 2 ou 3 lotes por rodada; o horário
    fechou 1.
  - **[H]** Com a consulta das chaves rápida: ~30 s contra 354 s, ~90% a menos.
- **[H]** Parte do custo mudou de lugar: juntar os pagamentos agora acontece na chegada de cada um,
  ao longo do dia. Falta medir a entrada no lote aberto para a comparação ficar completa.
- **[C]** Tempo não era o objetivo principal da tarefa 13 (`tasks/13-closing-design.md`, seção 1):
  o objetivo é fechar dentro da cessão, por horário por produto, sem a varredura da VM.

## Rodada das 16:00 do produto 15, passo a passo [C]

| UTC | O quê |
| --- | --- |
| 19:00:01 | o worker começa `fechar_lotes_do_produto_por_horario(15)` |
| 19:00:01 → 19:04:17 | consulta das chaves: 255 s, sem nenhum pagamento sem lote (os pagamentos já estavam no lote aberto) |
| 19:04:17 | pedido de fechamento da chave do originador 19, fundo 3, origem `PPV_baixa_ordinaria_padrao`, por `agendamento_fechamento_por_horario` |
| 19:04:17 → 19:04:40 | o worker de fechamento fecha o lote aberto `b68ac682…`: 22,7 s, espera na fila de 11 ms, 1ª tentativa |
| 19:04:40 | aviso do compromisso de saldo (ver "Fora do fechamento"); lote em `pendente` |
| 19:04:42 | `"Fechamento de lotes por horário concluído"`: 1 fechada, 0 falhas |
| 19:04:43 → 19:05:11 | atualização de status dos contratos do lote (28 s) |
| no mesmo trace | `esteira_baixar` roda (3 s) |

## Ponto de atenção: a consulta das chaves

- **[C]** `_chaves_com_pagamento_sem_lote_apto_query` (`cessao/api/liquidacao/refact.py:2848`,
  commit `d28b83a`) junta pagamento, processo, parcela, contrato e configuração do produto, sem
  janela de data, e roda antes de qualquer pedido de fechamento.
- **[C]** Limites: `statement_timeout` de 480 s (`FAKE_BATCH_CLOSING_STATEMENT_TIMEOUT_MS`, padrão
  do código; não está no values do argocd; Parameter Store não conferido) e orçamento de 480 s da
  execução (`ORCAMENTO_FECHAMENTO_POR_HORARIO_SEGUNDOS`). Acima disso o banco cancela a consulta e
  a rodada daquele horário não fecha nada.
- **[C]** A rodada das 16:00 usou 255 s dos 480 s; a de 24/11 20:45 levou 1,9 s no total.
- **[H]** A diferença vem da carga do banco às 16h ou do plano escolhido pelo Postgres. Validar:
  comparar as rodadas das 17:00, 18:00 e 20:45 e, se a lentidão repetir, o `EXPLAIN` na réplica.
- Se repetir: proposta de card para a próxima sprint, pelo `task-shaping`.

## Fora do fechamento [C]

- **Compromisso de saldo:** `"Nao foi possivel registrar o compromisso de saldo do lote; ele nao
  sera descontado do disponivel da conta."` é tolerado: o fundo não tem conta vinculada de
  conciliação, e o lote não é descontado do disponível da conta. De 24/11 21:00 a 25/11 19:10 UTC,
  24 avisos:

  | Fundo | Produto | Avisos |
  | --- | --- | --- |
  | 869 | 1703 | 6 |
  | 506 | 1145 | 5 |
  | 506 | 1143 | 4 |
  | 26 | 1901 | 4 |
  | 770 | 1571 | 4 |
  | 3 | 15 | 1 |

  **[H]** As contas se cadastram pela tela da TS-5925, que ainda espera as roles no Azure.
- **Worker de fechamento:** 6 `"Warm shutdown"` no `platform-cessao-fake-batch-closing-worker`
  entre 24/11 23:50 e 25/11 00:48 UTC, durante a correção da variável duplicada (argocd `1ff0a57`)
  e o deploy da TS-5773; nenhum depois. A troca de pods a cada ~5 min acabou.
- Nenhum `error` da cessão em produção de 18:55 a 19:10 UTC; só o aviso acima.

## Pendentes

- Execução da VM das ~17h de Brasília: o produto 15 não pode aparecer em
  `"Criar lote de liquidacoes - payload"`; esperados 4, 80, 81, 581 e 1406.
- Rodadas das 17:00, 18:00 e 20:45 do produto 15, com a duração da consulta das chaves.
- Se a consulta das chaves repetir a lentidão: `EXPLAIN` na réplica e proposta de correção.
- Custo da entrada no lote aberto ao longo do dia (produto 15), para comparar o custo total com a VM.

## Consultas para repetir

- Rodadas: `env:production service:platform-cessao* "Fechamento de lotes por horário concluído"`,
  com `@produto_id`, `@duracao_ms` e `@qtd_*`.
- Agendador: `"Agendamentos despachados"` (`@qtd_disparados`, `@qtd_falhas`, `@qtd_perdidos`,
  `@qtd_presas`).
- Consulta das chaves: spans do trace da rodada agrupados por `resource_name`, soma de `@duration`
  (nanossegundos); a consulta começa por `SELECT CASE WHEN ( produto_config.agrupamento_lote_liquidacao`.
- Compromisso de saldo: a mensagem acima, agrupada por `@fundo_id` e `@produto_id`.
- Worker: `env:production "Warm shutdown"`, agrupado por `kube_deployment`.
- VM: `"Criar lote de liquidacoes - payload"`, contando `'produto_id': N` por hora de Brasília.
- Linha de base da VM: spans `service:platform-cessao operation_name:flask.request
  resource_name:"POST /liquidacao/" @http.client_ip:<IP da EC2 de automações>` (lista, não
  agregado) e logs do payload no mesmo período; casar cada span com o primeiro log do mesmo `host`
  entre o início e o fim da chamada; agrupar por produto em rodadas (intervalo de menos de 20 min).
