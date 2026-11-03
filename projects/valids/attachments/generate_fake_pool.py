"""Gera uma poça fictícia: o CSV da `valid_stock_movement` com dados inventados,
para ver a Mov. Estoque no mock do portal sem nenhum dado real.

Uso (Python do sistema, sem dependências):
    python3 generate_fake_pool.py <saida.csv> [--inicio 2026-07-01] [--fim 2026-10-22]
        [--fundos <controllership.json do smoke>]

Os fundos são os fictícios do mock do portal (`controllership/valid/funds` em
`.ai/scripts/smoke-data/controllership.json` do apl-credit-whitelabel), então
os nomes no filtro batem. Um dia por fundo e dia útil (segunda a sexta, sem
feriados), encadeados: o estoque real de um dia é o saldo inicial do seguinte.

Os números fecham a conta da conferência como os reais: em cada dia,
    estoque real − (saldo inicial + aquisições − baixas + accrual)
      = (VP das entradas − aquisições) + (baixas − pagamentos de quem ficou − VP das saídas)
com uma diferença pequena, de propósito, para a pílula da tela ter o que mostrar.
A semente é fixa: rodar de novo dá o mesmo arquivo.
"""

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

DEFAULT_FUNDS = (
    Path(__file__).resolve().parents[4]
    / "apl-credit-whitelabel/.ai/scripts/smoke-data/controllership.json"
)
SOURCE = "ADMINISTRADORA FICTICIA"
COLUMNS = (
    "fund_cnpj",
    "source",
    "previous_ref_date",
    "ref_date",
    "opening_balance",
    "closing_balance",
    "acquisitions",
    "liquidations",
    "interest_accrual",
    "paid_on_remaining",
    "pv_entered",
    "pv_exited",
)


def weekdays(start: date, end: date) -> list[date]:
    days = (start + timedelta(days=offset) for offset in range((end - start).days + 1))
    return [day for day in days if day.weekday() < 5]


def fund_days(rng: random.Random, cnpj: str, photos: list[date]) -> list[dict]:
    """Os dias de um fundo: VP inicial entre R$ 80 mi e R$ 1,5 bi, aquisições em
    ~70% dos dias, baixas todo dia e juros de ~1,5% ao mês."""
    balance = rng.uniform(80e6, 1.5e9)
    rows = []
    for previous, current in zip(photos, photos[1:]):
        opening = balance
        acquisitions = (
            opening * rng.uniform(0.002, 0.015) if rng.random() < 0.7 else 0.0
        )
        liquidations = opening * rng.uniform(0.002, 0.012)
        accrual = opening * rng.uniform(0.0005, 0.0009)
        # O que a conferência não explica: entradas e saídas a VP fora das
        # aquisições e baixas (resultado nas baixas, parcela sem registro).
        entries_gap = acquisitions * rng.gauss(0, 0.003)
        exits_gap = liquidations * rng.gauss(0, 0.01)
        paid_on_remaining = liquidations * rng.uniform(0.05, 0.3)
        closing = (
            opening + acquisitions - liquidations + accrual + entries_gap + exits_gap
        )
        rows.append(
            {
                "fund_cnpj": cnpj,
                "source": SOURCE,
                "previous_ref_date": previous.isoformat(),
                "ref_date": current.isoformat(),
                "opening_balance": round(opening, 2),
                "closing_balance": round(closing, 2),
                "acquisitions": round(acquisitions, 2),
                "liquidations": round(liquidations, 2),
                "interest_accrual": round(accrual, 2),
                "paid_on_remaining": round(paid_on_remaining, 2),
                "pv_entered": round(acquisitions + entries_gap, 2),
                "pv_exited": round(liquidations - paid_on_remaining - exits_gap, 2),
            }
        )
        balance = closing
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("saida")
    parser.add_argument("--inicio", type=date.fromisoformat, default=date(2026, 7, 1))
    parser.add_argument("--fim", type=date.fromisoformat, default=date(2026, 10, 22))
    parser.add_argument("--fundos", type=Path, default=DEFAULT_FUNDS)
    args = parser.parse_args()

    funds = json.loads(args.fundos.read_text())["controllership/valid/funds"]
    # A foto que abre o período vem antes do início, como na consolidação.
    photos = weekdays(args.inicio - timedelta(days=7), args.fim)
    opening = max(day for day in photos if day < args.inicio)
    photos = [day for day in photos if day >= opening]

    rng = random.Random(4366)
    rows = [row for fund in funds for row in fund_days(rng, fund["legal_id"], photos)]

    with open(args.saida, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} dia(s) de {len(funds)} fundo(s) fictício(s) em {args.saida}")


if __name__ == "__main__":
    main()
