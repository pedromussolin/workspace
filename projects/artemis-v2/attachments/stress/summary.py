"""Junta os JSON de /estresse/results numa tabela Markdown por cenário."""

import glob
import json
import sys

ORDER = ["rajada", "clique_repetido", "acumula", "gigante", "trava_externa", "worker_parado",
         "worker_morto", "redis_fora", "status"]
BAD = ["lotes_novos_vazios", "violacoes_regra_d9", "lotes_com_mais_de_uma_linha",
       "pagamentos_de_linhas_nao_pedidas", "esteira_lotes_enviados_mais_de_uma_vez",
       "esteira_lotes_fechados_sem_envio", "travas_que_sobraram"]


def fmt(stats, unit=""):
    if not stats:
        return "—"
    return f"{stats['p50']}{unit} / {stats['p95']}{unit} / {stats['max']}{unit}"


def main(folder):
    rows = [json.load(open(path))["summary"] for path in glob.glob(f"{folder}/*.json")]
    rows.sort(key=lambda r: (ORDER.index(r["scenario"]) if r["scenario"] in ORDER else 99, r["label"]))
    print("| Cenário | Versão | Pedidos (resultado da rota) | Resultado final | Sumiram | Até o resultado p50/p95/máx | "
          "Rota p50/p95/máx | Banco: ativas / esperando trava | Invariantes |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        inv = r["invariants"]
        broken = {k: inv[k] for k in BAD if inv.get(k)}
        extra = f" status: {fmt(r['status_latency_ms'], ' ms')}" if r.get("status_latency_ms") else ""
        print(
            f"| {r['scenario']} | {r['label'].rsplit('-' + r['scenario'], 1)[0]} | {r['requests']} "
            f"{dict(sorted(r['outcomes'].items()))} | {r['finals']} | {r['vanished']} | "
            f"{fmt(r['seconds_to_result'], ' s')} | {fmt(r['request_latency_ms'], ' ms')}{extra} | "
            f"{r['db_peak']['active']} / {r['db_peak']['waiting_lock']} | "
            f"{'ok' if not broken else broken} (fechados: {inv['pagamentos_fechados']}, "
            f"aptos que ficaram: {inv['aptos_que_ficaram_nas_linhas_pedidas']}) |"
        )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results")
