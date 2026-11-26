# Fechamento por horário em produção — 25/11/2026

Acompanhamento da B1 do [guia da release de 24/11](../tasks/13-post-deploy-switch-on-guide.md)
(fechamento por horário, TS-5570) nos produtos 15 e 1604, ligados em 24/11.

- **Fontes:** Datadog (logs e APM), `env:production`; código da cessão no commit `d28b83a`, o que
  está em produção.
- **Consulta feita em:** 25/11/2026, ~19:10 UTC; atualizada em 26/11, ~14:05 UTC. Horários em UTC;
  Brasília é UTC−3.
- **Atualizar:** a cada rodada do produto 15 (17:00, 18:00 e 20:45 de Brasília), na tabela das
  rodadas e nos pendentes.

## Versão em produção [C]

Cessão `prod-d28b83a` desde 25/11 00:46 UTC (argocd `d389626`): a release de 24/11 mais a TS-5773
(`851e7f3cf`, fila `liquidacao.atraso` declarada no consumer; `90817566f`, pagamento parcial de
parcela fechada).

Desde 25/11 21:57 UTC, `prod-c6f88ce` (argocd `6b5dba8` e `7459a6d`), a release de 25/11 de outro
dev: remessa do Dayvale (TS-5498) e ocorrência 91 do CNAB (TS-5845). Não muda
`cessao/api/liquidacao/refact.py` nem `cessao/framework/liquidacao/` (`git diff d28b83a c6f88ce`):
o fechamento é o mesmo código.

## Rodadas [C]

Fonte: `"Fechamento de lotes por horário concluído"`. "Consulta das chaves" é o span `postgres` da
consulta que lista os pagamentos sem lote aptos (ver o ponto de atenção).

| Brasília | Produto | Chaves | Com lote aberto | Pagamentos sem lote | Fechadas | Falhas | Duração | Consulta das chaves |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 24/11 20:45 | 15 | 0 | 0 | 0 | 0 | 0 | 1,9 s | — |
| 25/11 16:00 | 1604 | 0 | 0 | 0 | 0 | 0 | 0,05 s | — |
| 25/11 16:00 | 15 | 1 | 1 | 0 | 1 | 0 | 281 s | 255 s |
| 25/11 17:00 | 15 | 0 | 0 | 0 | 0 | 0 | 233 s | 233 s |
| 25/11 18:00 | 15 | 0 | 0 | 0 | 0 | 0 | 5,2 s | 5,2 s |
| 25/11 20:45 | 15 | 0 | 0 | 0 | 0 | 0 | 1,9 s | 1,8 s |

Agendador (`"Agendamentos despachados"`): 25/11 19:00:01 UTC, 3 disparos (1604, 15 e o backstop,
que roda a cada :00 e :30); 20:00:01 e 21:00:01 UTC, 2 disparos cada (15 e o backstop). Em todos,
0 falhas, 0 perdidos, 0 presos. De 25/11 21:30 a 26/11 14:00 UTC, 35 despachos e 34 disparos, sem
falha nem presa; 1 perdido, às 26/11 12:16:03 (ver "Ponto de atenção: o beat para às 12:00 UTC").

**VM das 17h de 25/11 [C]:** 80 payloads de 20:01 a 20:24 UTC: produto 4 (34), 80 (33), 1406 (6),
81 (5) e 581 (2). O 15 não aparece.

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
- **[C]** Em 25/11 a consulta levou 255 s às 16:00, 233 s às 17:00, 5,2 s às 18:00 e 1,8 s às
  20:45 (Brasília), nas quatro vezes sem achar pagamento sem lote. A rodada de 24/11 20:45 levou
  1,9 s no total.
- **[H]** A lentidão acompanha o horário de carga do banco (16h e 17h; a VM roda às 17h), não o
  plano fixo da consulta. Validar com o `EXPLAIN` na réplica nesses horários, e conferir as
  sessões ativas do banco às 16h no Datadog.
- Se repetir: proposta de card para a próxima sprint, pelo `task-shaping`.

## Ponto de atenção: o beat para às 12:00 UTC

