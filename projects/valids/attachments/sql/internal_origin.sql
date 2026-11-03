-- De onde vem a fonte INTERNAL e por que ela não tem parcela, aquisição nem
-- liquidação (P2), em 27/10/2026. Todas leves: catálogo, ou um dia filtrado
-- por data_ref (sortkey), só agregados (sem CNPJ, nome nem CPF).
-- Parâmetro: :dia (usado: 2026-09-30).

-- 1. As views plgn.administradores_* são só SELECT * de plgn_physical.
SELECT viewname, definition
FROM pg_views
WHERE schemaname = 'plgn' AND viewname LIKE 'administradores%';

-- 2. Colunas das tabelas físicas: as três sem INTERNAL têm loaded_at e campos
--    do arquivo do administrador; as duas por contrato não têm loaded_at.
SELECT table_name, LISTAGG(column_name, ', ') WITHIN GROUP (ORDER BY ordinal_position) AS colunas
FROM svv_columns
WHERE table_schema = 'plgn_physical'
  AND (table_name LIKE 'administradores%' OR table_name = 'estoque_contrato')
GROUP BY table_name;

-- 3. Fundos e contratos por fonte nas três tabelas de estoque, num dia.
WITH a AS (
    SELECT source, COUNT(DISTINCT cnpj_classe) AS fundos, COUNT(*) AS n, SUM(vl_presente) AS vp
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :dia
    GROUP BY 1
), e AS (
    SELECT source, COUNT(DISTINCT cnpj_classe) AS fundos, COUNT(*) AS n, SUM(vl_presente) AS vp
    FROM plgn.estoque_contrato
    WHERE data_ref = :dia
    GROUP BY 1
), p AS (
    SELECT source, COUNT(DISTINCT cnpj_classe) AS fundos, COUNT(*) AS n
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia
    GROUP BY 1
)
SELECT COALESCE(a.source, e.source, p.source) AS source,
       a.fundos AS fundos_contrato, e.fundos AS fundos_estoque_contrato, p.fundos AS fundos_parcela,
       a.n AS contratos, e.n AS contratos_estoque_contrato, p.n AS parcelas,
       ROUND(a.vp / 1e6, 1) AS vp_mi, ROUND(e.vp / 1e6, 1) AS vp_estoque_contrato_mi
FROM a
FULL JOIN e ON e.source = a.source
FULL JOIN p ON p.source = COALESCE(a.source, e.source)
ORDER BY 1;

-- 4. Os fundos da INTERNAL na estoque_contrato, totais por fundo comparados.
WITH a AS (
    SELECT cnpj_classe, COUNT(*) AS n, SUM(vl_presente) AS vp
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :dia AND source = 'INTERNAL'
    GROUP BY 1
), e AS (
    SELECT cnpj_classe, source, COUNT(*) AS n, SUM(vl_presente) AS vp
    FROM plgn.estoque_contrato
    WHERE data_ref = :dia AND cnpj_classe IN (SELECT cnpj_classe FROM a)
    GROUP BY 1, 2
)
SELECT COALESCE(e.source, '(não está)') AS source_estoque_contrato, COUNT(*) AS fundos,
       SUM(a.n) AS contratos_internal, SUM(e.n) AS contratos_estoque_contrato,
       ROUND(SUM(a.vp) / 1e6, 1) AS vp_internal_mi, ROUND(SUM(e.vp) / 1e6, 1) AS vp_estoque_contrato_mi,
       ROUND(MAX(ABS(a.vp - e.vp)), 2) AS maior_dif_fundo,
       SUM(CASE WHEN a.n = e.n THEN 1 ELSE 0 END) AS fundos_mesma_qtd
FROM a
LEFT JOIN e ON e.cnpj_classe = a.cnpj_classe
GROUP BY 1;

-- 5. Vínculo com a plataforma de cessão por fonte (% preenchido).
SELECT source, COUNT(*) AS contratos,
       ROUND(100.0 * COUNT(id_contrato_cessao) / COUNT(*), 1) AS pct_id_contrato_cessao,
       ROUND(100.0 * COUNT(id_sacado_cessao) / COUNT(*), 1) AS pct_id_sacado_cessao,
       ROUND(100.0 * COUNT(id_produto_cessao) / COUNT(*), 1) AS pct_id_produto_cessao,
       ROUND(100.0 * COUNT(vl_ltv) / COUNT(*), 1) AS pct_vl_ltv
FROM plgn.estoque_contrato
WHERE data_ref = :dia
GROUP BY 1
ORDER BY 1;

-- 6. Quantos fundos de cada fonte também têm linhas INTERNAL (e quantos da
--    INTERNAL também vêm por um administrador), num dia.
WITH f AS (
    SELECT cnpj_classe, source
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :dia
    GROUP BY 1, 2
), s AS (
    SELECT cnpj_classe,
           MAX(CASE WHEN source = 'INTERNAL' THEN 1 ELSE 0 END) AS ti,
           SUM(CASE WHEN source <> 'INTERNAL' THEN 1 ELSE 0 END) AS na
    FROM f
    GROUP BY 1
)
SELECT f.source, COUNT(*) AS fundos,
       SUM(CASE WHEN f.source <> 'INTERNAL' THEN s.ti END) AS tambem_internal,
       SUM(CASE WHEN f.source = 'INTERNAL' AND s.na > 0 THEN 1
                WHEN f.source = 'INTERNAL' THEN 0 END) AS tambem_administradora
