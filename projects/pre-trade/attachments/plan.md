Status: rascunho
Data: 18/11/2026
Tags: pre-trade, workflows, sla, aprovacoes, portal

# Plano de implementação: SLA por etapa, trade antecipado e 2ª aprovação genérica

> **Para agentes:** use superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans, tarefa a tarefa. Os passos usam caixas (`- [ ]`).

**Objetivo:** SLA opcional por etapa em horas úteis, trade antecipado por Operações (aprovações
puladas, com motivo) e a 2ª aprovação pela permissão `portfolio-manager-pre-trade:approve`.

**Arquitetura:** o motor de workflows da shared ganha dois recursos genéricos (vencimento de SLA
gravado na entrada da etapa; transição marcada `skips_approvals` que fecha as vagas com `SKIPPED`).
O módulo `pre_trade` configura o fluxo, manda os avisos e expõe os campos. O BFF só troca o nome
da permissão; o front mostra SLA, pulo e o botão "Antecipar trade".

**Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Postgres 16, Celery, biblioteca `holidays`
(shared); FastAPI (BFF); Angular com Jasmine/Karma (front).

**Desenho:** `attachments/design.md` (as seções citadas como §5.x). Decisões: `decisions.md`.

## Restrições globais

- Horas úteis: seg. a sex., 9h às 18h, `America/Sao_Paulo`, sem `holidays.financial_holidays("BVMF")`.
- Migration aplicada não se altera; head atual da shared: `c3f81d5a92e7`.
- Valor novo de enum: `ALTER TYPE ... ADD VALUE IF NOT EXISTS` dentro de
  `op.get_context().autocommit_block()` (padrão `e80222c01aa3`); downgrade não remove o valor.
- Motor não cita Pré-Trade; `shared/business` não importa `src.infra` (`tests/test_arch.py`).
- Função nova de repositório entra também no `FakeWorkflowsRepository`
  (`tests/unit/shared/test_workflows_business.py`).
- Logs como eventos: mensagem fixa, dimensões no `extra`, um INFO por execução de job.
- Sem comentários divisores; comentário só para explicar um porquê.
- Nomes no código em inglês; textos de tela e e-mail em PT-BR, exatamente como abaixo.
- Commits: `feat(TS-<id>): ...` em PT-BR, até 72 caracteres, sem `Co-Authored-By`; branch por card;
  commit só depois da revisão do usuário.
- Pytest com `--basetemp=$HOME/.cache/pytest-<repo>` (o `/tmp` é tmpfs pequeno); apagar no fim.

## Foco de revisão

1. Operações antecipa enquanto um aprovador decide: o segundo a chegar recebe erro (o processo
   já saiu da etapa), sem vaga com duas decisões. Teste na Tarefa 8.
2. Solicitação que voltou dos Ajustes para a 1ª aprovação (rodada 2) e é antecipada: só as vagas
   da rodada 2 viram `SKIPPED`; a rodada 1 fica intacta. Teste na Tarefa 8.
3. Antecipar com Compliance já aprovado pela regra: Compliance continua `APPROVED`, Risco vira
   `SKIPPED`; a tela mostra cada área com o seu estado. Testes nas Tarefas 8 e 10.
4. SLA nas bordas: entrada às 17:59 com 1 minuto vence às 18:00 do mesmo dia; entrada às 18:00
   com 1 minuto vence às 09:01 do próximo dia útil; feriado da B3 no meio. Teste na Tarefa 1.
5. Rodada da 2ª aprovação aberta antes da troca do nome: depois da migration, quem tem
   `portfolio-manager:approve` decide a vaga normalmente (mesmo `permission_id`). Teste na Tarefa 14.

## Cards e branches

Épico TS-5046 (prefixo `[PRE-TRADE]`). Um card por entrega que se valida sozinha, passando pelos
repositórios que ela toca; branch `feature/TS-<id>-<descricao>` a partir da master, com
`--no-track`, em cada repositório do card.

| Card | Repositórios | Tarefas |
|---|---|---|
| TS-5846 SLA por etapa | shared, front | 1 a 5 |
| TS-5847 Trade antecipado | shared, front | 6 a 13 |
| TS-5848 2ª aprovação pela Gestão (Aprovação trade) | shared, BFF, front | 14 a 16 |

As migrations dos três cards ficam numa corrente só. Ordem de merge: SLA → trade antecipado → 2ª
aprovação. Se a ordem mudar, quem entra depois ajusta o `down_revision` para a head do momento.
Os cards 1 e 2 mexem no motor em pontos diferentes (`_move` nos dois): quem entra depois faz o
rebase.

Comandos da shared:

- Unitários: `python -m pytest <arquivos> -q -p no:cacheprovider --basetemp=$HOME/.cache/pytest-shared`
- Integração: subir o banco descartável e exportar a `CFG_TEST_DATABASE_URL` exatamente como no
  docstring de `tests/integration/shared/test_workflows.py:4-11`, depois `pytest tests/integration`.

