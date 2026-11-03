-- Cadeia estoque (lake) → dim_contrato → fundo/produto/regra (plataforma),
-- pelo espelho das tabelas do platform-cessao no lake (26/10/2026).
-- Consultas pequenas, uma etapa por vez: juntas numa consulta só, passaram
-- de 60 s (subconsulta escalar e dim_contrato sem filtro antes da junção).
--
-- Parâmetros: :produtos, :fundo_plataforma, :dia, :source.

-- 1. Produto → fundo da plataforma (vigência e fundo padrão).
SELECT produto_id, fundo_id, "default" AS padrao, data_inicio::date, data_fim::date
FROM captalys_trusted.platform_cessao_master_produto_fundo
WHERE produto_id IN (:produtos)
ORDER BY 1, 2;

-- 2. Régua de PDD do produto no fundo (ativa e inativas).
SELECT produto_id, fundo_id, ativada,
       JSON_EXTRACT_PATH_TEXT(kwargs, 'prazo_pdd', TRUE) AS prazo_pdd,
       JSON_EXTRACT_PATH_TEXT(kwargs, 'faixa_pdd', TRUE) AS faixas,
       JSON_EXTRACT_PATH_TEXT(kwargs, 'pdd_rate', TRUE) AS rates
FROM captalys_trusted.platform_cessao_master_regra
WHERE tipo_regra = 'pdd' AND produto_id IN (:produtos) AND fundo_id = :fundo_plataforma;

-- 3. Contratos do fundo numa faixa, com quantos contratos o sacado tem
--    (o CNPJ sai do cadastro do fundo da plataforma, sem escrevê-lo).
WITH f AS (
    SELECT REGEXP_REPLACE(cnpj, '[^0-9]', '') AS cnpj
    FROM captalys_trusted.platform_cessao_master_fundo WHERE id = :fundo_plataforma
),
cand AS (
    SELECT x.cpf_cnpj_sacado, x.faixa_pdd, x.dias_atraso, x.vl_presente, x.vl_pdd
    FROM plgn.administradores_estoque_contrato x
    WHERE x.data_ref = :dia AND x.source = :source
      AND x.cnpj_classe IN (SELECT cnpj FROM f)
      AND x.faixa_pdd = 'C' AND x.dias_atraso BETWEEN 16 AND 30 AND x.qt_parcelas_vencidas = 1
    LIMIT 20
),
sac AS (
    SELECT y.cpf_cnpj_sacado, COUNT(*) AS n
    FROM plgn.administradores_estoque_contrato y
    WHERE y.data_ref = :dia AND y.source = :source
      AND y.cpf_cnpj_sacado IN (SELECT cpf_cnpj_sacado FROM cand)
    GROUP BY 1
)
SELECT s.n AS contratos_do_sacado, c.faixa_pdd, c.dias_atraso,
       ROUND(-c.vl_pdd / NULLIF(c.vl_presente, 0), 4) AS pct_pdd
FROM cand c JOIN sac s ON s.cpf_cnpj_sacado = c.cpf_cnpj_sacado;