FROM f
JOIN s ON s.cnpj_classe = f.cnpj_classe
GROUP BY 1
UNION ALL
SELECT '(fundos distintos)', COUNT(*), NULL, NULL FROM s
ORDER BY 1;

-- 7. Nos fundos que vêm pela INTERNAL e por um administrador (só um), a
--    INTERNAL casada com o administrador contrato a contrato (id_contrato_admin).
--    Só totais por fundo; usar um dia sem duplicação de fonte (30/09).
WITH c AS (
    SELECT cnpj_classe, source
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :dia
    GROUP BY 1, 2
), dup AS (
    SELECT cnpj_classe, MAX(CASE WHEN source <> 'INTERNAL' THEN source END) AS adm
    FROM c
    GROUP BY 1
    HAVING MAX(CASE WHEN source = 'INTERNAL' THEN 1 ELSE 0 END) = 1
       AND SUM(CASE WHEN source <> 'INTERNAL' THEN 1 ELSE 0 END) = 1
), x AS (
    SELECT e.cnpj_classe, e.source, e.id_contrato_admin, e.vl_presente, e.vl_nominal,
           e.vl_aquisicao, e.vl_pdd, e.taxa_aquisicao, e.data_cessao
    FROM plgn.administradores_estoque_contrato e
    JOIN dup d ON d.cnpj_classe = e.cnpj_classe
    WHERE e.data_ref = :dia
), j AS (
    SELECT COALESCE(i.cnpj_classe, a.cnpj_classe) AS cnpj_classe,
           i.id_contrato_admin AS id_i, a.id_contrato_admin AS id_a,
           i.vl_presente AS vp_i, a.vl_presente AS vp_a,
           i.vl_nominal AS nom_i, a.vl_nominal AS nom_a,
           i.vl_aquisicao AS aq_i, a.vl_aquisicao AS aq_a,
           i.vl_pdd AS pdd_i, a.vl_pdd AS pdd_a,
           i.taxa_aquisicao AS tx_i, a.taxa_aquisicao AS tx_a,
           i.data_cessao AS dc_i, a.data_cessao AS dc_a
    FROM (SELECT * FROM x WHERE source = 'INTERNAL') i
    FULL JOIN (SELECT * FROM x WHERE source <> 'INTERNAL') a
      ON a.cnpj_classe = i.cnpj_classe AND a.id_contrato_admin = i.id_contrato_admin
)
SELECT d.adm,
       ROUND(SUM(j.vp_a) / 1e6, 2) AS vp_adm_mi,
       COUNT(j.id_i) AS n_internal, COUNT(j.id_a) AS n_adm,
       SUM(CASE WHEN j.id_i IS NOT NULL AND j.id_a IS NOT NULL THEN 1 ELSE 0 END) AS casados,
       ROUND(SUM(CASE WHEN j.id_a IS NOT NULL THEN j.vp_i END) / 1e6, 2) AS vp_i_casados,
       ROUND(SUM(CASE WHEN j.id_i IS NOT NULL THEN j.vp_a END) / 1e6, 2) AS vp_a_casados,
       ROUND(SUM(CASE WHEN j.id_a IS NOT NULL THEN j.nom_i END) / 1e6, 2) AS nom_i_casados,
       ROUND(SUM(CASE WHEN j.id_i IS NOT NULL THEN j.nom_a END) / 1e6, 2) AS nom_a_casados,
       ROUND(SUM(CASE WHEN j.id_a IS NOT NULL THEN j.aq_i END) / 1e6, 2) AS aq_i_casados,
       ROUND(SUM(CASE WHEN j.id_i IS NOT NULL THEN j.aq_a END) / 1e6, 2) AS aq_a_casados,
       ROUND(SUM(CASE WHEN j.id_a IS NOT NULL THEN j.pdd_i END) / 1e6, 2) AS pdd_i_casados,
       ROUND(SUM(CASE WHEN j.id_i IS NOT NULL THEN j.pdd_a END) / 1e6, 2) AS pdd_a_casados,
       ROUND(100.0 * SUM(CASE WHEN ABS(j.nom_i - j.nom_a) < 0.01 THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN j.id_i IS NOT NULL AND j.id_a IS NOT NULL THEN 1 ELSE 0 END), 0), 1) AS pct_nominal_igual,
       ROUND(100.0 * SUM(CASE WHEN ABS(j.aq_i - j.aq_a) < 0.01 THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN j.id_i IS NOT NULL AND j.id_a IS NOT NULL THEN 1 ELSE 0 END), 0), 1) AS pct_aquisicao_igual,
       ROUND(100.0 * SUM(CASE WHEN ABS(j.tx_i - j.tx_a) < 0.0001 THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN j.id_i IS NOT NULL AND j.id_a IS NOT NULL THEN 1 ELSE 0 END), 0), 1) AS pct_taxa_igual,
       ROUND(100.0 * SUM(CASE WHEN j.dc_i = j.dc_a THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN j.id_i IS NOT NULL AND j.id_a IS NOT NULL THEN 1 ELSE 0 END), 0), 1) AS pct_cessao_igual,
       ROUND(100.0 * SUM(CASE WHEN ABS(j.vp_i - j.vp_a) < 0.01 THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN j.id_i IS NOT NULL AND j.id_a IS NOT NULL THEN 1 ELSE 0 END), 0), 1) AS pct_vp_igual
FROM j
JOIN dup d ON d.cnpj_classe = j.cnpj_classe
GROUP BY d.adm, d.cnpj_classe
ORDER BY 1, 2;