Comandos do front: `npm test -- --watch=false --include='src/app/features/pre-trade/**/*.spec.ts'`
e, no fim de cada card, `npm test -- --watch=false` e `npm run lint`. Responsivo até o celular;
`prefers-reduced-motion` respeitado.

---

## Card 1: SLA por etapa (shared e front)

### Tarefa 1: calendário de horas úteis

**Arquivos:**
- Criar: `src/shared/utils/business_hours.py`
- Alterar: `requirements.in`, `requirements.txt` (via `make compile-requirements`)
- Teste: `tests/unit/shared/utils/test_business_hours.py`

**Interfaces:**
- Produz:
  - `BUSINESS_DAY_START = time(9, 0)`, `BUSINESS_DAY_END = time(18, 0)`
  - `is_business_day(day: date) -> bool`
  - `add_business_minutes(start: datetime, minutes: int) -> datetime`: `start` com fuso; resultado em
    `BUSINESS_TIMEZONE`. Início fora da janela anda para a próxima abertura; o fim da janela
    (18:00) é um vencimento válido.
  - `business_minutes_between(start: datetime, end: datetime) -> int`: minutos úteis; negativo se
    `end < start`.

- [ ] **Passo 1: testes que falham** (datas em `BUSINESS_TIMEZONE`)
  - `test_add_business_minutes_skips_weekend`: sex. 27/11/2026 16:00 + 240 → seg. 30/11/2026 11:00.
  - `test_add_business_minutes_starts_at_next_opening`: sáb. 28/11/2026 10:00 + 60 → seg. 30/11 10:00;
    seg. 30/11 07:30 + 30 → 30/11 09:30; seg. 30/11 17:30 + 60 → ter. 01/12 09:30.
  - `test_add_business_minutes_window_edges`: 30/11 17:59 + 1 → 30/11 18:00; 30/11 18:00 + 1 →
    01/12 09:01.
  - `test_add_business_minutes_skips_b3_holiday`: ter. 20/04/2027 17:00 + 120 → qui. 22/04/2027 10:00
    (21/04 é feriado nacional); `is_business_day(date(2027, 4, 21)) is False`.
  - `test_business_minutes_between`: sex. 27/11 17:00 → seg. 30/11 10:00 == 120; invertido == -120.
- [ ] **Passo 2:** rodar e ver falhar (módulo não existe).
- [ ] **Passo 3:** adicionar `holidays` ao `requirements.in`, rodar `make compile-requirements` e
  implementar o módulo. Calendário criado uma vez no módulo, como em
  `data-lake-api/src/shared/utils/business_days.py`.
- [ ] **Passo 4:** rodar e ver passar; `make check-requirements` sem diferença.
- [ ] **Passo 5:** commit `feat(TS-<id>): calendário de horas úteis com feriados da B3`.

### Tarefa 2: SLA no motor (migration, models e regras)

**Arquivos:**
- Criar: `src/infra/postgres/migrations/versions/<rev>_workflows_stage_sla.py`
  (`down_revision = 'c3f81d5a92e7'`)
- Alterar: `src/infra/postgres/models/workflows.py`, `src/shared/utils/constants.py`,
  `src/shared/business/workflows.py` (criação ~727, `_move` ~1485, `list_processes` ~1334),
  `src/shared/repository/workflows.py` (`move_process_to_stage` 590, `search_processes` 478, criação
  do processo), `src/shared/schemas/workflows.py`
- Teste: `tests/unit/shared/test_workflows_business.py` (e o fake), `tests/integration/shared/test_workflows.py`

**Interfaces:**
- Consome: `add_business_minutes`, `business_minutes_between` (Tarefa 1).
- Produz:
  - Banco: `workflows.stage.sla_business_minutes integer NULL` com
    `ck_stage_sla_business_minutes_positive CHECK (sla_business_minutes > 0)`;
    `workflows.process.stage_due_at timestamptz NULL`; enum `workflownotificationtype` + `SLA_OVERDUE`
    (`ALTER TYPE` num `autocommit_block`). O downgrade remove as colunas; o valor de enum fica.
  - `WorkflowNotificationType.SLA_OVERDUE`; `StageSlaStatus(StrEnum)`: `NONE="none"`,
    `ON_TIME="on_time"`, `AT_RISK="at_risk"`, `OVERDUE="overdue"` (em `constants.py`).
  - `StageSla` (dataclass em `shared/schemas/workflows.py`): `due_at: datetime | None`,
    `status: StageSlaStatus`, `business_minutes: int | None`.
  - `WorkflowBusiness.stage_sla(self, process: dict[str, Any], now: datetime | None = None) -> StageSla`:
    `NONE` sem SLA ou processo fechado; `OVERDUE` se `now > due_at`; `AT_RISK` se faltam
    `<= 25%` de `business_minutes` da config atual da etapa; senão `ON_TIME`.
  - `move_process_to_stage(process_id, stage_id, close: bool, stage_due_at: datetime | None)`.
  - `list_processes(..., sla_overdue: bool | None = None)` e o mesmo filtro em `search_processes`:
    `closed_at IS NULL AND stage_due_at < now()`.
  - `notification_emails` (570) trata `SLA_OVERDUE` como o `DEADLINE_OVERDUE`.

