from datetime import date

from ws.observereport import render
from ws.observestatus import plan_status

TZ = "America/Sao_Paulo"
PLAN = {
    "task": "TS-5",
    "job": "fechamento de lotes",
    "switched_off": "2026-12-08",
    "days": 5,
    "timezone": TZ,
    "checks": [
        {"id": "sweep", "kind": "database", "label": "Varredura", "sql": "select secret_sql"},
        {"id": "calls", "kind": "observability", "query": "secret_query", "signal": "traces"},
        {"id": "ok-man", "kind": "manual", "question": "tudo certo?"},
    ],
}
HASHES = {"sweep": "111111111111", "calls": "222222222222", "ok-man": "333333333333"}


def row(day, check, verdict="pass", value=0, hash_=None, **extra):
    base = {
        "day": day,
        "check": check,
        "verdict": verdict,
        "value": value,
        "hash": hash_ or HASHES[check],
        "started": "2026-12-10T11:02:03Z",
        "finished": "2026-12-10T11:02:05Z",
        "times": "run",
    }
    base.update(extra)
    return base


def build(rows, today=date(2026, 12, 11), title=None, plan=PLAN):
    entry = plan_status(plan, "demo", HASHES, rows, today, frozenset())
    return render(plan, HASHES, rows, entry, title)


def test_report_table_days_and_checks():
    text = build([row("2026-12-09", "sweep"), row("2026-12-10", "sweep", "fail", 3)])
    assert "| Dia | Janela | Varredura | calls | ok-man |" in text
    assert "1 · 09/12" in text
    assert "09/12 00:00 – 10/12 00:00" in text
    assert "0 · ok" in text
    assert "3 · falhou" in text
    assert "—" in text
    assert "Desligado em 08/12/2026" in text and "5 dias" in text and TZ in text


def test_report_real_times_with_offset():
    text = build([row("2026-12-10", "sweep")])
    assert "0 · ok · 08:02:03–08:02:05 (-03:00)" in text


def test_report_verdicts():
    full = [row(f"2026-12-{d:02d}", c) for d in (9, 10, 11, 14, 15) for c in HASHES]
    done = build(full, today=date(2026, 12, 16))
    assert "**Resultado:** pode desligar de vez: 5 dias úteis seguidos ok" in done
    bad_rows = [row("2026-12-09", "sweep", "fail", 2)]
    bad = build(bad_rows, today=date(2026, 12, 10))
    assert "**Resultado:** atenção em 09/12; sequência atual 0 de 5" in bad
    obs = build([row("2026-12-09", c) for c in HASHES], today=date(2026, 12, 11))
    assert "**Resultado:** em observação: dia 2 de 5" in obs


def test_report_manual_record_stale_and_title():
    rows = [
        row("2026-12-09", "ok-man", value=True, by="pat", times="record"),
        row("2026-12-09", "calls", hash_="old"),
    ]
    text = build(rows, today=date(2026, 12, 10), title="Fechamento")
    assert "sim · por pat" in text
    assert "horário do registro" in text
    assert "(desatualizado)" in text
    assert text.startswith("# Observação TS-5: Fechamento")
    assert build(rows, today=date(2026, 12, 10)).startswith(
        "# Observação TS-5: fechamento de lotes"
    )
    assert "Consultas:" in text and "calls 222222222222" in text


def test_report_never_prints_queries():
    text = build([row("2026-12-09", "sweep")])
    assert "secret_sql" not in text and "secret_query" not in text
    assert "111111111111" in text
