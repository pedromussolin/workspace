Status: rascunho
Data: 18/11/2026
Tags: pre-trade, workflows, sla, aprovacoes, portal

# Desenho: SLA por etapa, trade antecipado e 2ª aprovação genérica

Primeira entrega do projeto `pre-trade`. Decisões de negócio em `../decisions.md` (D1 a D14). Onde
este documento diz "minha decisão", é escolha técnica minha, que o usuário pode trocar ao revisar.

## 1. Intenção

O Pré-Trade sai do e-mail para o portal. Para virar o fluxo oficial, ele precisa de três coisas:

- **SLA por etapa:** dizer quanto tempo cada área tem para agir e avisar quando estourar.
- **Trade antecipado:** Operações executa o trade sem esperar as aprovações quando o mercado exige.
  O registro precisa ser honesto: a tela nunca pode dar a entender que houve aprovação.
- **2ª aprovação genérica:** a aprovação final é do time de gestão (quem tem a CGA), não de um
  cargo.

## 2. Objetivos, não objetivos e anti-objetivos

**Objetivos**

- SLA opcional por etapa, em horas úteis (seg. a sex., 9h às 18h, America/Sao_Paulo, sem os
  feriados da B3), visível na lista e no detalhe e com um e-mail único quando estoura.
- Operações antecipa o trade na 1ª ou na 2ª aprovação, com motivo obrigatório. A solicitação vai
  para a Conferência do Jurídico, e as aprovações que faltavam ficam registradas como **puladas**.
- As áreas puladas recebem um e-mail informativo.
- A permissão da 2ª aprovação passa de `ceo-pre-trade:approve` para
  `portfolio-manager-pre-trade:approve`, exibida como "Gestão (Aprovação trade)".
- Tudo no motor de workflows é genérico (SLA, transição que pula aprovações). O módulo
  `pre_trade` só integra: configuração, avisos e rótulos.

**Não objetivos (fora desta entrega)**

- Fast track.
- Tela para editar o SLA: ele é configurado por migration, como o resto do fluxo.
- Pausar o SLA, relatório ou métrica de SLA, filtro ou ordenação por SLA na lista.
- Horário comercial por workflow e calendários além da B3.
- Desfazer um trade antecipado.

**Anti-objetivos (falha mesmo que funcione)**

- Uma aprovação pulada aparecer como aprovada em qualquer lugar: trilha, bolinhas da lista,
  histórico, e-mail, contagem de progresso.
- O chip do SLA se confundir com o chip de prazo da solicitação (`deadline_date`).
- O motor citar o Pré-Trade (nome de etapa, de permissão ou de template).
- O e-mail do SLA sair mais de uma vez para a mesma entrada na etapa.
- Antecipar sem motivo.

## 3. Restrições

- Features genéricas da shared (workflows, e-mail, agendamento) não se acoplam entre si nem ao
  `pre_trade`.
- Migration aplicada não se altera: tudo em migrations novas, a partir da head `c3f81d5a92e7`.
- Status, tipo de evento e tipo de aviso são enums nativos do Postgres: valor novo entra com
  `ALTER TYPE ... ADD VALUE IF NOT EXISTS` num `autocommit_block` (padrão de
  `e80222c01aa3_workflows_rule.py`). O downgrade não remove o valor.
- Agendamento só pelo banco (`scheduler.scheduled_jobs`), no padrão de
  `c3f81d5a92e7_scheduled_jobs_interrupted_watchdog.py`.
- `tests/test_arch.py` da shared: `shared/business` não importa `src.infra`; utilitários ficam em
  `shared/utils`.
- Toda função nova do repositório entra também no `FakeWorkflowsRepository`
  (`tests/unit/shared/test_workflows_business.py`).
- Front: responsivo, sem Angular Material, `prefers-reduced-motion` respeitado.
- Permissões são app roles do Azure. A troca de nome é uma migração de roles, feita pelo usuário.

## 4. Abordagens

**Trade antecipado**

- **A (escolhida): no motor.** A transição ganha uma marca `skips_approvals`; o motor fecha as vagas
  abertas com o status `SKIPPED` e grava quais etapas foram puladas. Histórico coerente,
  reaproveitável por outro fluxo só com configuração.