- [ ] **Passo 1: testes que falham**
  - `test_entering_stage_with_sla_sets_due_at`: etapa com `sla_business_minutes=240`, entrada sex.
    27/11/2026 16:00 (relógio congelado) → `stage_due_at` = seg. 30/11 11:00.
  - `test_entering_stage_without_sla_clears_due_at` e `test_terminal_stage_has_no_due_at`.
  - `test_process_creation_sets_due_at_for_initial_stage`.
  - `test_stage_sla_statuses`: os quatro status, incluindo `AT_RISK` com 60 de 240 minutos restantes.
  - Integração: `test_stage_sla_must_be_positive` (`0` viola a check) e
    `test_list_processes_sla_overdue_filter`.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** migration, models, enums e regras. O vencimento é calculado em Python a partir
  de `get_utc_now()` no momento da mudança; etapa terminal grava nulo.
- [ ] **Passo 4:** unitários, integração inteira, `alembic downgrade -1` e `upgrade head` no banco
  descartável, `python -m pytest tests/test_arch.py`.
- [ ] **Passo 5:** commit `feat(TS-<id>): vencimento de SLA na entrada da etapa`.

### Tarefa 3: SLA no Pré-Trade (leitura e aviso)

**Arquivos:**
- Alterar: `src/modules/pre_trade/business.py` (`_summary` 957, `_variables` 926, método novo),
  `src/modules/pre_trade/viewer.py` (task nova), `src/modules/pre_trade/schemas.py` (resumo e
  resposta da task), `src/infra/celery/tasks.py`
- Teste: `tests/unit/modules/pre_trade/test_pre_trade_business.py`, `test_pre_trade_viewer.py`,
  `tests/unit/infra/test_celery_tasks.py`

**Interfaces:**
- Consome: `stage_sla`, `list_processes(sla_overdue=...)` (Tarefa 2).
- Produz:
  - No resumo da lista e do detalhe: `stage_due_at: datetime | None`,
    `stage_sla_status: StageSlaStatus`, `stage_sla_business_minutes: int | None`.
  - `PreTradeBusiness.notify_sla_overdue(self, page_size: int = 100) -> int`: pagina
    `list_processes(is_open=True, sla_overdue=True)`; destinatários como `_overdue_emails` (nos
    Ajustes, só quem abriu); chave `pre-trade:{key}:{stage}:{stage_entered_at}:sla-overdue`.
  - Variáveis novas: `sla_hours` (minutos/60, sem casas se inteiro) e `stage_due_at`
    (dd/mm/aaaa hh:mm).
  - Task `notify_sla_overdue() -> SlaOverdueReminderResponse(reminded: int, dispatched: int)` no
    viewer; entrada em `tasks.py` igual à de `remind_overdue_requests` (fila padrão, `schedulable`).
  - Log: `"[PRE-TRADE] SLA overdue requests reminded"`, `extra={"reminded", "dispatched"}`.

- [ ] **Passo 1: testes que falham**
  - `test_summary_exposes_sla` (os três campos).
  - `test_notify_sla_overdue_key_is_stable`: duas execuções geram a mesma chave.
  - `test_notify_sla_overdue_in_adjustments_goes_to_creator`.
  - `test_notify_sla_overdue_disabled_does_not_query` (aviso desligado na config).
  - Em `test_celery_tasks.py`, a lista de tasks agendáveis inclui `pre_trade.notify_sla_overdue`.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar e ver passar.
- [ ] **Passo 5:** commit `feat(TS-<id>): SLA da etapa e aviso de SLA estourado no Pré-Trade`.

### Tarefa 4: configuração do SLA no Pré-Trade (migration de dados)

**Arquivos:**
- Criar: `src/infra/postgres/migrations/versions/<rev>_pre_trade_sla_notification.py`
  (`down_revision` = Tarefa 2), no padrão de `450e6b005132_pre_trade_bypass.py` (`SENDER_KEY`,
  `CREATED_BY = 'migration'`, `sa.table` leves) e de `c3f81d5a92e7` para o job
- Teste: `tests/integration/test_pre_trade_integration.py`

