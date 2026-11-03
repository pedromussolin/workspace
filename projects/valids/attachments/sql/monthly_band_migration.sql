-- Análise de Migração: VP por faixa de atraso em cada fechamento mensal
-- (tabela "Segregação por faixa de atraso" do protótipo). Revisto em
-- 26/10/2026 com D17, D18, D20, D22 e D33.
--
-- Uma foto por mês, sem comparar contratos entre meses (isso é a matriz do
-- "Estudo de Migração", migration_matrix.sql). Cada mês fechado é calculado
-- uma vez e gravado no Postgres (D22); a rota só lê.

-- 1. Fechamento do mês: o último data_ref do mês com foto de cada fundo.
--    Procurar só na última semana do mês, para não ler o mês inteiro; por
--    fundo, porque o último dia pode vir incompleto (P15).
--    A INTERNAL só vale para fundo sem administrador (D55, D56).
WITH ultimo AS (
    SELECT source, cnpj_classe, MAX(data_ref) AS fechamento
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref BETWEEN :ultimo_dia_do_mes - 7 AND :ultimo_dia_do_mes
    GROUP BY 1, 2
)
SELECT u.source, u.cnpj_classe, u.fechamento
FROM ultimo u
WHERE u.source <> 'INTERNAL'
   OR u.cnpj_classe NOT IN (SELECT cnpj_classe FROM ultimo WHERE source <> 'INTERNAL');

-- 2. VP por fechamento, fundo, produto e faixa. :fechamentos = as datas da
--    consulta 1 (passadas como lista, para o filtro usar a sortkey).
--    Faixas da Análise de Migração (D33): 0 em dia, 1 = 1–30 … 6 = 151–180,
--    7 = 181+. Contrato inteiro na faixa do seu dias_atraso (nulo = em dia).
--    INTERNAL só para fundo sem administrador na data (D55, D56); ela traz
--    dias_atraso (confirmado pelo Heitor em 27/10).
WITH base AS (
    SELECT data_ref, source, cnpj_classe, id_contrato_admin, vl_presente, vl_pdd,
           CASE WHEN dias_atraso IS NULL THEN 0
                WHEN dias_atraso > 180 THEN 7
                ELSE CAST(FLOOR((dias_atraso - 1) / 30) AS INT) + 1 END AS faixa
    FROM plgn.administradores_estoque_contrato
    WHERE data_ref IN (:fechamentos)
),
com_administrador AS (
    SELECT DISTINCT data_ref, cnpj_classe FROM base WHERE source <> 'INTERNAL'
),
e AS (
    SELECT b.*
    FROM base b
    LEFT JOIN com_administrador a ON a.data_ref = b.data_ref AND a.cnpj_classe = b.cnpj_classe
    WHERE b.source <> 'INTERNAL' OR a.cnpj_classe IS NULL
),
d AS (
    SELECT cnpj_classe, num_controle, identificador, produto_id
    FROM plgn.dim_contrato
    WHERE cnpj_classe IN (SELECT DISTINCT cnpj_classe FROM e)
)
SELECT e.data_ref AS fechamento,
       e.source AS admin,
       e.cnpj_classe AS fund_legal_id,
       COALESCE(d1.produto_id, d2.produto_id) AS product_id,   -- nulo = sem produto (D18)
       e.faixa,
       COUNT(*) AS contract_count,
       SUM(e.vl_presente) AS pv,
       -SUM(e.vl_pdd) AS pdd
FROM e
LEFT JOIN d d1 ON d1.cnpj_classe = e.cnpj_classe AND d1.num_controle = e.id_contrato_admin
LEFT JOIN d d2 ON d2.cnpj_classe = e.cnpj_classe AND d2.identificador = e.id_contrato_admin
              AND d1.num_controle IS NULL
GROUP BY 1, 2, 3, 4, 5;