- B: só no módulo. Menor, mas deixa vagas `PENDING` para sempre e tira o conceito do motor.
- Descartada: o Sistema aprovar as vagas (como a regra de bypass). Registraria "aprovado".

**SLA**

- **A (escolhida): vencimento gravado na entrada da etapa.** Mudar o SLA vale para as próximas
  entradas. Lista e job usam SQL simples.
- B: vencimento calculado a cada leitura. Nada gravado no processo, mas sem filtro no banco e com o
  job calculando processo a processo.

**2ª aprovação:** um caminho só (renomear a permissão no lugar, mantendo o id).

## 5. Desenho

### 5.1 Calendário de horas úteis (shared, genérico)

- Arquivo novo `src/shared/utils/business_hours.py`:
  - `add_business_minutes(start: datetime, minutes: int) -> datetime`
  - `business_minutes_between(start: datetime, end: datetime) -> int` (negativo se `end < start`)
- Janela 9h às 18h em `BUSINESS_TIMEZONE`, seg. a sex., fora dos feriados de
  `holidays.financial_holidays("BVMF")`. É o mesmo calendário do `data-lake-api`
  (`src/shared/utils/business_days.py`).
- Dependência nova `holidays` em `requirements.in` e `requirements.txt`.
- Início fora da janela anda para a próxima abertura. Exemplo: entrou sexta às 16h com SLA de 240
  min, vence segunda às 11h.

### 5.2 SLA no motor (shared, genérico)

**Banco (migration nova)**

- `workflows.stage.sla_business_minutes integer NULL`, com `CHECK (sla_business_minutes > 0)`.
  Nulo significa sem SLA. Minha decisão: minutos, para permitir SLA menor que uma hora; a tela
  mostra em horas.
- `workflows.process.stage_due_at timestamptz NULL`: vencimento do SLA da etapa atual.

**Escrita**

- `move_process_to_stage` (`repository/workflows.py:590`) passa a receber `stage_due_at`. O `_move`
  (`business/workflows.py:1485`) calcula com `add_business_minutes(agora, sla)` da etapa de destino,
  ou nulo.
- A criação do processo (`business/workflows.py:727`) faz o mesmo para a etapa inicial.
- Etapa terminal sempre grava nulo.
- Cada entrada na etapa recalcula. Por exemplo, voltar dos Ajustes para a 1ª aprovação abre um SLA
  novo.

**Leitura**

- `search_processes` já seleciona `process.c`, então `stage_due_at` vem sem mudança.
- Filtro novo `sla_overdue`: `closed_at IS NULL AND stage_due_at < now()`. O job usa; a tela não
  usa nesta entrega.
- Método genérico no motor, `stage_sla(process, now)`, que devolve `{due_at, status}`:
  - `status` é `none` (sem SLA ou processo fechado), `on_time`, `at_risk` ou `overdue`;
  - `at_risk` quando faltam no máximo 25% do SLA atual da etapa, em minutos úteis (minha decisão).
- O `_summary` do `pre_trade` (`modules/pre_trade/business.py:957`) expõe `stage_due_at` e
  `stage_sla_status`.

**Validação de config:** nenhuma além do `CHECK`. Etapa terminal com SLA é ignorada na escrita.

### 5.3 Transição que pula aprovações (shared, genérico)

**Banco (migration nova)**

- `workflows.transition.skips_approvals boolean NOT NULL DEFAULT false`.
- `ALTER TYPE workflowapprovalstatus ADD VALUE 'SKIPPED'`.
- O índice `uq_approval_decider_per_round` é recriado com o predicado
  `status <> 'PENDING' AND status <> 'SKIPPED' AND rule_id IS NULL`. Sem isso, quem pula duas vagas
  na mesma rodada viola o índice. A check `ck_approval_decided_by_matches_status` continua: a linha
  `SKIPPED` tem `decided_by`, que é quem antecipou.
- Model (`infra/postgres/models/workflows.py`) e `WorkflowApprovalStatus` (`shared/utils/constants.py`)
  acompanham.

**Validação de config:** um novo `_assert_skips_approvals` no carregamento (`business/workflows.py`,
junto das linhas 180-190). `skips_approvals = true` só vale em transição com `on_decision` nulo que
sai de etapa de aprovação. Fora disso, `WorkflowConfigurationError`.

