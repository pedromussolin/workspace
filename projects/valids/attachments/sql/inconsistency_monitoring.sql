-- Monitoramento de Inconsistências (tarefa 04): consultas de viabilidade de
-- 27/10/2026. Só leitura, sempre filtradas por data_ref (sortkey).
--
-- Parâmetros: :dia (foto), :dia_anterior (foto anterior), :inicio e :fim
-- (período da liquidação), :fonte (valor de `source`, ver privado.md),
-- :final_cnpj (6 últimos dígitos do cnpj_classe, ver privado.md),
-- :fontes_taxa_percentual (fontes cuja taxa vem em %, ver privado.md).
--
-- Custo medido em 27/10 (com a conexão): 1 e 2 ~5–10 s (foto inteira,
-- agregada); 3 de 2 a 6 s num fundo pequeno, **57 s no BGT A** (1,1 mi de
-- parcelas: as janelas ordenam o fundo inteiro; não rodar em fundo grande);
-- 4 de 6 a 8 s; 5 ~6 s; 6 ~4 s; 7 ~11 s; 8 ~3 s; 9 ~7 s.

-- 1. Análise Residual: preenchimento das colunas e parcelas com valor nominal
--    abaixo do valor de aquisição, por administrador, numa foto.
SELECT source,
       COUNT(*) AS parcelas,
       SUM(CASE WHEN num_parcela IS NULL THEN 1 ELSE 0 END) AS sem_num,
       SUM(CASE WHEN vl_nominal_parcela IS NULL THEN 1 ELSE 0 END) AS sem_nominal,
       SUM(CASE WHEN vl_aquisicao_parcela IS NULL THEN 1 ELSE 0 END) AS aquis_nula,
       SUM(CASE WHEN vl_aquisicao_parcela = 0 THEN 1 ELSE 0 END) AS aquis_zero,
       SUM(CASE WHEN vl_nominal_parcela < vl_aquisicao_parcela THEN 1 ELSE 0 END) AS nom_lt_aq,
       ROUND(SUM(CASE WHEN vl_nominal_parcela < vl_aquisicao_parcela THEN vl_presente_parcela END) / 1e6, 2) AS vp_nom_lt_aq,
       ROUND(SUM(vl_presente_parcela) / 1e6, 2) AS vp,
       ROUND(SUM(vl_nominal_parcela) / 1e6, 2) AS nominal,
       ROUND(SUM(vl_aquisicao_parcela) / 1e6, 2) AS aquis
FROM plgn.administradores_estoque
WHERE data_ref = :dia
GROUP BY 1
ORDER BY 1;

-- 2. Análise Residual: faixas de 10% de nominal ÷ aquisição (as do protótipo,
--    `nomChart`), por administrador. Faixa -1 = nominal zero ou negativo.
WITH p AS (
    SELECT source, flag_vencido, vl_presente_parcela AS vp,
           CASE WHEN vl_nominal_parcela <= 0 THEN -1
                ELSE LEAST(9, FLOOR(10 * vl_nominal_parcela / vl_aquisicao_parcela))::int END AS faixa
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia
      AND vl_aquisicao_parcela > 0
      AND vl_nominal_parcela < vl_aquisicao_parcela
)
SELECT source, faixa,
       COUNT(*) AS parcelas,
       SUM(CASE WHEN flag_vencido = 1 THEN 1 ELSE 0 END) AS vencidas,
       ROUND(SUM(vp) / 1e6, 2) AS vp
FROM p
GROUP BY 1, 2
ORDER BY 1, 2;

-- 3. Análise Residual por fundo de um administrador, com a razão
--    aquisição ÷ nominal do fundo inteiro.
SELECT RIGHT(cnpj_classe, 6) AS final_cnpj,
       ROUND(SUM(vl_presente_parcela) / 1e6, 2) AS vp_fundo,
       COUNT(*) AS parcelas,
       SUM(CASE WHEN vl_nominal_parcela < vl_aquisicao_parcela THEN 1 ELSE 0 END) AS nom_lt_aq,
       ROUND(SUM(CASE WHEN vl_nominal_parcela < vl_aquisicao_parcela THEN vl_presente_parcela END) / 1e6, 2) AS vp_nom_lt_aq,
       ROUND(SUM(vl_aquisicao_parcela) / NULLIF(SUM(vl_nominal_parcela), 0), 3) AS aquis_sobre_nominal
