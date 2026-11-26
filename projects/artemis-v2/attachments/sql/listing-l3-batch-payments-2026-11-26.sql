-- Pagamentos de um lote (L3) na réplica: uma carga de página, nas duas rotas.
-- Base: platform-cessao c6f88ce39; BFF 2bc0f37; front fc3ad6d0.
-- Rodar um passo por vez, sessão só leitura, statement_timeout de 120 s: set statement_timeout = 120000;
-- Parâmetros da tela: per_page 5 (NESTED_TABLE_PAGE_SIZE), page 1, rejeitados false, sem filtro de texto, sem sort.
--
-- Variáveis psql (os passos A e B preenchem com \gset; as demais com \set):
--   \set dia '2026-11-26'       -- só na rota fake: a janela da listagem (filters.apiDate(), data_inicio = data_fim)
--   \set limite 5
--   \set deslocamento 0
--   A.2 preenche: :lote_id, :n_remessas, :proc_ids (lista de literais), :uuids (lista de literais)
--   B.1 preenche: :chave, :produto_id, :originador_id, :fundo_id, :'origem', :sem_origem, :'proc_id'
--
-- Soft delete (ContratoSoftDeleteListener, listeners.py:540): cada comando diz se ganhou o filtro.

--------------------------------------------------------------------------------
-- A. Escolha do lote real (só índices)
--------------------------------------------------------------------------------

-- A.1 Os 50 lotes mais recentes criados em 2026-11-25, com a contagem por liquidacao_lote_id.
select l.id, l.identificador, l.estado_atual, l.data_criacao,
       (select count(*) from master.liquidacao_pagamento p where p.liquidacao_lote_id = l.id) as qtd
from (select id, identificador, estado_atual, data_criacao
      from master.liquidacao_lote_processo
      where data_criacao >= timestamp '2026-11-25 00:00' and data_criacao < timestamp '2026-11-26 00:00'
      order by data_criacao desc
      limit 50) l
order by qtd desc
limit 10;

-- A.2 Escolher um id do A.1 (\set lote_id <id>) e medir as remessas dele: as listas que o service
-- monta no passo R1 (proc_ids, em texto) e em R2 (uuid de todo liquidacao_processo das remessas).
-- Se n_remessas <= 20 vale R3a (proc_id IN); se > 20 vale R2 + R3b (uuid IN).
select count(distinct lp.proc_id) as n_remessas,
       string_agg(distinct quote_literal(lp.proc_id::text), ',') as proc_ids
from master.liquidacao_pagamento p
join master.liquidacao_processo lp on lp.uuid = p.liquidacao_processo_uuid
where p.liquidacao_lote_id = :lote_id
\gset

select string_agg(quote_literal(lp.uuid::text), ',') as uuids
from master.liquidacao_processo lp
where lp.proc_id in (:proc_ids)
\gset

--------------------------------------------------------------------------------
-- B. Escolha da linha fake (o maior lote aberto, como a listagem monta a chave)
--------------------------------------------------------------------------------

-- B.1 Vigentes abertos (fechado = false) cujo lote real está pendente, criados desde 2026-11-24.
-- A chave é _chave_do_vigente_aberto (refact.py:799). Mostra os 5 maiores.
select case when v.proc_id is not null then 'proc:' || cast(v.proc_id as varchar)
            else 'origem:' || v.origem_pagamento || ':' || cast(v.produto_id as varchar) || ':'
                 || cast(v.originador_id as varchar) || ':' || cast(v.fundo_id as varchar) end as chave,
       v.liquidacao_lote_id, l.data_criacao,
       (select count(*) from master.liquidacao_pagamento p where p.liquidacao_lote_id = v.liquidacao_lote_id) as qtd
from master.liquidacao_lote_vigente v
join master.liquidacao_lote_processo l on l.id = v.liquidacao_lote_id
where v.fechado is false and l.estado_atual = 'pendente' and l.data_criacao >= timestamp '2026-11-24'
order by qtd desc
limit 5;

-- B.2 Preencher as variáveis com a linha de maior qtd do B.1 (copiar os campos do vigente dela; troque :vig):
--   \set vig <liquidacao_lote_id da linha escolhida>
select 'origem:' || v.origem_pagamento || ':' || v.produto_id || ':' || v.originador_id || ':' || v.fundo_id as chave,
       v.produto_id, v.originador_id, v.fundo_id, v.origem_pagamento as origem,
       (v.origem_pagamento = '*')::text as sem_origem, v.proc_id as proc_id
