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


-- 6. Teste só com os filtros da tela: fundo, produto e período.
-- Monta a página como a tela (20 lotes mais recentes), tira dela as remessas
-- e roda a busca dos lotes irmãos na versão atual (6b) e na nova (6c).
-- Compare o tempo de execução que o DBeaver mostra. Rode cada uma duas
-- vezes e compare a segunda (a primeira paga o cache do disco).
-- :inicio e :fim são datas (ex.: 2026-10-01 e 2026-10-14), como na tela.
-- Para "todos os produtos", apague a linha do :produto_id.
SET statement_timeout = '300s';

-- 6a. Tamanho do problema: quantas remessas e pagamentos a página arrasta.
WITH pagina AS MATERIALIZED (
    SELECT llp.id AS lote_id
    FROM liquidacao_lote_processo llp
    WHERE llp.data_criacao >= CAST(:inicio AS date)
      AND llp.data_criacao < CAST(:fim AS date) + 1
      AND llp.produto_id = :produto_id
      AND EXISTS (
          SELECT 1
          FROM liquidacao_pagamento lp
          JOIN contrato_parcela cp ON cp.id = lp.parcela_id
          WHERE lp.liquidacao_lote_id = llp.id
            AND cp.fundo_id = :fundo_id
      )
    ORDER BY llp.data_criacao DESC, llp.identificador
    LIMIT 20
),
remessas AS MATERIALIZED (
    SELECT DISTINCT pr.proc_id
    FROM pagina
    JOIN liquidacao_pagamento lp ON lp.liquidacao_lote_id = pagina.lote_id
    JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
)
SELECT (SELECT count(*) FROM pagina)   AS lotes_na_pagina,
       (SELECT count(*) FROM remessas) AS remessas,
       (SELECT count(*)
        FROM liquidacao_processo pr
        JOIN liquidacao_pagamento lp ON lp.liquidacao_processo_uuid = pr.uuid
        WHERE pr.proc_id = ANY(ARRAY(SELECT proc_id FROM remessas))
       ) AS pagamentos_das_remessas;

-- 6b. Lotes irmãos como a cessão faz hoje.
WITH pagina AS MATERIALIZED (
    SELECT llp.id AS lote_id
    FROM liquidacao_lote_processo llp
    WHERE llp.data_criacao >= CAST(:inicio AS date)
      AND llp.data_criacao < CAST(:fim AS date) + 1
      AND llp.produto_id = :produto_id
      AND EXISTS (
          SELECT 1
          FROM liquidacao_pagamento lp
          JOIN contrato_parcela cp ON cp.id = lp.parcela_id
          WHERE lp.liquidacao_lote_id = llp.id
            AND cp.fundo_id = :fundo_id
      )
    ORDER BY llp.data_criacao DESC, llp.identificador
    LIMIT 20
),
remessas AS MATERIALIZED (
    SELECT DISTINCT pr.proc_id
    FROM pagina
    JOIN liquidacao_pagamento lp ON lp.liquidacao_lote_id = pagina.lote_id
    JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
)
SELECT DISTINCT pr.proc_id::text AS proc_id, lp.liquidacao_lote_id AS lote_id
FROM liquidacao_pagamento lp
JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
JOIN contrato_parcela cp ON cp.id = lp.parcela_id
WHERE pr.proc_id = ANY(ARRAY(SELECT proc_id FROM remessas))
  AND lp.liquidacao_lote_id IS NOT NULL
  AND cp.fundo_id = :fundo_id
  -- O filtro de soft delete entra duas vezes hoje (por Parcela e por
  -- LiquidacaoPagamento); repetido aqui para medir o custo real.
  AND NOT EXISTS (
      SELECT 1
      FROM contrato c
      JOIN contrato_processo cpr ON cpr.uuid = c.processo_uuid
      WHERE c.id = cp.contrato_id
        AND cpr.data_delete IS NOT NULL
  )
  AND NOT EXISTS (
      SELECT 1
      FROM contrato_parcela cp2
      JOIN contrato c2 ON c2.id = cp2.contrato_id
      JOIN contrato_processo cpr2 ON cpr2.uuid = c2.processo_uuid
      WHERE cp2.id = lp.parcela_id
        AND cpr2.data_delete IS NOT NULL
  );