- **[C]** Em 25/11 e em 26/11, o `platform-cessao-beat` registrou às 12:00:00 UTC (09:00 de
  Brasília) `"Scheduler: Sending due task contrato_registro_baixa_task"` e não registrou mais nada até
  `"Agendamentos despachados"` às 12:16:04 e 12:16:03. Nos dois dias, o despacho das 12:16 teve
  `qtd_vencidos` 1, `qtd_disparados` 0 e `qtd_perdidos` 1. É a ocorrência das 12:00 do backstop
  (a das 12:30 disparou normalmente).
- **[C] Por que vira perdido:** o beat tem um laço só. O `tick` de `SchedulerComBanco` primeiro
  envia as entradas fixas do Celery (`super().tick()`) e só depois despacha os agendamentos do banco
  (`cessao/agendamento/beat.py`, commit `c6f88ce`). Quem é encontrado com mais de 900 s de atraso
  (`AGENDAMENTO_ATRASO_TOLERADO_SEGUNDOS`, `cessao/constants.py:12`) vira `perdida`
  (`cessao/agendamento/service.py:497-498`) e não dispara; o `agora` é tirado no início do despacho
  (`service.py:540`), por isso o atraso conta a parada inteira.
- **[H]** O tempo vai no envio da `contrato_registro_baixa_task` (`cessao/schedule/registro.py:40`,
  `crontab(hour=12, minute=0)`). De 11:59 a 12:40 UTC de 26/11, a busca
  `env:production *contrato_registro_baixa*` só acha o envio do beat; pode ser que os workers não
  registrem o recebimento. O código não roda a tarefa dentro do beat (não há `task_always_eager`).
  Validar no trace do beat das 12:00 e nos logs do broker.
- **Efeito no fechamento:** hoje nenhum, porque o 15 e o 1604 fecham às 16h ou depois. Um produto
  com fechamento por horário entre 09:00 e ~09:16 de Brasília perderia a rodada do dia, sem nova
  tentativa.
- Proposta de card para a próxima sprint, pelo `task-shaping`.

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
  De 25/11 21:10 a 26/11 14:00 UTC, nenhum aviso.
- **Worker de fechamento:** 6 `"Warm shutdown"` no `platform-cessao-fake-batch-closing-worker`
  entre 24/11 23:50 e 25/11 00:48 UTC, durante a correção da variável duplicada (argocd `1ff0a57`)
  e o deploy da TS-5773; nenhum depois. A troca de pods a cada ~5 min acabou. De 25/11 21:10 a
  26/11 14:00 UTC, 2, às 21:58:40 e 21:59:06 de 25/11: a troca de pods do deploy da `prod-c6f88ce`.
- Nenhum `error` da cessão em produção de 18:55 a 19:10 UTC; só o aviso acima. Até 21:13 UTC, mais
  62 avisos do compromisso de saldo.
