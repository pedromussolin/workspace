"""Carrega uma poça no mock do portal, para ver a Mov. Estoque em modo mock,
sem BFF, sem Azure e sem tabela: a fictícia (`generate_fake_pool.py`, o
caminho mais seguro) ou a simulada com dados reais (`simulate_fund_movement.py`).

Uso (Python do sistema, sem dependências):
    python3 pool_to_mock.py <poca.csv> <saida.js> [--manter-fundos]

Com `--manter-fundos`, a lista de fundos do mock fica como está (use com a
poça fictícia do `generate_fake_pool.py`, que já usa os fundos do mock).

Gera um script que só grava os dados no `localStorage` do navegador (chave
`portal.mock-api`, a mesma que o mock usa para o que muda) e recarrega a
página: nada vai para a rede. Para usar, abrir o portal em
http://localhost:4200, colar o conteúdo do `.js` no console do DevTools e
apertar Enter.

Segurança:
- com a poça simulada, o CSV e o `.js` têm CNPJ e valores reais: os dois
  ficam em `~/.local/share/workspace/projects/valids/`, fora de qualquer repositório;
- os dados ficam só neste navegador, nesta origem (localhost:4200). Para
  apagar: abrir http://localhost:4200/?mock-reset (ou apagar a chave
  `portal.mock-api` no DevTools).
"""

import argparse
import csv
import json
from collections import Counter

AMOUNTS = (
    "opening_balance",
    "closing_balance",
    "acquisitions",
    "liquidations",
    "interest_accrual",
    "paid_on_remaining",
    "pv_entered",
    "pv_exited",
)


def read_days(path: str) -> list[dict]:
    with open(path, newline="") as file:
        return [
            {
                "fund_cnpj": row["fund_cnpj"],
                "source": row["source"],
                "previous_ref_date": row["previous_ref_date"],
                "ref_date": row["ref_date"],
                **{field: float(row[field]) for field in AMOUNTS},
            }
            for row in csv.DictReader(file)
        ]


def funds_of(days: list[dict]) -> list[dict]:
    """A lista de fundos do filtro: o nome não está no CSV, então vai a fonte
    principal (a de mais dias) e o CNPJ."""
    sources: dict[str, Counter] = {}
    for day in days:
        sources.setdefault(day["fund_cnpj"], Counter())[day["source"]] += 1
    return [
        {
            "id": position,
            "name": f"{counter.most_common(1)[0][0]} · {cnpj}",
            "legal_id": cnpj,
            "products": [],
        }
        for position, (cnpj, counter) in enumerate(sorted(sources.items()), start=1)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("poca")
    parser.add_argument("saida")
    parser.add_argument("--manter-fundos", action="store_true")
    args = parser.parse_args()
    output_path = args.saida

    days = read_days(args.poca)
    overrides = {"controllership/valid/stock-movement/days": days}
    if not args.manter_fundos:
        overrides["controllership/valid/funds"] = funds_of(days)
    state = {"session": True, "changes": {"set": overrides, "removed": []}}
    # JSON é JavaScript válido: o script só grava a chave e recarrega a página.
    script = (
        "// Poça simulada no mock do portal (só neste navegador). Para apagar:\n"
        "// http://localhost:4200/?mock-reset\n"
        f"localStorage.setItem('portal.mock-api', JSON.stringify({json.dumps(state)}));\n"
        "location.reload();\n"
    )
    with open(output_path, "w") as file:
        file.write(script)

    size_kb = len(script.encode()) / 1024
    print(
        f"{len(days)} dia(s) de {len({day['fund_cnpj'] for day in days})} fundo(s) em "
        f"{output_path} ({size_kb:.0f} KB)"
    )
    if size_kb > 4000:
        print("Atenção: perto do limite do localStorage (~5 MB); use um período menor.")


if __name__ == "__main__":
    main()
