-- SUBSTITUÍDA em 26/10/2026 (D34): a consolidação passou a ser por fundo e usa
-- a consulta de período com uma linha por dia
-- (data-lake-api, src/infra/redshift/queries/plgn/valid.py,
-- fund_stock_movement_query). Fica aqui como referência da versão de todos os
-- fundos num intervalo.
--
-- Movimentação do estoque de UM intervalo entre duas fotos, por fundo (D15).
-- Mesma consulta da data-lake-api (`GET_STOCK_MOVEMENT`), otimizada em 23/10:
-- a parcela é identificada por um número de 64 bits (FNV_HASH de fonte, CNPJ e
-- id_parcela) no lugar dos três textos, e a presença em cada foto vem de
-- marcadores. Medido com o mesmo resultado: fundo de 15,6 mi de parcelas,
-- 14,9 s -> 7,7 s; fundo de 5,9 mi, 6,9 s -> 5,9 s.
--
-- Intervalo = (:foto_anterior, :foto]; intervalo de dia (D23). Encadeando os
-- intervalos, o estoque real de um é o saldo inicial do seguinte.
--
-- Accrual = variação de VP das parcelas presentes nas duas fotos + pagamentos
-- dessas parcelas no intervalo (o pagamento parcial reduz o VP; sem somar de
-- volta, ele sairia duas vezes: no VP e na baixa).
--
-- Sinal das baixas (D5): o mapa fica no código e entra por parâmetro. Para
-- testar um fundo só, acrescente `AND source = '<fonte>' AND cnpj_classe =
-- '<cnpj>'` nos quatro WHERE.
WITH anterior AS (
    SELECT FNV_HASH(id_parcela, FNV_HASH(cnpj_classe, FNV_HASH(source))) AS k,
           source, cnpj_classe, vl_presente_parcela AS vp
    FROM plgn.administradores_estoque
    WHERE data_ref = :foto_anterior
),
atual AS (
    SELECT FNV_HASH(id_parcela, FNV_HASH(cnpj_classe, FNV_HASH(source))) AS k,
           source, cnpj_classe, vl_presente_parcela AS vp
    FROM plgn.administradores_estoque
    WHERE data_ref = :foto
),
pagamentos AS (
    SELECT
        FNV_HASH(id_parcela, FNV_HASH(cnpj_classe, FNV_HASH(source))) AS k,
        source,
        cnpj_classe,
        SUM(COALESCE(vl_pago, 0) * CASE
            WHEN tipo_movimento IN (:tipos_estorno) THEN -1
            WHEN tipo_movimento IN (:tipos_ignorados) THEN 0
            ELSE 1
        END) AS pago
    FROM plgn.administradores_liquidacao
    WHERE data_ref > :foto_anterior AND data_ref <= :foto
    GROUP BY 1, 2, 3
),
aquisicoes AS (
    SELECT source, cnpj_classe, SUM(COALESCE(vl_aquisicao, 0)) AS aquisicoes
    FROM plgn.administradores_aquisicao
    WHERE data_ref > :foto_anterior AND data_ref <= :foto
    GROUP BY 1, 2
),
baixas AS (
    SELECT source, cnpj_classe, SUM(pago) AS baixas
    FROM pagamentos
    GROUP BY 1, 2
),
parcelas AS (
    SELECT
        COALESCE(a.source, p.source) AS source,
        COALESCE(a.cnpj_classe, p.cnpj_classe) AS cnpj_classe,
        COALESCE(a.k, p.k) AS k,
        p.vp AS vp_anterior,
        a.vp AS vp_atual,
        CASE WHEN p.k IS NOT NULL THEN 1 ELSE 0 END AS na_anterior,
        CASE WHEN a.k IS NOT NULL THEN 1 ELSE 0 END AS na_atual
    FROM atual a
    FULL JOIN anterior p ON p.k = a.k
),
movimento AS (
    SELECT
        x.source,
        x.cnpj_classe,
        SUM(x.vp_anterior) AS saldo_inicial,
        SUM(x.vp_atual) AS estoque_real,
        SUM(CASE WHEN x.na_anterior = 1 AND x.na_atual = 1
                 THEN x.vp_atual - x.vp_anterior + COALESCE(pg.pago, 0)
            END) AS accrual,
        SUM(CASE WHEN x.na_anterior = 1 AND x.na_atual = 1
                 THEN pg.pago END) AS pago_parcelas_que_ficaram,
        SUM(CASE WHEN x.na_anterior = 0 THEN x.vp_atual END) AS vp_entradas,
        SUM(CASE WHEN x.na_atual = 0 THEN x.vp_anterior END) AS vp_saidas
    FROM parcelas x
    LEFT JOIN pagamentos pg ON pg.k = x.k
    GROUP BY 1, 2
)
SELECT
    COALESCE(m.source, q.source, b.source) AS source,
    COALESCE(m.cnpj_classe, q.cnpj_classe, b.cnpj_classe) AS fund_legal_id,
    COALESCE(m.saldo_inicial, 0) AS opening_balance,
    COALESCE(q.aquisicoes, 0) AS acquisitions,
    COALESCE(b.baixas, 0) AS liquidations,
    COALESCE(m.accrual, 0) AS interest_accrual,
    COALESCE(m.estoque_real, 0) AS closing_balance,
    COALESCE(m.pago_parcelas_que_ficaram, 0) AS paid_on_remaining,
    COALESCE(m.vp_entradas, 0) AS pv_entered,
    COALESCE(m.vp_saidas, 0) AS pv_exited
FROM movimento m
FULL JOIN aquisicoes q
    ON q.source = m.source AND q.cnpj_classe = m.cnpj_classe
FULL JOIN baixas b
    ON b.source = COALESCE(m.source, q.source)
   AND b.cnpj_classe = COALESCE(m.cnpj_classe, q.cnpj_classe);
