"""Simulador de pressão do fechamento de lote fake.

Roda dentro do container `driver`, com o código (master ou branch) montado em
/app. Chama a mesma função da rota (`request_fake_batch_closing`) e a do status,
em threads, como vários usuários na tela. No fim confere invariantes no banco,
no Redis e na fila da esteira, e grava um JSON em /estresse/results.
"""

import cessao.app  # noqa: F401  (ordem de import igual à da aplicação)

import argparse
import json
import os
import random
import statistics
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, text

from cessao.api.liquidacao import refact
from cessao.api.liquidacao.refact import RefactLiquidacaoService as Service
from cessao.app import app, celery
from cessao.extensions import db

# As threads do simulador não herdam a app "atual" do Celery; sem isto a task
# publicaria pela app padrão (localhost). Na API isso não acontece.
celery.set_default()

ENGINE = create_engine(os.environ["DB_POSTGRESQL_PLATFORM_CESSAO"], pool_size=10)
NEW_BATCH_MIN_ID = 100000
PIPELINE_QUEUE = "liquidacao_lote_celery"
CLOSING_QUEUE = "fake_batch_closing_celery"
FINAL = ("closed", "failed")


def sql(query, **params):
    with ENGINE.begin() as conn:
        result = conn.execute(text(query), params)
        return result.fetchall() if result.returns_rows else result.rowcount


def reset():
    """Volta o banco, o Redis e as filas ao estado da massa gerada."""
    sql("UPDATE liquidacao_pagamento SET liquidacao_lote_id = NULL WHERE liquidacao_lote_id > :m", m=NEW_BATCH_MIN_ID)
    sql("DELETE FROM liquidacao_lote_log WHERE liquidacao_lote_id > :m", m=NEW_BATCH_MIN_ID)
    sql("DELETE FROM liquidacao_lote_processo WHERE id > :m", m=NEW_BATCH_MIN_ID)
    sql("UPDATE liquidacao_lote_vigente SET fechado = false WHERE fechado")
    with ENGINE.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("VACUUM ANALYZE liquidacao_pagamento"))
        conn.execute(text("VACUUM ANALYZE liquidacao_lote_processo"))
    refact.Cache.retrieve_client_controle().flushall()
    with celery.connection_for_write() as conn:
        for queue in (PIPELINE_QUEUE, CLOSING_QUEUE):
            try:
                conn.default_channel.queue_purge(queue)
            except Exception:
                pass


def keys(where, limit=None, order="key_id"):
    rows = sql(
        f"SELECT origem, produto_id, originador_id, fundo_id, n FROM gen_keys WHERE {where} ORDER BY {order}"
        + (f" LIMIT {int(limit)}" if limit else "")
    )
    return [
        {"key": f"origem:{o}:{p}:{orig}:{f}", "product_id": p, "origin": o, "n": n}
        for o, p, orig, f, n in rows
    ]