from master.liquidacao_lote_vigente v
where v.liquidacao_lote_id = :vig
\gset

--------------------------------------------------------------------------------
-- ROTA REAL: GET /pagamentos/query?lote_id=:lote_id&page=1&per_page=5&rejeitados=false
-- viewer.py:1336 -> service.py:1698 (get_pagamentos_query_paginated)
--------------------------------------------------------------------------------

-- R1. service.py:1728 -> repository.py:914 remessas_do_lote. Varre o lote inteiro (DISTINCT), sem custo de soft delete.
-- Listener: NÃO ganha filtro (a query só tem ProcessoLiquidacao como entidade).
explain (analyze, buffers)
select distinct cast(lp.proc_id as varchar) as proc_id
from master.liquidacao_pagamento p
join master.liquidacao_processo lp on lp.uuid = p.liquidacao_processo_uuid
where p.liquidacao_lote_id = :lote_id;

-- R2. Só se n_remessas > 20: metricas_do_lote (repository.py:1358) -> _filtro_das_remessas (:873) ->
-- processos_das_remessas (:885, execute em Core: sem listener). Roda uma vez e vale para R5 e R6.
-- O repositório monta o array com os proc_ids de R1.
explain (analyze, buffers)
select pr.uuid
from (select unnest(cast(array[:proc_ids] as uuid[])) as proc_id) requested_remittance
join lateral (select lp.uuid from master.liquidacao_processo lp
              where lp.proc_id = requested_remittance.proc_id) pr on true;

-- R3. repository.py:1179 query.count() = select count(*) from (<mesma query da página, sem order/limit>).
-- Varre o lote inteiro com a cadeia de cadastro (parcela, contrato, processo) por pagamento.
-- Listener: GANHA contrato_processo.data_delete IS NULL (a query tem ProcessoEstado; o wrapper do count não ganha de novo).
-- lote_id tem precedência: proc_ids NÃO entra no filtro (repository.py:1124).
explain (analyze, buffers)
select count(*) as count_1
from (
  select p.id as pagamento_id, cp.identificador as identificador, c.num_controle as num_controle,
         s.id as sacado_id, s.nome as sacado_nome, p.tipo_liquidacao as tipo_baixa,
         (select pac.uuid from master.produto_acesso pac where pac.produto_id = prod.id order by pac.id asc limit 1) as identificador_parceiro,
         prod.id as produto_id, p.valor_pago as valor_pago
  from master.liquidacao_pagamento p
  join master.liquidacao_processo lp on lp.uuid = p.liquidacao_processo_uuid
  join master.contrato_parcela pa on pa.id = p.parcela_id
  join master.contrato c on c.id = pa.contrato_id
  join master.contrato_processo cp on cp.uuid = c.processo_uuid
  join master.produto prod on prod.id = lp.produto_id
  join master.sacado s on s.id = c.sacado_id
  where p.liquidacao_lote_id = :lote_id
    and cp.data_delete is null
) as anon_1;

-- R4. repository.py:1196 query.all(): a página. Sem ORDER BY (o viewer não manda sort), LIMIT 5 OFFSET 0.
-- Listener: GANHA cp.data_delete IS NULL.
explain (analyze, buffers)
select p.id as pagamento_id, cp.identificador as identificador, c.num_controle as num_controle,
       s.id as sacado_id, s.nome as sacado_nome, p.tipo_liquidacao as tipo_baixa,
       (select pac.uuid from master.produto_acesso pac where pac.produto_id = prod.id order by pac.id asc limit 1) as identificador_parceiro,
       prod.id as produto_id, p.valor_pago as valor_pago
from master.liquidacao_pagamento p
join master.liquidacao_processo lp on lp.uuid = p.liquidacao_processo_uuid
join master.contrato_parcela pa on pa.id = p.parcela_id
join master.contrato c on c.id = pa.contrato_id
join master.contrato_processo cp on cp.uuid = c.processo_uuid
join master.produto prod on prod.id = lp.produto_id
join master.sacado s on s.id = c.sacado_id
where p.liquidacao_lote_id = :lote_id
  and cp.data_delete is null
limit :limite offset :deslocamento;

