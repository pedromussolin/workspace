# C - Scheduler no banco (shared) x rotinas periódicas da cessão

Fontes: `apl-shared-service` origin/master `8e4a1ab`; `platform-cessao` origin/master `579ad13e3`;
`platform-cessao-argocd` HEAD local `4e99643`. Só leitura. **[C]** = visto no código, **[H]** = hipótese.
Termos: *beat* = processo do Celery que dispara tasks por horário; *cron* = expressão de horário de 5 campos;
*SKIP LOCKED* = o Postgres pula linhas já travadas por outra transação; *dedupe* = descartar execução repetida.

## Conclusão
- A shared já tem um scheduler completo no banco, quase todo copiável em lógica. O que muda é a cola com o
  framework (FastAPI/SQLAlchemy 2 na shared; Flask/SQLAlchemy 1.3 na cessão) e o Celery (5.5.3 x 5.2.2).
- A cessão tem 6 entradas no beat fixo (`registro.py`) e nenhum CronJob do Kubernetes. Todas parecem
  operacionais agendáveis; uma delas (renegociação BGT) e a baixa de registro tendem a ser candidatas a evento.
- O beat da cessão é 1 réplica por configuração de infra: não há proteção contra duplo disparo no código.

## 1. Shared: de ponta a ponta [C]

### Tabelas (schema `scheduler`) - `src/infra/postgres/models/scheduled_jobs.py`
- `scheduled_jobs` (:21-58): `id`, `key` (uuid), `name` (único), `job_type` (`{módulo}.{função}`),
  `schedule_type` (`CRON` | `ONCE`), `cron_expression`, `run_at` (só ONCE), `timezone` (nome IANA, ex.
  America/Sao_Paulo), `payload` (JSONB = kwargs da task), `is_active`, `last_run_at`, `next_run_at`,
  `created_by`, `updated_by`, `created_at`, `updated_at`. CHECK (:24-29) obriga cron XOR run_at.
  Índice parcial `ix_scheduled_jobs_due` em `next_run_at` onde ativo (:30-34).
- `job_executions` (:61-85): `scheduled_job_id`, `task_id` (único = id do Celery), `trigger_type`
  (`SCHEDULED`|`MANUAL`), `status` (PENDING, RUNNING, SUCCEEDED, FAILED, SKIPPED, MISSED, REVOKED),
  `scheduled_for`, `payload`, `result` (JSONB), `error`, `created_by`, `started_at`, `finished_at`.
  Enums em `modules/scheduled_jobs/business.py:29-41`.
- Migrations: `9ab95b36b58e_scheduled_jobs.py` (cria schema e tabelas, 25/09/2026);
  `0c6c13336616_report_transfer_scheduled_jobs.py` (insere os jobs que o beat fixo tinha, `created_by='migration'`,
  cron convertido de UTC para Brasília, `timezone='America/Sao_Paulo'`, uuids fixos, `JOBS` na linha ~41);
  `5b2e9c41d7a3_report_transfer_flows_from_code.py`.

### Como uma task vira agendável
- `src/infra/celery/tasks.py:~18-75`: lista `tasks_data` com `"schedulable": True`; `TaskElement`
  (`tasks_models.py`) tem `module`, `function`, `queue`, `schedulable`. `job_type = "{module}.{function}"`.
- `CeleryManager._apply_tasks` (`infra/celery/__init__.py:218-262`) registra a task e guarda as agendáveis em
  `_schedulable_tasks` (:237-245); a função fica no `viewer.py` do módulo.
- Validação (`business.py:72-88`, `validate_job`): fuso válido, cron de 5 campos (`shared/utils/cron.py:14-37`,
  croniter), `job_type` existe, payload validado contra a assinatura da função (`shared/utils/task_kwargs.py`,
  sem coerção de tipo). Roda ao salvar e a cada disparo.