-- 6c. Lotes irmãos na versão nova: lotes primeiro, fundo depois.
WITH pagina AS MATERIALIZED (
    SELECT llp.id AS lote_id
    FROM liquidacao_lote_processo llp
    WHERE llp.data_criacao >= CAST(:inicio AS date)
      AND llp.data_criacao < CAST(:fim AS date) + 1
      AND llp.produto_id = :produto_id
      AND EXISTS (
          SELECT 1
          FROM liquidacao_pagamento lp
          JOIN contrato_parcela cp ON cp.id = lp.parcela_id
          WHERE lp.liquidacao_lote_id = llp.id
            AND cp.fundo_id = :fundo_id
      )
    ORDER BY llp.data_criacao DESC, llp.identificador
    LIMIT 20
),
remessas AS MATERIALIZED (
    SELECT DISTINCT pr.proc_id
    FROM pagina
    JOIN liquidacao_pagamento lp ON lp.liquidacao_lote_id = pagina.lote_id
    JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
),
lotes_das_remessas AS MATERIALIZED (
    SELECT DISTINCT pr.proc_id::text AS proc_id, lp.liquidacao_lote_id AS lote_id
    FROM liquidacao_processo pr
    JOIN liquidacao_pagamento lp ON lp.liquidacao_processo_uuid = pr.uuid
    WHERE pr.proc_id = ANY(ARRAY(SELECT proc_id FROM remessas))
      AND lp.liquidacao_lote_id IS NOT NULL
)
SELECT l.proc_id, l.lote_id
FROM lotes_das_remessas l
WHERE (
    SELECT cp.fundo_id
    FROM liquidacao_pagamento lp
    JOIN contrato_parcela cp ON cp.id = lp.parcela_id
    WHERE lp.liquidacao_lote_id = l.lote_id
    LIMIT 1
) = :fundo_id;


-- 7. Tamanho da janela: quantos lotes a página nova testa (um pagamento por
-- lote) e quantos são do fundo. É o custo do filtro de fundo e da contagem
-- total na versão em etapas. Rodar sem produto, com a janela da tela.
SELECT count(*)                                  AS lotes_na_janela,
       count(*) FILTER (WHERE fundo = :fundo_id) AS lotes_do_fundo
FROM (
    SELECT (
        SELECT cp.fundo_id
        FROM liquidacao_pagamento lp
        JOIN contrato_parcela cp ON cp.id = lp.parcela_id
        WHERE lp.liquidacao_lote_id = llp.id
        LIMIT 1
    ) AS fundo
    FROM liquidacao_lote_processo llp
    WHERE llp.data_criacao >= CAST(:inicio AS date)
      AND llp.data_criacao < CAST(:fim AS date) + 1
) x;


-- 8. Por remessa: pagamentos x lotes distintos. A razão entre os dois é o
-- ganho do salto de lote em lote (passo 9) sobre ler todos os pagamentos.
SELECT pr.proc_id,
       count(*)                              AS pagamentos,
       count(DISTINCT lp.liquidacao_lote_id) AS lotes
FROM liquidacao_processo pr
JOIN liquidacao_pagamento lp ON lp.liquidacao_processo_uuid = pr.uuid
WHERE pr.proc_id = ANY(CAST(:proc_ids AS uuid[]))
  AND lp.liquidacao_lote_id IS NOT NULL
GROUP BY pr.proc_id;


-- 9. DESCARTADO em 20/10: na réplica, liquidacao_processo tem uma linha por
-- pagamento (802 milhões), então não há lote para saltar. Fica só como
-- registro do mecanismo.
-- Lotes de cada remessa saltando de lote em lote (loose index scan).
-- NÃO rodar antes de existir o índice abaixo: sem ele, cada volta lê todos
-- os pagamentos da remessa e fica pior que a consulta atual. O índice é
-- criado pela DBA no primário e chega à réplica sozinho:
--   CREATE INDEX CONCURRENTLY ix_liquidacao_pagamento_processo_lote
--       ON liquidacao_pagamento (liquidacao_processo_uuid, liquidacao_lote_id);
-- Cada volta do WITH RECURSIVE pede ao índice "o menor lote desta remessa
-- maior que o último achado": o custo vira o número de lotes da remessa,
-- não o de pagamentos. min() já ignora pagamento sem lote.
EXPLAIN (ANALYZE, BUFFERS)
WITH RECURSIVE processos AS (
    SELECT pr.uuid, pr.proc_id
    FROM liquidacao_processo pr
    WHERE pr.proc_id = ANY(CAST(:proc_ids AS uuid[]))
),
lotes AS (
    SELECT p.uuid,
           p.proc_id,
           (SELECT min(lp.liquidacao_lote_id)
            FROM liquidacao_pagamento lp
            WHERE lp.liquidacao_processo_uuid = p.uuid) AS lote_id
    FROM processos p
    UNION ALL
    SELECT l.uuid,
           l.proc_id,
           (SELECT min(lp.liquidacao_lote_id)
            FROM liquidacao_pagamento lp
            WHERE lp.liquidacao_processo_uuid = l.uuid
              AND lp.liquidacao_lote_id > l.lote_id)
    FROM lotes l
    WHERE l.lote_id IS NOT NULL
)
SELECT DISTINCT proc_id::text AS proc_id, lote_id
FROM lotes
WHERE lote_id IS NOT NULL;