-- R5. service.py:1786 -> repository.py:1336 metricas_do_lote, ativos (por_lote, repository.py:1404).
-- NÃO é só o lote: com proc_ids (sempre, pois o service os deriva do lote) a varredura é a das REMESSAS do lote,
-- agrupada por lote (inclui lotes irmãos), com a cadeia de cadastro por pagamento e um lateral por linha.
-- Listener: GANHA o anti-join do contrato (a query tem Contrato por join, sem ProcessoEstado):
--   not exists (select 1 from contrato_processo where uuid = contrato.processo_uuid and data_delete is not null).
-- R5a (n_remessas <= 20): filtro lp.proc_id IN (...).
explain (analyze, buffers)
select p.liquidacao_lote_id as lote_id, count(p.id) as qtd, coalesce(sum(p.valor_pago), 0) as valor,
       estado_na_adm.estado_adm
from master.liquidacao_pagamento p
join master.liquidacao_processo lp on lp.uuid = p.liquidacao_processo_uuid
join master.contrato_parcela pa on pa.id = p.parcela_id
join master.contrato c on c.id = pa.contrato_id
left join lateral (select a.estado_atual as estado_adm
                   from master.liquidacao_lote_adm a
                   where a.liquidacao_lote_id = p.liquidacao_lote_id
                   order by a.id desc limit 1) estado_na_adm on true
where lp.proc_id in (:proc_ids)
  and not exists (select 1 from master.contrato_processo cp2
                  where cp2.uuid = c.processo_uuid and cp2.data_delete is not null)
group by p.liquidacao_lote_id, estado_na_adm.estado_adm;

-- R5b (n_remessas > 20): o mesmo, com lp.uuid IN (uuids do R2).
explain (analyze, buffers)
select p.liquidacao_lote_id as lote_id, count(p.id) as qtd, coalesce(sum(p.valor_pago), 0) as valor,
       estado_na_adm.estado_adm
from master.liquidacao_pagamento p
join master.liquidacao_processo lp on lp.uuid = p.liquidacao_processo_uuid
join master.contrato_parcela pa on pa.id = p.parcela_id
join master.contrato c on c.id = pa.contrato_id
left join lateral (select a.estado_atual as estado_adm
                   from master.liquidacao_lote_adm a
                   where a.liquidacao_lote_id = p.liquidacao_lote_id
                   order by a.id desc limit 1) estado_na_adm on true
where lp.uuid in (:uuids)
  and not exists (select 1 from master.contrato_processo cp2
                  where cp2.uuid = c.processo_uuid and cp2.data_delete is not null)
group by p.liquidacao_lote_id, estado_na_adm.estado_adm;

-- R6. repository.py:1466 rejeitados.one(): processos rejeitados das remessas e o JSON da liquidacao_raw
-- (roda mesmo com rejeitados=false). Listener: NÃO ganha filtro (entidades LiquidacaoRaw e ProcessoLiquidacao).
-- R6a (n_remessas <= 20):
explain (analyze, buffers)
select count(case when coalesce(o.estado_anterior, '') in ('cadastrado') then lr.id end) as count_1,
       count(case when coalesce(o.estado_anterior, '') not in ('cadastrado') then lr.id end) as count_2,
       coalesce(sum(case when coalesce(o.estado_anterior, '') in ('cadastrado')
                         then (case when (lr.data_raw ->> 'valor_pago') ~ '^-?[0-9]+(\.[0-9]+)?$'
                                    then cast(lr.data_raw ->> 'valor_pago' as numeric) else 0 end)
                         else 0 end), 0) as coalesce_1,
       coalesce(sum(case when coalesce(o.estado_anterior, '') not in ('cadastrado')
                         then (case when (lr.data_raw ->> 'valor_pago') ~ '^-?[0-9]+(\.[0-9]+)?$'
                                    then cast(lr.data_raw ->> 'valor_pago' as numeric) else 0 end)
                         else 0 end), 0) as coalesce_2
from master.liquidacao_raw lr
join master.liquidacao_processo lp on lp.uuid = lr.liquidacao_processo_uuid
left join lateral (select g.estado_anterior
                   from master.liquidacao_processo_log g
                   where g.liquidacao_processo_uuid = lp.uuid and g.estado_atual = 'rejeitado'
                   order by g.data_criacao desc limit 1) o on true
where lp.estado_atual = 'rejeitado'
  and lp.proc_id in (:proc_ids);

