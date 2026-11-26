-- Listagem de lotes fake (L2) na réplica, 26/11/2026: as partes medidas em separado.
-- Base: RefactLiquidacaoRepository.listar_lotes_fake (cessao/api/liquidacao/refact.py:953, c6f88ce39).
-- Rodar uma por vez, sessão só leitura, statement_timeout de 60 a 120 s.

-- 1. Avulsos do dia: pagamentos sem lote na janela, remessa pelo número e cadastro.
explain (analyze, buffers)
with cand as (
    select p.liquidacao_processo_uuid as processo_uuid, p.parcela_id, p.origem_pagamento as origem,
           p.valor_pago
    from master.liquidacao_pagamento p
    where p.liquidacao_lote_id is null
      and p.data_criacao >= timestamp '2026-11-25 00:00' - interval '2 hours'
      and p.data_criacao < timestamp '2026-11-26 00:00' + interval '2 hours'
),
narrow as (
    select cand.parcela_id, cand.origem, cand.valor_pago, lp.proc_id, lp.data_criacao, lp.produto_id
    from cand
    join master.liquidacao_processo lp on lp.uuid = cand.processo_uuid
    where lp.data_criacao >= timestamp '2026-11-25 00:00'
      and lp.data_criacao < timestamp '2026-11-26 00:00'
)
select narrow.proc_id, count(distinct narrow.parcela_id), coalesce(sum(narrow.valor_pago), 0)
from narrow
join master.contrato_parcela pa on pa.id = narrow.parcela_id
join master.contrato c on c.id = pa.contrato_id
left join master.contrato_processo cp on cp.uuid = c.processo_uuid
where cp.data_delete is null
group by 1;

-- 2. Lotes abertos por idade, sem ler pagamentos.
select case when l.data_criacao >= now() - interval '7 days' then '1: até 7 dias'
            when l.data_criacao >= now() - interval '6 months' then '2: até 6 meses'
            else '3: mais de 6 meses' end as idade,
       count(*) as lotes_abertos, min(l.data_criacao)::date, max(l.data_criacao)::date
from master.liquidacao_lote_vigente v
join master.liquidacao_lote_processo l on l.id = v.liquidacao_lote_id
where v.fechado is false and l.estado_atual = 'pendente'
group by 1 order by 1;

-- 3. Pagamentos nos lotes abertos de um período (trocar o recorte de data do lote).
with lotes as (
    select l.id
    from master.liquidacao_lote_vigente v
    join master.liquidacao_lote_processo l on l.id = v.liquidacao_lote_id
    where v.fechado is false and l.estado_atual = 'pendente'
      and l.data_criacao >= timestamp '2026-07-01'
), por_lote as (
    select id, (select count(*) from master.liquidacao_pagamento p where p.liquidacao_lote_id = lotes.id) as qtd
    from lotes
)
select count(*) as lotes, sum(qtd) as pagamentos, max(qtd) as maior,
       count(*) filter (where qtd = 0) as sem_pagamento
from por_lote;

-- 4. A subconsulta LATERAL dos lotes abertos (refact.py:822) no maior lote aberto recente;
--    depois, a mesma contagem sem as junções do cadastro.
explain (analyze, buffers)
select count(p.id), coalesce(sum(p.valor_pago), 0)
from master.liquidacao_pagamento p
join master.contrato_parcela pa on pa.id = p.parcela_id
join master.contrato c on c.id = pa.contrato_id
join master.contrato_processo cp on cp.uuid = c.processo_uuid
where p.liquidacao_lote_id = (
    select l.id
    from master.liquidacao_lote_vigente v
    join master.liquidacao_lote_processo l on l.id = v.liquidacao_lote_id
    where v.fechado is false and l.estado_atual = 'pendente' and l.data_criacao >= timestamp '2026-07-01'
    order by (select count(*) from master.liquidacao_pagamento p2 where p2.liquidacao_lote_id = l.id) desc
    limit 1)
  and cp.data_delete is null;

explain (analyze, buffers)
select count(p.id)
from master.liquidacao_pagamento p
where p.liquidacao_lote_id = (
    select l.id
    from master.liquidacao_lote_vigente v
    join master.liquidacao_lote_processo l on l.id = v.liquidacao_lote_id
    where v.fechado is false and l.estado_atual = 'pendente' and l.data_criacao >= timestamp '2026-07-01'
    order by (select count(*) from master.liquidacao_pagamento p2 where p2.liquidacao_lote_id = l.id) desc
    limit 1);