- **Recuo do lote aberto:** `"Pagamento de liquidação ficou sem lote aberto"` é o recuo previsto no
  desenho do lote aberto: a entrada falha, o pagamento fica sem lote e entra no fechamento seguinte
  (`cessao/api/liquidacao/refact.py:4352` e `:4369`, commit `d28b83a`). De 24/11 21:00 a 25/11 21:13 UTC,
  119 avisos, todos com motivo `OperationalError`: produto 80 (84, de 11:01 a 19:32), 4 (26, às
  11:15) e 713 (9, às 21:00).
  - **[C] Novo desde o deploy de 24/11:** o aviso veio com o lote aberto (TS-5567, `ceadb3185`); antes
    não havia entrada no lote na chegada. O guia de 24/11 (A1) e o plano da TS-5567 (passo 4 da
    transição) já mandavam acompanhar esse evento.
  - **[C] Todos por trava:** no evento `"Entrada no lote aberto da liquidação concluída"`, os 119
    recuos têm `recuos_por_trava` (espera acima de 2 s, `LOTE_ABERTO_LOCK_TIMEOUT_MS`). Fração das
    entradas: 80, 84 em 102.103 (0,08%); 4, 26 em 16.417 (0,16%); 713, 9 em 4.032 (0,22%). Nenhum
    outro produto teve recuo.
  - **[C] Para onde foram (réplica, 25/11 ~21:30 UTC, pelos `liquidacao_uuid` dos avisos):** no 4,
    os 26 pagamentos estão em 2 lotes `concluido` criados de 20:08 a 20:12 UTC; no 80, os 84 estão
    em 2 lotes `concluido` criados de 20:14 a 20:17 UTC. Os dois pela VM das 17h. No 713, os 9
    seguem sem lote.
  - **[C]** O 713 é fechado à mão pela tela, uma vez por dia por volta das 12h de Brasília (24/11 e
    25/11, de 14:50 a 15:19 UTC), na mesma chave dos recuos (originador 1282, fundo 209).
    **[H]** Os 9 entram no fechamento de 26/11, que leva o vigente e os avulsos da chave.
  - **[C] O fechamento leva os avulsos:** o núcleo (`_close_fake_batch`,
    `cessao/api/liquidacao/refact.py:4069`, commit `d28b83a`), usado pela tela, pelo horário e pelo
    automático, marca o vigente como fechado e junta no mesmo lote todos os avulsos aptos da chave,
    de qualquer data. Os fechamentos do 713 em 24 e 25/11 passaram por ele.
  - **[C] Nenhuma entrada sem destino:** em todos os produtos, entradas = pagamentos no lote aberto +
    recuos, e cada recuo tem aviso (119 avisos, 119 recuos). Ex.: 80, 102.019 + 84 = 102.103; 4,
    16.391 + 26 = 16.417; 713, 4.023 + 9 = 4.032. No 15, as rodadas das 16h, 17h e 18h não acharam
    avulso apto.
  - **Falta cobrir:** vigente aberto ou avulso de chave que a VM não chama (ela usa uma lista fixa).
    Conferir os vigentes abertos com mais de um dia nos produtos do Mercato Libero e da Voltis.
  - **[C] De 25/11 21:10 a 26/11 14:00 UTC:** 128 recuos, todos `OperationalError` e todos com
    `recuos_por_trava`:

    | Produto | Recuos | Entradas | Fração | Quando (UTC) | Chave |
    | --- | --- | --- | --- | --- | --- |
    | 1637 | 78 | 11.244 | 0,69% | 26/11 05:12:49 | uma remessa (agrupamento por remessa, `d7668909…`) |
    | 80 | 46 | 112.368 | 0,04% | ao longo do dia | — |
    | 15 | 4 | 40.766 | 0,01% | 26/11 08:22:56 | originador 19, fundo 3, `PPV_baixa_ordinaria_padrao` |
    | 713 | 0 | 3.089 | — | — | — |

  - **[C] 1637:** os 78 vieram numa rajada da mesma remessa, ~0,4 s antes do fechamento automático
    dela (`"Remessa de liquidação fechada automaticamente"`, 05:12:49,934, origem `esteira`, 376
    esperados). É o caso da D43 numa forma mais aguda: 21% dos pagamentos da remessa recuaram.
    **[C] Réplica, 26/11 ~15:45 UTC:** os 376 pagamentos da remessa estão em 2 lotes, um por fundo e
    originador (186 e 190), em `conciliacao_manual`; nenhum solto. O fechamento da remessa levou os
    recuos para o lote dela.
  - **[C] Vigentes abertos com mais de um dia (réplica, 26/11 ~15:45 UTC):** nenhum nos produtos do
    Mercato Libero (4, 15, 80, 81, 581, 1406) nem no 713. Fora deles: 1571 (3, desde 24/11) e 1340
    (1, desde 25/11); e vigentes de fluxos antigos, com lotes `concluido` e `pendente`: 1109 (27.922,
    desde 14/05/2026), 1373 (627), 944, 977 e 911 (325, 257 e 241, desde 10/04/2024), 1213, 1212 e
    1211 (89, 70 e 66, desde 03/04/2025). Ligado ao retrato do B25 (TS-5573); não investigado aqui.
  - **[C] D9 na chegada:** de 25/11 00:46 a 26/11 ~15:00 UTC, nenhuma entrada no lote aberto achou a
    chave e deixou o pagamento de fora sem recuo (`@chaves:>0 @pagamentos_no_lote:0
    @chaves_com_recuo:0`: 0; com `@chaves_com_recuo:>0`: 247). Nos últimos 60 dias, todo pagamento
    solto na réplica é de contrato com a cessão `cadastrado` (1 exceção, contrato rejeitado e
    apagado). A D9 tardia não aparece. Detalhe em
    [13-d43-retry-and-reconciliation-design](../tasks/13-d43-retry-and-reconciliation-design.md).
  - **[C] 15:** os 4 avulsos são da chave que o horário fecha. **[H]** A rodada das 16:00 de 26/11
    deve trazer `qtd_pagamentos_sem_lote` 4 e levá-los no lote.
