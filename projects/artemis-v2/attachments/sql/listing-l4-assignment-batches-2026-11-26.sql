-- L4: assignment batches listing (TS-5733). Read only, for the production read replica.
-- Source: platform-cessao c6f88ce39. Route GET /cessao/query (cessao/api/cessao/viewers/cessao.py:306),
-- service ServiceCessao.get_lotes_and_lotes_fake_paginated (cessao/api/cessao/services/cessao.py:617),
-- repository cessao/api/cessao/repository/cessao.py (get_lotes_paginated:144, get_lotes_fake_paginated:228).
--
-- Variables (psql), fill before running:
--   \set dia_fechado '2026-11-25'   -- day with closed batches (see lookup 1)
--   \set dia_aberto  '2026-11-25'   -- day with open contracts (see lookup 2)
-- Defaults the screen sends: per_page = 5, page 1 (offset 0), no sort, no fund, no product, no cedente,
-- date_start = date_end = one day. The service does data_fim = data_fim + 1 day, so the range is
-- [dia, dia + 1). psycopg2 sends dates as 'YYYY-MM-DD'::date, reproduced with (:'dia')::date.
-- Both modes run: statement 1 = count (total_count), statement 2 = the page. Order in code: count first.
-- Soft-delete listener (listeners.py:540): every statement below carries "contrato_processo.data_delete IS NULL"
-- added by it; where marked [LISTENER] it is not in the repository code.

set search_path = master;

-- Lookup 1 (cheap): a day with closed batches = creation day of the process of a contract of the newest batch.
select cp.data_criacao::date as dia_fechado
from master.contrato_lote_processo l
join master.contrato c on c.lote_id = l.id
join master.contrato_processo cp on cp.uuid = c.processo_uuid
where l.id = (select max(id) from master.contrato_lote_processo)
limit 1;

-- Lookup 2 (cheap): newest day with a contract (index on contrato.data_criacao, backward scan).
select max(data_criacao)::date as dia_aberto from master.contrato;

-- ============================ MODE CLOSED (status_lote=fechado) ============================

-- Closed, statement 1: query.count() at repository line ~212 (from_self wrapper, count_1).
-- [LISTENER] contrato_processo.data_delete IS NULL (inner query only; the count wrapper is skipped).
explain (analyze, buffers)
select count(*) as count_1
from (
  select contrato_processo.proc_id as proc_id,
         contrato_lote_processo.identificador as cessao_id,
         contrato_lote_processo.estado_atual as estado_atual,
         contrato_lote_processo.data_criacao as data,
         fundo.id as fundo_id,
         fundo.nome as fundo_nome,
         fundo.cnpj as fundo_cnpj,
         cedente.id as cedente_id,
         cedente.nome as cedente_nome,
         cedente.email as cedente_email,
         cast(cedente.tipo as varchar) as cedente_tipo_pessoa,
         cast(cedente_documento.tipo_documento as varchar) as cedente_tipo_documento,
         cedente_documento.numero_documento as cedente_numero_documento,
         sum(contrato.valor_aquisicao) as valor_aquisicao,
         sum(contrato.valor_titulo) as valor_total
  from master.contrato_lote_processo
  join master.contrato on contrato.lote_id = contrato_lote_processo.id
  join master.contrato_processo on contrato_processo.uuid = contrato.processo_uuid
  join master.fundo on fundo.id = contrato_processo.fundo_id
  join master.cedente on cedente.id = contrato.cedente_id
  left outer join master.cedente_documento on cedente_documento.cedente_id = cedente.id
  where contrato.lote_id is not null
    and contrato_processo.data_criacao >= (:'dia_fechado')::date
    and contrato_processo.data_criacao < ((:'dia_fechado')::date + 1)
    and contrato_processo.data_delete is null                       -- [LISTENER]
  group by contrato_processo.proc_id, contrato_lote_processo.identificador,
           contrato_lote_processo.estado_atual, contrato_lote_processo.data_criacao,
           fundo.id, fundo.nome, fundo.cnpj,
           cedente.id, cedente.nome, cedente.email, cedente.tipo,
           cedente_documento.tipo_documento, cedente_documento.numero_documento
) as anon_1;

