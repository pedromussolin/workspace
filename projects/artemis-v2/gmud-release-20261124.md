# GMUD — release de 24/11/2026 (Artemis V2: fechamento de lotes de liquidação)

> **Status (24/11/2026):** criada no portal como GDM-374; janela de 24/11, das 17:30 às 19:30. Pendências marcadas
> "a confirmar"; testes do usuário na sandbox concluídos (A6 em 24/11).

Tipo: Mudança programada

## Início / Fim

24/11/2026, das 17:30 às 19:30 (horário de Brasília); previsão de terminar às 18:30.

## Summary

Liquidação: configuração do produto em tela e aprovação de lote antes do corte

## Descrição

**Contexto**
- A liquidação do Mercato Libero fecha lote por uma varredura externa (VM de automações),
  que sai junto com o Atlas. Esta release traz o fechamento para dentro da cessão, configurável por
  produto, e a operação passa a mexer na configuração pela tela, sem pedir ajuste no banco.
- Lote de liquidação sem pagamento quebra a esteira de baixa, a conciliação e o "aprovar" da fila
  manual; havia ~15,3 mil lotes vazios em produção (levantamento da TS-5582, novembro/2026).
- Em 09/11 um lote de 1.003.192 pagamentos (produto 80) se perdeu na esteira de baixa quando o
  worker reiniciou no meio, e ficou em `pendente` sem reenvio (TS-5737).