class Run:
    def __init__(self, label, scenario):
        self.label, self.scenario = label, scenario
        self.requests = []
        self.lock = threading.Lock()
        self.timeline = {}
        self.db_samples = []
        self.started = time.monotonic()
        self.stop = threading.Event()

    def now(self):
        return round(time.monotonic() - self.started, 2)

    def request(self, item):
        t0 = time.monotonic()
        outcome = "202"
        try:
            with app.app_context():
                try:
                    Service.request_fake_batch_closing(item["key"], item["product_id"])
                except refact.FakeBatchClosingInProgress:
                    outcome = "409"
                except refact.ParametrosInvalidos:
                    outcome = "400"
                finally:
                    db.session.remove()
        except Exception as exc:
            outcome = f"erro:{type(exc).__module__}.{type(exc).__name__}:{str(exc).splitlines()[0][:120]}"
        record = {
            "key": item["key"],
            "at": round(t0 - self.started, 2),
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "outcome": outcome,
        }
        with self.lock:
            self.requests.append(record)
            # Pedido com erro também é acompanhado: o comando pode ter chegado
            # ao Redis depois do timeout e deixado a linha travada.
            if outcome == "202" or outcome.startswith("erro"):
                self.timeline.setdefault(item["key"], {"requested_at": record["at"], "events": []})
        return record

    def _poll(self, interval):
        while not self.stop.is_set():
            with self.lock:
                tracked = [k for k in self.timeline if not k.startswith("_")]
            if tracked:
                try:
                    with app.app_context():
                        found = {}
                        for i in range(0, len(tracked), 200):
                            for r in Service.get_fake_batch_closing_statuses(tracked[i : i + 200])["records"]:
                                found[r["key"]] = r
                        db.session.remove()
                except Exception as exc:
                    found = None
                    with self.lock:
                        self.timeline.setdefault("_status_errors", []).append([self.now(), type(exc).__name__])
                if found is not None:
                    t = self.now()
                    with self.lock:
                        for key in tracked:
                            state = found.get(key)
                            status = (state["status"], state.get("reason")) if state else ("sem status", None)
                            events = self.timeline[key]["events"]
                            if not events or events[-1][1] != status[0] or events[-1][2] != status[1]:
                                events.append([t, status[0], status[1]])
            self._sample_db()
            self.stop.wait(interval)

    def _sample_db(self):
        try:
            row = sql(
                "SELECT count(*) FILTER (WHERE state = 'active'), "
                "count(*) FILTER (WHERE wait_event_type = 'Lock'), "
                "count(*) FILTER (WHERE state = 'idle in transaction') "
                "FROM pg_stat_activity WHERE datname = 'platform-cessao' AND pid <> pg_backend_pid()"
            )[0]
            self.db_samples.append([self.now(), *row])
        except Exception:
            pass

    def start_polling(self, interval=1.0):
        self.poller = threading.Thread(target=self._poll, args=(interval,), daemon=True)
        self.poller.start()

    def wait_final(self, timeout, settle_after_vanish=0):
        """Espera todos os pedidos aceitos terem resultado final, ou o prazo."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                pending = [
                    k for k, v in self.timeline.items()
                    if not k.startswith("_") and not (v["events"] and v["events"][-1][1] in FINAL)
                ]
                vanished_long = [
                    k for k in pending
                    if self.timeline[k]["events"] and self.timeline[k]["events"][-1][1] == "sem status"
                    and len(self.timeline[k]["events"]) > 1
                    and self.now() - self.timeline[k]["events"][-1][0] > settle_after_vanish
                ]
            if not pending or (settle_after_vanish and len(vanished_long) == len(pending)):
                break
            time.sleep(1)
        self.stop.set()
        self.poller.join(5)

    def report(self, extra=None):
        accepted = {k: v for k, v in self.timeline.items() if not k.startswith("_")}
        finals, to_final, vanished = Counter(), [], []
        for key, v in accepted.items():
            events = v["events"]
            last = events[-1] if events else [None, "sem status", None]
            if last[1] in FINAL:
                finals[f"{last[1]}: {last[2] or 'ok'}"] += 1
                to_final.append(last[0] - v["requested_at"])
            else:
                saw_closing = any(e[1] == "closing" for e in events)
                vanished.append(key) if saw_closing else None
                finals["sem resultado" + (" (sumiu depois de 'closing')" if saw_closing else "")] += 1
        latencies = [r["latency_ms"] for r in self.requests]
        result = {
            "label": self.label,
            "scenario": self.scenario,
            "requests": len(self.requests),
            "outcomes": dict(Counter(r["outcome"] for r in self.requests)),
            "request_latency_ms": _stats(latencies),
            "seconds_to_result": _stats(to_final),
            "finals": dict(finals),
            "vanished": len(vanished),
            "status_errors": len(self.timeline.get("_status_errors", [])),
            "db_peak": {
                "active": max((s[1] for s in self.db_samples), default=0),
                "waiting_lock": max((s[2] for s in self.db_samples), default=0),
                "idle_in_tx": max((s[3] for s in self.db_samples), default=0),
            },
            "invariants": invariants(list(accepted)),
            "elapsed_s": self.now(),
        }
        result.update(extra or {})
        os.makedirs("/estresse/results", exist_ok=True)
        with open(f"/estresse/results/{self.label}.json", "w") as fh:
            json.dump({"summary": result, "timeline": self.timeline, "requests": self.requests,
                       "db_samples": self.db_samples}, fh, indent=1, default=str)
        print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
        return result


def _stats(values):
    if not values:
        return None
    values = sorted(values)
    pick = lambda q: values[min(len(values) - 1, int(q * len(values)))]  # noqa: E731
    return {"n": len(values), "p50": round(statistics.median(values), 2), "p95": round(pick(0.95), 2),
            "max": round(values[-1], 2)}


def invariants(requested_keys):
    origins = sorted({k.split(":")[1] for k in requested_keys}) or ["-"]
    rows = sql(
        """
        WITH novos AS (SELECT id, identificador FROM liquidacao_lote_processo WHERE id > :m),
        pag AS (
          SELECT lp.id, lp.liquidacao_lote_id, lp.origem_pagamento, pr.produto_id, c.originador_id, pa.fundo_id,
                 pe.estado_atual AS cessao, pe.data_delete
          FROM liquidacao_pagamento lp
          JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
          JOIN contrato_parcela pa ON pa.id = lp.parcela_id
          JOIN contrato c ON c.id = pa.contrato_id
          JOIN contrato_processo pe ON pe.uuid = c.processo_uuid
          WHERE lp.liquidacao_lote_id IN (SELECT id FROM novos))
        SELECT
          (SELECT count(*) FROM novos),
          (SELECT count(*) FROM novos n WHERE NOT EXISTS (SELECT 1 FROM liquidacao_pagamento p WHERE p.liquidacao_lote_id = n.id)),
          (SELECT count(*) FROM pag),
          (SELECT count(*) FROM pag WHERE cessao <> 'cadastrado' OR data_delete IS NOT NULL),
          (SELECT count(*) FROM (SELECT liquidacao_lote_id FROM pag GROUP BY 1
                                 HAVING count(DISTINCT (origem_pagamento, produto_id, originador_id, fundo_id)) > 1) x),
          (SELECT count(*) FROM pag WHERE origem_pagamento <> ALL(:origins)),
          (SELECT count(*) FROM liquidacao_lote_vigente WHERE fechado)
        """,
        m=NEW_BATCH_MIN_ID, origins=origins,
    )[0]
    eligible_left = sql(
        """
        SELECT count(*) FROM liquidacao_pagamento lp
        JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
        JOIN contrato_parcela pa ON pa.id = lp.parcela_id
        JOIN contrato c ON c.id = pa.contrato_id
        JOIN contrato_processo pe ON pe.uuid = c.processo_uuid
        WHERE lp.liquidacao_lote_id IS NULL AND lp.origem_pagamento = ANY(:origins)
          AND pr.estado_atual = 'cadastrado' AND pe.estado_atual = 'cadastrado' AND pe.data_delete IS NULL
        """,
        origins=origins,
    )[0][0]
    dispatched = drain_pipeline()
    closed_ids = {str(r[0]) for r in sql(
        "SELECT identificador FROM liquidacao_lote_processo WHERE id > :m AND EXISTS "
        "(SELECT 1 FROM liquidacao_pagamento p WHERE p.liquidacao_lote_id = liquidacao_lote_processo.id) "
        "UNION SELECT l.identificador FROM liquidacao_lote_vigente v JOIN liquidacao_lote_processo l "
        "ON l.id = v.liquidacao_lote_id WHERE v.fechado", m=NEW_BATCH_MIN_ID)}
    leftover_locks = len(refact.Cache.retrieve_client_controle().keys("liquidacao:fake-batch-closing:lock:*"))
    return {
        "lotes_novos": rows[0],
        "lotes_novos_vazios": rows[1],
        "pagamentos_fechados": rows[2],
        "violacoes_regra_d9": rows[3],
        "lotes_com_mais_de_uma_linha": rows[4],
        "pagamentos_de_linhas_nao_pedidas": rows[5],
        "vigentes_fechados": rows[6],
        "aptos_que_ficaram_nas_linhas_pedidas": eligible_left,
        "esteira_envios": sum(dispatched.values()),
        "esteira_lotes_enviados_mais_de_uma_vez": sum(1 for v in dispatched.values() if v > 1),
        "esteira_lotes_fechados_sem_envio": len(closed_ids - set(dispatched)),
        "travas_que_sobraram": leftover_locks,
    }


def drain_pipeline():
    counts = Counter()
    with celery.connection_for_write() as conn:
        queue = conn.SimpleQueue(PIPELINE_QUEUE)
        while True:
            try:
                message = queue.get(block=True, timeout=1)
            except Exception:
                break
            body = message.decode() if hasattr(message, "decode") else message.payload
            args = body[0] if isinstance(body, (list, tuple)) else body.get("args", [])
            counts[str(args[0])] += 1
            message.ack()
        queue.close()
    return counts


def burst(run, items, per_second, workers=32):
    """Dispara os pedidos no ritmo pedido, cada um numa thread."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, item in enumerate(items):
            target = run.started + i / per_second
            time.sleep(max(0, target - time.monotonic()))
            pool.submit(run.request, item)