**Conteúdo:**
- `notification_config` ativa para `SLA_OVERDUE` com o template `pre-trade-sla-overdue`.
- Template (`email_dispatch.templates`, versão 1, com o `_FOOTER` do Pré-Trade): assunto
  `Pré-Trade #{{ request_id }}: SLA estourado em {{ stage_label }}`; corpo: "A solicitação de
  pré-trade **#{{ request_id }}** ({{ request_type_label }}) está em **{{ stage_label }}** e passou
  do SLA de {{ sla_hours }}h úteis. Vencimento: {{ stage_due_at }}."
- `scheduler.scheduled_jobs`: nome `avisos-pre-trade-sla-estourado`,
  `job_type = 'pre_trade.notify_sla_overdue'`, `CRON`, `*/15 9-18 * * 1-5`, `America/Sao_Paulo`,
  `payload = {}`, `is_active = false`.
- `workflows.stage.sla_business_minutes = 180` em `PENDING_FIRST_APPROVAL`, `PENDING_SECOND_APPROVAL`,
  `PENDING_TRADE`, `PENDING_FINAL_CHECK` e `PENDING_ADJUSTMENTS` do Pré-Trade (D18); `DRAFT` fica nulo.
  Downgrade apaga as linhas inseridas e volta o SLA para nulo.

- [ ] **Passo 1:** testes de integração que falham: `test_pre_trade_stages_have_default_sla` (180 nas
  cinco etapas, nulo no rascunho), `test_sla_job_row_is_inactive`,
  `test_sla_overdue_template_renders` (renderiza com as variáveis da Tarefa 3).
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** escrever a migration.
- [ ] **Passo 4:** integração inteira, `downgrade -1` e `upgrade head`.
- [ ] **Passo 5:** commit `feat(TS-<id>): configura o aviso de SLA do Pré-Trade`.

### Tarefa 5: chip do SLA na lista e no detalhe (front)

**Arquivos:**
- Criar: `features/pre-trade/components/sla-chip/sla-chip.component.{ts,html,scss,spec.ts}`
- Alterar: `features/pre-trade/data-access/pre-trade.dto.ts`, `pre-trade-list.ts` (`toListItem`),
  `pre-trade.page.html:105-118` (célula da Etapa), `details/pre-trade-details.page.{html,ts}`
  (ao lado do selo da etapa, linhas 22-38), `testing/pre-trade.fake.ts`, `testing/pre-trade.fixtures.ts`
- Teste: spec do chip, `pre-trade-list.spec.ts`, spec da página de detalhe

**Interfaces:**
- DTO: `PreTradeSlaStatus = 'none' | 'on_time' | 'at_risk' | 'overdue'`; no resumo
  `stage_due_at: string | null`, `stage_sla_status: PreTradeSlaStatus`,
  `stage_sla_business_minutes: number | null`.
- `SlaChipComponent`: entradas `status: PreTradeSlaStatus`, `dueAt: string | null`,
  `businessMinutes: number | null`; nada é exibido com `none`.
- Texto: "SLA até 14:30" quando vence hoje (fuso `America/Sao_Paulo`), senão "SLA até 19/11 11:00";
  `overdue` mostra "SLA estourado". Tons: `on_time` neutro, `at_risk` alerta, `overdue` perigo
  (mesmos tons do `PillComponent` do chip de prazo). Tooltip: "SLA de {h}h úteis (seg. a sex., 9h
  às 18h). Vence em dd/mm/aaaa hh:mm."
- Fake: SLA nos três tons nas solicitações abertas.

- [ ] **Passo 1:** specs que falham: chip nos três tons e nos dois formatos de data; nada com
  `none`; `toListItem` leva os campos de SLA.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** suíte inteira do front e lint.
- [ ] **Passo 5:** commit `feat(TS-<id>): chip de SLA da etapa no Pré-Trade`.

## Card 2: trade antecipado (shared e front)

### Tarefa 6: migration e models do pulo de aprovações

**Arquivos:**
- Criar: `src/infra/postgres/migrations/versions/<rev>_workflows_skip_approvals.py`
  (`down_revision` = head do card 1)
- Alterar: `src/infra/postgres/models/workflows.py`, `src/shared/utils/constants.py`
- Teste: `tests/integration/shared/test_workflows.py`

**Interfaces:**
- Produz:
  - `workflows.transition.skips_approvals boolean NOT NULL DEFAULT false`.
  - Constraint `uq_transition_workflow_id_stages` removida; índice único parcial
    `uq_transition_manual_stages (workflow_id, previous_stage_id, next_stage_id) WHERE on_decision IS NULL`.
  - Índice `uq_approval_decider_per_round` recriado com o predicado
    `status <> 'PENDING' AND status <> 'SKIPPED' AND rule_id IS NULL`.
  - Enums: `workflowapprovalstatus` + `SKIPPED`; `workflownotificationtype` + `APPROVALS_SKIPPED`;
    em Python, `WorkflowApprovalStatus.SKIPPED` e `WorkflowNotificationType.APPROVALS_SKIPPED`.
  - O downgrade desfaz coluna e índices (volta a constraint de pares); os valores de enum ficam.