FROM plgn.administradores_estoque
WHERE data_ref = :dia AND source = :fonte
GROUP BY 1
ORDER BY 2 DESC;

-- 4. Lacunas de Parcelas (D39), só pela sequência do estoque, num fundo:
--    parcela com 2+ meses de atraso e alguma parcela de número maior que
--    falta no estoque, entre ela e a última em estoque. PESADA em fundo
--    grande (janelas): 57 s no BGT A.
WITH p AS (
    SELECT cnpj_classe, id_contrato_admin, num_parcela,
           vl_presente_parcela AS vp, vl_pdd_parcela AS pdd,
           CASE WHEN data_vcto_original <= DATEADD(month, -2, :dia) THEN 1 ELSE 0 END AS atraso_2m
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
      AND num_parcela IS NOT NULL
),
w AS (
    SELECT p.*,
           COUNT(*) OVER (PARTITION BY cnpj_classe, id_contrato_admin ORDER BY num_parcela
                          ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING) AS depois_no_estoque,
           MAX(num_parcela) OVER (PARTITION BY cnpj_classe, id_contrato_admin) AS mx
    FROM p
)
SELECT COUNT(DISTINCT id_contrato_admin) AS contratos,
       COUNT(*) AS parcelas,
       SUM(atraso_2m) AS atraso_2m,
       SUM(CASE WHEN atraso_2m = 1 AND num_parcela = mx THEN 1 ELSE 0 END) AS atraso_2m_ultima_no_estoque,
       SUM(CASE WHEN atraso_2m = 1 AND COALESCE(depois_no_estoque, 0) < mx - num_parcela THEN 1 ELSE 0 END) AS candidatas,
       COUNT(DISTINCT CASE WHEN atraso_2m = 1 AND COALESCE(depois_no_estoque, 0) < mx - num_parcela THEN id_contrato_admin END) AS contratos_candidatos,
       ROUND(SUM(CASE WHEN atraso_2m = 1 AND COALESCE(depois_no_estoque, 0) < mx - num_parcela THEN vp END) / 1e6, 3) AS vp,
       ROUND(SUM(CASE WHEN atraso_2m = 1 AND COALESCE(depois_no_estoque, 0) < mx - num_parcela THEN pdd END) / 1e6, 3) AS pdd
FROM w;

-- 5. Lacunas: o `qt_parcelas_pagas` da view por contrato dá o total de
--    parcelas do contrato? (resposta de 27/10: não; é a primeira parcela em
--    estoque − 1).
WITH c AS (
    SELECT cnpj_classe, id_contrato_admin, COUNT(*) AS n, MIN(num_parcela) AS mn, MAX(num_parcela) AS mx
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
      AND num_parcela IS NOT NULL
    GROUP BY 1, 2
),
k AS (
    SELECT cnpj_classe, id_contrato_admin, qt_parcelas_pagas
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
)
SELECT COUNT(*) AS contratos,
       SUM(CASE WHEN c.n + k.qt_parcelas_pagas = c.mx THEN 1 ELSE 0 END) AS estoque_mais_pagas_igual_ultima,
       SUM(CASE WHEN c.n + k.qt_parcelas_pagas > c.mx THEN 1 ELSE 0 END) AS estoque_mais_pagas_maior,
       SUM(CASE WHEN c.n + k.qt_parcelas_pagas < c.mx THEN 1 ELSE 0 END) AS estoque_mais_pagas_menor,
       SUM(CASE WHEN c.mn - 1 = k.qt_parcelas_pagas THEN 1 ELSE 0 END) AS pagas_igual_primeira_menos_1
FROM c LEFT JOIN k ON k.cnpj_classe = c.cnpj_classe AND k.id_contrato_admin = c.id_contrato_admin;