**Execução** (`apply_transition`, `business/workflows.py:767`, e `_move`):

1. Se `skips_approvals` e `notes` vier vazio ou só com espaços: erro novo `ReasonRequiredError`
   (subclasse de `WorkflowError`, mapeado para 422 em `infra/fastapi/exceptions_handlers.py`). O
   motivo usa o `notes` que o corpo da transição já aceita na shared, no BFF e no front, então
   nenhum contrato de entrada muda (minha decisão).
2. Antes de mover, as etapas puladas são calculadas de forma genérica: a partir da origem, seguir
   as transições `APPROVED` enquanto o destino for etapa de aprovação.
   - No Pré-Trade, da 1ª aprovação: `[PENDING_FIRST_APPROVAL, PENDING_SECOND_APPROVAL]`.
   - Da 2ª aprovação: `[PENDING_SECOND_APPROVAL]`.
3. Cada vaga ainda aberta da rodada atual da origem ganha uma linha de decisão `SKIPPED`, com
   `decided_by` = ator e `reason` = motivo. Vaga já decidida (inclusive a aprovada pela regra) fica
   como está. Etapas que a solicitação nunca abriu, como a 2ª quando pula da 1ª, não ganham linhas:
   ficam só no evento.
4. O evento `STAGE_TRANSITION` continua único, com `notes` = motivo. O payload
   (`StageTransitionPayload` em `shared/schemas/workflows.py`) ganha o campo opcional
   `skipped_stages: list[str]`. Minha decisão: não criar tipo de evento novo, para o histórico
   continuar com um item por ação.
5. Segue o `_move` normal: move, abre vagas do destino (nenhuma na Conferência) e aplica regras.

**Leitura**

- `_first_open_slot` e `list_open_pending_approvals` já tratam qualquer status diferente de
  `PENDING` como decidido, então nada muda no "aguardando você".
- `_progress_of` conta só `APPROVED`, então a vaga pulada não vira progresso.
- `latest_approval_rounds` (bolinhas da lista) passa a trazer `status = SKIPPED` nas vagas puladas.
- Campo novo no resumo (lista e detalhe): `skipped_approval_stages: list[str]`. É a união dos
  `skipped_stages` dos eventos do processo, numa consulta por página, e serve para a lista saber do
  pulo sem carregar o histórico.
- `AvailableTransitionResponse` e `_transition_rows` (`modules/pre_trade/business.py:1025`) ganham
  `skips_approvals: bool`. O front decide rótulo e diálogo por essa marca, não pelo nome da etapa.

**Quem age na etapa:** `stage_permission_names` (`business/workflows.py:597`) conta como "age na
etapa" toda permissão autorizada numa saída manual. Sem ajuste, Operações passaria a receber o aviso
de ação e o de SLA de toda solicitação que entra na 1ª ou na 2ª aprovação. Por isso, saídas com
`skips_approvals` não contam ali: são exceção, não a ação normal da etapa. O "aguardando você" já
não é afetado, porque em etapa de aprovação ele só considera quem decide.

**Concorrência:** a decisão e a transição travam o processo (`_lock_open_process`). Se o aprovador e
Operações agirem juntos, o primeiro vence; `uq_approval_decided_slot` garante uma decisão por vaga.

### 5.4 Avisos (módulo `pre_trade`)

**Tipos novos** (`ALTER TYPE workflownotificationtype`): `SLA_OVERDUE` e `APPROVALS_SKIPPED`.

Para cada tipo:

- uma linha em `workflows.notification_config` do Pré-Trade, ativa;
- um template em `email_dispatch.templates`, inserido como no `_insert_email_templates` de
  `210f9f141480_pre_trade.py`:
  - `pre-trade-sla-overdue`
  - `pre-trade-approvals-skipped`

**SLA estourado**

- Task nova `notify_sla_overdue` em `modules/pre_trade/viewer.py`, registrada como `schedulable`
  em `infra/celery/tasks.py`, com o teste de `tests/unit/infra/test_celery_tasks.py` atualizado.
- A task pagina `list_processes(is_open=True, sla_overdue=True)`.
- Destinatários: quem age na etapa, ou só quem abriu quando a etapa é Ajustes, igual ao
  `_overdue_emails`.
