-- Remessas recentes de um produto + fundo e se viraram lote.
-- Filtra por produto_id e data_criacao (ambos com índice); prefira a réplica
-- ou um horário calmo. Validada contra o schema do master 9ddb97f.
WITH params AS (
    SELECT 0::int AS produto_id,
           0::int AS fundo_id,
           3      AS dias
),
processos AS (
    SELECT lp.proc_id, lp.uuid, lp.estado_atual, lp.data_criacao
    FROM liquidacao_processo lp, params
    WHERE lp.produto_id = params.produto_id
      AND lp.data_criacao >= now() - make_interval(days => params.dias)
)
SELECT pr.proc_id,
       min(pr.data_criacao) AS primeira_entrada,
       max(pr.data_criacao) AS ultima_entrada,
       count(DISTINCT pr.uuid) AS processos,
       count(DISTINCT pr.uuid) FILTER (WHERE pr.estado_atual = 'cadastrado') AS cadastrados,
       count(DISTINCT pr.uuid) FILTER (WHERE pr.estado_atual IN ('rejeitado', 'errado')) AS rejeitados_ou_errados,
       count(DISTINCT pr.uuid) FILTER (WHERE pr.estado_atual NOT IN ('cadastrado', 'rejeitado', 'errado')) AS em_processamento,
       count(pg.id) FILTER (WHERE pg.liquidacao_lote_id IS NULL) AS pagamentos_sem_lote,
       jsonb_agg(DISTINCT jsonb_build_object(
           'lote_id', l.id, 'estado', l.estado_atual, 'criado_em', l.data_criacao
       )) FILTER (WHERE l.id IS NOT NULL) AS lotes
FROM processos pr
CROSS JOIN params
LEFT JOIN liquidacao_pagamento pg ON pg.liquidacao_processo_uuid = pr.uuid
LEFT JOIN contrato_parcela cp ON cp.id = pg.parcela_id
LEFT JOIN liquidacao_lote_processo l ON l.id = pg.liquidacao_lote_id
WHERE pg.id IS NULL OR cp.fundo_id = params.fundo_id
GROUP BY pr.proc_id
ORDER BY primeira_entrada DESC;