-- 6. Lacunas: parcela posterior liquidada no período enquanto uma anterior
--    tem 2+ meses de atraso. Separa a parcela paga dentro do intervalo do
--    estoque (lacuna visível na foto) e depois da última em estoque (só a
--    liquidação mostra). Sem janela: leve.
WITH e AS (
    SELECT cnpj_classe, id_contrato_admin,
           MIN(CASE WHEN data_vcto_original <= DATEADD(month, -2, :dia) THEN num_parcela END) AS menor_atraso_2m,
           MIN(num_parcela) AS mn, MAX(num_parcela) AS mx, COUNT(*) AS n
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
      AND num_parcela IS NOT NULL
    GROUP BY 1, 2
),
l AS (
    SELECT cnpj_classe, id_contrato_admin, num_parcela, tipo_movimento, vl_pago
    FROM plgn.administradores_liquidacao
    WHERE data_ref BETWEEN :inicio AND :fim AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
)
SELECT l.tipo_movimento,
       COUNT(*) AS linhas,
       COUNT(DISTINCT e.id_contrato_admin) AS contratos,
       SUM(CASE WHEN l.num_parcela BETWEEN e.mn AND e.mx THEN 1 ELSE 0 END) AS dentro_do_estoque,
       SUM(CASE WHEN l.num_parcela > e.mx THEN 1 ELSE 0 END) AS depois_da_ultima_no_estoque,
       COUNT(DISTINCT CASE WHEN l.num_parcela > e.mx THEN e.id_contrato_admin END) AS contratos_depois_da_ultima,
       ROUND(SUM(l.vl_pago), 0) AS pago
FROM e
JOIN l ON l.cnpj_classe = e.cnpj_classe AND l.id_contrato_admin = e.id_contrato_admin
     AND l.num_parcela > e.menor_atraso_2m
GROUP BY 1
ORDER BY 2 DESC;

-- 7. Performance de Pagamento: escada de um dia num fundo. "Baixado" = VP na
--    foto anterior das parcelas que saíram do estoque, pela distância entre
--    o dia e o vencimento original; "liquidado" = vl_pago, pela distância
--    entre pagamento e vencimento. Faixas do protótipo (`ESC_LAB`).
WITH ant AS (
    SELECT id_parcela, vl_presente_parcela AS vp, data_vcto_original
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia_anterior AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
),
atu AS (
    SELECT id_parcela
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
),
u AS (
    SELECT 'baixado' AS serie, a.vp AS v, DATEDIFF(day, a.data_vcto_original, :dia) AS d
    FROM ant a LEFT JOIN atu b ON b.id_parcela = a.id_parcela
    WHERE b.id_parcela IS NULL
    UNION ALL
    SELECT 'liquidado', vl_pago, DATEDIFF(day, data_vcto, data_pagamento)
    FROM plgn.administradores_liquidacao
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
)
SELECT serie,
       CASE WHEN d < -60 THEN 0 WHEN d <= -31 THEN 1 WHEN d <= -16 THEN 2 WHEN d <= -1 THEN 3
            WHEN d = 0 THEN 4 WHEN d <= 15 THEN 5 WHEN d <= 30 THEN 6 WHEN d <= 60 THEN 7
            WHEN d <= 90 THEN 8 WHEN d > 90 THEN 9 END AS faixa,
       COUNT(*) AS n,
       ROUND(SUM(v)) AS valor
FROM u
GROUP BY 1, 2
ORDER BY 1, 2;

-- 8. Performance de Pagamento: escada do valor liquidado num período, por
--    administrador, com o preenchimento das chaves.
WITH l AS (
    SELECT source, vl_pago, id_parcela, num_parcela, data_vcto, vl_presente,
           DATEDIFF(day, data_vcto, data_pagamento) AS d
    FROM plgn.administradores_liquidacao
    WHERE data_ref BETWEEN :inicio AND :fim
)
SELECT source,
       CASE WHEN d < -60 THEN 0 WHEN d <= -31 THEN 1 WHEN d <= -16 THEN 2 WHEN d <= -1 THEN 3
            WHEN d = 0 THEN 4 WHEN d <= 15 THEN 5 WHEN d <= 30 THEN 6 WHEN d <= 60 THEN 7
            WHEN d <= 90 THEN 8 WHEN d > 90 THEN 9 END AS faixa,
       COUNT(*) AS linhas,
       SUM(CASE WHEN id_parcela IS NULL THEN 1 ELSE 0 END) AS sem_id_parcela,
       SUM(CASE WHEN vl_presente IS NOT NULL AND vl_presente <> 0 THEN 1 ELSE 0 END) AS com_vp,
       ROUND(SUM(vl_pago) / 1e6, 2) AS pago
