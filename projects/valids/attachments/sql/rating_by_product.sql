-- Abertura de Rating por fundo, produto e rating do administrador (faixa_pdd)
-- numa data de referência (proposta, 22/10/2026; D17).
--
-- - Rating = faixa_pdd do administrador ("visão do cliente"). O rating de
--   dim_contrato é outro (o da originação) e não entra.
-- - Produto = dim_contrato.produto_id, pelo mesmo fundo (cnpj_classe) e por
--   num_controle; se não casar, por identificador. Sem casamento: produto nulo.
-- - PDD vem negativo na view: a consulta devolve o módulo.
-- - Validada inteira para um fundo (Genius E, 30/09/2026, ~11 s): soma do VP
--   igual à do estoque do fundo, sem linha duplicada.
--
-- Parâmetros: :data_ref; :fund_cnpj opcional (na consolidação, todos os fundos).
-- 27/10/2026: fundo só-INTERNAL entra (D56); a INTERNAL traz faixa_pdd e
-- dias_atraso (confirmado pelo Heitor).

WITH base AS (
    SELECT source, cnpj_classe, id_contrato_admin, faixa_pdd, dias_atraso, vl_presente, vl_pdd
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :data_ref
      AND (:fund_cnpj IS NULL OR cnpj_classe = :fund_cnpj)
),
-- INTERNAL só para fundo sem dado de administrador na data (D55, D56).
com_administrador AS (
    SELECT DISTINCT cnpj_classe FROM base WHERE source <> 'INTERNAL'
),
e AS (
    SELECT b.*
    FROM base b
    LEFT JOIN com_administrador a ON a.cnpj_classe = b.cnpj_classe
    WHERE b.source <> 'INTERNAL' OR a.cnpj_classe IS NULL
),
d AS (
    SELECT cnpj_classe, num_controle, identificador, produto_id
    FROM plgn.dim_contrato
    WHERE cnpj_classe IN (SELECT DISTINCT cnpj_classe FROM e)
)
SELECT e.source AS admin,
       e.cnpj_classe AS fund_legal_id,
       COALESCE(d1.produto_id, d2.produto_id) AS product_id,
       e.faixa_pdd AS rating,
       COUNT(*) AS contract_count,
       MIN(e.dias_atraso) AS aging_min,
       MAX(e.dias_atraso) AS aging_max,
       SUM(e.vl_presente) AS pv,
       -SUM(e.vl_pdd) AS pdd
FROM e
LEFT JOIN d d1 ON d1.cnpj_classe = e.cnpj_classe AND d1.num_controle = e.id_contrato_admin
LEFT JOIN d d2 ON d2.cnpj_classe = e.cnpj_classe AND d2.identificador = e.id_contrato_admin
              AND d1.num_controle IS NULL
GROUP BY 1, 2, 3, 4;
