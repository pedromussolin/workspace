-- Conferência por parcela entre dois fechamentos de UM fundo (validação, não
-- vai para a rota). Usada em 21/10/2026 para validar a D4 e para investigar
-- fundo cuja conferência passe de 1%.
-- Separa as parcelas em: ficaram a vencer, venceram no período, já vencidas,
-- saíram, entraram. Compara a variação real do VP com o taxa × prazo.
-- :du_periodo / :dc_periodo = dias úteis e corridos entre as duas fotos.
WITH t0 AS (
    SELECT
        id_parcela,
        vl_presente_parcela AS vp,
        prazo_du,
        prazo_dc,
        flag_vencido,
        COALESCE(metodo_taxa_recebivel, metodo_taxa_cessao) AS metodo,
        CASE
            WHEN source IN (:fontes_taxa_percentual) THEN COALESCE(taxa_recebivel, taxa_cessao) / 100.0
            ELSE COALESCE(taxa_recebivel, taxa_cessao)
        END AS taxa
    FROM plgn.administradores_estoque
    WHERE data_ref = :fechamento_anterior
      AND source = :admin
      AND cnpj_classe = :cnpj_classe
),
t1 AS (
    SELECT id_parcela, vl_presente_parcela AS vp, flag_vencido
    FROM plgn.administradores_estoque
    WHERE data_ref = :fechamento
      AND source = :admin
      AND cnpj_classe = :cnpj_classe
)
SELECT
    CASE
        WHEN t1.id_parcela IS NULL THEN '4 saiu'
        WHEN t0.id_parcela IS NULL THEN '5 entrou'
        WHEN t0.flag_vencido = 1 THEN '3 vencida no início'
        WHEN t1.flag_vencido = 1 THEN '2 venceu no período'
        ELSE '1 a vencer'
    END AS grupo,
    COUNT(*) AS parcelas,
    SUM(t0.vp) AS vp_inicio,
    SUM(t1.vp) AS vp_fim,
    SUM(t1.vp - t0.vp) AS variacao_vp_real,
    SUM(t0.vp * (
        CASE t0.metodo
            WHEN 'expb252_aa' THEN POWER(1 + t0.taxa, LEAST(:du_periodo, GREATEST(t0.prazo_du, 0)) / 252.0)
            WHEN 'exp360_aa'  THEN POWER(1 + t0.taxa, LEAST(:dc_periodo, GREATEST(t0.prazo_dc, 0)) / 360.0)
            WHEN 'exp365_aa'  THEN POWER(1 + t0.taxa, LEAST(:dc_periodo, GREATEST(t0.prazo_dc, 0)) / 365.0)
        END - 1
    )) AS taxa_x_prazo
FROM t0
FULL JOIN t1 ON t1.id_parcela = t0.id_parcela
GROUP BY 1
ORDER BY 1;
