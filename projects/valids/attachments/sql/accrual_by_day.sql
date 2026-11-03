-- SUBSTITUÍDA pela D15 (22/10/2026): o accrual passou a ser por roll-forward,
-- em attachments/sql/movement_by_interval.sql. Mantida como histórico.
--
-- Accrual de juros de UM dia (foto), por taxa × prazo (D4, D9, D12).
-- Para cada parcela a vencer na foto anterior:
--   accrual = VP × ((1 + taxa)^(n / base) − 1)
--   n = dias entre a foto anterior e a foto do dia, limitado aos dias até o vencimento
--   base = 252 dias úteis (expb252_aa), 360 ou 365 dias corridos (exp360_aa, exp365_aa)
-- Só há foto em dia útil: de sexta para segunda, :du_desde_anterior = 1 e
-- :dc_desde_anterior = 3. Contar com o calendário B3 da data-lake-api.
-- O resultado é o accrual atribuído à foto do dia. Qualquer período é a soma
-- dos dias dele.
-- Taxas como vêm do lake (D12). :fontes_taxa_percentual = fontes que mandam a
-- taxa em % (ver privado.md); as demais mandam em fração.
-- Parcela sem taxa ou sem método sai com accrual nulo (P7).
-- Em 21/10/2026 esta consulta rodou com :foto_anterior = 31/08/2026,
-- :du_desde_anterior = 21 e :dc_desde_anterior = 30 (o mês inteiro numa foto só).
SELECT
    e.source AS admin,
    e.cnpj_classe AS fund_legal_id,
    SUM(e.vl_presente_parcela) AS pv_to_mature,
    SUM(e.vl_presente_parcela * (
        CASE e.metodo
            WHEN 'expb252_aa' THEN POWER(1 + e.taxa, LEAST(:du_desde_anterior, GREATEST(e.prazo_du, 0)) / 252.0)
            WHEN 'exp360_aa'  THEN POWER(1 + e.taxa, LEAST(:dc_desde_anterior, GREATEST(e.prazo_dc, 0)) / 360.0)
            WHEN 'exp365_aa'  THEN POWER(1 + e.taxa, LEAST(:dc_desde_anterior, GREATEST(e.prazo_dc, 0)) / 365.0)
        END - 1
    )) AS interest_accrual,
    SUM(CASE WHEN e.taxa IS NULL OR e.metodo IS NULL THEN 1 ELSE 0 END) AS parcels_without_rate
FROM (
    SELECT
        source,
        cnpj_classe,
        vl_presente_parcela,
        prazo_du,
        prazo_dc,
        COALESCE(metodo_taxa_recebivel, metodo_taxa_cessao) AS metodo,
        CASE
            WHEN source IN (:fontes_taxa_percentual) THEN COALESCE(taxa_recebivel, taxa_cessao) / 100.0
            ELSE COALESCE(taxa_recebivel, taxa_cessao)
        END AS taxa
    FROM plgn.administradores_estoque
    WHERE data_ref = :foto_anterior
      AND flag_vencido = 0
) e
GROUP BY 1, 2;
