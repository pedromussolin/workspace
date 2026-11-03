"""Gera a consulta de movimentação de UM fundo num PERÍODO (versão P1, 23/10).

Uso (num ambiente com a lib `holidays`, como o da data-lake-api):
    python generate_period_movement.py <inicio> <fim> <fonte> <cnpj> <saida.sql>
    ex.: python generate_period_movement.py 2026-10-16 2026-10-22 <fonte> <cnpj> semana.sql

Saldo inicial = foto do dia útil anterior a <inicio>; estoque real = foto de
<fim> (D13). A lista de fotos sai do calendário B3 e entra pronta na consulta:
calculada dentro dela, o Redshift refaz a leitura que descobre as datas a cada
uso da CTE, e a consulta fica ~2x mais lenta.

Por que é mais rápida que a versão anterior (medido em 23/10, um fundo de 5,9
mi de parcelas, semana: 24,3 s -> 5,9 s, mesmo resultado):
- cada foto é lida uma vez e ganha os dois papéis (anterior e atual) por uma
  junção com uma tabela pequena, em vez de uma CTE lida duas vezes e gravada
  em área temporária;
- a parcela é um número de 64 bits (FNV_HASH), não um texto;
- pagamentos e aquisições caem no intervalo por uma junção pequena (datas x
  fotos), em vez de uma junção em laço com as linhas de liquidação.
"""
import sys
from datetime import date, timedelta

import holidays

CAL = holidays.financial_holidays("BVMF")


def util(d):
    return d.weekday() < 5 and d not in CAL


def anterior_util(d):
    d -= timedelta(days=1)
    while not util(d):
        d -= timedelta(days=1)
    return d


def gerar(inicio: date, fim: date, fonte: str, fundo: str) -> str:
    dias = [anterior_util(inicio)]
    d = inicio
    while d <= fim:
        if util(d):
            dias.append(d)
        d += timedelta(days=1)
    linhas = []
    for i, d in enumerate(dias):
        ant = f"DATE '{dias[i - 1]}'" if i > 0 else "CAST(NULL AS DATE)"
        prox = f"DATE '{dias[i + 1]}'" if i + 1 < len(dias) else "CAST(NULL AS DATE)"
        prefixo = "    SELECT" if i == 0 else "    UNION ALL SELECT"
        nomes = " AS foto, {} AS anterior, {} AS proxima" if i == 0 else ", {}, {}"
        linhas.append(f"{prefixo} DATE '{d}'" + nomes.format(ant, prox))
    filtro = f"AND source = '{fonte}' AND cnpj_classe = '{fundo}'"
    primeira, ultima = dias[0], dias[-1]
    return f"""WITH fotos_seq AS (
{chr(10).join(linhas)}
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
    WHERE data_ref BETWEEN DATE '{primeira}' AND DATE '{ultima}'
      {filtro}
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
    WHERE data_ref > DATE '{primeira}' AND data_ref <= DATE '{ultima}'
      {filtro}
    GROUP BY 1, 2
),
aquisicoes AS (
    SELECT data_ref, SUM(COALESCE(vl_aquisicao, 0)) AS aquisicoes
    FROM plgn.administradores_aquisicao
    WHERE data_ref > DATE '{primeira}' AND data_ref <= DATE '{ultima}'
      {filtro}
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
FROM totais t CROSS JOIN fluxos f CROSS JOIN limites li"""


if __name__ == "__main__":
    inicio, fim, fonte, fundo, saida = sys.argv[1:6]
    open(saida, "w").write(gerar(date.fromisoformat(inicio), date.fromisoformat(fim), fonte, fundo))
