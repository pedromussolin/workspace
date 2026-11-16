from datetime import date, datetime

from ws.observestatus import (
    day_number,
    day_problem,
    day_window,
    due_day,
    plan_status,
    status_document,
    status_line,
)

EXTRA = frozenset()
OFF = date(2026, 12, 8)
TZ = "America/Sao_Paulo"
PLAN = {
    "task": "TS-5",
    "job": "fechamento de lotes",
    "switched_off": "2026-12-08",
    "days": 5,
    "timezone": TZ,
    "checks": [{"id": "a", "kind": "manual"}, {"id": "b", "kind": "manual"}],
}
HASHES = {"a": "aaa", "b": "bbb"}


def row(day, check, verdict="pass", hash_=None):
    return {"day": day, "check": check, "verdict": verdict, "hash": hash_ or HASHES[check]}


def rows_for(days, verdict="pass"):
    return [row(f"2026-12-{d:02d}", c, verdict) for d in days for c in ("a", "b")]


def status(rows, today):
    return plan_status(PLAN, "demo", HASHES, rows, today, EXTRA)


def test_due_day_and_day_number():
    assert due_day(date(2026, 12, 14), EXTRA) == date(2026, 12, 11)
    assert day_number(date(2026, 12, 11), OFF, EXTRA) == 3
    assert due_day(date(2026, 12, 9), EXTRA) == date(2026, 12, 8)
    assert day_number(date(2026, 12, 8), OFF, EXTRA) == 0


def test_day_window_covers_the_weekend():
    start, end = day_window(date(2026, 12, 14), OFF, TZ, EXTRA)
    assert start.isoformat() == "2026-12-12T00:00:00-03:00"
    assert end.isoformat() == "2026-12-15T00:00:00-03:00"
    start, end = day_window(date(2026, 12, 9), OFF, TZ, EXTRA)
    assert (start.isoformat(), end.isoformat()) == (
        "2026-12-09T00:00:00-03:00",
        "2026-12-10T00:00:00-03:00",
    )
    assert isinstance(start, datetime) and start.tzinfo is not None


def test_day_window_after_a_holiday():
    start, _ = day_window(date(2026, 12, 28), OFF, TZ, EXTRA)
    assert start.isoformat() == "2026-12-25T00:00:00-03:00"


def test_day_window_never_covers_the_switch_off_day():
    start, _ = day_window(date(2026, 12, 14), date(2026, 12, 12), TZ, EXTRA)
    assert start.isoformat() == "2026-12-13T00:00:00-03:00"


def test_day_problem():
    today = date(2026, 12, 14)
    assert "next one is 2026-12-14" in day_problem(date(2026, 12, 12), OFF, today, EXTRA)
    assert "2026-12-25 is not a business day; the next one is 2026-12-28" == day_problem(
        date(2026, 12, 25), OFF, date(2027, 1, 4), EXTRA
    )
    assert day_problem(date(2026, 12, 8), OFF, today, EXTRA) == (
        "2026-12-08 is not after the switch-off day 2026-12-08; day 1 is 2026-12-09"
    )
    assert day_problem(today, OFF, today, EXTRA) == (
        "the window of 2026-12-14 closes at 00:00 of 2026-12-15; "
        "the latest closed day is 2026-12-11"
    )
    assert day_problem(date(2026, 12, 11), OFF, today, EXTRA) is None


def test_status_done_after_n_passing_days():
    entry = status(rows_for([9, 10, 11, 14, 15]), date(2026, 12, 16))
    assert entry["state"] == "done"
    assert entry["streak"] == 5
    assert entry["pending"] == []
    assert entry["day"] == 5


def test_status_pending_today():
    entry = status(rows_for([9, 10]), date(2026, 12, 14))
    assert entry["day"] == 3
    assert entry["pending"] == ["a", "b"]
    assert entry["streak"] == 2
    assert entry["state"] == "observing"


def test_status_failing_day_restarts_the_streak():
    rows = rows_for([9]) + [row("2026-12-10", "a", "fail"), row("2026-12-10", "b")]
    entry = status(rows, date(2026, 12, 11))
    assert entry["attention_days"] == ["2026-12-10"]
    assert entry["state"] == "attention"
    assert entry["streak"] == 0
    rows += rows_for([11, 14, 15, 16, 17])
    entry = status(rows, date(2026, 12, 18))
    assert entry["state"] == "done"
    assert entry["day"] == 7
    assert entry["streak"] == 5


