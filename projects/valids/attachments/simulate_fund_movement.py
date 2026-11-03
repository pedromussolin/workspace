"""Simula a Mov. Estoque de um fundo com dados reais, sem gravar nada.

Lê o Redshift do lake pelas mesmas consultas e blocos que a run da
consolidação usa (só SELECT) e monta, em memória, a resposta que a
`/valid/stock-movement` daria. Não usa Postgres nem cria tabela.

Uso, na raiz da data-lake-api (branch da TS-4815), com o ambiente dela:
    PYTHONPATH=. python <caminho>/simulate_fund_movement.py <cnpj> <inicio> <fim>
        [--csv dias.csv] [--dias-por-bloco 31]
    PYTHONPATH=. python <caminho>/simulate_fund_movement.py todos <inicio> <fim>
        [--csv dias.csv]

Com `todos`, roda fundo a fundo (como a consolidação), um depois do outro,
para cada fundo de administrador que tem foto na view por parcela na data
<fim>, e imprime uma tabela com os totais de cada um. O `--csv` sai com as
colunas da `valid_stock_movement`: é a tabela da "poça" simulada.

<inicio> e <fim> são a Data inicial e a Data final da tela (AAAA-MM-DD). O
saldo inicial é a última foto antes de <inicio> e os dias vão até a última
foto até <fim> (D13). O resultado tem de bater com a consulta de período
(`generate_period_movement.py`) no mesmo intervalo.

Custo: o da run, ~30 s por mês de um fundo de 5,9 mi de parcelas (mais com o
Redshift cheio). Períodos longos, só fora do horário comercial.

Só leitura: uma trava na conexão recusa, antes de sair para o Redshift, todo
comando que não seja SELECT/WITH/SHOW ou o limite de tempo da sessão.
"""

import argparse
import asyncio
import csv
import re
import sys
import time
from dataclasses import asdict
from datetime import date, timedelta

from sqlalchemy import event, text
from src.infra.redshift.engine import get_engine
from src.infra.redshift.session import SessionLocal
from src.modules.valid.business import summarize_movement
from src.modules.valid.business import (
    ValidStockMovementConsolidationBusiness,
)
from src.modules.valid.repository import ValidMovementSourceRepository

# Trava de só leitura: o que pode sair para o Redshift, e o que nunca pode.
ALLOWED = re.compile(r"^\s*(select|with|show|set local statement_timeout)\b", re.I)
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|copy|"
    r"unload|call|vacuum|analyze|comment|lock)\b",
    re.I,
)


class WriteRefusedError(RuntimeError):
    pass


def refuse_writes(conn, cursor, statement, parameters, context, executemany) -> None:
    if not ALLOWED.match(statement) or FORBIDDEN.search(statement):
        raise WriteRefusedError(f"comando recusado (só leitura): {statement[:80]!r}")


event.listen(get_engine(), "before_cursor_execute", refuse_writes)

# Quanto procurar para trás a foto que abre o período (fim de semana, feriado,
# foto que faltou).
OPENING_LOOKBACK_DAYS = 15


# Fundos com foto na view por parcela numa data: lê só as colunas do filtro
# de uma foto.
FUNDS_IN_PHOTO = text(
    """
    SELECT DISTINCT cnpj_classe
    FROM plgn.administradores_estoque
    WHERE data_ref = :ref_date
    ORDER BY cnpj_classe
    """
)


def funds_in_last_photo(end: date) -> tuple[date, list[str]]:
    """Os fundos da última foto até `end` (procura até 10 dias para trás)."""
    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '120000'"))
        for back in range(10):
            day = end - timedelta(days=back)
            funds = list(session.execute(FUNDS_IN_PHOTO, {"ref_date": day}).scalars())
            if funds:
                return day, funds
    return end, []


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


