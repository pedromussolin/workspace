-- Listagem de lotes reais (L1) na réplica: GET /liquidacao/lotes/reais, uma carga de página.
-- Base: platform-cessao c6f88ce39. Rota: cessao/api/liquidacao/viewer.py:1218.
-- Service: cessao/api/liquidacao/service.py:1466 (get_lotes_reais_paginated).
-- Variáveis psql (preencher com \set antes de rodar):
--   \set dia '2026-11-25'
--   \set fundo_id <resultado do passo 0>
--   \set limite 5            -- per_page; a tela abre com 5 (TableState(5)), a rota aceita até 200
--   \set deslocamento 0      -- (page - 1) * per_page
--   \set proc_ids '{uuid1,uuid2}'   -- só nos passos 3 e 4: a coluna proc_ids das linhas do passo 2
--   \set lote_ids '101,102'         -- só no passo 4: os lotes devolvidos pelo passo 3 (mesmo texto do IN)
-- Sem filtro de produto nem de status (a tela abre sem eles); ordem padrão: data_criacao desc.
-- Rodar um passo por vez, sessão só leitura.

-- 0. Escolha do fundo (sem varrer pagamento): fundo com mais lotes reais criados em :dia.
-- O lote não tem fundo; aproxima pelo fundo da primeira parcela de um pagamento do lote
-- (o mesmo atalho de _real_batch_belongs_to_fund, repository.py:~700). Duas buscas por índice por lote.
select f.fundo_id, count(*) as lotes
from master.liquidacao_lote_processo l
cross join lateral (
    select pa.fundo_id
    from master.liquidacao_pagamento p
    join master.contrato_parcela pa on pa.id = p.parcela_id
    where p.liquidacao_lote_id = l.id
    limit 1
) f
where l.data_criacao >= :'dia'::date
  and l.data_criacao < :'dia'::date + 1
group by 1
order by 2 desc
limit 5;

-- 1. service.py:~1486 -> RepositoryLiquidacao.limitar_tempo_das_consultas (repository.py:62), SET LOCAL.
set statement_timeout = 120000;

-- 2. service.py:1489 -> RepositoryLiquidacao.get_lotes (repository.py:526). Uma consulta: página + total
-- (count() over) + valores por lateral. Sem proc_ids, vale a janela do dia (_janela, repository.py:~456),
-- _real_batch_belongs_to_fund (repository.py:~690) e _lote_e_o_aberto_de_um_vigente (repository.py:737).
-- Soft delete (ContratoSoftDeleteListener): a CTE "pagina" NÃO ganha filtro (entidades LiquidacaoLoteProcesso,
-- Produto, Fundo, nenhuma das que o listener olha). O lateral "valores" GANHA o anti-join do pagamento
-- (via parcela -> contrato -> processo), porque a query tem LiquidacaoPagamento como entidade e não toca
-- Contrato nem ProcessoEstado. É o NOT EXISTS ao final do lateral.
explain (analyze, buffers)
with pagina as (
    select l.id as lote_id,
           cast(l.identificador as varchar) as liquidacao_id,
           l.data_criacao,
           l.data_atualizacao,
           l.estado_atual,
           pr.id as produto_id,
           pr.nome as produto_nome,
           fu.id as fundo_id,
           fu.nome as fundo_nome,
           count(*) over () as total_lotes
    from master.liquidacao_lote_processo l
    join master.produto pr on pr.id = l.produto_id
    join master.fundo fu on fu.id = :fundo_id
    where (
            (select pa.fundo_id
             from master.liquidacao_pagamento p
             join master.contrato_parcela pa on pa.id = p.parcela_id
             where p.liquidacao_lote_id = l.id
             limit 1) = :fundo_id
            or (
                exists (select 1 from master.produto_config pc
                        where pc.produto_id = l.produto_id and pc.fechar_lote_por_proc_id is true)
                and exists (select 1
                            from master.liquidacao_pagamento p
                            join master.contrato_parcela pa on pa.id = p.parcela_id
                            where p.liquidacao_lote_id = l.id and pa.fundo_id = :fundo_id
                            offset 0)
            )
          )
      and not exists (select 1 from master.liquidacao_lote_vigente v
                      where v.liquidacao_lote_id = l.id and v.fechado is false and l.estado_atual = 'pendente')
      and l.data_criacao >= :'dia'::date
      and l.data_criacao < :'dia'::date + 1
    order by l.data_criacao desc, l.identificador
    limit :limite offset :deslocamento
)
select pagina.lote_id, pagina.liquidacao_id, pagina.data_criacao, pagina.data_atualizacao,
       pagina.estado_atual, pagina.produto_id, pagina.produto_nome, pagina.fundo_id, pagina.fundo_nome,
       pagina.total_lotes,
       valores.valor_pago, valores.qtd_registros, valores.proc_id, valores.proc_ids