def test_status_missing_and_stale():
    entry = status(rows_for([11]), date(2026, 12, 12))
    assert entry["missing_days"] == ["2026-12-09", "2026-12-10"]
    assert entry["streak"] == 1
    rows = rows_for([9, 11, 14]) + [row("2026-12-10", "a"), row("2026-12-10", "b", hash_="old")]
    entry = status(rows, date(2026, 12, 15))
    assert entry["stale"] == [{"day": "2026-12-10", "check": "b"}]
    assert entry["missing_days"] == ["2026-12-10"]
    assert entry["streak"] == 2
    assert entry["state"] == "observing"


def test_status_rerun_keeps_the_latest_row():
    rows = rows_for([9], "fail") + rows_for([9])
    entry = status(rows, date(2026, 12, 10))
    assert entry["attention_days"] == []
    assert entry["streak"] == 1


def test_status_plan_created_late_starts_from_a_complete_day():
    entry = status(rows_for([14]), date(2026, 12, 15))
    assert entry["missing_days"] == ["2026-12-09", "2026-12-10", "2026-12-11"]
    assert entry["streak"] == 1
    assert entry["day"] == 4


def test_status_waiting_before_day_one():
    entry = status([], date(2026, 12, 9))
    assert entry["state"] == "waiting"
    assert entry["day"] == 0
    assert entry["pending"] == []
    assert entry["first_day"] == "2026-12-09"


def test_status_on_a_weekend_and_after_a_holiday():
    entry = status(rows_for([9, 10, 11]), date(2026, 12, 13))
    assert entry["due_day"] == "2026-12-11"
    assert entry["pending"] == []
    assert entry["streak"] == 3


def test_status_document():
    doc = status_document([{"task": "TS-5"}], date(2026, 12, 14), ["p"])
    assert doc == {
        "version": 1,
        "today": "2026-12-14",
        "plans": [{"task": "TS-5"}],
        "problems": ["p"],
    }


def test_status_line_pt_br():
    entry = status(rows_for([9, 10]), date(2026, 12, 14))
    assert status_line(entry) == (
        "TS-5 (fechamento de lotes): dia 3 de 5, pendente: a, b; 2 dias seguidos ok"
    )
    done = status(rows_for([9, 10, 11, 14, 15]), date(2026, 12, 16))
    assert "pode desligar de vez" in status_line(done)
    bad = status([row("2026-12-09", "a", "fail"), row("2026-12-09", "b")], date(2026, 12, 10))
    assert "atenção em 09/12" in status_line(bad)
    assert status_line(status([], date(2026, 12, 9))).endswith("aguardando o dia 1 (09/12)")


def test_status_line_names_missing_days_and_stale_checks():
    head = "TS-5 (fechamento de lotes): "
    missing = status(rows_for([11]), date(2026, 12, 14))
    assert status_line(missing) == head + "dia 3 de 5; faltam 09/12, 10/12; 1 dia seguido ok"
    one = status(rows_for([10]), date(2026, 12, 11))
    assert status_line(one) == head + "dia 2 de 5; falta 09/12; 1 dia seguido ok"

    rows = rows_for([9, 11, 14]) + [row("2026-12-10", "a"), row("2026-12-10", "b", hash_="old")]
    stale = status(rows, date(2026, 12, 15))
    assert status_line(stale) == (
        head + "dia 4 de 5; falta 10/12; 1 desatualizado; 2 dias seguidos ok"
    )
    rows = rows_for([10]) + [row("2026-12-09", "a", hash_="x"), row("2026-12-09", "b", hash_="y")]
    two = status(rows, date(2026, 12, 11))
    assert status_line(two) == head + "dia 2 de 5; falta 09/12; 2 desatualizados; 1 dia seguido ok"

    late = [row("2026-12-10", "a", "fail"), row("2026-12-10", "b")]
    attention = status(late, date(2026, 12, 11))
    assert status_line(attention) == head + "dia 2 de 5, atenção em 10/12; falta 09/12"
