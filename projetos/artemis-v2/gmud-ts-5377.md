# GMUD — TS-5377: fechamento de lote fake assíncrono pela tela

> **Status (15/10/2026): não submeter ainda.** A revisão antes de produção
> ([tarefas/03-revisao-pre-producao.md](tarefas/03-revisao-pre-producao.md))
> achou bloqueios (R1 a R6). Este texto já está corrigido; falta o PR do
> worker de produção e as correções.

Tipo: Mudança programada

## Summary

platform-cessao, BFF, Portal e argocd: fechamento de lote fake pela tela passa
a ser assíncrono, em fila dedicada

## Descrição

**Contexto**
Hoje o fechamento de lote pela tela de lotes de liquidação chama
`POST /liquidacao/` e espera o lote ser criado. Em 30 dias até 09/10/2026 essa
rota teve p95 de 7,1 min nas respostas 200, 71 erros 500 (49 deles pela trava
de 10 min expirando, mesmo com o lote criado) e 89 erros 429 por clique
repetido. O BFF desiste em 120 s e o operador não sabe se o lote foi fechado.

**O que muda**
- **Cessão:** rotas novas `POST /liquidacao/fake-batches/close` (responde 202
  na hora, com a chave da linha e o status "em fechamento") e
  `POST /liquidacao/fake-batches/close/status` (situação de cada linha). O
  fechamento roda na task `close_fake_batch`, na fila dedicada
  `fake_batch_closing_celery`. Cada linha da tela tem uma trava no Redis com
  validade renovada enquanto a task roda; a proteção contra fechar em dobro
  continua no banco (`liquidacao_lote_id IS NULL`). Os pagamentos do grupo
  entram no lote num único UPDATE, só com a cessão do contrato finalizada
  (`cadastrado`). Se a linha tiver lote vigente aberto, ele é fechado junto.
- **BFF:** rotas `POST /operations/liquidation/fake-batches/close` e
  `/fake-batches/close/status`, conferindo se o produto da linha é do usuário.
  A rota existente de fechamento (`consolidate`) passa a fazer a mesma
  conferência de produto.
- **Portal:** as linhas de lote fake agrupadas por origem fecham pelo fluxo
  novo; a célula mostra "em fechamento" e consulta a situação até concluir.
  Linhas agrupadas por remessa (`proc:`) continuam no fluxo atual.
- **Argocd:** deployment novo do worker dedicado (1 pod, concorrência 2) em
  asgard-production e vivo-production, igual ao que já roda no sandbox. É o
  **único** consumidor da fila: os workers de produção têm a lista de filas
  fixa e não a incluem.

**O que não muda**
`POST /liquidacao/` e quem o usa fora da tela (Atlas, automações externas,
fechamento automático e agendado) seguem iguais. Sem migration.

## Prioridade

Medium

## Link Tarefa

<link do Jira da TS-5377>

## Risco

Médio.

- **Regra de entrada no lote mais restrita:** pelo fluxo novo, pagamento de
  contrato com a cessão ainda não finalizada não entra no lote; fica na
  listagem até a cessão terminar. É a regra pedida pelo negócio, mas muda o
  que o operador vê.
- **Dependência do Redis:** a situação "em fechamento" fica no Redis. Se ele
  estiver indisponível, o pedido responde erro, sem enfileirar, sem fechar
  nada e sem gravar dado errado. Se a conexão ficar pendurada (sem recusa), a
  resposta só vem pelo corte do BFF (504).
- **Fila dedicada:** o worker novo é o único consumidor em produção. Se ele
  não subir, nenhum fechamento acontece: o pedido fica "em fechamento" por
  até 5 min e é descartado. Por isso o front só sobe depois de conferido o
  consumidor (passo 3).
- **Fechamento em dobro:** coberto pela trava por linha e, no banco, pelo
  `liquidacao_lote_id IS NULL`; o pedido repetido para a mesma linha recebe
  409 ("Lote já está em fechamento"). Mensagem que ficar na fila além da
  validade da trava é descartada, para não fechar uma linha pedida de novo.
- **Deploy com fechamento em andamento:** um fechamento que estiver rodando
  no worker durante o deploy é interrompido e a linha volta a ficar
  disponível; o operador fecha de novo. Fazer o deploy fora do horário de
  fechamento.
- Mudança restrita à tela; os outros chamadores do fechamento não são
  afetados.

## Impacto