- Metadado de parâmetro: `Annotated[str, Field(description=...)]` (ex. `report_transfer/viewer.py:119`);
  `task_parameters`/`task_summary` (`task_kwargs.py:39-61`) alimentam `GET /job-types`.

### Quem lê o banco e dispara
- `main_celery.py`: liga `scheduled_jobs.dispatch_due_jobs` como extensão do beat só se
  `CFG_SCHEDULED_JOBS_BEAT_ENABLED` (padrão false) e conecta os sinais `task_prerun/postrun` e `task_skipped`.
- `infra/celery/scheduler.py:15-38`: `ExtendedScheduler(PersistentScheduler)` sobrescreve `tick()` e chama a
  extensão; ela devolve em quantos segundos voltar. Sem entradas fixas no beat.
- `dispatch_due_jobs` (`business.py:204-232`): (1) calcula `next_run_at` de quem foi ativado direto no banco
  (:234-254); (2) `lock_due_jobs` com `FOR UPDATE SKIP LOCKED` (`repository.py:193-207`); (3) grava a
  execução como PENDING e **commita antes de publicar**; (4) publica na fila com header
  `scheduled_job_execution_key` (`repository.py:89-97`); falha de publicação vira FAILED, nunca segundo disparo.
- Espera: `poll_interval_seconds` 15 (1-300), mínimo `min_wait_seconds` 1, lote `batch_size` 50; usa o
  próximo vencimento para acordar antes (`ScheduledJobsSettings`, `config/__init__.py:506-520`).
- Atraso: `misfire_grace_seconds` 900; passou disso a ocorrência vira MISSED e não roda. Próxima ocorrência é
  contada a partir de agora (depois de parada, roda uma vez só) (`_record_occurrence`, :256-296).
- Resultado: `on_task_prerun` -> RUNNING; `on_task_postrun` -> SUCCEEDED/FAILED/REVOKED com `result` ou `error`
  truncado (`viewer.py:249-275`, `business.py:319-353`).

### Execução dupla com várias réplicas
- Entre beats: `SKIP LOCKED` (README:331). Entre mensagens: dedupe em Redis com chave `processed` (id da task) e
  `inflight` (hash dos argumentos, TTL) em `infra/celery/__init__.py:80-191`; descarte vira SKIPPED. Exige Redis.

### Dia útil e feriado
- **Não existe** no scheduler (grep sem resultado em `src`): só cron + fuso (com horário de verão tratado).
  Dia útil, quando necessário, fica dentro da task [C] (ausência) - a decisão de onde pôr é da cessão.

### Rotas (`modules/scheduled_jobs/viewer.py`, router tag TASKS)
`GET /job-types?module=`, `GET ?is_active=&module=` (lista com última execução), `POST` (cria),
`GET|PUT|PATCH|DELETE /{key}` (delete só se nunca rodou), `POST /{key}/run` (dispara agora, mesmo inativo,
aceita `payload` extra), `GET /{key}/executions`, `GET /executions` (filtros module, job, status, trigger,
datas; paginação limit<=200), `GET /executions/summary`. Filtro `module` = prefixo `job_type LIKE 'módulo.%'`
com autoescape (`repository.py:26-28`). Erros: 404/409/422/502 (`viewer.py:41-46`).

### Versões [C]
Celery 5.5.3 (broker SQS), SQLAlchemy 2.0.44, FastAPI 0.117.1, pydantic 2.13.4, croniter 6.2.4, redis 7.1.0
(`requirements.txt`). Tasks agendáveis hoje: report_transfer (3), scheduled_jobs.ping, email_dispatch.purge_messages,
pre_trade.remind_overdue_requests, workflows.sync_users.

## 2. Cessão: inventário de rotinas periódicas [C]

Beat fixo em `cessao/schedule/registro.py:36-64`. Sem `timezone` configurado: tudo é **UTC**. Fila por
`task_routes` (:24-35). Natureza = sugestão **[H]** (validar com operação).

