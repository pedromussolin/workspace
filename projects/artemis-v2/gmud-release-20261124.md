# GMUD — release de 24/11/2026 (Artemis V2: fechamento de lotes de liquidação)

> **Status (23/11/2026):** rascunho. Deploy previsto para 24/11, à noite. Pendências marcadas
> "a confirmar"; as evidências dos testes do usuário na sandbox entram quando ele terminar.

Tipo: Mudança programada

## Summary

Liquidação: configuração do produto em tela e aprovação de lote antes do corte

## Descrição

**Contexto**
- A liquidação do Mercato Libero e da Voltis fecha lote por uma varredura externa (VM de automações),
  que sai junto com o Atlas. Esta release traz o fechamento para dentro da cessão, configurável por
  produto, e a operação passa a mexer na configuração pela tela, sem pedir ajuste no banco.
- Lote de liquidação sem pagamento quebra a esteira de baixa, a conciliação e o "aprovar" da fila
  manual; havia ~15,3 mil lotes vazios em produção (levantamento da TS-5582, novembro/2026).
- Em 09/11 um lote de 1.003.192 pagamentos (produto 80) se perdeu na esteira de baixa quando o
  worker reiniciou no meio, e ficou em `pendente` sem reenvio (TS-5737).

**O que muda**
- **apl-shared-service** (PR a abrir, `release/20261124` → `master`):
  - `POST /email-dispatches` aceita anexo em Excel montado a partir de dados tabulares (TS-5584);
  - templates dos e-mails da liquidação e destinatários padrão por template, na tabela nova
    `email_dispatch.template_recipients`; pedido sem destinatário usa os do template (TS-5585).
- **platform-cessao** (PR a abrir):
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
  - lote aberto passa a ser o padrão de todos os produtos (TS-5567);
  - API da configuração do produto (TS-5624);
  - aprovar em tela um lote fechado antes das 14h, sem esperar a rotina do corte (TS-5571);
  - o gatilho automático passa a fechar pelo fluxo novo, com a tabela de remessas e um backstop a
    cada 30 min para remessa presa (TS-5572);
  - esteira de baixa nova com reentrega segura e arquivo em blocos, ligada por produto pela coluna
    `liquidacao_baixa_refact`, que nasce desligada em todos; fila própria
    `liquidacao_baixa_isolada_celery` (TS-5737).
- **apl-credit-whitelabel-api** (BFF, a camada entre o portal e os serviços; PR a abrir): guardas de
  lote vazio (TS-5582), lote aberto (TS-5567), rotas da configuração do produto (TS-5624), contrato
  do envio de e-mail com anexo (TS-5584), remoção da rota `/fake-batches/consolidate`, que o portal
  já não chama (TS-5568), e atualização do `virtualenv` de desenvolvimento por CVE (TS-5871).
- **apl-credit-whitelabel** (portal; PR a abrir): página "Configuração do produto", com as abas
  Cessão e Liquidação (TS-5624); aprovação antes do corte (TS-5571); lote aberto (TS-5567);
  guardas de lote vazio (TS-5582).
- **Argocd** (`platform-cessao-argocd`): worker novo `liquidacao-baixa-isolada` em
  `asgard-production` (1 pod, limite de 2 CPU e 4,5 GiB, `CELERY_WORKER_QUEUES` só com a fila
  isolada, `INICIAR_CONSUMER=0`, sondas), igual ao da sandbox (`be348ed`). Tags novas nos argocds dos
  quatro serviços.

**O que não muda**
- A varredura externa segue fechando os lotes do Mercato Libero e da Voltis até os horários por
  produto serem ligados; o produto 1604 continua no agendamento fixo atual.
- A rota legada `POST /liquidacao/` da cessão e a esteira de baixa atual (todo produto continua
  nela, porque a chave nova nasce desligada).
- A limpeza dos lotes vazios antigos não roda neste deploy; depende da revisão da DBA.
- A coluna antiga `modalidade_fechamento_lote` e as flags antigas ficam (saem depois, com o legado).

## Prioridade

High

## Link Tarefa

`<link do Jira>` das 14 tarefas: TS-5582, TS-5583, TS-5567, TS-5569, TS-5570, TS-5585, TS-5571,
TS-5572, TS-5568, TS-5584, TS-5624, TS-5596, TS-5737 e TS-5871.

## Risco

**Médio.**
- **6 produtos passam a fechar e enviar sozinhos** (22, 26, 27, 28, 39, 42: hoje automáticos com a
  flag `liquidacao_automatico` desligada, fecham e esperam o "liquidar") → depois da migration, o
  lote vai à administradora sem esperar o liquidar → segura: conferência da lista no dia (passo 2);
  volta por produto, sem deploy, com o gatilho `manual` na tela de configuração.
- **Migration esperando trava na `produto_config`** (inclui colunas e faz um UPDATE em todas as
  linhas) → leituras da tabela ficam na fila atrás dela → segura: janela noturna; acompanhar o Job
  de migration; DBA de prontidão (a confirmar). A migration não define `lock_timeout` (a confirmar).
- **Pods novos antes do fim da migration** → leitura de coluna inexistente na `produto_config` →
  na sandbox, em 23/11, nenhum erro de coluna ou tabela inexistente durante a migration → segura:
  conferir a revisão do Alembic antes do BFF e do portal (passo 6).