from pagina
left join lateral (
    select coalesce(sum(p.valor_pago), 0) as valor_pago,
           count(*) as qtd_registros,
           min(cast(lp.proc_id as varchar)) as proc_id,
           array_agg(distinct cast(lp.proc_id as varchar)) as proc_ids
    from master.liquidacao_pagamento p
    join master.liquidacao_processo lp on lp.uuid = p.liquidacao_processo_uuid
    where p.liquidacao_lote_id = pagina.lote_id
      -- adicionado pelo ContratoSoftDeleteListener
      and not exists (select 1
                      from master.contrato_parcela pa
                      join master.contrato c on c.id = pa.contrato_id
                      join master.contrato_processo cp on cp.uuid = c.processo_uuid
                      where pa.id = p.parcela_id and cp.data_delete is not null)
) valores on true
order by pagina.data_criacao desc, pagina.liquidacao_id;

-- 3. service.py:1513 (_lotes_por_remessa) -> lotes_das_remessas (repository.py:778)
--    -> _batches_fed_by_remittances (repository.py:~822). Core select via db.session.execute: SEM listener
--    (nenhum filtro de soft delete). Roda só se alguma linha do passo 2 trouxe proc_ids (sempre, na prática).
--    A lista é a união dos proc_ids das linhas da página.
explain (analyze, buffers)
select cast(r.proc_id as varchar) as proc_id, b.lote_id
from unnest(cast(cast(:'proc_ids' as varchar[]) as uuid[])) as r(proc_id)
join lateral (
    select distinct p.liquidacao_lote_id as lote_id
    from master.liquidacao_processo lp
    join master.liquidacao_pagamento p on p.liquidacao_processo_uuid = lp.uuid
    where lp.proc_id = r.proc_id
      and p.liquidacao_lote_id is not null
) b on true;

-- 4. lotes_das_remessas, segunda consulta (repository.py:~800): dos lotes do passo 3, quais pertencem ao fundo.
--    db.session.query(LiquidacaoLoteProcesso.id): a única entidade é o lote, SEM filtro do listener.
--    Roda só se o passo 3 devolveu linhas. Mesma regra de fundo do passo 2.
explain (analyze, buffers)
select l.id
from master.liquidacao_lote_processo l
where l.id in (:lote_ids)
  and (
        (select pa.fundo_id
         from master.liquidacao_pagamento p
         join master.contrato_parcela pa on pa.id = p.parcela_id
         where p.liquidacao_lote_id = l.id
         limit 1) = :fundo_id
        or (
            exists (select 1 from master.produto_config pc
                    where pc.produto_id = l.produto_id and pc.fechar_lote_por_proc_id is true)
            and exists (select 1
                        from master.liquidacao_pagamento p
                        join master.contrato_parcela pa on pa.id = p.parcela_id
                        where p.liquidacao_lote_id = l.id and pa.fundo_id = :fundo_id
                        offset 0)
        )
      );
