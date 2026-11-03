-- Mov. Estoque lida da "poça" (Postgres da data-lake-api, D34): o que a rota
-- /valid/stock-movement faz, em SQL. A rota lê os dias (consulta 1) e soma em
-- Python (src/modules/valid/business.py, summarize_movement); as consultas 2 e
-- 3 fazem a mesma conta direto no banco, para conferir.
--
-- Parâmetros: :fund_cnpj (14 dígitos, sem máscara), :start_date, :end_date
-- (Data inicial e Data final da tela; padrão da D27: o último mês).
-- Tabela vazia até o fundo ser cadastrado e consolidado (/valid/movement).

-- 1. Os dias do período: um por intervalo entre duas fotos seguidas. É a
--    leitura da rota (índice único por fundo, dia e fonte).
SELECT source, previous_ref_date, ref_date,
       opening_balance, acquisitions, liquidations, interest_accrual,
       closing_balance, paid_on_remaining, pv_entered, pv_exited
FROM valid_stock_movement
WHERE fund_cnpj = :fund_cnpj
  AND ref_date BETWEEN :start_date AND :end_date
ORDER BY ref_date, source;

-- 2. O período inteiro (waterfall): saldo inicial do primeiro dia, estoque
--    real do último, soma dos componentes e a conferência.
WITH dias AS (
    SELECT *
    FROM valid_stock_movement
    WHERE fund_cnpj = :fund_cnpj
      AND ref_date BETWEEN :start_date AND :end_date
),
fonte AS (
    -- Fundo sob dois administradores (carga duplicada): fica o que tem mais
    -- dias, como na rota.
    SELECT source
    FROM dias
    GROUP BY source
    ORDER BY COUNT(*) DESC, source
    LIMIT 1
),
periodo AS (
    SELECT d.* FROM dias d JOIN fonte f ON f.source = d.source
),
totais AS (
    SELECT
        MIN(previous_ref_date) AS opening_date,
        MAX(ref_date) AS closing_date,
        (ARRAY_AGG(opening_balance ORDER BY ref_date))[1] AS opening_balance,
        SUM(acquisitions) AS acquisitions,
        SUM(liquidations) AS liquidations,
        SUM(interest_accrual) AS interest_accrual,
        (ARRAY_AGG(closing_balance ORDER BY ref_date DESC))[1] AS closing_balance,
        SUM(paid_on_remaining) AS paid_on_remaining,
        SUM(pv_entered) AS pv_entered,
        SUM(pv_exited) AS pv_exited
    FROM periodo
)
SELECT
    t.opening_date,
    t.closing_date,
    (SELECT MAX(ref_date) FROM valid_stock_movement
      WHERE fund_cnpj = :fund_cnpj) AS last_consolidated_date,
    t.opening_balance,
    t.acquisitions,
    t.liquidations,
    t.interest_accrual,
    t.closing_balance,
    t.opening_balance + t.acquisitions - t.liquidations + t.interest_accrual
        AS calculated_closing_balance,
    t.closing_balance
        - (t.opening_balance + t.acquisitions - t.liquidations + t.interest_accrual)
        AS difference,
    t.pv_entered - t.acquisitions AS difference_on_entries,
    t.liquidations - t.paid_on_remaining - t.pv_exited AS difference_on_exits
FROM totais t;

-- 3. Evolução mensal: a mesma conta, mês a mês.
WITH dias AS (
    SELECT *
    FROM valid_stock_movement
    WHERE fund_cnpj = :fund_cnpj
      AND ref_date BETWEEN :start_date AND :end_date
),
fonte AS (
    SELECT source FROM dias GROUP BY source ORDER BY COUNT(*) DESC, source LIMIT 1
)
SELECT
    TO_CHAR(d.ref_date, 'YYYY-MM') AS month,
    (ARRAY_AGG(d.opening_balance ORDER BY d.ref_date))[1] AS opening_balance,
    SUM(d.acquisitions) AS acquisitions,
    SUM(d.liquidations) AS liquidations,
    SUM(d.interest_accrual) AS interest_accrual,
    (ARRAY_AGG(d.closing_balance ORDER BY d.ref_date DESC))[1] AS closing_balance
FROM dias d
JOIN fonte f ON f.source = d.source
GROUP BY 1
ORDER BY 1;
