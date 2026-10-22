# GMUD — TS-5377: fechamento de lote fake assíncrono pela tela

> **Status (22/10/2026):** já executada em produção em 19/10/2026; registrar
> como retroativa. Falta: testes dos três commits (orquestrador), confirmar a
> prioridade, colar o link do Jira, e os itens "a confirmar" marcados abaixo.
> A fase 1 de robustez (subiu em 20/10) tem GMUD própria:
> [gmud-ts-5377-fase1.md](gmud-ts-5377-fase1.md).

Tipo: Mudança não programada (já executada em 19/10/2026)

## Summary

platform-cessao, BFF, Portal e argocd: fechamento de lote fake pela tela passa
a ser assíncrono, em fila dedicada

## Descrição

**Contexto**
- **Problema (30 dias até 09/10/2026, Datadog):** o fechamento pela tela
  (`POST /liquidacao/`) esperava o lote ser criado. Nas respostas 200 o p95 foi
  de 7,1 min; houve 71 erros 500 (49 deles pela trava de 10 min expirando, com o
  lote já criado) e 89 erros 429 por clique repetido. O BFF desiste em 120 s e
  o operador não sabia se o lote fechou. Fonte e consultas:
  `evidencias/fechamento-lote-datadog-2026-10-09.md`.
- **Como foi para produção:** em 19/10/2026, na `release/20261019` da
  cessão (PR #2670). A release levou também a TS-5207, de outro dev.

**O que muda**
- **platform-cessao** (PR #2675, dentro da PR #2670; merge `f19ef2cef`, imagem
  `prod-f19ef2c`):
  - rotas `POST /liquidacao/fake-batches/close` (responde 202 na hora, com a
    chave da linha e o status "em fechamento") e
    `POST /liquidacao/fake-batches/close/status` (situação de cada linha);
  - o fechamento roda na task `close_fake_batch`, na fila dedicada
    `fake_batch_closing_celery` (roteada em `app_factory.py`);
  - cada linha tem uma trava no Redis (`liquidacao:fake-batch-closing:lock:*`,
    validade de 300 s, renovada enquanto a task roda) e um resultado
    (`...:result:*`, 600 s); a proteção contra fechar em dobro continua no
    banco, `liquidacao_lote_id IS NULL`;
  - os pagamentos do grupo entram no lote num único UPDATE, só com a cessão do
    contrato finalizada (`cadastrado`); se a linha tiver lote vigente aberto,
    ele é fechado junto;
  - `entrypoint.sh`: `INICIAR_CONSUMER=0` deixa um worker dedicado sem o
    consumer do RabbitMQ; a fila nova entra na lista padrão de filas.
- **BFF** (PR #210; merge `fe2bee2`, imagem `prod-fe2bee2`): rotas
  `POST /operations/liquidation/fake-batches/close` e `/close/status`,
  conferindo se o produto da linha é do usuário. A rota existente
  (`consolidate`) passa a fazer a mesma conferência de produto (403 se o
  produto não for do usuário).
- **Portal** (PR #225; merge `d23eaef6`, imagem `prod-d23eaef`, as três marcas): as
  linhas de lote fake agrupadas por origem fecham pelo fluxo novo; a célula
  mostra "em fechamento" e consulta a situação até concluir. Linhas agrupadas
  por remessa (`proc:`) seguem no fluxo atual (`consolidate`).
- **Argocd** (`platform-cessao-argocd`, PR #7, commit `61ecc97`): deployment
  novo `fake-batch-closing` em `asgard-production` (1 pod, 3 GiB de limite,
  `CELERY_WORKER_QUEUES=fake_batch_closing_celery`, `INICIAR_CONSUMER=0`).
  Pede concorrência 2, mas o pod sobe com 16 (ver Risco). É o **único**
  consumidor da fila em produção: os outros workers têm a lista de filas fixa
  no values e não a incluem. O `viva-production` **não** recebeu o worker.

**O que não muda**
- `POST /liquidacao/` e quem o usa fora da tela (Atlas, varredura, fechamento
  automático e agendado).
- Banco: sem migration. Variável nova: nenhuma obrigatória.

## Prioridade

Medium

## Link Tarefa

<link do Jira da TS-5377>

## Risco

Médio. O que pode dar errado, o que acontece e o que segura. O que a fase 1
(GMUD da fase 1, 20/10) já corrigiu está dito em cada item.

- **Worker de produção com concorrência 16, não 2 [C, Datadog]:** o values pede
  2; o pod sobe com `CELERY_WORKER_CONCURRENCY=16` (log de partida em todas as
  versões, 19/10 21:45 UTC em diante). Causa provável, a confirmar: o
  `entrypoint.sh` exporta as variáveis do Parameter Store por cima das do pod.
  Efeito: o limite de 2 fechamentos simultâneos, que protegia o banco primário,
  não vale; 16 processos dividem 3 GiB. Observado em 20/10 14:29 UTC: pico de 13
  fechamentos juntos, 1,92 GiB de 3 GiB, sem reinício. Decisão do usuário em
  20/10: 16 fica como padrão por enquanto; a proteção passa a vir dos limites
  de tempo da fase 1.
- **Espera por trava de outra transação [C]:** em 20/10, 14:28–14:29 UTC, 11
  fechamentos do fundo 209 ficaram até 25 s parados no UPDATE; terminaram todos
  no mesmo instante, sinal de uma trava liberada uma vez. Só atraso, sem falha.
  Sem limite de espera na versão desta GMUD; a fase 1 pôs `lock_timeout`
  (ver a GMUD da fase 1 sobre esperas maiores que o limite, que se repetiram
  em 21/10).
- **Falha sem aviso (código desta GMUD, revisão de 20/10) [C no código]:** a
  mensagem expirava na fila em 300 s (R18), um pod morto no meio do fechamento
  não devolvia a mensagem (R19), o soft limit da task virava "Erro
  inesperado" (R17), o vigente fechado podia ficar sem esteira (R9) e o
  resultado podia ser sobrescrito (R14). Em produção nenhum aconteceu (28
  pedidos, 28 fechados, ver Evidências). A fase 1 tratou todos.
- **Redis sem timeout [C no código]:** Redis inacessível prendia os 4 processos
  do uWSGI da API (R13). Corrigido na fase 1 (cliente com 2 s).
- **Deploy no meio de um fechamento (R3), não corrigido [C no código]:** o
  `entrypoint.sh` roda o Celery como filho do bash (PID 1) e o values não define
  `terminationGracePeriodSeconds`; o Celery não recebe o sinal de desligamento e
  o pod é morto. Sem perda de dado (o UPDATE é desfeito e a linha volta a ficar
  disponível), mas o operador pode ter de fechar de novo. Nenhum deploy pegou um
  fechamento em andamento, então o reenvio por `acks_late` da fase 1 não foi
  visto em produção (a confirmar).
- **Regra de entrada no lote mais restrita (D9, pedida pelo negócio):** pelo
  fluxo novo, pagamento de contrato com a cessão não finalizada não entra no
  lote. A listagem ainda mostra a linha (R7, em aberto): pode aparecer linha
  "fechável" que fecha parcial ou responde "nenhum pagamento apto". Em produção:
  zero casos até 22/10.
- **Permissão no BFF:** a conferência de produto é o único controle das rotas
  novas. O bug B9 (parceiro sem `internal_id` vê todos os produtos) estava em
  aberto em 19/10; se continua depois da reestrutura do BFF (TS-5394, o escopo
  agora vem de `scope.assignment_product_ids`): a confirmar.
- **Ordem real do deploy, a inversa da segura [C, Datadog]:** o Portal subiu às
  21:37 UTC, o BFF às 21:38, a API da cessão às 21:39 e o worker só às 21:45.
  Houve ~2 min com o Portal chamando rotas que a cessão ainda não tinha (404) e
  ~6 min com a rota aceitando pedido sem consumidor. Sem efeito: o primeiro
  pedido de fechamento foi em 20/10, 14:28 UTC (e o primeiro `close/status`,
  12:26 UTC).
- **Viva sem worker [C no argocd, Datadog]:** a cessão do Viva recebeu a imagem
  nova em 19/10 21:45 UTC sem worker nem fila. Sem Portal lá, nenhum dos 91
  pedidos de fechamento registrados até 22/10 chegou a ela (todos na cessão
  principal). Se um pedido chegasse, ficaria na fila sem consumidor; a confirmar
  se a fila do Viva é a mesma da principal.
- **A release levou a TS-5207, de outro dev:** reverter a release inteira
  (`f19ef2cef`) desfaz o trabalho dele; ver o Rollback.

## Impacto

- **Tela de lotes de liquidação (aba lotes fake):** o clique responde na hora; a
  linha mostra "em fechamento" e depois o resultado. Some a espera de minutos, o
  429 por clique repetido e o 500 com lote criado.
- **Banco:** cada fechamento vira um UPDATE por grupo, em vez de buscar os ids
  no Python. A concorrência prevista era 2; na prática é 16.
- **Infra:** um pod novo em produção (worker de fechamento) e uma fila nova no
  RabbitMQ; chaves novas no Redis, com validade de até 1 h.
- **Deploy:** sem indisponibilidade da tela, sem migration. Os workers da cessão
  reiniciam no deploy da imagem.

## Plano de implantação

Passos **como foram feitos** em 19/10/2026 (horários em UTC; os do git estavam
em -03:00). A ordem real foi Portal, BFF, cessão, worker.

1. **PRs aprovadas e mescladas.** 21:11 resolução de conflitos com a release
   (`8ac428fb7`); 21:18 PR #2675 na `release/20261019`; 21:20 BFF #210 e Portal
   #225 na `master`; 21:26 release #2670 na `master` da cessão (merge
   `f19ef2cef`, por outro dev). Conferido: a imagem `prod-f19ef2c` existe.
2. **Portal e BFF (argocd, 21:34:59 e 21:35:00).** Tags `prod-d23eaef` (três
   marcas, commit `64657e5`) e `prod-fe2bee2` (commit `eeecd2a`).
   - Conferido (Datadog, logs por `version`): Portal na nova versão a partir de
     21:37:17 nas três marcas; BFF a partir de 21:38:30.
3. **Cessão (argocd, 21:38:11).** `asgard-production` com `prod-f19ef2c` (commit
   `ef04c0d`, outro dev); `viva-production` às 21:43:04 (commit `6170225`).
   - Conferido: primeiro log da API em `prod-f19ef2c` às 21:39:11; Viva às
     21:45:13.
4. **Worker de fechamento (argocd, PR #7, 21:43:06; merge 21:44:40).** Cria o
   deployment `fake-batch-closing` só em `asgard-production`.
   - Conferido: pod novo, primeiro log 21:45:17; worker conectado ao broker às
     21:45:27, escutando só `fake_batch_closing_celery`, concorrência 16.
     Contagem de consumidores na fila no painel do RabbitMQ: a confirmar (sem
     registro).
5. **Primeiro uso real.** 20/10, 12:26:39 UTC, primeira chamada a `close/status`
   (tela aberta); 14:28:41 UTC, primeiro pedido de fechamento; 14:29:07 UTC,
   primeiro "Fechamento de lote fake concluído", `closed`.
6. **Acompanhamento** pelo roteiro
   `evidencias/acompanhamento-fechamento-assincrono.md`: pedidos × conclusões,
   descartes, falhas, trava perdida. Resultado nas Evidências.

## Plano de Rollback

Vale para **hoje (22/10/2026)**. Voltar a imagem da cessão para a anterior
(`prod-3ea7d5f`) **não serve**: desfaria também a fase 1 da TS-5377, a TS-5383
(lotes reais), o hotfix de pagamentos pelo lote (`prod-bcf8447`), a TS-5207 e a
onda 6 de outro dev (`prod-fb6f409`, com `CELERY_MAX_MEMORY_PER_CHILD`). O
caminho é `git revert` dos merges e deploy novo. Testado em 22/10 numa cópia
descartável do código atual:

1. **Portal (primeiro).** O `git revert -m 1 d23eaef6` **não aplica mais**: a
   reestrutura do Portal (TS-5394) moveu os arquivos e dá conflito em 8.
   Ajuste manual na estrutura nova: as linhas por origem voltam a fechar pelo
   `consolidate` (rota que continua no BFF) e sai a consulta de situação.
   Deploy nas três marcas (`apl-credit-whitelabel-argocd`). Conferir: nenhuma
   chamada a `fake-batches/close` no BFF e chamadas a `consolidate`.
2. **BFF: não reverter.** As rotas novas ficam sem uso. O `git revert -m 1
   fe2bee2` dá conflito em `business.py` e `viewer.py` e **desfaria também a
   conferência de produto do `consolidate`** (correção de segurança, B5). Se
   precisar tirar as rotas, remover só elas, à mão.
3. **Esperar esvaziar.** Sem pedido em andamento: no Datadog, "solicitado" =
   "concluído" por `job_id`; no RabbitMQ, a fila `fake_batch_closing_celery`
   com 0 prontas e 0 sem confirmação. Prazo máximo: 10 min (`time_limit` da
   task é 600 s; o maior fechamento observado levou 52 s).
4. **Argocd: remover o worker, antes da imagem.** `git revert -m 1 fc91749`
   (PR #7); aplica limpo e tira 49 linhas de `asgard-production`. Se a imagem
   sem `INICIAR_CONSUMER` subir com o deployment ainda lá, o worker dedicado
   sobe também o consumer do RabbitMQ (aconteceu no sandbox em 14/10).
5. **Cessão: reverter os dois merges, nesta ordem, e fazer deploy.** Primeiro a
   fase 1 (PR #2683, `8c7870222`), depois esta (PR #2675, `7c739f0eb`).
   - Aplica limpo, exceto `entrypoint.sh`. Resolver tirando o bloco
     `INICIAR_CONSUMER` e `fake_batch_closing_celery` da lista padrão, e
     **mantendo** `--max-memory-per-child` (onda 6) e a fila da Dayvale (TS-5207).
   - **Não reverter** a PR #2684 (pagamentos pelo lote real): é independente do
     fechamento (repository, service e viewer).
   - Código do fechamento e testes ficam isolados em `refact.py`,
     `fake_batch_closing.py`, `schema.py`, `viewer.py`, `app_factory.py`,
     `tarefas.py`; nada de outra equipe depende deles.
   - Subir a tag nova em `asgard-production` **e** em `viva-production`
     (a tag de cada um é trocada à parte).
6. **O que fica para trás:**
   - Fila `fake_batch_closing_celery` no RabbitMQ, com eventuais mensagens: sem
     `expires`, ficam até alguém consumir ou apagar. Pedir ao time de infra
     para apagar a fila depois do passo 3.
   - Chaves no Redis (`liquidacao:fake-batch-closing:lock:*` e `:result:*`):
     vencem sozinhas em até 1 h e o código antigo não as lê.
   - Lotes já criados pelo fluxo novo são lotes normais; seguem a esteira.
7. **Efeito do rollback:** a tela volta ao comportamento antigo (espera de
   minutos, 429 em ~11,7% dos cliques e 500 em ~4,9% dos fechamentos, medidos
   nos 30 dias antes de 19/10).
8. **Sem deploy:** não há como desligar o fluxo só por configuração. Zerar o
   worker acumula pedidos na fila; não usar.

## Evidências de validação

- **Testes:** <preenchido pelo orquestrador>
  - Commits da GMUD: cessão `f19ef2cef`, BFF `fe2bee2`, Portal `d23eaef6`.
- **Produção (Datadog, `env:production`, UTC):**
  - versões por `version`/`@version`: Portal `prod-d23eaef` desde 19/10
    21:37:17 (três marcas); BFF `prod-fe2bee2` desde 21:38:30; cessão
    `prod-f19ef2c` desde 21:39:11; worker de fechamento desde 21:45:17. O Portal
    e o BFF **não** entraram em 20/10 12:26, como estava anotado: essa hora é a
    primeira chamada de status, não a subida;
  - ancestralidade (`git merge-base --is-ancestor`): `7c739f0eb`, `8ac428fb7` e
    `cb071c2d6` estão em `f19ef2cef`; `9b073e2` em `fe2bee2`; `c8fbd26c` em
    `d23eaef6`;
  - de 19/10 21:39 a 20/10 23:06, versão `prod-f19ef2c`: **28 pedidos e 28
    concluídos, todos `closed`** (cada `job_id` tem 1 "solicitado" e 1
    "concluído"), 53.555 pagamentos, 8 produtos; mediana de 7,4 s, p95 de 24,4 s,
    máximo de 27,6 s (maior grupo, 29.792 pagamentos); 5 fechamentos acima de 20
    s (a espera por trava);
  - zero "descartado", falha, trava perdida ou erro na esteira dessas
    mensagens; spans `close_fake_batch` todos `ok`;
  - rotas: cessão `close` 202 (28 chamadas, p95 28 ms), `close/status` 200 (58);
    BFF sem 4xx/5xx nas rotas de lote fake (só um 401 de sessão expirada);
  - pod do worker sem reinício fora dos deploys; os 6 avisos de cada partida são
    o aviso do Celery por rodar como root e a mensagem de variáveis OK;
  - comparação com a rota antiga: `evidencias/fechamento-assincrono-datadog-2026-10-20.md`
    (clique de 5,0 s para 0,25 s; 429 de 11,7% para 0; 500 de 4,9% para 0).
- **Sandbox (14/10/2026, 19:08 UTC)**, `sand-e7e26d6` (cessão) e `sand-4b5309a`
  (BFF): clique no Portal, 202 em 270 ms no BFF (trace
  `6acfd32b000000004c2dd9b4a6d3fa9f`) e 99 ms na cessão; worker dedicado
  concluiu com `closed`, 2 pagamentos, 1 lote, 424 ms; o lote seguiu a esteira.
- **Fora desta GMUD, sem relação com a mudança:** `GET /liquidacao/lotes/reais`
  com 500 por `statement_timeout` (tarefa 12, tratada na TS-5383) e o erro
  antigo "Erro na esteira 'NoneType' object is not iterable" (B18, desde 06/10).