def hold_rows(origins, seconds, ready):
    """Outra transação segurando os pagamentos dessas linhas, como em 20/10."""
    with ENGINE.connect() as conn:
        tx = conn.begin()
        conn.execute(text("UPDATE liquidacao_pagamento SET data_atualizacao = now() "
                          "WHERE origem_pagamento = ANY(:o) AND liquidacao_lote_id IS NULL"), {"o": origins})
        ready.set()
        time.sleep(seconds)
        tx.rollback()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario")
    parser.add_argument("label")
    parser.add_argument("--rate", type=float, default=5)
    parser.add_argument("--hold", type=int, default=400)
    parser.add_argument("--locked", type=int, default=5)
    parser.add_argument("--others", type=int, default=15)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    random.seed(20)
    reset()
    run = Run(args.label, args.scenario)
    # O orquestrador espera este aviso para injetar falhas (pausar Redis, matar
    # o worker) só depois que a limpeza terminou.
    open(f"/estresse/logs/{args.label}.started", "w").close()
    extra = {}

    if args.scenario == "rajada":
        # 10x a rajada de 20/10: 150 linhas em 30 s, misturando tamanhos.
        items = (keys("kind='tela' AND n < 100", 100) + keys("kind='tela' AND n BETWEEN 200 AND 2000", 40)
                 + keys("kind='tela' AND n BETWEEN 5000 AND 15000", 8) + keys("origem LIKE 'tela-x-%'"))
        random.shuffle(items)
        run.start_polling()
        burst(run, items, args.rate)
        run.wait_final(args.timeout, settle_after_vanish=30)

    elif args.scenario == "clique_repetido":
        # 10 linhas, 20 cliques simultâneos em cada.
        base = keys("kind='tela' AND n BETWEEN 200 AND 2000", 10)
        run.start_polling()
        with ThreadPoolExecutor(max_workers=200) as pool:
            list(pool.map(run.request, [k for k in base for _ in range(20)]))
        run.wait_final(args.timeout, settle_after_vanish=30)

    elif args.scenario == "acumula":
        # Produto que acumula: fecha o vigente e os pagamentos em trânsito.
        run.start_polling()
        burst(run, keys("kind='acumula'"), args.rate)
        run.wait_final(args.timeout, settle_after_vanish=30)

    elif args.scenario == "gigante":
        run.start_polling()
        for item in keys("kind='gigante'", order="n"):
            run.request(item)
        run.wait_final(args.timeout, settle_after_vanish=30)

    elif args.scenario == "trava_externa":
        # --locked linhas presas por outra transação por --hold s, no meio de
        # --others pedidos livres.
        locked = keys("kind='tela' AND n BETWEEN 200 AND 2000", args.locked)
        others = keys("kind='tela' AND n BETWEEN 200 AND 2000", args.others, order="key_id DESC")
        ready = threading.Event()
        holder = threading.Thread(target=hold_rows, args=([k["origin"] for k in locked], args.hold, ready), daemon=True)
        holder.start()
        ready.wait(30)
        run.start_polling()
        burst(run, locked + others, 2)
        run.wait_final(args.timeout, settle_after_vanish=30)
        extra["locked_keys"] = [k["key"] for k in locked]

    elif args.scenario == "morto_com_trava":
        # A primeira linha fica presa por --hold s; o orquestrador mata o worker
        # com o fechamento dela parado no UPDATE e sobe outro em seguida.
        items = keys("kind='tela' AND n BETWEEN 200 AND 2000", 5)
        ready = threading.Event()
        threading.Thread(target=hold_rows, args=([items[0]["origin"]], args.hold, ready), daemon=True).start()
        ready.wait(30)
        run.start_polling()
        burst(run, items, args.rate)
        run.wait_final(args.timeout, settle_after_vanish=60)
        extra["locked_keys"] = [items[0]["key"]]

    elif args.scenario in ("so_pedir", "worker_parado", "redis_fora", "worker_morto"):
        # Só dispara; a ação (pausar/matar) é feita de fora pelo orquestrador.
        selection = {
            "so_pedir": "kind='tela' AND n BETWEEN 200 AND 2000",
            "worker_parado": "kind='tela' AND n BETWEEN 200 AND 2000",
            "redis_fora": "kind='tela' AND n < 100",
        }
        items = keys("origem = 'gigante-300k'") + keys("kind='tela' AND n BETWEEN 200 AND 2000", 4) \
            if args.scenario == "worker_morto" else keys(selection[args.scenario], 40 if args.scenario == "redis_fora" else 10)
        run.start_polling()
        burst(run, items, args.rate)
        run.wait_final(args.timeout, settle_after_vanish=60)

    elif args.scenario == "status":
        # 50 telas consultando o status de 5 linhas a cada segundo, por 60 s.
        all_keys = [k["key"] for k in keys("kind='tela'", 250)]
        latencies = []
        def screen(i):
            mine = all_keys[(i * 5) % len(all_keys):][:5]
            end = time.monotonic() + 60
            while time.monotonic() < end:
                t0 = time.monotonic()
                with app.app_context():
                    Service.get_fake_batch_closing_statuses(mine)
                    db.session.remove()
                latencies.append((time.monotonic() - t0) * 1000)
                time.sleep(max(0, 1 - (time.monotonic() - t0)))
        with ThreadPoolExecutor(max_workers=50) as pool:
            list(pool.map(screen, range(50)))
        extra["status_latency_ms"] = _stats(latencies)
        run.start_polling()
        run.stop.set()

    run.report(extra)


if __name__ == "__main__":
    main()
