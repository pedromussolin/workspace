-- Estudo de Migração: matriz de migração (roll rate) entre dois fechamentos
-- mensais (D20). Revisto em 26/10/2026 com D17, D20, D22 e a recomendação da
-- D33 (8 faixas fixas; por fundo e produto).
--
-- Cada contrato do fechamento anterior cai numa faixa do fechamento atual,
-- ou em "saiu" (8); contrato novo entra como "novo" (-1). Faixa pelo
-- dias_atraso do próprio contrato (nulo = em dia), sem arrasto por sacado.
-- Só fundos com foto nas duas datas: um fundo que sai do arquivo não vira
-- uma linha inteira de "saiu". Cada par de meses é calculado uma vez e
-- gravado no Postgres (D22).
--
-- Parâmetros: :fechamento_anterior e :fechamento (etapa 1 de
-- monthly_band_migration.sql, mês anterior e mês atual).

WITH f0 AS (
    SELECT data_ref, source, cnpj_classe, id_contrato_admin, vl_presente,
           CASE WHEN dias_atraso IS NULL THEN 0
                WHEN dias_atraso > 180 THEN 7
                ELSE CAST(FLOOR((dias_atraso - 1) / 30) AS INT) + 1 END AS faixa
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref IN (:fechamento_anterior, :fechamento)
),
-- INTERNAL só para fundo sem administrador na data (D55, D56).
com_administrador AS (
    SELECT DISTINCT data_ref, cnpj_classe FROM f0 WHERE source <> 'INTERNAL'
),
f AS (
    SELECT t.*
    FROM f0 t
    LEFT JOIN com_administrador c ON c.data_ref = t.data_ref AND c.cnpj_classe = t.cnpj_classe
    WHERE t.source <> 'INTERNAL' OR c.cnpj_classe IS NULL
),
a AS (SELECT * FROM f WHERE data_ref = :fechamento_anterior),
b AS (SELECT * FROM f WHERE data_ref = :fechamento),
fundos AS (
    SELECT source, cnpj_classe FROM a
    INTERSECT
    SELECT source, cnpj_classe FROM b
),
m AS (
    SELECT COALESCE(a.source, b.source) AS source,
           COALESCE(a.cnpj_classe, b.cnpj_classe) AS cnpj_classe,
           COALESCE(a.id_contrato_admin, b.id_contrato_admin) AS id_contrato_admin,
           COALESCE(a.faixa, -1) AS faixa_de,      -- -1 = novo
           COALESCE(b.faixa, 8) AS faixa_para,     --  8 = saiu
           a.vl_presente AS vp_inicio,
           b.vl_presente AS vp_fim
    FROM a
    FULL JOIN b ON b.source = a.source
               AND b.cnpj_classe = a.cnpj_classe
               AND b.id_contrato_admin = a.id_contrato_admin
),
d AS (
    SELECT cnpj_classe, num_controle, identificador, produto_id
    FROM plgn.dim_contrato
    WHERE cnpj_classe IN (SELECT cnpj_classe FROM fundos)
)
SELECT m.source AS admin,
       m.cnpj_classe AS fund_legal_id,
       COALESCE(d1.produto_id, d2.produto_id) AS product_id,   -- nulo = sem produto (D18)
       m.faixa_de,
       m.faixa_para,
       COUNT(*) AS contract_count,
       SUM(m.vp_inicio) AS pv_inicio,                          -- VP no fechamento anterior
       SUM(m.vp_fim) AS pv_fim                                 -- VP no fechamento atual
FROM m
JOIN fundos ON fundos.source = m.source AND fundos.cnpj_classe = m.cnpj_classe
LEFT JOIN d d1 ON d1.cnpj_classe = m.cnpj_classe AND d1.num_controle = m.id_contrato_admin
LEFT JOIN d d2 ON d2.cnpj_classe = m.cnpj_classe AND d2.identificador = m.id_contrato_admin
              AND d1.num_controle IS NULL
GROUP BY 1, 2, 3, 4, 5;
