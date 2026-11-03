-- Aquisições por administrador, fundo e dia (D2, D6).
-- Filtra por data_ref (sortkey). Em todas as linhas vistas em 21/10/2026,
-- data_ref = data_aquisicao. Qualquer período é a soma dos dias.
SELECT
    a.source AS admin,
    a.cnpj_classe AS fund_legal_id,
    a.data_ref AS reference_date,
    COUNT(*) AS acquisitions_count,
    SUM(COALESCE(a.vl_aquisicao, 0)) AS acquisitions_amount
FROM plgn.administradores_aquisicao a
WHERE a.data_ref BETWEEN :start_date AND :end_date
GROUP BY 1, 2, 3;