- Chave de idempotência: `pre-trade:{key}:{stage}:{stage_entered_at}:sla-overdue`. O
  `email_dispatch` deduplica entre execuções, então sai um e-mail por entrada na etapa.
- Linha em `scheduler.scheduled_jobs` por migration:
  - `job_type`: `pre_trade.notify_sla_overdue`;
  - cron `*/15 9-18 * * 1-5`, America/Sao_Paulo (o vencimento sempre cai dentro da janela);
  - `is_active = false`, como os outros jobs que enviam e-mail (minha decisão). Ligar faz parte do
    deploy.
- Variáveis do template: as de `_variables` (`modules/pre_trade/business.py:926`) mais `sla_hours`
  e `stage_due_at` formatado.

**Aprovações puladas**

- O `move_request` (`modules/pre_trade/business.py:453`) chama o `_notify_move` de sempre: Gestão
  recebe a mudança de etapa e o Jurídico recebe a ação. Além disso, chama um `_notify_skipped`
  novo.
- O `_notify_skipped` manda um aviso por permissão com config ativa nas etapas puladas, no estilo
  do `_notify_rule_approvals`:
  - da 1ª aprovação: Compliance, Risco e Gestão (Aprovação trade);
  - da 2ª: só Gestão.
- Só permissões com config **ativa** recebem. Na sandbox, o Jurídico está inativo na 1ª aprovação,
  então não recebe esse aviso; recebe só o de ação da Conferência.
- Chave: `pre-trade:{key}:{origem}:{stage_entered_at}:skipped:{permission}`.
- Quem tem duas permissões pode receber dois e-mails de tipos diferentes (por exemplo, a mudança de
  etapa como quem abriu e o aviso de pulo como aprovador). Não há deduplicação entre tipos, como
  hoje (minha decisão).
- Variáveis: as de sempre mais `actor_name`, `reason` e `skipped_stage_labels`.

### 5.5 Configuração do fluxo (migration de dados do Pré-Trade)

- Transições novas, autorizadas para `operations-pre-trade:update` e com `skips_approvals = true`:
  - `PENDING_FIRST_APPROVAL → PENDING_FINAL_CHECK`
  - `PENDING_SECOND_APPROVAL → PENDING_FINAL_CHECK`
- Não há conflito com `uq_transition_workflow_id_stages`, porque esses pares não existem hoje.
- `notification_config` e templates da seção 5.4. Job do SLA (5.4).
- SLA das etapas fica nulo nesta migration. Os valores (P4) entram numa migration própria quando
  o usuário definir, para não travar a entrega.
- Sem preenchimento retroativo: o SLA vale para as entradas em etapa depois da migration dos
  valores. Solicitações que já estão na etapa seguem sem SLA até a próxima mudança de etapa, e
  ligar o job não dispara uma leva de e-mails atrasados (minha decisão).
- O downgrade remove as linhas inseridas. Os valores de enum ficam.

### 5.6 2ª aprovação genérica

**Shared (migration de dados):**

```sql
UPDATE workflows.permission
   SET group_name = 'portfolio-manager', alias = 'Gestão (Aprovação trade)'
 WHERE scope = 'pre-trade' AND group_name = 'ceo' AND policy = 'approve';
```

- O `name` é calculado e vira `portfolio-manager-pre-trade:approve`. O id não muda, então o
  histórico de aprovações e as configs continuam ligados. O downgrade volta para `ceo`/`CEO`.
- O `sync_workflow_users` (a cada 15 min) troca os usuários da permissão pelos que têm a role nova
  no Azure.

**BFF** (`apl-credit-whitelabel-api`):

- `src/shared/utils/permissions.py`:
  - a entrada do catálogo passa a ser `portfolio-manager-pre-trade`, com rótulo
    "Pré-Trade (Gestão – Aprovação trade)" e ação `APPROVE` "Decide a 2ª aprovação";
  - `DEPARTMENT_NAMES` ganha `portfolio-manager`. O `ceo` fica, porque a POLI usa
    (`ceo-poli-knowledge-base`).
- `src/modules/access_control/business/pages.py`: escopos da página PRE-TRADE e
  `SCOPES_OUTSIDE_THE_PREFIX_RULE` trocam `ceo-pre-trade` por `portfolio-manager-pre-trade` (D11).