- **Tela de lotes de liquidação (aba lotes fake):** o clique em fechar
  responde na hora; a linha mostra "em fechamento" e depois o resultado. Some
  a espera de minutos, o 429 por clique repetido e o 500 com lote criado.
- **Banco:** cada fechamento vira um UPDATE por grupo, em vez de buscar os ids
  no Python e devolvê-los num UPDATE com a lista inteira. A concorrência fica
  limitada a 2 fechamentos simultâneos pela fila dedicada.
- **Infra:** um pod novo em produção (worker de fechamento de lote fake).
- Sem indisponibilidade das telas no deploy, sem migration, sem variável nova
  no Parameter Store (as variáveis do worker ficam no values do argocd).

## Plano de implantação

1. Merge e deploy da platform-cessao em produção. Conferir pods na nova
   versão e healthcheck ok.
2. Só depois que o tag de produção apontar para a imagem nova: merge e sync do
   PR do platform-cessao-argocd que cria o worker. (Worker antes da imagem
   nova roda o código antigo e sobe o consumer do RabbitMQ.)
3. Conferir que a fila `fake_batch_closing_celery` tem 1 consumidor (painel
   do RabbitMQ ou `celery -A cessao.app.celery inspect active_queues` no pod
   do worker).
4. Merge e deploy do BFF; por último, do Portal (é o que expõe o fluxo ao
   usuário).
5. Fechar um lote fake pequeno pela tela e conferir:
   - célula "em fechamento" e depois "fechado";
   - no Datadog, os logs `Fechamento de lote fake solicitado`
     (`service:platform-cessao`) e `Fechamento de lote fake concluído`
     (deployment do worker dedicado) com o mesmo `job_id`;
   - o lote criado na aba de lotes reais.
6. Acompanhar no Datadog, no restante do dia: pedidos `solicitado` sem
   `concluído` correspondente, logs `Fechamento de lote fake descartado`,
   tamanho da fila e erros nas rotas `fake-batches/close`.

## Plano de Rollback

1. Reverter o PR do Portal e fazer deploy: a tela volta a fechar pelo fluxo
   atual (`POST /liquidacao/` via BFF). As rotas novas do BFF e da cessão
   ficam sem uso e não interferem no resto.
2. Se o problema for na cessão, nesta ordem: esperar a fila esvaziar e não
   haver fechamento em andamento (até ~15 min); reverter o PR do argocd
   (remove o worker); voltar a imagem da cessão; limpar a fila
   `fake_batch_closing_celery` no RabbitMQ.
3. Se o problema for a conferência de produto na rota `consolidate`: reverter
   o PR do BFF.
4. Lotes já criados pelo fluxo novo são lotes normais e seguem a esteira; não
   há dado a desfazer.

## Evidências de validação

- **Testes automatizados (cessão, commit `cb071c2d6`):** 39 testes do fluxo
  novo passando (`test_refact_liquidacao.py`,
  `test_viewer_fake_batch_closing.py`, `test_fake_batch_closing.py`): regra de
  entrada no lote, UPDATE único, trava por linha e liberação pelo dono,
  fechamento do lote vigente, rotas 202 e status, task na fila dedicada.
  Suíte completa da cessão no mesmo commit: 4.647 testes passando, 41
  ignorados, nenhuma falha (15/10/2026).
- **Testes do BFF e do Portal (13/10, na implementação):** 106 testes do
  módulo de lotes de liquidação do BFF e 19 specs da tela e do serviço do
  Portal passando.
- **Sandbox (Datadog, 14/10/2026, 19:08 UTC)**, versões `sand-e7e26d6`
  (cessão, contém todos os commits da TS-5377) e `sand-4b5309a` (BFF, PR #209):
  - Portal → BFF `POST /operations/liquidation/fake-batches/close`: 202 em
    270 ms (trace `6acfd32b000000004c2dd9b4a6d3fa9f`).
  - Cessão `POST /liquidacao/fake-batches/close`: 202 em 99 ms; log
    `Fechamento de lote fake solicitado` (job
    `e71d048f-1e0d-4119-be59-780542407c5f`).
  - Worker dedicado (`platform-cessao-sandbox-fake-batch-closing-worker`):
    `Fechamento de lote fake concluído`, status `closed`, 2 pagamentos, 1 lote
    criado, 424 ms.
  - Na sequência, o lote seguiu a esteira (log de roteamento para a
    conciliação no mesmo trace `5489282890750753439`).
  - Consulta de situação: 3 chamadas com 200 (até 84 ms na cessão e 321 ms no
    BFF).
