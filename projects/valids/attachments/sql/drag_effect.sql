-- Efeito vagão: o administrador aplica o rating do pior atraso ao contrato
-- inteiro e a todos os contratos do mesmo sacado? (26/10/2026)

-- 1. Por sacado, numa foto (leve: uma data_ref da view por contrato).
--    "misto" = sacado com contrato em dia e contrato atrasado no mesmo fundo.
WITH s AS (
    SELECT source, cnpj_classe, cpf_cnpj_sacado,
           COUNT(*) AS contratos,
           COUNT(DISTINCT COALESCE(faixa_pdd, '?')) AS ratings,
           SUM(CASE WHEN dias_atraso IS NULL THEN 1 ELSE 0 END) AS em_dia,
           SUM(CASE WHEN dias_atraso IS NOT NULL THEN 1 ELSE 0 END) AS atrasados
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :dia AND source <> 'INTERNAL'
    GROUP BY 1, 2, 3
)
SELECT source,
       COUNT(*) AS sacados,
       SUM(CASE WHEN contratos > 1 THEN 1 ELSE 0 END) AS com_2_ou_mais,
       SUM(CASE WHEN contratos > 1 AND ratings = 1 THEN 1 ELSE 0 END) AS mesmo_rating,
       SUM(CASE WHEN em_dia > 0 AND atrasados > 0 THEN 1 ELSE 0 END) AS misto,
       SUM(CASE WHEN em_dia > 0 AND atrasados > 0 AND ratings = 1 THEN 1 ELSE 0 END) AS misto_mesmo_rating
FROM s
GROUP BY 1
ORDER BY 1;

-- 2. Dentro do contrato, pela view por parcela. Amostra de contratos
--    atrasados de UM administrador por vez: com vários administradores juntos,
--    o Redshift abortou aos 60 s (26/10/2026).
WITH c AS (
    SELECT source, cnpj_classe, id_contrato_admin
    FROM (
        SELECT source, cnpj_classe, id_contrato_admin,
               ROW_NUMBER() OVER (PARTITION BY source ORDER BY MD5(id_contrato_admin)) AS rn
        FROM plgn.administradores_estoque_contrato
        WHERE data_ref = :dia AND source = :source AND dias_atraso IS NOT NULL
    ) x
    WHERE rn <= :amostra
),
p AS (
    SELECT e.source, e.cnpj_classe, e.id_contrato_admin,
           COUNT(*) AS parcelas,
           SUM(CASE WHEN e.flag_vencido = 1 THEN 1 ELSE 0 END) AS vencidas,
           SUM(CASE WHEN e.flag_vencido = 0 THEN 1 ELSE 0 END) AS a_vencer,
           COUNT(DISTINCT e.faixa_pdd) AS ratings,
           MIN(-e.vl_pdd_parcela / NULLIF(e.vl_presente_parcela, 0)) AS pct_min,
           MAX(-e.vl_pdd_parcela / NULLIF(e.vl_presente_parcela, 0)) AS pct_max,
           SUM(CASE WHEN e.flag_vencido = 0 AND e.vl_pdd_parcela <> 0 THEN 1 ELSE 0 END) AS a_vencer_com_pdd
    FROM plgn.administradores_estoque e
    JOIN c ON c.source = e.source AND c.cnpj_classe = e.cnpj_classe AND c.id_contrato_admin = e.id_contrato_admin
    WHERE e.data_ref = :dia AND e.source = :source
    GROUP BY 1, 2, 3
)
SELECT source,
       COUNT(*) AS contratos,
       SUM(CASE WHEN vencidas > 0 AND a_vencer > 0 THEN 1 ELSE 0 END) AS com_vencida_e_a_vencer,
       SUM(CASE WHEN vencidas > 0 AND a_vencer > 0 AND ratings = 1 THEN 1 ELSE 0 END) AS mesmo_rating,
       SUM(CASE WHEN vencidas > 0 AND a_vencer > 0 AND pct_max - pct_min < 0.001 THEN 1 ELSE 0 END) AS mesmo_pct,
       SUM(CASE WHEN vencidas > 0 AND a_vencer > 0 AND a_vencer_com_pdd > 0 THEN 1 ELSE 0 END) AS a_vencer_com_pdd,
       ROUND(AVG(parcelas), 1) AS parcelas_media
FROM p
GROUP BY 1;

-- 3. Réguas de PDD da plataforma, pelo espelho no lake (só configuração).
SELECT produto_id, ativada,
       JSON_EXTRACT_PATH_TEXT(kwargs, 'prazo_pdd', TRUE) AS prazo_pdd,
       JSON_EXTRACT_PATH_TEXT(kwargs, 'faixa_pdd', TRUE) AS faixas,
       JSON_EXTRACT_PATH_TEXT(kwargs, 'pdd_rate', TRUE) AS rates
FROM captalys_trusted.platform_cessao_master_regra
WHERE tipo_regra = 'pdd' AND produto_id IN (:produtos)
ORDER BY produto_id, ativada DESC;
