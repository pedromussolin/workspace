+++
card = "TS-5709"
type = "feature"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5713"]
blocked_by = ["TS-5717"]
docs = ["09-shared-calendar-schedule-alerts.md"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-17
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 29 — Calendário de dias úteis: rota no data-lake-api e uso no shared

Card ampliado em 24/11/2026 para incluir a rota do data-lake-api (T29), que não tinha card.

## Contexto

A agenda por dia útil das Automações (TS-5713), a função `DIAS_UTEIS` do bloco Calcular colunas e
as datas relativas nos filtros dependem de um calendário de dias úteis. A fonte é uma rota só de
leitura no data-lake-api sobre a tabela de calendário do lake (fins de semana, feriados nacionais e
ANBIMA). O shared consulta essa rota e guarda o resultado em cache por ano.

## Desenho combinado

- data-lake-api: `GET /calendar/business-days?year=AAAA` responde `{year, business_days: [datas
  ISO]}`, com o SQL em `src/infra/redshift/queries`. A tabela do lake ainda está a confirmar.
- shared: cliente da rota com cache por ano, `DIAS_UTEIS` na fórmula, N-ésimo e último dia útil do
  mês, e datas relativas nos filtros (D-1 útil, início do mês, desde o último dia útil).

## Pronto quando

- A rota do data-lake-api responde com testes.
- O shared resolve N-ésimo e último dia útil, `DIAS_UTEIS` e D-1 útil, com testes de feriado.

## Situação (24/11/2026)

- shared: cliente com cache por ano e `DIAS_UTEIS` na branch local `feature/TS-5709-calendario-dias-uteis`; faltam as datas relativas nos filtros.
- data-lake-api: rota feita na branch local `feature/TS-5709-calendario-dias-uteis` (commit `2b79d27`, 24/11), módulo `business_calendar`, 10 testes. O commit pulou só o hook `test-arch` (`SKIP=test-arch`, com o aval do Heitor): o hook falha em qualquer commit desde 29/09, porque roda sem as dependências que o `tests/conftest.py` importa, e o `test_arch` tem uma violação antiga da master (`src/shared/utils/day_cache` importa `src.infra.redis`). Antes da rota, o repositório não lia tabela de calendário do lake [C]: o único calendário era a biblioteca `holidays` com o calendário da B3 (`BVMF`), usado na consolidação.
- Datas relativas (24/11, em andamento): a definição ganha `date_offset_business_days` (D-1 útil, D-2 útil, que os relatórios usam) e os filtros de data aceitam `PREVIOUS_BUSINESS_DAY`, `LAST_BUSINESS_DAY` e `MONTH_START`, além da data de referência e de um dia fixo.
- Regra "1º dia útil da semana" (`FIRST_BUSINESS_DAY_OF_WEEK`, como a `primeiro_dia_util_semana` do orquestrador, usada pelo alerta BD03 do inventário): pedida pelo Heitor em 24/11 e incluída na agenda das Automações (TS-5713 no shared, TS-5718 no BFF, TS-5721 no front).
- Tabela confirmada [C]: os scripts da EC2 de automações usam a `dom_calendario` do schema analítico do lake (`mv_lib/utilitario.py:7`, a agenda do orquestrador por `checar_se_du`, e as telas de Compliance). Dia útil é a data (`dcl_dt`) sem nenhuma das três marcas: fim de semana (`dcl_lg_weekend_flag`), feriado nacional (`dcl_lg_holiday_br_flag`) e feriado ANBIMA (`dcl_lg_holiday_anbima_flag`). A rota usa a mesma regra.

