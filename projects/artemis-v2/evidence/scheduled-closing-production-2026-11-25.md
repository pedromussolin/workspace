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