| # | Entrada | Task (linha) | Horário | O que faz | Origem do horário | Natureza [H] |
|---|---|---|---|---|---|---|
| 1 | contrato_registro_baixa_task | `tasks/registro.py:27` | 12:00 UTC (9h BRT), :39 | Para cada produto com regra "arranjo" ativa, enfileira a baixa de contratos liquidados (janela D-2) | fixo no código | (b) por evento: baixa deveria sair da liquidação; hoje usa carência de 2 dias. Se mantida por lote, (a) |
| 2 | contrato_renegociacao_bgt_task | `tasks/renegociacao/renegociacao.py:126` | 11:00 UTC (8h BRT), :44 | Lê fundos do BGT e enfileira obtenção de contratos renegociados | fixo | (a), porque o BGT disponibiliza arquivo e não avisa; (b) só se houver webhook/arquivo detectável |
| 3 | contrato_calculo_taxa_operacao_task | `tasks/taxa_operacao/taxa_operacao.py:10` | 20:00 UTC (17h BRT), :48 | Calcula taxa de operação dos produtos com `calcular_taxa_operacao=True` | fixo; seleção por `ProdutoConfig` | (a) cálculo diário |
| 4 | liquidacao_fecha_lote_task | `tasks/liquidacao_lote.py:240` | 19:00 UTC (16h BRT), :52 | Fecha lotes de liquidação dos produtos com `baixa_por_agendamento` (por vigente ou `proc_id`) | fixo; produto escolhe por flag | (a); horário por produto seria ganho (hoje um só) |
| 5 | conciliacao_liquidacao_corte_task | `tasks/conciliacao_liquidacao.py:190` | corte (padrão 14:00 BRT) via `crontab_do_horario`, :58 | Concilia a fila do dia depois do corte (aprova/envia à fila manual) | Parameter Store/env `CONCILIACAO_HORARIO_CORTE` (`config/__init__.py:186`); padrão em `corte.py:26` | (a); candidata natural a ler horário do scheduler em vez do env |
| 6 | conciliacao_liquidacao_verificacao_d0_task | `tasks/conciliacao_liquidacao.py:236` | padrão 20:00 BRT, :62 | Marca como falha o que não debitou em D0; alerta via `logger.error` | env `CONCILIACAO_HORARIO_VERIFICACAO_D0` (`config:187`); padrão `corte.py:27` | (a) |

Observações:
- Horário #5/#6 é lido **na subida do beat** (`registro.py` roda no import): mudar o env exige reiniciar o beat.
  `crontab_do_horario` converte BRT -> UTC (`corte.py:96-106`); `passou_do_corte` usa `is_bizday`
  (violeta) só para roteamento do lote (:80-93), **não** para impedir o disparo do cron.
- Nenhuma das 6 tasks checa dia útil [C] (grep em `tasks/`); o cron roda todo dia, inclusive feriado/fim de
  semana. #5 e #6 não filtram, #1-#4 também não. **[H]** isso é comportamento atual desejado ou lacuna: perguntar à operação.