- [ ] **Passo 1: testes de integração que falham**
  - `test_skipped_rows_by_same_actor_in_one_round`: o mesmo usuário grava duas linhas `SKIPPED`
    (vagas de permissões diferentes) na mesma rodada sem violar índice.
  - `test_manual_and_decision_transition_to_same_stage`: uma saída manual e uma por `APPROVED`
    para o mesmo destino são aceitas; duas manuais para o mesmo destino violam
    `uq_transition_manual_stages`.
- [ ] **Passo 2:** rodar contra o banco descartável e ver falhar.
- [ ] **Passo 3:** migration (DDL e os `ALTER TYPE` num `autocommit_block`), models e enums.
- [ ] **Passo 4:** integração inteira, `downgrade -1` e `upgrade head`.
- [ ] **Passo 5:** commit `feat(TS-<id>): colunas e índices do pulo de aprovações`.

### Tarefa 7: duas saídas para o mesmo destino

**Arquivos:**
- Alterar: `src/shared/business/workflows.py` (`_resolve_transition` 1420, `apply_transition` 767)
- Teste: `tests/unit/shared/test_workflows_business.py`

**Regras:** `_resolve_transition` considera só as saídas manuais (`on_decision` nulo); destino que só
tem saída por decisão mantém o erro "use decide()". As decisões continuam pelo
`_decision_transition` (1466).

- [ ] **Passo 1:** teste que falha, `test_manual_exit_and_approval_to_same_stage`: `apply_transition`
  usa a saída manual; `decide(APPROVED)` usa a de decisão; sem saída manual, o erro de hoje.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar e ver passar.
- [ ] **Passo 5:** commit `feat(TS-<id>): saída manual e por decisão para a mesma etapa`.

### Tarefa 8: transição que pula aprovações no motor

**Arquivos:**
- Alterar: `src/shared/business/workflows.py` (config ~180-360, `apply_transition` 767, `_move`
  1485, `stage_permission_names` 597, `_participant_permission_ids` 1443, `available_transitions`
  1103), `src/shared/repository/workflows.py`, `src/shared/schemas/workflows.py`
  (`StageTransitionPayload`), `src/shared/utils/workflow_errors.py`,
  `src/infra/fastapi/exceptions_handlers.py` (`_WORKFLOW_ERROR_STATUS`)
- Teste: `tests/unit/shared/test_workflows_business.py` (e o fake), `tests/integration/shared/test_workflows.py`

**Interfaces:**
- Produz:
  - `ReasonRequiredError(WorkflowError)`, mapeado para o status 422 em `_WORKFLOW_ERROR_STATUS`.
  - `StageTransitionPayload.skipped_stages: list[str] | None = None`.
  - `WorkflowBusiness._skipped_stages(self, origin_stage_id: int) -> list[str]`: a partir da
    origem, segue as saídas `APPROVED` enquanto o destino for etapa de aprovação.
  - `WorkflowBusiness.skipped_approval_stages(self, process_ids: list[int]) -> dict[int, list[str]]`,
    apoiado no repositório `list_skipped_stages_by_process(process_ids) -> dict[int, list[str]]`
    (uma consulta: eventos `STAGE_TRANSITION` com `kwargs->'skipped_stages'` não nulo, união por
    processo, na ordem das etapas).
  - Linhas de `available_transitions` passam a levar `skips_approvals: bool`.
  - `_assert_skips_approvals`: `skips_approvals` só em saída com `on_decision` nulo que parte de
    etapa de aprovação; senão `WorkflowConfigurationError`.
- Regras (§5.3):
  - Com `skips_approvals`: `notes` vazio ou só espaços → `ReasonRequiredError`; cada vaga aberta da
    rodada atual da origem ganha linha `SKIPPED` (`decided_by` = ator, `reason` = `notes`); vagas
    já decididas ficam; o evento `STAGE_TRANSITION` leva `skipped_stages`.
  - `stage_permission_names` e `_participant_permission_ids` ignoram as saídas com
    `skips_approvals`: Operações não recebe avisos nem anexa durante as aprovações.