async def simulate(fund: str, start: date, end: date, block_days: int) -> list[dict]:
    source = ValidMovementSourceRepository(movement_timeout_seconds=1800)
    business = ValidStockMovementConsolidationBusiness(source, block_days=block_days)

    latest = await source.get_latest_photos(fund, start, end)
    if not latest:
        log(f"Nenhuma foto do fundo entre {start} e {end} na view por parcela.")

    rows = []
    for name, until in sorted(latest.items()):
        before = await source.list_photos(
            fund,
            name,
            start - timedelta(days=OPENING_LOOKBACK_DAYS),
            start - timedelta(days=1),
        )
        if not before:
            log(f"{name}: sem foto nos {OPENING_LOOKBACK_DAYS} dias antes de {start}")
            continue

        opening = before[-1]
        log(f"{name}: abre na foto de {opening}, vai até a de {until}")
        async for days in business.blocks(fund, name, opening, until, opening):
            log(f"  bloco {days[0].ref_date} a {days[-1].ref_date}: {len(days)} dia(s)")
            rows += [{**asdict(day), "source": name} for day in days]

    return rows


# As colunas da `valid_stock_movement` que a consolidação grava (sem `id`,
# `run_id` e `created_at`): o CSV é a tabela simulada.
TABLE_COLUMNS = (
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


def table_rows(fund: str, rows: list[dict]) -> list[dict]:
    """Os dias como linhas da tabela, com os valores em centavos (`Numeric(18, 2)`)."""
    return [
        {
            column: (round(value, 2) if isinstance(value, float) else value)
            for column, value in (
                (column, {"fund_cnpj": fund, **row}[column]) for column in TABLE_COLUMNS
            )
        }
        for row in rows
    ]


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TABLE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    log(f"{len(rows)} linha(s) da valid_stock_movement em {path}")


def run_all(start: date, end: date, block_days: int, csv_path: str | None) -> None:
    photo, funds = funds_in_last_photo(end)
    log(f"{len(funds)} fundo(s) na foto de {photo}")

    columns = (
        "fundo",
        "fonte",
        "dias",
        "saldo_inicial",
        "aquisicoes",
        "baixas",
        "accrual",
        "estoque_real",
        "diferenca",
        "segundos",
    )
    print(";".join(columns))
    all_rows = []
    for fund in funds:
        started = time.monotonic()
        try:
            rows = asyncio.run(simulate(fund, start, end, block_days))
        except Exception as exc:  # um fundo com erro não para os outros
            log(f"{fund}: erro {exc!r}")
            continue
        seconds = time.monotonic() - started
        if not rows:
            print(f"{fund};;0;;;;;;;{seconds:.1f}")
            continue
        all_rows += table_rows(fund, rows)
        summary = summarize_movement(fund, rows, max(row["ref_date"] for row in rows))
        values = (
            summary.opening_balance,
            summary.acquisitions,
            summary.liquidations,
            summary.interest_accrual,
            summary.closing_balance,
            summary.difference,
        )
        days = sum(1 for row in rows if row["source"] == summary.admin)
        print(
            f"{fund};{summary.admin};{days};"
            + ";".join(f"{value:.2f}" for value in values)
            + f";{seconds:.1f}"
        )

    if csv_path and all_rows:
        write_csv(csv_path, all_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cnpj", help="CNPJ do fundo, ou `todos`")
    parser.add_argument("inicio", type=date.fromisoformat)
    parser.add_argument("fim", type=date.fromisoformat)
    parser.add_argument("--csv", help="grava os dias neste arquivo")
    parser.add_argument("--dias-por-bloco", type=int, default=31)
    args = parser.parse_args()

    if args.cnpj == "todos":
        run_all(args.inicio, args.fim, args.dias_por_bloco, args.csv)
        return

    fund = re.sub(r"\D", "", args.cnpj)
    rows = asyncio.run(simulate(fund, args.inicio, args.fim, args.dias_por_bloco))

    if args.csv and rows:
        write_csv(args.csv, table_rows(fund, rows))

    if not rows:
        print('{"available": false}')
        return

    last_day = max(row["ref_date"] for row in rows)
    print(summarize_movement(fund, rows, last_day).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