**O que muda**
- **apl-shared-service** ([PR #90](https://github.com/Capitalis/apl-shared-service/pull/90), `release/20261124` → `master`):
  - `POST /email-dispatches` aceita anexo em Excel montado a partir de dados tabulares (TS-5584);
  - templates dos e-mails da liquidação e destinatários padrão por template, na tabela nova
    `email_dispatch.template_recipients`; pedido sem destinatário usa os do template (TS-5585).
- **platform-cessao** ([PR #2796](https://github.com/Capitalis/platform-cessao/pull/2796)):
  - lote sem pagamento não segue na esteira, na conciliação nem no "aprovar" (TS-5582); script de
    limpeza dos vazios antigos entra no código, sem rodar (TS-5596);
  - a configuração de fechamento vira duas colunas, gatilho (quem fecha: manual, agendado,
    automático) e agrupamento (como junta) (TS-5583);
  - agendador em tabela: o beat (processo que dispara as tarefas agendadas) passa a ler os
    agendamentos do banco, grava cada execução e o histórico de alterações; rotas `/agendamento`
    (TS-5569);
  - fechamento por horário, por produto, pelo agendador (TS-5570); os 12 agendamentos nascem
    desligados;
  - resumo diário dos lotes por e-mail, com Excel, e aviso quando um horário de fechamento fica
    depois do corte da conciliação (TS-5585); o job nasce desligado;
  - lote aberto passa a ser o padrão de todos os produtos, inclusive os de gatilho automático
    (TS-5567);
  - API da configuração do produto (TS-5624); fora do gatilho agendado, apagar todos os horários
    de fechamento deixa o agendamento do produto inativo e sem horário: a CHECK
    `ck_agendamento_tipo_coerente` passa a aceitar cron inativo sem expressão (migration
    `a4f7c2d9e1b6`);
  - junção das migrations da release com a da master (`1f00f6aacbb7`, sem efeito no banco): a
    TS-5616 já está em produção, com a `b8e41f6c2a93`;
  - aprovar em tela um lote fechado antes das 14h, sem esperar a rotina do corte (TS-5571);
  - o gatilho automático passa a fechar pelo fluxo novo, com a tabela de remessas e um backstop a
    cada 30 min para remessa presa (TS-5572);
  - esteira de baixa nova com reentrega segura e arquivo em blocos, ligada por produto pela coluna
    `liquidacao_baixa_refact`, que nasce desligada em todos; fila própria
    `liquidacao_baixa_isolada_celery` (TS-5737);
  - sai a rotina fixa de fechamento por agendamento do beat (`liquidacao_fecha_lote_task`, 16h de
    Brasília): com a release, ela fecharia todo produto com gatilho agendado junto com o horário
    novo; produto agendado passa a fechar só pelo agendamento dele (TS-5612);
  - a liberação de contratos deixa de quebrar em título sem callbacks, que hoje deixa contratos
    presos em `liberando` e para a liberação dos seguintes (TS-5537; na sandbox desde 03/11).
- **apl-credit-whitelabel-api** (BFF, a camada entre o portal e os serviços; [PR #286](https://github.com/Capitalis/apl-credit-whitelabel-api/pull/286)): guardas de
  lote vazio (TS-5582), lote aberto (TS-5567), rotas da configuração do produto, que aceitam a lista
  de horários vazia fora do agendado (TS-5624), contrato
  do envio de e-mail com anexo (TS-5584), remoção da rota `/fake-batches/consolidate`, que o portal
  já não chama (TS-5568), e atualização do `virtualenv` de desenvolvimento por CVE (TS-5871).
- **apl-credit-whitelabel** (portal; [PR #327](https://github.com/Capitalis/apl-credit-whitelabel/pull/327)): página "Configuração do produto", com as abas
  Cessão e Liquidação (TS-5624); aprovação antes do corte (TS-5571); lote aberto (TS-5567);
  guardas de lote vazio (TS-5582).
- **Argocd** (`platform-cessao-argocd`): worker novo `liquidacao-baixa-isolada` em
  `asgard-production` (1 pod, limite de 2 CPU e 4,5 GiB, `CELERY_WORKER_QUEUES` só com a fila
  isolada, `INICIAR_CONSUMER=0`, sondas), igual ao da sandbox (`be348ed`). Tags novas nos argocds dos
  quatro serviços.

**O que não muda**
- A varredura externa segue fechando os lotes do Mercato Libero nos primeiros dias, mesmo com os
  horários por produto ligados.
- A rota legada `POST /liquidacao/` da cessão e a esteira de baixa atual (todo produto continua
  nela, porque a chave nova nasce desligada).
- A limpeza dos lotes vazios antigos não roda neste deploy; depende da revisão da DBA.
- A coluna antiga `modalidade_fechamento_lote` e as flags antigas ficam (saem depois, com o legado).

## Prioridade

High

## Link Tarefa

Filtro do Jira com as 16 tarefas (o link completo está na GDM-374): TS-5582, TS-5583, TS-5567, TS-5569, TS-5570, TS-5585, TS-5571, TS-5572, TS-5568, TS-5584, TS-5624, TS-5596, TS-5737, TS-5871, TS-5612 e TS-5537.

## Há mudança no banco?

Sim

## Risco

**Médio.**
- **6 produtos passam a fechar e enviar sozinhos** (22, 26, 27, 28, 39, 42: hoje automáticos com a
  flag `liquidacao_automatico` desligada, fecham e esperam o "liquidar") → depois da migration, o
  lote vai à administradora sem esperar o liquidar → segura: conferência da lista no dia (passo 2);
  volta por produto, sem deploy, com o gatilho `manual` na tela de configuração.
- **Produto agendado sem agendamento ligado** (a rotina fixa sai e os agendamentos de liquidação
  nascem desligados) → o produto em gatilho agendado não fecha sozinho; no principal é só o 1604
  (réplica, 24/11) → segura: ligar o horário das 16:00 do 1604 logo depois do deploy (passo 9),
  antes das 16h do dia seguinte.
- **Contratos presos em `liberando` pelo erro da TS-5537** (19 do produto 15, réplica em 24/11:
  cedente concluído, sem recompra; fora do fluxo há meses, sem reclamação) → com a correção, iriam
  para `cadastrado` na próxima baixa do produto → segura: decisão do time de mandá-los para
  `errado` (reprocessável) antes do deploy da cessão, por SQL revisado pela DBA (passo 6). O
  produto 15 não tem lote de cessão nem desembolso automáticos.
- **Migration esperando trava na `produto_config`** (inclui colunas e faz um UPDATE em todas as
  linhas) → leituras da tabela ficam na fila atrás dela; as migrations da cessão rodam numa
  transação só, sem `lock_timeout` → segura: janela às 17:30, depois do corte das 14h e da rotina
  das 16h; acompanhar o Job de migration; DBA na janela (roda o SQL do passo 6).
- **Pods novos antes do fim da migration** → leitura de coluna inexistente na `produto_config` →
  na sandbox, em 23/11, nenhum erro de coluna ou tabela inexistente durante a migration → segura:
  conferir a revisão do Alembic antes do BFF e do portal (passo 6).
- **Segundo ambiente de produção da cessão (`viva-production`)**: fica fora deste deploy e segue em
  `prod-ca52465`, sem as migrations; o principal e ele ficam em versões diferentes até lá → a
  subida dele vai em outra mudança, com o que ainda está a confirmar (banco sem acesso): o
  mapeamento das colunas novas nos produtos de lá, os agendamentos com os ids de produto do
  principal, a `APL_SHARED_SERVICE_URL` no Parameter Store que ele lê e os produtos que fecham pela
  rotina fixa das 16h (flag `baixa_por_agendamento`), que sai.
- **Disparo do agendador perdido ou travado** (sandbox, 23/11): o despacho reaproveita a
  conexão com o RabbitMQ, e depois de ~30 min parada ela é derrubada em silêncio no caminho. Sem
  confirmação de publicação, a mensagem some (execução das 17:00 UTC publicada e nunca recebida);
  com `CELERY_CONFIRM_PUBLISH=1` no beat (teste a partir das 17:43 UTC), o beat trava ~16 min esperando a
  confirmação, até a conexão cair, e o Celery republica (18:30 UTC: execução gravada, sem log de
  despacho, rodou às 18:46). Conexão nova
  funciona (16:30, 17:30 e 18:00 UTC). No backstop, disparos perdidos; num fechamento por horário
  (nasce desligado), o lote do dia não fecharia → segura: `CELERY_CONFIRM_PUBLISH` **não** vai no
  beat de produção; fechamento por horário só se liga depois que a correção do despacho (conexão nova a
  cada publicação, TS-5569, já nesta release) for validada na sandbox (validada em 24/11: disparos das
  15:00 e 15:30 UTC em sucesso, sem a variável no beat); o agendador marca como falha, com aviso no log, a execução
  não consumida em 2 h.
- **E-mail recusado pelo shared** (sem remetente ativo ou sem destinatário: 422) → a execução do
  resumo ou do aviso fica registrada com erro, sem nova tentativa → segura: o job do resumo nasce
  desligado; remetente e grupo cadastrados no passo 11, antes de ligar.
- **Deploy no meio de uma tarefa** → o pod que sai tem 30 s para terminar
  (`terminationGracePeriodSeconds`) e depois é morto; a mensagem volta à fila (`acks_late`) e o pod
  novo refaz. Repetir é seguro: o fechamento só pega pagamento sem lote.
- **Fila isolada sem consumidor** fora do `asgard-production` → só recebe tarefa de produto com
  `liquidacao_baixa_refact` ligada, e nenhum nasce ligado → sem efeito no deploy.

## Impacto

- **Portal (três marcas):** página nova "Configuração do produto"; aprovação de lote antes do
  corte; lote aberto como padrão. A operação dos 6 produtos do primeiro risco deixa de esperar o
  liquidar.
- **Banco da cessão:** 7 enums, 4 tabelas novas (`agendamento`, `agendamento_execucao`,
  `agendamento_alteracao`, `liquidacao_remessa`), `produto_config` com 3 colunas novas,
  `liquidacao_lote_vigente` com 1 coluna e 1 índice parcial, 14 agendamentos inseridos e 1 UPDATE
  de preenchimento; a CHECK `ck_agendamento_tipo_coerente` da tabela nova `agendamento` é recriada,
  mais permissiva, na mesma release (`a4f7c2d9e1b6`). Nenhuma coluna removida. Detalhe para a DBA
  no resumo dos objetos.
- **Banco do shared:** tabela `email_dispatch.template_recipients`, 1 remetente inativo e 4
  templates (os 2 da primeira versão ficam desativados pela segunda: 2 ativos).
- **Infra:** worker novo `liquidacao-baixa-isolada` (1 pod); o beat passa a ler o banco; os jobs
  novos rodam na fila `liquidacao_lote_celery`, que o `worker` (15 pods) já consome.
- **Deploy:** sem indisponibilidade prevista; migrations no shared e na cessão; variável nova
  `APL_SHARED_SERVICE_URL` na cessão; a `CONCORRENCIA_POR_FILA` ganha a fila isolada.

## Plano de implantação

**Antes da janela**
1. Parameter Store de produção da cessão: criar `APL_SHARED_SERVICE_URL` (tipo `String`, mesmo
   valor do parâmetro de URL do shared no BFF) e acrescentar `liquidacao_baixa_isolada_celery=2` à
   `CONCORRENCIA_POR_FILA`. Sem a primeira, o pod da cessão não passa na checagem de variáveis e
   não sobe. **Feito em 24/11**, com `APL_CREDIT_WHITELABEL_URL` (endereço do portal, para os links
   dos e-mails); conferido pelo nome e pelo valor.
2. Réplica, somente leitura: repetir a conferência dos produtos automáticos com
   `liquidacao_automatico` desligada (esperado: 22, 26, 27, 28, 39, 42) e a das flags incoerentes
   com a modalidade (esperado: nenhuma linha). Se a lista mudou, decidir produto a produto antes.
3. DBA: resumo dos objetos novos e SQL da TS-5537 enviados em 24/11; ela confirma o Alembic da
   cessão em `b8e41f6c2a93` antes da janela. As permissões dos objetos novos só podem ser dadas
   depois de cada migration (passos 5 e 6), inclusive a leitura da
   `email_dispatch.template_recipients` para os usuários de consulta (na sandbox ela nasceu sem).

**Janela (shared → cessão → BFF → portal)**
4. Merge das PRs `release/20261124` → `master` dos quatro repositórios.
5. **Shared:** tag nova em `asgard-production`. Conferir: pods prontos; Alembic em `5e7b2d94a1c8`.
   DBA: permissões da `email_dispatch.template_recipients`.
6. **Cessão:** antes da tag, a DBA roda o SQL da TS-5537 (19 contratos do produto 15 de
   `liberando` para `errado`: prévia, transação que aborta se não forem 19, log em cada contrato e
   conferência). Depois, um commit no argocd com a tag nova e o worker `liquidacao-baixa-isolada` no
   `asgard-production`; o `viva-production` não muda. Sem `CELERY_CONFIRM_PUBLISH` no beat
   (ver o risco do disparo do agendador). Conferir:
   - Alembic em `a4f7c2d9e1b6` (pela réplica); DBA: permissões das 4 tabelas novas;
   - `produto_config` com o gatilho e o agrupamento preenchidos conforme o mapeamento;
   - beat: "Agendamentos despachados" no próximo :00 ou :30, e "Backstop de remessas automáticas
     concluído" no worker. Na partida o beat costuma reiniciar 1 ou 2 vezes por falta de
     variáveis (acontece em quase todo deploy desde 03/11); vale o despacho seguinte;
   - worker isolado: log de partida com a fila `liquidacao_baixa_isolada_celery`.
7. **BFF:** tag nova. Conferir: a consulta da configuração de um produto responde 200.
8. **Portal:** tag nova nas três marcas (`apl-credit-whitelabel-front`, `-dots` e `-cerys`). Hoje
   cada marca está numa versão diferente (`prod-0c4dc76`, `prod-2ff9802`, `prod-91670d4`); a nova
   leva as três para a mesma. Conferir: a página "Configuração do produto" abre; a listagem de
   lotes carrega.

**Depois**
9. Produto 1604: ligar o fechamento por horário às 16:00 pela tela de configuração (ou
   `PUT /liquidacao/fechamento-por-horario/1604`). Conferir o agendamento ativo, com próxima
   execução às 16:00, e, no dia seguinte, "Fechamento de lotes por horário concluído".
10. Produto 15 (Mercato Libero): fechamento por horário ligado pelo usuário pela tela (16:00, 17:00,
    18:00 e 20:45); a varredura externa segue ligada nos primeiros dias.
11. E-mails: ativar o remetente com a caixa compartilhada de produção e cadastrar o grupo do Entra ID
    nos dois templates da liquidação, antes de ligar o resumo diário.
12. Fica desligado até decisão: fechamento por horário dos outros produtos do Mercato Libero,
    resumo diário e `liquidacao_baixa_refact` por produto. A Voltis segue manual.

## Plano de Rollback

- **Sem deploy, por produto:** gatilho `manual` na tela de configuração (os 6 produtos do primeiro
  risco); desligar um agendamento (inclusive o backstop) pela rota de agendamento.
- **Com deploy, na ordem inversa:** portal (as três tags anteriores), BFF `prod-5aca171`, cessão
  `prod-ca52465` no `asgard-production` (em produção desde 23/11, com a TS-5616; remover o worker
  isolado depois de conferir a fila vazia), shared `prod-79d43a7`.
- **Contratos da TS-5537:** o fim do SQL tem o desfazer (volta os 19 para `liberando`, pelo log).
- **Banco:** as migrations só acrescentam; a imagem anterior ignora as tabelas e colunas novas, então
  a volta não pede downgrade. O downgrade, se preciso, é com a DBA: apaga as tabelas do agendador
  (perde o histórico) e não desfaz o preenchimento. O primeiro passo dele (`a4f7c2d9e1b6`) volta a
  CHECK estrita e falha se houver agendamento cron inativo sem horário; apagar essas linhas antes.
- **O que fica:** tabelas, colunas, enums e agendamentos novos; linhas de `liquidacao_remessa`;
  e configuração gravada pela tela nova, que a imagem anterior não lê (ela lê a coluna antiga).

## Evidências de validação

- **Testes (24/11, TS-5612 e TS-5537):** cessão 6691 passaram e 207 pulados no Docker, sem falha
  (`dd004bf5e`); antes da TS-5612, 6698 e 210: saíram os testes da rotina removida e entraram 2 da
  TS-5537.
- **Testes (23/11):** shared 898 (`15cb14d`, contém a `release/20261124` em `93835fe`); cessão 7082
  nos dois modos da suíte e integração 124 e 45 (`71be313a3`, contém `79747b2c0`). CI das PRs da
  sandbox (#87, #2782, #280, #317): verde, salvo o Semgrep no shared e na cessão (aceito).
- **Sandbox (23/11, UTC):** `sand-356a9b2` (shared), `sand-b588264` (cessão), `sand-c791f68` (BFF) e
  `sand-9b7cc4e` (portal), cada uma contendo a release (ancestralidade conferida).
  - beat `sand-b588264`: "Agendamentos despachados" às 16:30:01 e 17:00:01;
  - backstop concluído às 16:30:02, 0 remessas avaliadas e 0 falhas (trace
    `18073983290972130364`); a execução das 17:00 ficou `pendente` (mensagem publicada às
    17:00:01, nunca consumida); a das 17:30 terminou em `sucesso`;
  - e-mails: remetente da liquidação ativo e ligado aos dois templates; destinatários cadastrados
    pelo usuário (a tabela nova ainda não tem permissão de leitura para o usuário de consulta);
  - nenhum erro de coluna ou tabela inexistente de 15:30 a 17:06.
- **Correção da TS-5624 (23/11):** cessão 1202 (liquidação, agendamento e o teste que compara a
  migration com o model), BFF 4678 e portal 116 specs da configuração do produto; CHECK nova provada
  num Postgres descartável. Imagens finais da sandbox: cessão `sand-a03d015`, BFF `sand-a9812b0`,
  portal `sand-01bf80e`, shared `sand-e8bb038`.
- **Testes do usuário na sandbox (23/11, horário de Brasília)**, pelo guia
  `tasks/13-post-deploy-switch-on-guide.md`:
  - A1, lote aberto: produto 584, lote 50027 com 5 pagamentos;
  - manual por chave (produto 187): dois vigentes e dois lotes (50031 e 50032) fechados pela tela
    às 18:43, `concluido`, envio simulado. O aviso de compromisso de saldo é esperado: fundo sem
    conta vinculada;
  - A2, automático no lote aberto (`sand-822b5f9`): produto 54 por remessa (lote 50044, fechado
    às 19:34:57) e 187 por chave (lote 50046, 2 pagamentos, 19:38:27); os dois com "Remessa de
    liquidação fechada automaticamente", 0 recusadas, 0 ocupadas, lote `concluido`;
  - A3, backstop: a cada :00 e :30 (último visto às 19:30), 0 remessas avaliadas;
  - A4, agendador: uma execução presa às 16:16, do incidente da tarde (ver o risco do disparo);
    nenhuma depois. Em 24/11, sem `CELERY_CONFIRM_PUBLISH` no beat (tirada às 14:33 UTC), disparos
    das 15:00 e 15:30 UTC em sucesso, com a conexão parada 30 min entre eles;
  - A5, lote sem pagamento (24/11): produto 35 em Agendado com o horário das 10:17; "Agendamentos
    despachados" às 10:17:01 e "Fechamento de lotes por horário concluído" às 10:17:06; o lote
    50048, aberto e sem pagamento, foi fechado e descartado pela esteira às 10:17:02 ("Lote sem
    pagamento descartado." no log do lote). O descarte só sai no Datadog em DEBUG: em produção,
    conferir na réplica (`liquidacao_lote_processo.estado_atual = 'descartado'`);
  - B1, por horário: produto 24 às 19:00, "Agendamentos despachados" às 19:00:01 e "Fechamento de
    lotes por horário concluído" às 19:00:07 (9 lotes, 0 falhas);
  - B2, esteira de baixa nova: produto 28 com `liquidacao_baixa_refact` ligada, lote 50047 fechado
    pela tela, desviado e concluído às 19:47:16; chave desligada de novo;
  - C1, aviso de horário depois do corte: produto 55, 23:50 ligado às 19:48:38, 1 aviso, shared
    `sent=1`;
  - C2, resumo diário: execução às 19:40 com 15 lotes e anexo, shared `sent=1`; duas execuções
    anteriores do dia tinham a mesma chave de envio e só uma saiu (B28);
  - TS-5624, apagar os horários: o 23:50 do produto 55 e o 19:00 do 24 (os dois em Manual)
    apagados pela tela às 20:20; no banco, os dois agendamentos inativos, sem horário e sem próxima
    execução; Alembic da sandbox em `d2e8b5a7c013` (a junção própria da `-sdbx`), com a CHECK nova;
    num produto em Agendado, tirar o último horário deixa o "Salvar horários" desligado;
  - A6, aprovar antes do corte (24/11): produto 55 (fundo 27, conciliação automática), lote 50049
    com 2 pagamentos fechado pela tela às 09:12:01 e roteado para a fila do dia
    (`aguarda_conciliacao`); aprovado em tela às 09:14:45 ("Conciliacao de conta APROVADA em tela
    antes do corte"), compromisso `manual` de R$ 2.000,00 na conta vinculada e lote em
    `liquidando` às 09:14:46, aguardando o retorno da administradora; Datadog "Conciliacao de
    conta aprovada em tela; lote retoma a esteira de baixa." às 09:14:46 (`sand-a03d015`);
  - ajustes de 24/11 no front (`sand-4917fe3`): o aviso de lote fechado lista só os lotes (a
    contagem vinha dos avulsos e mostrava 0 no lote aberto) e o exemplo da observação no aprovar
    deixou de citar uma pessoa real; o exemplo foi conferido na tela;
  - Produtos de teste de volta a Manual (53, 54, 55, 187, 24, 35); esteira nova do 28 desligada.
