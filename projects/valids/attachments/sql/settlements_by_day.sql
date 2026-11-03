-- Baixas por administrador, fundo, dia e tipo de movimento (D3, D5, D6).
-- Valor = vl_pago. O sinal de cada tipo (baixa, estorno, ignorar) é aplicado
-- depois, pelo mapa no código (D5); por isso o tipo sai separado.
-- Observação (D3): o estoque é medido a VP; vl_pago diferente do VP da
-- parcela na saída aparece como diferença entre saldo calculado e estoque real.
SELECT
    l.source AS admin,
    l.cnpj_classe AS fund_legal_id,
    l.data_ref AS reference_date,
    l.tipo_movimento AS movement_type,
    COUNT(*) AS liquidations_count,
    SUM(COALESCE(l.vl_pago, 0)) AS paid_amount
FROM plgn.administradores_liquidacao l
WHERE l.data_ref BETWEEN :start_date AND :end_date
GROUP BY 1, 2, 3, 4;
