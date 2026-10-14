-- Tarefa 12: lotes reais, lotes antes dos valores.
-- Rodar na réplica de leitura. Cada bloco é independente.
-- Os parâmetros (:fundo_id, :inicio, :fim, :proc_ids) vêm de uma chamada real
-- da tela; pegar no log "Buscando lotes reais de liquidação paginados".

SET statement_timeout = '300s';


-- 1. Lote real com pagamento de mais de um fundo (decide a D11).
-- Vazio: o fundo do lote é o fundo de qualquer pagamento dele, e a checagem
-- do fundo pode olhar um pagamento só.
SELECT lp.liquidacao_lote_id,
       count(DISTINCT cp.fundo_id) AS fundos,
       min(llp.data_criacao)       AS data_criacao
FROM liquidacao_lote_processo llp
JOIN liquidacao_pagamento lp ON lp.liquidacao_lote_id = llp.id
JOIN contrato_parcela cp ON cp.id = lp.parcela_id
WHERE llp.data_criacao >= now() - interval '90 days'
GROUP BY lp.liquidacao_lote_id
HAVING count(DISTINCT cp.fundo_id) > 1;


-- 2. Índices que as consultas novas precisam.
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN (
    'liquidacao_lote_processo', 'liquidacao_pagamento',
    'liquidacao_processo', 'contrato_parcela'
)
ORDER BY tablename, indexname;


-- 3. Página nova: o filtro de fundo olha UM pagamento do lote, em vez de
-- procurar (com soft delete) entre todos os pagamentos de cada lote da janela.
-- Comparar com o EXPLAIN da consulta atual (copiar do trace do Datadog).
EXPLAIN (ANALYZE, BUFFERS)
WITH pagina AS (
    SELECT llp.id AS lote_id,
           llp.identificador::text AS liquidacao_id,
           llp.data_criacao,
           llp.data_atualizacao,
           llp.estado_atual,
           p.id AS produto_id,
           p.nome AS produto_nome,
           f.id AS fundo_id,
           f.nome AS fundo_nome,
           count(*) OVER () AS total_lotes
    FROM liquidacao_lote_processo llp
    JOIN produto p ON p.id = llp.produto_id
    JOIN fundo f ON f.id = :fundo_id
    WHERE llp.data_criacao >= :inicio
      AND llp.data_criacao < :fim
      AND (
          SELECT cp.fundo_id
          FROM liquidacao_pagamento lp
          JOIN contrato_parcela cp ON cp.id = lp.parcela_id
          WHERE lp.liquidacao_lote_id = llp.id
          LIMIT 1
      ) = f.id
    ORDER BY llp.data_criacao DESC, llp.identificador
    LIMIT 20 OFFSET 0
)
SELECT pagina.*, valores.*
FROM pagina
LEFT JOIN LATERAL (
    SELECT coalesce(sum(lp.valor_pago), 0) AS valor_pago,
           count(*) AS qtd_registros,
           min(pr.proc_id::text) AS proc_id,
           array_agg(DISTINCT pr.proc_id::text) AS proc_ids
    FROM liquidacao_pagamento lp
    JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
    WHERE lp.liquidacao_lote_id = pagina.lote_id
      AND NOT EXISTS (
          SELECT 1
          FROM contrato_parcela cp
          JOIN contrato c ON c.id = cp.contrato_id
          JOIN contrato_processo cpr ON cpr.uuid = c.processo_uuid
          WHERE cp.id = lp.parcela_id
            AND cpr.data_delete IS NOT NULL
      )
) valores ON true
ORDER BY pagina.data_criacao DESC, pagina.liquidacao_id;


-- 4a. Lotes irmãos, etapa A: que lotes cada remessa alimentou.
-- Sem parcela e sem soft delete: dois acessos por índice por pagamento, em vez
-- de oito (parcela + duas vezes parcela -> contrato -> processo).
EXPLAIN (ANALYZE, BUFFERS)
SELECT DISTINCT pr.proc_id::text AS proc_id, lp.liquidacao_lote_id AS lote_id
FROM liquidacao_processo pr
JOIN liquidacao_pagamento lp ON lp.liquidacao_processo_uuid = pr.uuid
WHERE pr.proc_id = ANY(CAST(:proc_ids AS uuid[]))
  AND lp.liquidacao_lote_id IS NOT NULL;


-- 4b. Lotes irmãos, etapa B: desses lotes (poucos), os do fundo da listagem.
EXPLAIN (ANALYZE, BUFFERS)
SELECT llp.id
FROM liquidacao_lote_processo llp
WHERE llp.id = ANY(CAST(:lote_ids AS int[]))
  AND (
      SELECT cp.fundo_id
      FROM liquidacao_pagamento lp
      JOIN contrato_parcela cp ON cp.id = lp.parcela_id
      WHERE lp.liquidacao_lote_id = llp.id
      LIMIT 1
  ) = :fundo_id;


-- 5. Equivalência: pares (proc_id, lote_id) da consulta atual que a nova não
-- devolve, e vice-versa. As duas listas precisam sair vazias.
WITH atual AS (
    SELECT DISTINCT pr.proc_id::text AS proc_id, lp.liquidacao_lote_id AS lote_id
    FROM liquidacao_pagamento lp
    JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
    JOIN contrato_parcela cp ON cp.id = lp.parcela_id
    WHERE pr.proc_id = ANY(CAST(:proc_ids AS uuid[]))
      AND lp.liquidacao_lote_id IS NOT NULL
      AND cp.fundo_id = :fundo_id
      AND NOT EXISTS (
          SELECT 1
          FROM contrato c
          JOIN contrato_processo cpr ON cpr.uuid = c.processo_uuid
          WHERE c.id = cp.contrato_id
            AND cpr.data_delete IS NOT NULL
      )
),
etapa_a AS (
    SELECT DISTINCT pr.proc_id::text AS proc_id, lp.liquidacao_lote_id AS lote_id
    FROM liquidacao_processo pr
    JOIN liquidacao_pagamento lp ON lp.liquidacao_processo_uuid = pr.uuid
    WHERE pr.proc_id = ANY(CAST(:proc_ids AS uuid[]))
      AND lp.liquidacao_lote_id IS NOT NULL
),
nova AS (
    SELECT a.proc_id, a.lote_id
    FROM etapa_a a
    WHERE (
        SELECT cp.fundo_id
        FROM liquidacao_pagamento lp
        JOIN contrato_parcela cp ON cp.id = lp.parcela_id
        WHERE lp.liquidacao_lote_id = a.lote_id
        LIMIT 1
    ) = :fundo_id
)
SELECT 'so_na_atual' AS lado, * FROM (SELECT * FROM atual EXCEPT SELECT * FROM nova) x
UNION ALL
SELECT 'so_na_nova', * FROM (SELECT * FROM nova EXCEPT SELECT * FROM atual) y;