- [ ] **Passo 1: testes que falham** (fluxo de teste com duas etapas de aprovação, como o Pré-Trade)
  - `test_skip_requires_reason`: `notes=None` e `notes="  "` → `ReasonRequiredError`.
  - `test_skip_from_first_approval_skips_open_slots`: vagas abertas viram `SKIPPED` com o ator e o
    motivo; payload `skipped_stages == ["FIRST", "SECOND"]` (nomes do fluxo de teste).
  - `test_skip_keeps_slots_already_decided`: vaga aprovada pela regra continua `APPROVED`.
  - `test_skip_only_touches_current_round`: rodada 1 (devolvida) intacta; só a rodada 2 recebe `SKIPPED`.
  - `test_skip_from_second_approval`: `skipped_stages == ["SECOND"]`.
  - `test_skip_transition_not_counted_as_stage_actor`: `stage_permission_names` e
    `_participant_permission_ids` da etapa de aprovação não incluem a permissão só autorizada na
    saída `skips_approvals`.
  - `test_config_rejects_skip_flag_outside_approval_stage`.
  - `test_decide_after_skip_fails`: depois do pulo, decidir na etapa antiga dá erro e não grava linha.
  - `test_skipped_approval_stages_by_process`.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar; atualizar o `FakeWorkflowsRepository`.
- [ ] **Passo 4:** unitários, integração e `tests/test_arch.py`.
- [ ] **Passo 5:** commit `feat(TS-<id>): transição que pula aprovações no motor`.

### Tarefa 9: trade antecipado no Pré-Trade (leitura, aviso e configuração)

**Arquivos:**
- Alterar: `src/modules/pre_trade/business.py` (`_summary` 957, `_transition_rows` 1025,
  `move_request` 453, `_variables` 926, método novo), `src/modules/pre_trade/schemas.py`
- Criar: `src/infra/postgres/migrations/versions/<rev>_pre_trade_early_trade.py`
  (`down_revision` = Tarefa 6), no padrão de `450e6b005132_pre_trade_bypass.py`
- Teste: `tests/unit/modules/pre_trade/test_pre_trade_business.py`, `test_pre_trade_viewer.py`,
  `tests/integration/test_pre_trade_integration.py`

**Interfaces:**
- Consome: `skipped_approval_stages`, `skips_approvals` (Tarefa 8).
- Produz:
  - No resumo da lista e do detalhe: `skipped_approval_stages: list[PreTradeStage]`; em
    `available_transitions[]` (`AvailableTransitionResponse`): `skips_approvals: bool`.
  - `PreTradeBusiness._notify_skipped(self, process, origin: PreTradeStage, skipped: list[str], actor_name: str | None, reason: str) -> None`:
    um aviso por permissão com config **ativa** nas etapas puladas; destinatários = membros da
    permissão; chave `pre-trade:{key}:{origin}:{stage_entered_at}:skipped:{permission_name}`;
    variáveis novas `permission_alias` e `skipped_stage_labels` ("1ª e 2ª aprovação" ou "2ª aprovação").
- Migration:
  - Transições com `skips_approvals = true` e `authorized_permission` de `operations:update`:
    `PENDING_FIRST_APPROVAL → PENDING_TRADE` e `PENDING_SECOND_APPROVAL → PENDING_TRADE`.
  - `notification_config` ativa para `APPROVALS_SKIPPED` com o template `pre-trade-approvals-skipped`:
    assunto `Pré-Trade #{{ request_id }}: trade antecipado, aprovação de {{ permission_alias }} pulada`;
    corpo: "{{ actor_name }} antecipou o trade da solicitação de pré-trade **#{{ request_id }}**
    ({{ request_type_label }}). A {{ skipped_stage_labels }} foi pulada para {{ permission_alias }}.
    Motivo: {{ reason }}." (com o `_FOOTER` do Pré-Trade).
  - Downgrade apaga as linhas inseridas.

- [ ] **Passo 1: testes que falham**
  - `test_summary_exposes_skipped_approval_stages` (uma consulta por página, não por item).
  - `test_transition_rows_flag_skips_approvals`.
  - `test_early_trade_notifies_skipped_permissions`: da 1ª aprovação, avisos para Compliance, Risco
    e a permissão da 2ª; nenhum para permissão com config inativa.
  - `test_early_trade_from_second_approval_notifies_only_second`.
  - Integração: `test_operations_can_early_trade_from_first_approval` (vai para `PENDING_TRADE`,
    vagas `SKIPPED`, `skipped_approval_stages` no resumo, Operações edita e envia para a
    Conferência) e `test_approver_still_approves_to_trade`.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar e escrever a migration.
- [ ] **Passo 4:** unitários, integração inteira, `downgrade -1` e `upgrade head`.
- [ ] **Passo 5:** commit `feat(TS-<id>): trade antecipado no Pré-Trade`.

### Tarefa 10: dados, fake e estado "pulada" das aprovações (front)

**Arquivos:**
- Alterar: `features/pre-trade/data-access/pre-trade.dto.ts`, `pre-trade.approvals.ts`
  (`flowStepsOf` 116, `roundState` ~232, `FLOW_STEP_STATUS`), `components/approval-dots/*`,
  `pre-trade-list.ts` (`toListItem`), `details/pre-trade-details.page.ts:55`,
  `components/request-preview/*`, `testing/pre-trade.fake.ts`, `testing/pre-trade.fixtures.ts`