-- R6b (n_remessas > 20): o mesmo, com lp.uuid IN (uuids do R2).
explain (analyze, buffers)
select count(case when coalesce(o.estado_anterior, '') in ('cadastrado') then lr.id end) as count_1,
       count(case when coalesce(o.estado_anterior, '') not in ('cadastrado') then lr.id end) as count_2,
       coalesce(sum(case when coalesce(o.estado_anterior, '') in ('cadastrado')
                         then (case when (lr.data_raw ->> 'valor_pago') ~ '^-?[0-9]+(\.[0-9]+)?$'
                                    then cast(lr.data_raw ->> 'valor_pago' as numeric) else 0 end)
                         else 0 end), 0) as coalesce_1,
       coalesce(sum(case when coalesce(o.estado_anterior, '') not in ('cadastrado')
                         then (case when (lr.data_raw ->> 'valor_pago') ~ '^-?[0-9]+(\.[0-9]+)?$'
                                    then cast(lr.data_raw ->> 'valor_pago' as numeric) else 0 end)
                         else 0 end), 0) as coalesce_2
from master.liquidacao_raw lr
join master.liquidacao_processo lp on lp.uuid = lr.liquidacao_processo_uuid
left join lateral (select g.estado_anterior
                   from master.liquidacao_processo_log g
                   where g.liquidacao_processo_uuid = lp.uuid and g.estado_atual = 'rejeitado'
                   order by g.data_criacao desc limit 1) o on true
where lp.estado_atual = 'rejeitado'
  and lp.uuid in (:uuids);

--------------------------------------------------------------------------------
-- ROTA FAKE: GET /liquidacao/fake-batches/payments?chave=:chave&data_inicio=:dia&data_fim=:dia&page=1&per_page=5
-- viewer.py:1152 -> refact.py:3621 listar_pagamentos_do_lote_fake. Sem filtro de texto: não há count separado
-- (total_count = qtd dos totais, refact.py:3652). Dois comandos.
-- Condição da linha (_consulta_da_linha_do_lote_fake, refact.py:2139, incluir_lote_aberto=True):
--   (avulsos na janela) OR (pagamento do lote aberto da chave, sem janela)  [_condicao_do_lote_aberto_da_linha, :2097]
-- Chave aqui: linha de origem (chave 'origem:...'). Se B.1 escolheu 'proc:', use F3 e F4.
--------------------------------------------------------------------------------

-- F1. refact.py:2350 totais_da_linha_do_lote_fake (chamado em :3648). Conta e soma a linha inteira.
-- O lote aberto entra pelo OR; cada pagamento paga a cadeia parcela -> contrato -> processo.
-- Listener: GANHA o anti-join do contrato (Contrato por join, sem ProcessoEstado).
explain (analyze, buffers)
select count(p.id) as qtd, coalesce(sum(p.valor_pago), 0) as valor
from master.liquidacao_pagamento p
join master.liquidacao_processo lp on lp.uuid = p.liquidacao_processo_uuid
join master.contrato_parcela pa on pa.id = p.parcela_id
join master.contrato c on c.id = pa.contrato_id
left join master.produto_config pc on pc.produto_id = lp.produto_id
where (
        (p.liquidacao_lote_id is null
         and (case when pc.agrupamento_lote_liquidacao = 'por_remessa'
                   then 'proc:' || cast(lp.proc_id as varchar)
                   when pc.agrupamento_lote_liquidacao = 'por_chave_sem_origem'
                   then 'origem:*:' || coalesce(cast(lp.produto_id as varchar), '') || ':'
                        || coalesce(cast(c.originador_id as varchar), '') || ':' || coalesce(cast(pa.fundo_id as varchar), '')
                   else 'origem:' || coalesce(p.origem_pagamento, '') || ':' || coalesce(cast(lp.produto_id as varchar), '') || ':'
                        || coalesce(cast(c.originador_id as varchar), '') || ':' || coalesce(cast(pa.fundo_id as varchar), '')
              end) = :'chave'
         and p.data_criacao >= :'dia'::timestamp - interval '2 hours'
         and p.data_criacao < :'dia'::timestamp + interval '1 day' + interval '2 hours'
         and lp.data_criacao >= :'dia'::timestamp
         and lp.data_criacao < :'dia'::timestamp + interval '1 day'
         and lp.produto_id = :produto_id
         and c.originador_id = :originador_id
         and pa.fundo_id = :fundo_id
         and (:sem_origem or coalesce(p.origem_pagamento, '') = :'origem'))
        or p.liquidacao_lote_id in (
            select v.liquidacao_lote_id from master.liquidacao_lote_vigente v
            where v.produto_id = :produto_id and v.originador_id = :originador_id and v.fundo_id = :fundo_id
              and v.origem_pagamento = :'origem' and v.proc_id is null and v.fechado is false
              and v.liquidacao_lote_id in (select l.id from master.liquidacao_lote_processo l where l.estado_atual = 'pendente'))
      )
  and not exists (select 1 from master.contrato_processo cp2
                  where cp2.uuid = c.processo_uuid and cp2.data_delete is not null);

