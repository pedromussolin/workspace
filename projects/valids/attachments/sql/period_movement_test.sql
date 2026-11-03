-- Movimentação de UM fundo de 16/10 a 22/10/2026 (versão P1, 23/10), gerada por
-- attachments/generate_period_movement.py. Troque <fonte> e <cnpj> pelos do fundo.
-- Medido: semana de um fundo de 5,9 mi de parcelas em 5,9 s (a versão anterior
-- levava 24,3 s), mesmo resultado.
WITH fotos_seq AS (
    SELECT DATE '2026-10-15' AS foto, CAST(NULL AS DATE) AS anterior, DATE '2026-10-16' AS proxima
    UNION ALL SELECT DATE '2026-10-16', DATE '2026-10-15', DATE '2026-10-19'
    UNION ALL SELECT DATE '2026-10-19', DATE '2026-10-16', DATE '2026-10-20'
    UNION ALL SELECT DATE '2026-10-20', DATE '2026-10-19', DATE '2026-10-21'
    UNION ALL SELECT DATE '2026-10-21', DATE '2026-10-20', DATE '2026-10-22'
    UNION ALL SELECT DATE '2026-10-22', DATE '2026-10-21', CAST(NULL AS DATE)
),
limites AS (
    SELECT MIN(foto) AS primeira, MAX(foto) AS ultima, COUNT(*) AS dias
    FROM fotos_seq WHERE anterior IS NOT NULL
),
papeis AS (
    SELECT foto AS data_ref, proxima AS foto, 1 AS lado FROM fotos_seq WHERE proxima IS NOT NULL
    UNION ALL
    SELECT foto AS data_ref, foto, 2 AS lado FROM fotos_seq WHERE anterior IS NOT NULL
),
estoque AS (
    SELECT data_ref, FNV_HASH(id_parcela) AS k, vl_presente_parcela AS vp
    FROM plgn.administradores_estoque
    WHERE data_ref BETWEEN DATE '2026-10-15' AND DATE '2026-10-22'
      AND source = '<fonte>' AND cnpj_classe = '<cnpj>'
),
lados AS (
    SELECT p.foto, e.k,
           MAX(CASE WHEN p.lado = 1 THEN e.vp END) AS vp_anterior,
           MAX(CASE WHEN p.lado = 2 THEN e.vp END) AS vp_atual,
           MAX(CASE WHEN p.lado = 1 THEN 1 ELSE 0 END) AS na_anterior,
           MAX(CASE WHEN p.lado = 2 THEN 1 ELSE 0 END) AS na_atual
    FROM estoque e
    JOIN papeis p ON p.data_ref = e.data_ref
    GROUP BY 1, 2
),
pagamentos AS (
    SELECT data_ref, FNV_HASH(id_parcela) AS k,
           SUM(COALESCE(vl_pago, 0) * CASE
               WHEN tipo_movimento IN ('installment_payment_reversal', 'installment_partial_refund') THEN -1
               WHEN tipo_movimento IN ('installment_reactivation') THEN 0
               ELSE 1
           END) AS pago
    FROM plgn.administradores_liquidacao
    WHERE data_ref > DATE '2026-10-15' AND data_ref <= DATE '2026-10-22'
      AND source = '<fonte>' AND cnpj_classe = '<cnpj>'
    GROUP BY 1, 2
),
aquisicoes AS (
    SELECT data_ref, SUM(COALESCE(vl_aquisicao, 0)) AS aquisicoes
    FROM plgn.administradores_aquisicao
    WHERE data_ref > DATE '2026-10-15' AND data_ref <= DATE '2026-10-22'
      AND source = '<fonte>' AND cnpj_classe = '<cnpj>'
    GROUP BY 1
),
mapa AS (
    -- cada dia com movimento cai num intervalo (foto anterior, foto]
    SELECT d.data_ref, fs.foto
    FROM (SELECT data_ref FROM pagamentos UNION SELECT data_ref FROM aquisicoes) d
    JOIN fotos_seq fs ON d.data_ref > fs.anterior AND d.data_ref <= fs.foto
),
pago_foto AS (
    SELECT m.foto, p.k, SUM(p.pago) AS pago
    FROM pagamentos p JOIN mapa m ON m.data_ref = p.data_ref
    GROUP BY 1, 2
),
fluxos AS (
    SELECT
        (SELECT SUM(aquisicoes) FROM aquisicoes) AS acquisitions,
        (SELECT SUM(pago) FROM pagamentos) AS liquidations
),
totais AS (
    SELECT
        SUM(CASE WHEN l.foto = li.primeira THEN l.vp_anterior END) AS opening_balance,
        SUM(CASE WHEN l.foto = li.ultima THEN l.vp_atual END) AS closing_balance,
        SUM(CASE WHEN l.na_anterior = 1 AND l.na_atual = 1
                 THEN l.vp_atual - l.vp_anterior + COALESCE(pf.pago, 0) END) AS interest_accrual,
        SUM(CASE WHEN l.na_anterior = 1 AND l.na_atual = 1 THEN pf.pago END) AS paid_on_remaining,
        SUM(CASE WHEN l.na_anterior = 0 THEN l.vp_atual END) AS pv_entered,
        SUM(CASE WHEN l.na_atual = 0 THEN l.vp_anterior END) AS pv_exited
    FROM lados l
    CROSS JOIN limites li
    LEFT JOIN pago_foto pf ON pf.foto = l.foto AND pf.k = l.k
)
SELECT li.primeira, li.ultima, li.dias,
       t.opening_balance, f.acquisitions, f.liquidations, t.interest_accrual, t.closing_balance,
       t.opening_balance + f.acquisitions - f.liquidations + t.interest_accrual AS calculated_closing_balance,
       t.closing_balance - (t.opening_balance + f.acquisitions - f.liquidations + t.interest_accrual) AS difference,
       t.pv_entered - f.acquisitions AS difference_on_entries,
       f.liquidations - t.paid_on_remaining - t.pv_exited AS difference_on_exits
FROM totais t CROSS JOIN fluxos f CROSS JOIN limites li