-- Closed, statement 2: query.all() with default order, limit 5 offset 0 (repository lines ~215-235).
-- [LISTENER] contrato_processo.data_delete IS NULL.
explain (analyze, buffers)
select contrato_processo.proc_id as proc_id,
       contrato_lote_processo.identificador as cessao_id,
       contrato_lote_processo.estado_atual as estado_atual,
       contrato_lote_processo.data_criacao as data,
       fundo.id as fundo_id,
       fundo.nome as fundo_nome,
       fundo.cnpj as fundo_cnpj,
       cedente.id as cedente_id,
       cedente.nome as cedente_nome,
       cedente.email as cedente_email,
       cast(cedente.tipo as varchar) as cedente_tipo_pessoa,
       cast(cedente_documento.tipo_documento as varchar) as cedente_tipo_documento,
       cedente_documento.numero_documento as cedente_numero_documento,
       sum(contrato.valor_aquisicao) as valor_aquisicao,
       sum(contrato.valor_titulo) as valor_total
from master.contrato_lote_processo
join master.contrato on contrato.lote_id = contrato_lote_processo.id
join master.contrato_processo on contrato_processo.uuid = contrato.processo_uuid
join master.fundo on fundo.id = contrato_processo.fundo_id
join master.cedente on cedente.id = contrato.cedente_id
left outer join master.cedente_documento on cedente_documento.cedente_id = cedente.id
where contrato.lote_id is not null
  and contrato_processo.data_criacao >= (:'dia_fechado')::date
  and contrato_processo.data_criacao < ((:'dia_fechado')::date + 1)
  and contrato_processo.data_delete is null                         -- [LISTENER]
group by contrato_processo.proc_id, contrato_lote_processo.identificador,
         contrato_lote_processo.estado_atual, contrato_lote_processo.data_criacao,
         fundo.id, fundo.nome, fundo.cnpj,
         cedente.id, cedente.nome, cedente.email, cedente.tipo,
         cedente_documento.tipo_documento, cedente_documento.numero_documento
order by contrato_lote_processo.data_criacao asc
limit 5 offset 0;

-- ============================ MODE OPEN (status_lote=em_aberto) ============================

-- Open, statement 1: query.count() at repository line ~292. The inner subquery contrato_agregado is
-- built at lines 244-256. [LISTENER] contrato_processo.data_delete IS NULL appears twice: in the
-- aggregate subquery (WHERE, over the LEFT JOIN) and in the outer query (WHERE). The count wrapper is skipped.
-- Note: "group by ... cessao_id, estado_atual" comes from string group_by labels in the code. In PostgreSQL
-- estado_atual binds to the input column contrato_processo.estado_atual (input column wins over output alias),
-- so the real grouping also splits by the process state; cessao_id has no input column and binds to the alias.
explain (analyze, buffers)
select count(*) as count_1
from (
  select contrato_agregado.proc_id as proc_id,
         '-' as cessao_id,
         'em_aberto' as estado_atual,
         contrato_agregado.primeira_data as data,
         fundo.id as fundo_id,
         fundo.nome as fundo_nome,
         fundo.cnpj as fundo_cnpj,
         cedente.id as cedente_id,
         cedente.nome as cedente_nome,
         cedente.email as cedente_email,
         cast(cedente.tipo as varchar) as cedente_tipo_pessoa,
         cast(cedente_documento.tipo_documento as varchar) as cedente_tipo_documento,
         cedente_documento.numero_documento as cedente_numero_documento,
         coalesce(contrato_agregado.valor_aquisicao, 0) as valor_aquisicao,
         coalesce(contrato_agregado.valor_total, 0) as valor_total
  from (
    select contrato_processo.proc_id as proc_id,
           contrato.cedente_id as cedente_id,
           sum(contrato.valor_aquisicao) as valor_aquisicao,
           sum(contrato.valor_titulo) as valor_total,
           min(contrato_processo.data_criacao) as primeira_data
    from master.contrato
    left outer join master.contrato_processo on contrato_processo.uuid = contrato.processo_uuid
    where contrato.lote_id is null
      and contrato.data_criacao >= (:'dia_aberto')::date
      and contrato.data_criacao < ((:'dia_aberto')::date + 1)
      and contrato_processo.data_delete is null                     -- [LISTENER]
    group by contrato_processo.proc_id, contrato.cedente_id
  ) as contrato_agregado
  join master.contrato_processo on contrato_processo.proc_id = contrato_agregado.proc_id
  join master.fundo on fundo.id = contrato_processo.fundo_id
  join master.cedente on cedente.id = contrato_agregado.cedente_id
  left outer join master.cedente_documento on cedente_documento.cedente_id = cedente.id
  where contrato_processo.data_delete is null                       -- [LISTENER]
  group by contrato_agregado.proc_id, cessao_id, estado_atual,
           fundo.id, fundo.nome, fundo.cnpj,
           cedente.id, cedente.nome, cedente.email, cedente.tipo,
           cedente_documento.tipo_documento, cedente_documento.numero_documento,
           contrato_agregado.primeira_data, contrato_agregado.valor_aquisicao, contrato_agregado.valor_total
) as anon_1;