FROM l
GROUP BY 1, 2
ORDER BY 1, 2;

-- 9. Performance de Pagamento: taxa média ponderada pelo VP das parcelas a
--    vencer, com a regra do protótipo (`metricasFor`): taxa em fração a.a.
--    e fora de 0–500% a.a. descartada.
WITH p AS (
    SELECT source, vl_presente_parcela AS vp,
           taxa_recebivel * CASE WHEN source IN (:fontes_taxa_percentual) THEN 0.01 ELSE 1 END AS taxa
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia AND flag_vencido = 0
)
SELECT source,
       ROUND(SUM(vp) / 1e6, 2) AS vp_a_vencer,
       ROUND(SUM(CASE WHEN taxa IS NULL THEN vp END) / 1e6, 2) AS vp_sem_taxa,
       ROUND(SUM(CASE WHEN taxa < 0 OR taxa > 5 THEN vp END) / 1e6, 2) AS vp_taxa_fora,
       ROUND(SUM(CASE WHEN taxa BETWEEN 0 AND 5 THEN taxa * vp END)
           / NULLIF(SUM(CASE WHEN taxa BETWEEN 0 AND 5 THEN vp END), 0), 4) AS taxa_media_pond
FROM p
GROUP BY 1
ORDER BY 1;

-- 10. Lacunas: o que os campos da view por contrato guardam, contra a foto por
--     parcela do mesmo dia (resposta de 29/10: tudo sai das parcelas em aberto).
WITH p AS (
    SELECT cnpj_classe, id_contrato_admin,
           MIN(num_parcela) AS mn, MAX(data_vcto_original) AS vcto_max,
           SUM(CASE WHEN flag_vencido = 1 THEN 1 ELSE 0 END) AS vencidas,
           MIN(CASE WHEN flag_vencido = 1 THEN data_vcto_original END) AS vcto_min_vencida
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
      AND num_parcela IS NOT NULL
    GROUP BY 1, 2
),
c AS (
    SELECT cnpj_classe, id_contrato_admin, qt_parcelas_pagas, qt_parcelas_vencidas, num_parcela_vigente,
           data_vcto_original, dias_atraso, prazo_original_contrato, prazo_contrato, data_cessao
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
)
SELECT COUNT(*) AS contratos,
       SUM(CASE WHEN c.qt_parcelas_pagas = p.mn - 1 THEN 1 ELSE 0 END) AS pagas_igual_primeira_menos_1,
       SUM(CASE WHEN c.qt_parcelas_vencidas = p.vencidas THEN 1 ELSE 0 END) AS vencidas_igual_vencidas_em_aberto,
       SUM(CASE WHEN c.num_parcela_vigente = p.mn THEN 1 ELSE 0 END) AS vigente_igual_primeira,
       SUM(CASE WHEN c.num_parcela_vigente IS NULL THEN 1 ELSE 0 END) AS vigente_nulo,
       SUM(CASE WHEN c.data_vcto_original = p.vcto_max THEN 1 ELSE 0 END) AS vcto_igual_ultima_em_aberto,
       SUM(CASE WHEN c.dias_atraso = DATEDIFF(day, p.vcto_min_vencida, :dia) THEN 1 ELSE 0 END) AS atraso_exato,
       SUM(CASE WHEN c.dias_atraso - DATEDIFF(day, p.vcto_min_vencida, :dia) BETWEEN -4 AND -1 THEN 1 ELSE 0 END) AS atraso_1_a_4_dias_menor,
       SUM(CASE WHEN c.prazo_original_contrato = DATEDIFF(day, c.data_cessao, p.vcto_max) THEN 1 ELSE 0 END) AS prazo_orig_cessao_ate_ultima,
       SUM(CASE WHEN c.prazo_contrato = DATEDIFF(day, :dia, p.vcto_max) THEN 1 ELSE 0 END) AS prazo_hoje_ate_ultima
FROM c
JOIN p ON p.cnpj_classe = c.cnpj_classe AND p.id_contrato_admin = c.id_contrato_admin;