-- F2. refact.py:2316 pagamentos_da_linha_do_lote_fake (chamado em :3659): a página, ORDER BY p.id LIMIT 5 OFFSET 0.
-- Mesma condição de F1; sacado por LEFT JOIN, processo e produto por JOIN.
-- Listener: GANHA cp.data_delete IS NULL (tem ProcessoEstado); sem o anti-join do contrato.
explain (analyze, buffers)
select p.id as pagamento_id, cp.identificador as identificador, c.num_controle as num_controle,
       s.id as sacado_id, s.nome as sacado_nome, p.tipo_liquidacao as tipo_baixa,
       (select pac.uuid from master.produto_acesso pac where pac.produto_id = prod.id order by pac.id asc limit 1) as identificador_parceiro,
       prod.id as produto_id, p.valor_pago as valor_pago
from master.liquidacao_pagamento p
join master.liquidacao_processo lp on lp.uuid = p.liquidacao_processo_uuid
join master.contrato_parcela pa on pa.id = p.parcela_id
join master.contrato c on c.id = pa.contrato_id
left join master.produto_config pc on pc.produto_id = lp.produto_id
join master.contrato_processo cp on cp.uuid = c.processo_uuid
join master.produto prod on prod.id = lp.produto_id
left join master.sacado s on s.id = c.sacado_id
where (
        (p.liquidacao_lote_id is null
         and (case when pc.agrupamento_lote_liquidacao = 'por_remessa'
                   then 'proc:' || cast(lp.proc_id as varchar)
                   when pc.agrupamento_lote_liquidacao = 'por_chave_sem_origem'
                   then 'origem:*:' || coalesce(cast(lp.produto_id as varchar), '') || ':'
                        || coalesce(cast(c.originador_id as varchar), '') || ':' || coalesce(cast(pa.fundo_id as varchar), '')
                   else 'origem:' || coalesce(p.origem_pagamento, '') || ':' || coalesce(cast(lp.produto_id as varchar), '') || ':'
                        || coalesce(cast(c.originador_id as varchar), '') || ':' || coalesce(cast(pa.fundo_id as varchar), '')
              end) = :'chave'
         and p.data_criacao >= :'dia'::timestamp - interval '2 hours'
         and p.data_criacao < :'dia'::timestamp + interval '1 day' + interval '2 hours'
         and lp.data_criacao >= :'dia'::timestamp
         and lp.data_criacao < :'dia'::timestamp + interval '1 day'
         and lp.produto_id = :produto_id
         and c.originador_id = :originador_id
         and pa.fundo_id = :fundo_id
         and (:sem_origem or coalesce(p.origem_pagamento, '') = :'origem'))
        or p.liquidacao_lote_id in (
            select v.liquidacao_lote_id from master.liquidacao_lote_vigente v
            where v.produto_id = :produto_id and v.originador_id = :originador_id and v.fundo_id = :fundo_id
              and v.origem_pagamento = :'origem' and v.proc_id is null and v.fechado is false
              and v.liquidacao_lote_id in (select l.id from master.liquidacao_lote_processo l where l.estado_atual = 'pendente'))
      )
  and cp.data_delete is null
order by p.id
limit :limite offset :deslocamento;

-- F3 / F4 (só se a chave for 'proc:<proc_id>'): como F1 / F2, trocando no ramo dos avulsos os filtros de
-- produto/originador/fundo/origem por lp.proc_id = :'proc_id', e o lote aberto por
-- v.proc_id = :'proc_id' (sem os campos de origem; _condicao_do_lote_aberto_da_linha, refact.py:2105).
-- Não escrito por extenso: o plano muda pouco e a escolha do B.2 cobre a linha de origem.