- Teste: `pre-trade.approvals.spec.ts`, `pre-trade-list.spec.ts`,
  `components/approval-dots/approval-dots.component.spec.ts`

**Interfaces:**
- DTO: no resumo `skipped_approval_stages: PreTradeStage[]`; em `available_transitions[]`
  `skips_approvals: boolean`; status de vaga `'SKIPPED'`; payload de `STAGE_TRANSITION` com
  `skipped_stages?: PreTradeStage[] | null`.
- `flowStepsOf` devolve `state: 'skipped'` para cada etapa de `skipped_approval_stages`, com
  `action` (quem, quando, motivo) do evento de pulo; rótulo "Pulada" para esse caso e
  "Não realizada" para o rejeitado.
- Fake: uma solicitação antecipada da 1ª aprovação, em `PENDING_TRADE`, com Compliance aprovado
  pela regra e Risco `SKIPPED`.

- [ ] **Passo 1: specs que falham**
  - `flowStepsOf` com pulo da 1ª: 1ª e 2ª `skipped`, Trade `current`; com pulo da 2ª: só a 2ª.
  - Aprovação parcial: Compliance `approved`, Risco `skipped` na lista de áreas da etapa.
  - `toListItem` leva `skipped_approval_stages`.
  - `approval-dots` mostra o estado pulado com o tooltip "Pulada (trade antecipado)".
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar e ver passar.
- [ ] **Passo 5:** commit `feat(TS-<id>): estado de aprovação pulada no Pré-Trade`.

### Tarefa 11: botão "Antecipar trade" (front)

**Arquivos:**
- Alterar: `features/pre-trade/pre-trade.workflow.ts` (`actionsFor` 134-160, `confirmTransition` 306)
- Teste: `pre-trade.workflow.spec.ts`

**Regras:** transição com `skips_approvals` vira a ação `early-trade-${stage}`, rótulo
"Antecipar trade", tom de alerta, ícone de avanço (do conjunto próprio de ícones). O clique abre o
`RejectReasonDialogComponent` com `tone: 'warning'`, título "Antecipar trade", mensagem "As
aprovações pendentes serão puladas e ficarão registradas no histórico. A solicitação vai para a
execução do trade, e o resto do fluxo segue normal.", rótulo do campo "Motivo", botão "Antecipar",
e chama `moveRequest(key, stage, reason)`.

- [ ] **Passo 1:** specs que falham: a transição marcada gera a ação "Antecipar trade"; a saída
  normal para o Trade continua só como decisão "Aprovar"; confirmar chama `moveRequest` com o motivo.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar e ver passar.
- [ ] **Passo 5:** commit `feat(TS-<id>): ação de antecipar o trade no Pré-Trade`.

### Tarefa 12: trilha com etapas puladas (front)

**Arquivos:**
- Alterar: `components/stage-track/stage-track.component.{ts,html,scss}`,
  `details/pre-trade-details.view.ts` (`trackOf` ~92-103)
- Teste: `components/stage-track/stage-track.component.spec.ts`

**Interfaces:** `StepState` ganha `'skipped'`; entrada nova `skippedStages = input<PreTradeStage[]>([])`;
casa pulada tracejada, com ícone de pulo e cor de alerta, e o trecho que sai dela tracejado; legenda
`Etapa 4 de 6 · Trade · aprovações puladas` quando houver pulo.

- [ ] **Passo 1:** specs que falham: pulo da 1ª marca 1ª e 2ª como `skipped` e o Trade como
  `current`; legenda com "aprovações puladas"; sem pulo, nada muda.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar e ver passar.
- [ ] **Passo 5:** commit `feat(TS-<id>): etapas puladas na trilha do Pré-Trade`.

### Tarefa 13: selo da lista, faixa do detalhe e histórico (front)

**Arquivos:**
- Alterar: `pre-trade.page.html:105-118` (selo "Aprovações puladas", tom de alerta, quando
  `skipped_approval_stages` não estiver vazio), `details/pre-trade-details.page.{html,ts}` (faixa no
  topo), `components/request-history/request-history.component.ts` (`transitionTitle` 183-203)
- Teste: specs da lista, da página de detalhe e do histórico

**Textos:**
- Faixa do detalhe, quando houver pulo: "Trade antecipado por {nome} em {dd/mm hh:mm}.
  Aprovações puladas: {1ª e 2ª | 2ª}. Motivo: {motivo}." (dados do evento de pulo no histórico).
- Histórico: transição com `payload.skipped_stages` preenchido tem o título "Trade antecipado:
  aprovações puladas", testado antes dos títulos de hoje (`to === 'PENDING_TRADE'`).