-- 11. Lacunas só pela view por contrato: a vencida mais antiga (dias_atraso,
--     alinhada ao dia de vencimento do contrato pelo data_vcto_original) e as
--     vencidas esperadas até a última em aberto ou até o dia, se as parcelas
--     forem mensais. Menos vencidas em aberto que esperadas = parcela posterior
--     já vencida saiu do estoque. Comparada com a lacuna na foto por parcela.
WITH p AS (
    SELECT cnpj_classe, id_contrato_admin,
           COUNT(DISTINCT num_parcela) AS nd, MIN(num_parcela) AS mn, MAX(num_parcela) AS mx,
           MAX(CASE WHEN DATEDIFF(day, data_vcto_original, :dia) >= 60 THEN 1 ELSE 0 END) AS tem_candidata,
           CASE WHEN DATEDIFF(month, MIN(data_vcto_original), MAX(data_vcto_original)) = MAX(num_parcela) - MIN(num_parcela) THEN 1 ELSE 0 END AS mensal
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
      AND num_parcela IS NOT NULL
    GROUP BY 1, 2
),
c0 AS (
    SELECT cnpj_classe, id_contrato_admin, qt_parcelas_vencidas, data_vcto_original,
           ROUND(DATEDIFF(day, DATEADD(day, -dias_atraso, :dia), data_vcto_original) / 30.44) AS meses_ate_ultima
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
      AND dias_atraso IS NOT NULL
),
c1 AS (
    SELECT c0.*, DATEADD(month, -CAST(meses_ate_ultima AS INT), data_vcto_original) AS vcto_mais_antiga
    FROM c0
),
c AS (
    SELECT c1.*,
           CASE WHEN data_vcto_original < :dia THEN meses_ate_ultima + 1
                ELSE DATEDIFF(month, vcto_mais_antiga, :dia)
                     + CASE WHEN DATEADD(month, DATEDIFF(month, vcto_mais_antiga, :dia), vcto_mais_antiga) < :dia THEN 1 ELSE 0 END
           END AS vencidas_esperadas
    FROM c1
)
SELECT p.tem_candidata, p.mensal,
       CASE WHEN p.mx - p.mn + 1 > p.nd THEN 1 ELSE 0 END AS lacuna_foto,
       CASE WHEN DATEDIFF(day, c.vcto_mais_antiga, :dia) >= 60
             AND c.qt_parcelas_vencidas < c.vencidas_esperadas THEN 1 ELSE 0 END AS regra_contrato,
       COUNT(*) AS contratos
FROM p
LEFT JOIN c ON c.cnpj_classe = p.cnpj_classe AND c.id_contrato_admin = p.id_contrato_admin
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 2 DESC, 3 DESC, 4 DESC;

-- 12. Lacunas: contrato sem lacuna na foto cuja última parcela em estoque é
--     menor que a de uma foto anterior (parcelas posteriores saíram), contra a
--     liquidação do mesmo intervalo (parcela de número maior liquidada).
WITH e AS (
    SELECT cnpj_classe, id_contrato_admin,
           COUNT(DISTINCT num_parcela) AS nd, MIN(num_parcela) AS mn, MAX(num_parcela) AS mx,
           MAX(CASE WHEN DATEDIFF(day, data_vcto_original, :dia) >= 60 THEN 1 ELSE 0 END) AS tem_candidata
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
      AND num_parcela IS NOT NULL
    GROUP BY 1, 2
),
o AS (
    SELECT cnpj_classe, id_contrato_admin, MAX(num_parcela) AS mx_antes
    FROM plgn.administradores_estoque
    WHERE data_ref = :dia_anterior AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
      AND num_parcela IS NOT NULL
    GROUP BY 1, 2
),
l AS (
    SELECT cnpj_classe, id_contrato_admin, MAX(num_parcela) AS mx_liquidada
    FROM plgn.administradores_liquidacao
    WHERE data_ref BETWEEN :inicio AND :fim AND source = :fonte AND RIGHT(cnpj_classe, 6) = :final_cnpj
      AND num_parcela IS NOT NULL
    GROUP BY 1, 2
)
SELECT SUM(CASE WHEN e.mx - e.mn + 1 = e.nd THEN 1 ELSE 0 END) AS sem_lacuna_na_foto,
       SUM(CASE WHEN e.mx - e.mn + 1 = e.nd AND o.mx_antes IS NULL THEN 1 ELSE 0 END) AS fora_da_foto_anterior,
       SUM(CASE WHEN e.mx - e.mn + 1 = e.nd AND o.mx_antes > e.mx THEN 1 ELSE 0 END) AS saiu_parcela_posterior,
       SUM(CASE WHEN e.mx - e.mn + 1 = e.nd AND l.mx_liquidada > e.mx THEN 1 ELSE 0 END) AS liquidou_parcela_posterior,
       SUM(CASE WHEN e.mx - e.mn + 1 = e.nd AND o.mx_antes > e.mx AND l.mx_liquidada > e.mx THEN 1 ELSE 0 END) AS as_duas