-- Open, statement 2: query.all() with default order by primeira_data asc, limit 5 offset 0
-- (repository lines ~294-312). Same two [LISTENER] filters as statement 1.
explain (analyze, buffers)
select contrato_agregado.proc_id as proc_id,
       '-' as cessao_id,
       'em_aberto' as estado_atual,
       contrato_agregado.primeira_data as data,
       fundo.id as fundo_id,
       fundo.nome as fundo_nome,
       fundo.cnpj as fundo_cnpj,
       cedente.id as cedente_id,
       cedente.nome as cedente_nome,
       cedente.email as cedente_email,
       cast(cedente.tipo as varchar) as cedente_tipo_pessoa,
       cast(cedente_documento.tipo_documento as varchar) as cedente_tipo_documento,
       cedente_documento.numero_documento as cedente_numero_documento,
       coalesce(contrato_agregado.valor_aquisicao, 0) as valor_aquisicao,
       coalesce(contrato_agregado.valor_total, 0) as valor_total
from (
  select contrato_processo.proc_id as proc_id,
         contrato.cedente_id as cedente_id,
         sum(contrato.valor_aquisicao) as valor_aquisicao,
         sum(contrato.valor_titulo) as valor_total,
         min(contrato_processo.data_criacao) as primeira_data
  from master.contrato
  left outer join master.contrato_processo on contrato_processo.uuid = contrato.processo_uuid
  where contrato.lote_id is null
    and contrato.data_criacao >= (:'dia_aberto')::date
    and contrato.data_criacao < ((:'dia_aberto')::date + 1)
    and contrato_processo.data_delete is null                       -- [LISTENER]
  group by contrato_processo.proc_id, contrato.cedente_id
) as contrato_agregado
join master.contrato_processo on contrato_processo.proc_id = contrato_agregado.proc_id
join master.fundo on fundo.id = contrato_processo.fundo_id
join master.cedente on cedente.id = contrato_agregado.cedente_id
left outer join master.cedente_documento on cedente_documento.cedente_id = cedente.id
where contrato_processo.data_delete is null                         -- [LISTENER]
group by contrato_agregado.proc_id, cessao_id, estado_atual,
         fundo.id, fundo.nome, fundo.cnpj,
         cedente.id, cedente.nome, cedente.email, cedente.tipo,
         cedente_documento.tipo_documento, cedente_documento.numero_documento,
         contrato_agregado.primeira_data, contrato_agregado.valor_aquisicao, contrato_agregado.valor_total
order by contrato_agregado.primeira_data asc
limit 5 offset 0;