- `src/modules/pre_trade/business/__init__.py`: `PRE_TRADE_GROUPS`.
- `src/modules/account/viewer/iam.py:160`: o exemplo da descrição.
- `local/seed/pre_trade.py`: o seed.
- Testes: `tests/snapshots/route_permissions.json` (regerar; as entradas `ceo-poli-knowledge-base`
  ficam), `tests/unit/modules/pre_trade/test_business.py:79`, `tests/contract/test_pre_trade.py`,
  `tests/unit/modules/access_control/test_pages.py`, `test_scope_rule.py`,
  `tests/unit/modules/account/test_app_role_assignments.py` e
  `tests/unit/services/test_azure_app_roles.py`.
- Nada mais muda no BFF: as respostas da shared passam direto, sem `response_model`, e o corpo da
  transição já leva `notes`.

**Front** (`apl-credit-whitelabel`):

- `core/auth/groups.constants.ts`: `PORTFOLIO_MANAGER` no lugar de `CEO`.
- `features/pre-trade/pre-trade.permissions.ts`.
- `core/auth/iam/write-needs-read.ts`.
- Fakes e specs de `features/pre-trade` e `features/access-control` (lista no levantamento: busca
  por "ceo").

**Azure (usuário):** criar a app role `portfolio-manager-pre-trade:approve`, atribuir ao diretor e
ao CEO antes do deploy e apagar `ceo-pre-trade:approve` depois (D10).

**Janela do deploy:** o BFF manda as permissões no cabeçalho `X-User-Permissions` a partir de
`PRE_TRADE_GROUPS`. Entre o deploy da shared e o do BFF, quem decide a 2ª aprovação pode ficar
alguns minutos sem conseguir decidir. Mitigação: subir shared e BFF em sequência, sem intervalo.

### 5.7 Tela (front)

**Dados** (`data-access/pre-trade.dto.ts`)

- O resumo ganha `stage_due_at`, `stage_sla_status` e `skipped_approval_stages`.
- `available_transitions[]` ganha `skips_approvals`.
- O status da vaga ganha `'SKIPPED'`.
- O payload de `STAGE_TRANSITION` ganha `skipped_stages?`.

**Ação de antecipar** (`pre-trade.workflow.ts`)

- Transição com `skips_approvals` vira o botão "Antecipar trade", em tom de alerta.
- O botão abre o diálogo de motivo (`dialogs/reject-reason-dialog`, com `tone: 'warning'`) e chama
  `moveRequest(key, stage, motivo)`.
- Texto do diálogo: "As aprovações pendentes serão puladas e ficarão registradas no histórico. A
  solicitação segue para a conferência final do Jurídico."
- A Conferência normal (Trade → Conferência) continua "Enviar para conferência".

**Trilha** (`components/stage-track`)

- Estado novo `skipped`: casa tracejada, ícone de pulo e cor de alerta. O trecho até a próxima
  casa também fica tracejado.
- Entrada nova `skippedStages`.
- A casa do Trade, quando antecipado, conta como feita: o trade foi executado.
- Legenda: "Etapa 5 de 6 · Conferência · aprovações puladas".

**Aprovações** (`pre-trade.approvals.ts`)

- O `flowStepsOf` passa a usar `skipped_approval_stages` e o status `SKIPPED` para devolver
  `skipped`, com quem pulou, quando e o motivo vindos do evento.
- Isso corrige os três casos que hoje sairiam errados:
  - 2ª aprovação marcada como aprovada;
  - 2ª aprovação marcada como "a fazer";
  - Trade sem autor.
- `FLOW_STEP_STATUS` passa a dizer "Pulada" em vez de "Não realizada" quando o motivo é o
  antecipado; o rejeitado continua "Não realizada".

**Bolinhas da lista** (`components/approval-dots`): estado pulado com cor de alerta e tooltip "Pulada
(trade antecipado)".

**Lista** (`pre-trade.page.html`, `pre-trade-list.ts`)

- Na célula da Etapa entram dois selos: "Aprovações puladas" (alerta), quando
  `skipped_approval_stages` não estiver vazio, e o chip do SLA.
- O chip do SLA mostra "SLA até 14:30" (ou "até 19/11 11:00" se não for hoje):
  - cinza quando `on_time`;
  - amarelo quando `at_risk`;
  - vermelho, com o texto "SLA estourado", quando `overdue`.
