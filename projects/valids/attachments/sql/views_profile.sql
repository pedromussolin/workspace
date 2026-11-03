-- Consultas de perfil das views plgn.administradores_* usadas em 21/10/2026.
-- Todas leves: catálogo, ou filtro por data_ref (sortkey) de um dia a um mês.

-- 1. Views e tabelas físicas (as views são late-binding sobre plgn_physical,
--    por isso não aparecem em information_schema.columns).
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_name LIKE 'administradores%'
ORDER BY 1, 2;

SELECT viewname, definition
FROM pg_views
WHERE schemaname = 'plgn' AND viewname LIKE 'administradores%';

-- 2. Colunas (pelas tabelas físicas).
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'plgn_physical' AND table_name LIKE 'administradores%'
ORDER BY table_name, ordinal_position;

-- 3. Tamanho e sortkey.
SELECT "table", tbl_rows, size AS size_mb, sortkey1, diststyle
FROM svv_table_info
WHERE schema = 'plgn_physical' AND "table" LIKE 'administradores%';

-- 4. Aquisição por administrador e dia (data_ref × data_aquisicao).
SELECT source, data_ref, COUNT(*) AS n, COUNT(DISTINCT cnpj_classe) AS fundos,
       MIN(data_aquisicao) AS min_aq, MAX(data_aquisicao) AS max_aq,
       ROUND(SUM(vl_aquisicao)) AS vl_aq,
       SUM(CASE WHEN id_parcela IS NULL THEN 1 ELSE 0 END) AS sem_parcela
FROM plgn.administradores_aquisicao
WHERE data_ref BETWEEN :inicio AND :fim
GROUP BY 1, 2
ORDER BY 2 DESC, 1;

-- 5. Liquidação: tipos e preenchimento das colunas de valor, por administrador.
SELECT source, tipo_movimento, COUNT(*) AS n,
       ROUND(SUM(vl_pago)) AS pago, ROUND(SUM(vl_nominal)) AS nominal,
       ROUND(SUM(vl_presente)) AS vp, ROUND(SUM(vl_aquisicao)) AS aquis,
       ROUND(SUM(vl_ajuste)) AS ajuste, ROUND(SUM(vl_juros)) AS juros
FROM plgn.administradores_liquidacao
WHERE data_ref BETWEEN :inicio AND :fim
GROUP BY 1, 2
ORDER BY 1, 3 DESC;

-- 6. Estoque por contrato por administrador e dia; compara com a fonte atual.
SELECT data_ref, source, COUNT(*) AS n, COUNT(DISTINCT cnpj_classe) AS fundos,
       ROUND(SUM(vl_presente)) AS vp
FROM plgn.administradores_estoque_contrato
WHERE data_ref BETWEEN :inicio AND :fim
GROUP BY 1, 2
ORDER BY 1, 2;

SELECT source, COUNT(*) AS n, COUNT(DISTINCT cnpj_classe) AS fundos,
       ROUND(SUM(vl_presente)) AS vp, ROUND(SUM(vl_pdd)) AS pdd
FROM plgn.estoque_contrato
WHERE data_ref = :dia
GROUP BY 1
ORDER BY 1;

-- 7. Reconciliação residual por fundo num mês (saldo, aquisições, baixas).
WITH e AS (
    SELECT source, cnpj_classe,
           SUM(CASE WHEN data_ref = :fechamento_anterior THEN vl_presente END) AS ini,
           SUM(CASE WHEN data_ref = :fechamento THEN vl_presente END) AS fim
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref IN (:fechamento_anterior, :fechamento)
    GROUP BY 1, 2
),
a AS (
    SELECT source, cnpj_classe, SUM(vl_aquisicao) AS aq
    FROM plgn.administradores_aquisicao
    WHERE data_ref > :fechamento_anterior AND data_ref <= :fechamento
    GROUP BY 1, 2
),
l AS (
    SELECT source, cnpj_classe, SUM(vl_pago) AS bx
    FROM plgn.administradores_liquidacao
    WHERE data_ref > :fechamento_anterior AND data_ref <= :fechamento
    GROUP BY 1, 2
)
SELECT COALESCE(e.source, a.source, l.source) AS admin,
       COALESCE(e.cnpj_classe, a.cnpj_classe, l.cnpj_classe) AS fundo,
       e.ini, a.aq, l.bx, e.fim,
       e.fim - COALESCE(e.ini, 0) - COALESCE(a.aq, 0) + COALESCE(l.bx, 0) AS residual
FROM e
FULL JOIN a ON a.source = e.source AND a.cnpj_classe = e.cnpj_classe
FULL JOIN l ON l.source = COALESCE(e.source, a.source)
           AND l.cnpj_classe = COALESCE(e.cnpj_classe, a.cnpj_classe);