- Já existe disparo manual por API para três: `api/garantia/viewer.py:126` (#1, com produto/data),
  `api/liquidacao/service.py:398` (#5) e `:406` (#6, com `dia`). Ou seja, o padrão "agendada + manual" já existe.
- Outros mecanismos "periódicos" (nenhum é agenda):
  - **CronJob K8s: nenhum** (`grep kind: CronJob` vazio; o bloco `type: cronjob` em `values.yaml:351` é só exemplo comentado).
  - Re-agendamento por `countdown`: polling Dayvale (`tasks/dayvale.py:~255`, intervalo `polling_interval_seconds` de
    `get_dayvale()`) e Fydd (`tasks/fydd.py:255`): é polling por evento (após enviar arquivo), **fica fora** do scheduler.
  - `retry` com countdown (`cessao.py:93`, `dayvale.py:115`, `fydd.py:115`) e escalonamento do release de conciliação
    (`conciliacao_liquidacao.py:171`, env via `release_escalonado`, `corte.py:~118`): não são rotinas.
  - Loops: `consumer/start.py:145`, `consumer/sqs/start.py:20` (consumidores de fila), `cache/controle_conexoes.py:140`,
    `tasks/cessao_orchestrator.py:61`: infraestrutura, não agenda.
- Variáveis de horário citadas: `CONCILIACAO_HORARIO_CORTE`, `CONCILIACAO_HORARIO_VERIFICACAO_D0` (nomes apenas).
  Beat também usa `get_sqs_conf()` (broker SQS, `app_factory.py:112`).

## 3. Diferenças que pesam [C]

| Tema | Shared | Cessão |
|---|---|---|
| Framework | FastAPI 0.117, pydantic 2 | Flask 2.2.5, flask-restx 1.1.0, flask-sqlalchemy (`requirements.txt:5-11`) |
| SQLAlchemy | 2.0.44 (`Mapped`, `mapped_column`) | `>=1.3,<1.4` (sem `Mapped`, sem estilo 2.0; `with_for_update(skip_locked=True)` existe em 1.3) |
| Celery | 5.5.3; beat = `PersistentScheduler` + extensão no `tick` | 5.2.2; beat com `beat_schedule` em dict, `--schedule=../celerybeat-schedule` (`entrypoint.sh:13`); docstring cita doc 4.4.7 |
| Broker | SQS | SQS (`get_sqs_conf`) [C]; Redis não apareceu para dedupe [H: conferir se cessão usa Redis] |
| Beat no deploy | `beat_enabled` por env | Pod `beat`, `replicas: 1` em `values.yaml` (production vivo e asgard); healthcheck `test date` (não detecta travamento) |
| Execução dupla | SKIP LOCKED + dedupe Redis | Só "1 réplica" por infra (docstring `registro.py:13-15`); sem lock em banco |
| Fuso | por job (`timezone`) | UTC fixo, conversão manual com `crontab_do_horario` |
| Registro de execução | tabela `job_executions` + sinais | Nenhum: só log; sem histórico de rodou/falhou |
| Task agendável | `schedulable` + `Annotated[Field]` | `@shared_task` sem metadado; assinaturas simples (`produto_id: int=None`, `data: date`, `dia: str`) |

### Peças (sem desenho final)
- **Copiável quase igual:** `shared/utils/cron.py` (croniter + zoneinfo); lógica de `dispatch_due_jobs`,
  `_record_occurrence`, misfire/MISSED, máquina de status; `task_kwargs.py` (usa pydantic v2, checar compatibilidade
  com a stack da cessão); settings do scheduler.
- **Reescrever na cessão:** modelos (SQLAlchemy 1.3/flask-sqlalchemy, sem `Mapped`); migrations (Flask-Migrate/Alembic
  da cessão, convenção de `cessao/migrations/versions/`); rotas (flask-restx em vez de APIRouter) e autorização/RBAC
  do BFF; sessão de banco dentro do beat (hoje `app` Flask contexto); wiring ao Celery 5.2.2 (checar `tick` do
  `PersistentScheduler` na versão); `task_routes` hoje duplicado em `registro.py` e `app_factory.py:70`.
- **Decisões abertas:** dedupe (Redis ou só lock em banco); beat continua `replicas: 1`?; catálogo de tasks
  agendáveis (marca nas tasks da cessão); onde fica dia útil/feriado (task ou scheduler); horários #5/#6 migram do
  Parameter Store para o banco; conversão dos 6 jobs por migration (cron UTC -> BRT, como a shared fez); tela/BFF
  (`apl-credit-whitelabel-api`) filtra por `module`; granularidade por produto (#4) com payload.
- **Riscos:** (1) mudar de beat fixo para o banco sem desligar o antigo duplica execução; (2) migrar os cron em UTC
  para `America/Sao_Paulo` sem erro de 3 h; (3) tasks #1 e #4 não são idempotentes por data/produto até checar [H];
  (4) beat atual não tem observabilidade de resultado.