- O chip de prazo continua na coluna própria.

**Detalhe** (`details/pre-trade-details.page.*`)

- Faixa de alerta no topo: "Trade antecipado por {nome} em {data}. Aprovações puladas: 1ª e 2ª.
  Motivo: {texto}."
- Chip do SLA ao lado do selo da etapa. O tooltip explica "4h úteis, seg. a sex., 9h às 18h".
- Aprovação parcial: se uma área já tinha aprovado (inclusive pela regra) e outra foi pulada, a
  etapa aparece como pulada na trilha, mas a lista de áreas do detalhe e o tooltip mostram cada uma
  com o seu estado ("Compliance: aprovado", "Risco: pulado"). Nada aprovado vira pulado, nada
  pulado vira aprovado (minha decisão).
- Etapas de aprovação com o estado "Pulada" (o mapa de tons dos selos de etapa, em `details/pre-trade-details.page.ts:55`, ganha a chave).
- `components/request-preview` (expansão da linha da lista) recebe o mesmo estado.

**Histórico** (`components/request-history`): transição com `payload.skipped_stages` tem o título
"Trade antecipado: aprovações puladas", com o motivo na nota.

**Fake** (`testing/pre-trade.fake.ts`): uma solicitação antecipada na Conferência e campos de SLA
nas demais, cobrindo os três tons. A troca de `ceo` vai junto.

Esboço do detalhe:

```
┌──────────────────────────────────────────────────────────────────────┐
│ ⚠ Trade antecipado por {nome} em 18/11 15:42.                         │
│   Aprovações puladas: 1ª e 2ª. Motivo: "janela de mercado fecha às 16h"│
└──────────────────────────────────────────────────────────────────────┘
 Solicitação #42 · Títulos de dívida   [Conferência] [SLA até 19/11 11:00]  prazo 22/11

 ●──────◌┄┄┄┄┄◌┄┄┄┄┄●──────◉──────○
 Rascunho  1ª apr.  2ª apr.  Trade  Conferência  Concluído
           pulada   pulada
 Etapa 5 de 6 · Conferência · aprovações puladas
```

### 5.8 Testes

**Shared, unitários**

- Calendário: fim de semana, feriado da B3, início antes das 9h e depois das 18h, virada de dia,
  minutos negativos em `business_minutes_between`.
- Motor:
  - vencimento gravado na entrada e na criação; nulo sem SLA e em etapa terminal;
  - `stage_sla` nos quatro status;
  - pulo exige motivo;
  - pulo fecha só as vagas abertas, com `SKIPPED`;
  - `skipped_stages` da 1ª e da 2ª;
  - validação de config.
- Módulo: avisos de pulo por permissão, aviso de SLA com chave estável.
- O `FakeWorkflowsRepository` acompanha.

**Shared, integração** (Postgres real, migrations de ponta a ponta): índice recriado aceita N vagas
`SKIPPED` do mesmo ator; enums novos; filtro `sla_overdue`; rename da permissão.

**BFF:** testes da lista da seção 5.6 e o snapshot regerado.

**Front** (Jasmine): trilha com `skipped`, `flowStepsOf` nos três casos, botão e diálogo de
antecipar, chip do SLA nos tons, faixa do detalhe, título do histórico.

## 6. Entrega

- Um card no TS por repositório, ou um card com três PRs, conforme o `/card` (a definir no plano).
  Branches `feature/TS-<id>-...` a partir da master.
- Validação local primeiro, depois a sandbox.
- **Ordem:**
  1. Role nova no Azure, criada e atribuída. Conferir na tela de controle de acesso que o diretor
     e o CEO aparecem com ela antes do deploy. Sem ninguém na role, a sincronização de usuários
     esvazia a permissão e a 2ª aprovação fica sem aprovador.
  2. Shared (migrations).
  3. BFF, logo em seguida.
  4. Front.
  5. Ligar o job do SLA.
  6. Definir os SLAs por migration (P4).
  7. Apagar a role antiga.

## 7. Deixado para quem implementa

- Nomes internos de funções, textos finos de tela e ícones dentro do que está aqui.
- A consulta exata de `skipped_approval_stages` (uma por página, sem N+1).
- O formato da data no chip (hoje x outro dia) e o arredondamento das horas no tooltip.