- **Segundo ambiente de produção da cessão (`viva-production`)**: recebe a mesma imagem e roda as
  mesmas migrations no banco dele, sem o worker isolado →
  - o mapeamento das colunas novas vale para os produtos de lá (banco sem acesso; a confirmar);
  - os 14 agendamentos entram com os ids de produto do principal: os 13 de liquidação nascem
    desligados; o backstop nasce ligado e só olha remessas automáticas;
  - sem a `APL_SHARED_SERVICE_URL` no Parameter Store que ele lê, os pods de lá não sobem (a
    confirmar se é o mesmo do principal).
- **Disparo do agendador perdido ou travado** (sandbox, 23/11) **[C]**: o despacho reaproveita a
  conexão com o RabbitMQ, e depois de ~30 min parada ela é derrubada em silêncio no caminho. Sem
  confirmação de publicação, a mensagem some (execução das 17:00 UTC publicada e nunca recebida);
  com `CELERY_CONFIRM_PUBLISH=1` no beat (teste a partir das 17:43 UTC), o beat trava esperando a
  confirmação (18:30 UTC: execução gravada, sem log de despacho, publicação sem fim). Conexão nova
  funciona (16:30, 17:30 e 18:00 UTC). No backstop, disparos perdidos; num fechamento por horário
  (nasce desligado), o lote do dia não fecharia → segura: `CELERY_CONFIRM_PUBLISH` **não** vai no
  beat de produção; fechamento por horário só se liga depois da correção do despacho (conexão nova a
  cada publicação) validada na sandbox; o agendador marca como falha, com aviso no log, a execução
  não consumida em 2 h.
- **E-mail recusado pelo shared** (sem remetente ativo ou sem destinatário: 422) → a execução do
  resumo ou do aviso fica registrada com erro, sem nova tentativa → segura: o job do resumo nasce
  desligado; remetente e grupo cadastrados no passo 9, antes de ligar.
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
  de preenchimento. Nenhuma coluna removida. Detalhe para a DBA no resumo dos objetos.
- **Banco do shared:** tabela `email_dispatch.template_recipients`, 2 templates e 1 remetente
  inativo.
- **Infra:** worker novo `liquidacao-baixa-isolada` (1 pod); o beat passa a ler o banco; os jobs
  novos rodam na fila `liquidacao_lote_celery`, que o `worker` (15 pods) já consome.
- **Deploy:** sem indisponibilidade prevista; migrations no shared e na cessão; variável nova
  `APL_SHARED_SERVICE_URL` na cessão; a `CONCORRENCIA_POR_FILA` ganha a fila isolada.

## Plano de implantação

**Antes da janela**
1. Parameter Store de produção da cessão: criar `APL_SHARED_SERVICE_URL` (tipo `String`, mesmo
   valor do parâmetro de URL do shared no BFF) e acrescentar `liquidacao_baixa_isolada_celery=<N>` à
   `CONCORRENCIA_POR_FILA`. Conferir pelo nome. Sem a primeira, o pod da cessão não passa na
   checagem de variáveis e não sobe. **No `viva-production`:** conferir se ele lê o mesmo Parameter
   Store do principal; se não, criar a variável lá também.
2. Réplica, somente leitura: repetir a conferência dos produtos automáticos com
   `liquidacao_automatico` desligada (esperado: 22, 26, 27, 28, 39, 42) e a das flags incoerentes
   com a modalidade (esperado: nenhuma linha). Se a lista mudou, decidir produto a produto antes.
3. DBA: permissões dos objetos novos (schema da cessão a confirmar), inclusive leitura da
   `email_dispatch.template_recipients` para os usuários de consulta (na sandbox ela nasceu sem).

**Janela (shared → cessão → BFF → portal)**
4. Merge das PRs `release/20261124` → `master` dos quatro repositórios.
5. **Shared:** tag nova em `asgard-production`. Conferir: pods prontos; Alembic em `9300117a09ae`.
6. **Cessão:** um commit no argocd com a tag nova em `asgard-production` e em `viva-production`, o
   worker `liquidacao-baixa-isolada` no `asgard-production`. Sem `CELERY_CONFIRM_PUBLISH` no beat
   (ver o risco do disparo do agendador). Conferir:
   - Alembic em `c9d4a1e7f358` (pela réplica);
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
9. E-mails: ativar o remetente com a caixa compartilhada de produção e cadastrar o grupo do Entra ID
   nos dois templates da liquidação, antes de ligar o resumo diário.
10. Fica desligado até decisão: fechamento por horário do Mercato Libero e da Voltis (horários a
    confirmar com o negócio), resumo diário e `liquidacao_baixa_refact` por produto.

## Plano de Rollback

- **Sem deploy, por produto:** gatilho `manual` na tela de configuração (os 6 produtos do primeiro
  risco); desligar um agendamento (inclusive o backstop) pela rota de agendamento.
- **Com deploy, na ordem inversa:** portal (as três tags anteriores), BFF `prod-5aca171`, cessão
  `prod-a410fc9` nos dois ambientes (e remover o worker isolado depois de conferir a fila vazia),
  shared `prod-79d43a7`.
- **Banco:** as migrations só acrescentam; a imagem anterior ignora as tabelas e colunas novas, então
  a volta não pede downgrade. O downgrade, se preciso, é com a DBA: apaga as tabelas do agendador
  (perde o histórico) e não desfaz o preenchimento.
- **O que fica:** tabelas, colunas, enums e agendamentos novos; linhas de `liquidacao_remessa`;
  e configuração gravada pela tela nova, que a imagem anterior não lê (ela lê a coluna antiga).

## Evidências de validação

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
- **Testes do usuário na sandbox:** a preencher.
