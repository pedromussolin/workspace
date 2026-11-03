-- Abertura de Rating: como cada contrato do estoque acha o produto em
-- plgn.dim_contrato (22/10/2026). Amostra por fundo (MD5 do id), leve: uma
-- foto filtrada por data_ref e a dim filtrada pelos fundos da amostra.
-- dim_contrato NÃO tem sortkey: todo filtro nela lê a coluna inteira; manter
-- a amostra pequena e as junções por igualdade (um OR na junção vira produto
-- cartesiano dentro do fundo).
--
-- Parâmetros: :fechamento_letra (data das letras dos fundos, 2026-08-31),
-- :dia (foto testada), :sources (administradores), :amostra (contratos por fundo).

WITH vp_letra AS (
    SELECT source, cnpj_classe, SUM(vl_presente) AS vp
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :fechamento_letra AND source <> 'INTERNAL'
    GROUP BY 1, 2
),
letra AS (
    SELECT source, cnpj_classe,
           CHR(CAST(64 + ROW_NUMBER() OVER (PARTITION BY source ORDER BY vp DESC) AS INT)) AS letra
    FROM vp_letra
),
s AS (
    SELECT source, cnpj_classe, id_contrato_admin, faixa_pdd, vl_presente
    FROM (
        SELECT source, cnpj_classe, id_contrato_admin, faixa_pdd, vl_presente,
               ROW_NUMBER() OVER (PARTITION BY cnpj_classe ORDER BY MD5(id_contrato_admin)) AS rn
        FROM plgn.administradores_estoque_contrato
        WHERE data_ref = :dia AND source IN (:sources)
    ) x
    WHERE rn <= :amostra
),
d AS (
    SELECT cnpj_classe, id_contrato_cessao, num_controle, identificador, produto_id, rating
    FROM plgn.dim_contrato
    WHERE cnpj_classe IN (SELECT DISTINCT cnpj_classe FROM s)
),
m AS (
    SELECT s.source, s.cnpj_classe, s.id_contrato_admin, s.faixa_pdd, s.vl_presente,
           COUNT(DISTINCT d1.id_contrato_cessao) AS n_nc,
           COUNT(DISTINCT d2.id_contrato_cessao) AS n_id,
           COUNT(DISTINCT COALESCE(d1.produto_id, d2.produto_id)) AS n_prod,
           MAX(COALESCE(d1.rating, d2.rating)) AS rating_dim
    FROM s
    LEFT JOIN d d1 ON d1.cnpj_classe = s.cnpj_classe AND d1.num_controle = s.id_contrato_admin
    LEFT JOIN d d2 ON d2.cnpj_classe = s.cnpj_classe AND d2.identificador = s.id_contrato_admin
    GROUP BY 1, 2, 3, 4, 5
)
SELECT m.source, l.letra,
       COUNT(*) AS amostra,
       SUM(CASE WHEN n_nc > 0 THEN 1 ELSE 0 END) AS por_num_controle,
       SUM(CASE WHEN n_id > 0 THEN 1 ELSE 0 END) AS por_identificador,
       SUM(CASE WHEN n_nc > 0 OR n_id > 0 THEN 1 ELSE 0 END) AS casou,
       ROUND(SUM(CASE WHEN n_nc > 0 OR n_id > 0 THEN vl_presente ELSE 0 END) / NULLIF(SUM(vl_presente), 0), 3) AS vp_casado,
       SUM(CASE WHEN n_nc > 1 OR n_id > 1 THEN 1 ELSE 0 END) AS mais_de_uma_linha,
       SUM(CASE WHEN n_nc > 0 AND n_id > 0 AND n_prod > 1 THEN 1 ELSE 0 END) AS produto_em_conflito,
       SUM(CASE WHEN rating_dim = faixa_pdd THEN 1 ELSE 0 END) AS rating_dim_igual_faixa_pdd
FROM m
LEFT JOIN letra l ON l.source = m.source AND l.cnpj_classe = m.cnpj_classe
GROUP BY 1, 2
ORDER BY 1, 2;