- [ ] **Passo 1:** specs que falham: selo e faixa aparecem só com pulo; título do histórico.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** suíte inteira do front e lint.
- [ ] **Passo 5:** commit `feat(TS-<id>): aviso de trade antecipado na lista e no detalhe`.

## Card 3: 2ª aprovação pela Gestão (shared, BFF e front)

### Tarefa 14: renomear a permissão na shared

**Arquivos:**
- Criar: `src/infra/postgres/migrations/versions/<rev>_pre_trade_portfolio_manager_approval.py`
  (`down_revision` = head do momento), no padrão de `fe689412a2fe_pre_trade_bypass_policy.py`
- Alterar: testes de integração que esperam `ceo` depois das migrations
  (`tests/integration/test_pre_trade_integration.py:82`)

**Conteúdo:** `UPDATE workflows.permission SET group_name='portfolio-manager',
alias='Gestão (Aprovação trade)' WHERE scope='pre-trade' AND group_name='ceo' AND policy='approve'`;
downgrade volta para `ceo`/`CEO`. Docstring: a app role no Azure precisa ter o mesmo valor.

- [ ] **Passo 1:** teste de integração que falha, `test_second_approval_round_survives_rename`: abre a
  rodada da 2ª aprovação antes da migration, aplica a migration e decide com `portfolio-manager:approve`.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** escrever a migration e ajustar o teste que esperava `ceo`.
- [ ] **Passo 4:** rodar a integração inteira.
- [ ] **Passo 5:** commit `feat(TS-<id>): 2ª aprovação do Pré-Trade pela Gestão`.

### Tarefa 15: BFF

**Arquivos (master do `apl-credit-whitelabel-api`):**
- Alterar: `src/shared/utils/permissions.py` (`DEPARTMENT_NAMES` ganha
  `"portfolio-manager": "Gestão (Aprovação trade)"`, o `ceo` fica; entrada do catálogo 562-566 vira
  `PermissionScope("portfolio-manager-pre-trade", "Pré-Trade (Gestão – Aprovação trade)", (ScopeAction(Policies.APPROVE, "Decide a 2ª aprovação."),))`),
  `src/modules/access_control/business/pages.py:180,219`, `src/modules/pre_trade/business/__init__.py:65`,
  `src/modules/account/viewer/iam.py:160`, `local/seed/pre_trade.py`
- Teste: `tests/snapshots/route_permissions.json` (regerar; `ceo-poli-knowledge-base` fica),
  `tests/unit/modules/pre_trade/test_business.py:79`, `tests/contract/test_pre_trade.py`,
  `tests/unit/modules/access_control/test_pages.py`, `test_scope_rule.py`,
  `tests/unit/modules/account/test_app_role_assignments.py`, `tests/unit/services/test_azure_app_roles.py`

- [ ] **Passo 1:** trocar as expectativas dos testes para `portfolio-manager` e ver falhar.
- [ ] **Passo 2:** alterar o código.
- [ ] **Passo 3:** rodar a suíte inteira do BFF, inclusive `tests/test_arch_route_permissions.py`.
- [ ] **Passo 4:** commit `feat(TS-<id>): 2ª aprovação do Pré-Trade pela Gestão no BFF`.

### Tarefa 16: front (nome da permissão)

**Arquivos (`apl-credit-whitelabel`, `src/app`):**
- Alterar: `core/auth/groups.constants.ts` (`PORTFOLIO_MANAGER: { label: "Gestão (Aprovação trade)", value: "portfolio-manager" }` no lugar de `CEO`),
  `features/pre-trade/pre-trade.permissions.ts:12`, `core/auth/iam/write-needs-read.ts:29`,
  `features/pre-trade/testing/pre-trade.fake.ts:43`, `features/access-control/testing/access-control.fake.ts:116-118,270`
- Teste: os specs com `ceo` listados no §5.6 do desenho.

- [ ] **Passo 1:** trocar as expectativas dos specs e ver falhar.
- [ ] **Passo 2:** alterar o código.
- [ ] **Passo 3:** `npm test -- --watch=false` e `npm run lint` passando.
- [ ] **Passo 4:** commit `feat(TS-<id>): 2ª aprovação do Pré-Trade pela Gestão no front`.

## Entrega

1. Usuário cria e atribui a app role `portfolio-manager-pre-trade:approve` no Azure e confere na
   tela de controle de acesso (antes do deploy do card 3).
2. Validação local de cada card; depois a sandbox (release da semana).
3. Deploy de cada card: shared → BFF logo em seguida → front.
4. Ligar o job `avisos-pre-trade-sla-estourado` em cada ambiente (card 1).
5. SLA padrão de 3h úteis já vem na migration do card 1 (D18); mudar é uma migration nova.
6. Usuário apaga a role `ceo-pre-trade:approve` depois do deploy do card 3.
