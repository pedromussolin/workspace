-- Análise de Migração: comportamento de pagamento num mês (bloco "Série
-- histórica" do protótipo), sobre o valor pago (D21, opção a). Leve: um mês
-- de liquidação filtrado por data_ref. data_pagamento = data_ref em todas as
-- linhas de set/26. Falta aplicar o mapa de sinal por tipo de movimento (D5).
--
-- Parâmetros: :inicio, :fim (um mês).

SELECT source AS admin,
       cnpj_classe AS fund_legal_id,
       COUNT(*) AS n,
       SUM(CASE WHEN data_vcto IS NULL THEN 1 ELSE 0 END) AS sem_vencimento,
       SUM(vl_pago) AS pago,
       SUM(CASE WHEN data_pagamento <= data_vcto THEN vl_pago ELSE 0 END) AS pago_em_dia,
       SUM(CASE WHEN data_pagamento > data_vcto + 30 THEN vl_pago ELSE 0 END) AS pago_apos_30d
FROM plgn.administradores_liquidacao
WHERE data_ref BETWEEN :inicio AND :fim
GROUP BY 1, 2;