- **Custo da entrada no lote aberto [C]:** de 24/11 21:00 a 25/11 21:13 UTC, p95 de ~1,1 s por
  entrada no 80, no 15 e no 81 (102 mil, 38 mil e 35 mil entradas); máximo de 5,7 s. Falta a média
  para estimar o custo total do dia.
- Outros erros de 19:10 a 21:13 UTC, sem relação com o fechamento: `GET /titulo/contratos` (172,
  de 20:00 a 20:19), processamento de endosso (79), pagamento duplicado (2) e conexão fechada pelo
  cliente na listagem de lotes reais (2).

## Pendentes

- Rodadas das 16:00 e 17:00 de 26/11 do produto 15: a duração da consulta das chaves e os 4 avulsos
  de 26/11 08:22 UTC no lote.
- Na réplica, depois do fechamento manual do 713: os 9 recuos de 25/11 no lote.
- Beat parado às 12:00 UTC: confirmar a causa (trace do beat, broker) e propor o card pelo
  `task-shaping`.
- [D43](../decisions.md): desenho escrito para aprovação
  ([13-d43-retry-and-reconciliation-design](../tasks/13-d43-retry-and-reconciliation-design.md));
  validar com o negócio e propor os cards da próxima sprint.
- Consulta das chaves lenta às 16h e às 17h: `EXPLAIN` na réplica e proposta de correção (card
  para a próxima sprint, pelo `task-shaping`).
- Custo da entrada no lote aberto ao longo do dia (produto 15), para comparar o custo total com a VM.

## Consultas para repetir

- Rodadas: `env:production service:platform-cessao* "Fechamento de lotes por horário concluído"`,
  com `@produto_id`, `@duracao_ms` e `@qtd_*`.
- Agendador: `"Agendamentos despachados"` (`@qtd_disparados`, `@qtd_falhas`, `@qtd_perdidos`,
  `@qtd_presas`).
- Beat parado: todos os logs de `service:platform-cessao-beat` de 11:55 a 12:20 UTC, em ordem; a
  parada é o intervalo entre o `"Sending due task contrato_registro_baixa_task"` e o despacho seguinte.
- Recuos por produto: `"Entrada no lote aberto da liquidação concluída"` agrupado por `@produto_id`,
  contagem e soma de `@recuos_por_trava`; a chave e o `liquidacao_uuid` estão no aviso do recuo.
- Consulta das chaves: spans do trace da rodada agrupados por `resource_name`, soma de `@duration`
  (nanossegundos); a consulta começa por `SELECT CASE WHEN ( produto_config.agrupamento_lote_liquidacao`.
- Compromisso de saldo: a mensagem acima, agrupada por `@fundo_id` e `@produto_id`.
- Worker: `env:production "Warm shutdown"`, agrupado por `kube_deployment`.
- VM: `"Criar lote de liquidacoes - payload"`, contando `'produto_id': N` por hora de Brasília.
- Linha de base da VM: spans `service:platform-cessao operation_name:flask.request
  resource_name:"POST /liquidacao/" @http.client_ip:<IP da EC2 de automações>` (lista, não
  agregado) e logs do payload no mesmo período; casar cada span com o primeiro log do mesmo `host`
  entre o início e o fim da chamada; agrupar por produto em rodadas (intervalo de menos de 20 min).