FROM e
LEFT JOIN o ON o.cnpj_classe = e.cnpj_classe AND o.id_contrato_admin = e.id_contrato_admin
LEFT JOIN l ON l.cnpj_classe = e.cnpj_classe AND l.id_contrato_admin = e.id_contrato_admin
WHERE e.tem_candidata = 1;

-- 13. Performance de Pagamento: a fórmula do time de dados
--     (vl_pago = vl_vencimento + vl_juros − vl_ajuste) num arquivo de liquidação,
--     por administrador e momento do pagamento.
SELECT source,
       CASE WHEN data_vcto IS NULL OR data_pagamento IS NULL THEN 'sem data'
            WHEN data_pagamento < data_vcto THEN '1 antes'
            WHEN data_pagamento = data_vcto THEN '2 no dia'
            ELSE '3 depois' END AS momento,
       COUNT(*) AS linhas,
       SUM(CASE WHEN vl_vencimento IS NULL THEN 1 ELSE 0 END) AS venc_nulo,
       SUM(CASE WHEN vl_juros IS NULL THEN 1 ELSE 0 END) AS juros_nulo,
       SUM(CASE WHEN vl_ajuste IS NULL THEN 1 ELSE 0 END) AS ajuste_nulo,
       SUM(CASE WHEN ABS(vl_pago - (COALESCE(vl_vencimento, 0) + COALESCE(vl_juros, 0) - COALESCE(vl_ajuste, 0))) < 0.01 THEN 1 ELSE 0 END) AS formula_fecha,
       ROUND(SUM(vl_pago) / 1e3, 1) AS pago_mil,
       ROUND(SUM(vl_vencimento) / 1e3, 1) AS vencimento_mil,
       ROUND(SUM(vl_juros) / 1e3, 1) AS juros_mil,
       ROUND(SUM(vl_ajuste) / 1e3, 1) AS ajuste_mil,
       ROUND(SUM(vl_nominal) / 1e3, 1) AS nominal_mil
FROM plgn.administradores_liquidacao
WHERE data_ref = :dia
GROUP BY 1, 2
ORDER BY 1, 2;

-- 14. A mesma fórmula por tipo de movimento: onde o pago fica abaixo ou acima.
SELECT source, tipo_movimento,
       CASE WHEN data_vcto IS NULL OR data_pagamento IS NULL THEN 'sem data'
            WHEN data_pagamento < data_vcto THEN '1 antes'
            WHEN data_pagamento = data_vcto THEN '2 no dia'
            ELSE '3 depois' END AS momento,
       COUNT(*) AS linhas,
       SUM(CASE WHEN ABS(vl_pago - (COALESCE(vl_vencimento, 0) + COALESCE(vl_juros, 0) - COALESCE(vl_ajuste, 0))) < 0.01 THEN 1 ELSE 0 END) AS fecha,
       SUM(CASE WHEN vl_pago < COALESCE(vl_vencimento, 0) + COALESCE(vl_juros, 0) - COALESCE(vl_ajuste, 0) - 0.01 THEN 1 ELSE 0 END) AS pago_menor,
       SUM(CASE WHEN vl_pago > COALESCE(vl_vencimento, 0) + COALESCE(vl_juros, 0) - COALESCE(vl_ajuste, 0) + 0.01 THEN 1 ELSE 0 END) AS pago_maior,
       ROUND(SUM(vl_pago) / 1e3, 1) AS pago_mil,
       ROUND(SUM(vl_vencimento) / 1e3, 1) AS vencimento_mil
FROM plgn.administradores_liquidacao
WHERE data_ref = :dia
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
