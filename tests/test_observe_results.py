import json
import stat
import threading
import time
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ws import observeresults
from ws.observedef import Check, Invalid

STARTED = datetime(2026, 12, 9, 12, 0, tzinfo=UTC)
FINISHED = datetime(2026, 12, 9, 12, 1, tzinfo=UTC)
WINDOW = (datetime(2026, 12, 9, 3, 0, tzinfo=UTC), datetime(2026, 12, 10, 3, 0, tzinfo=UTC))


def row(check, day, value, **extra):
    return observeresults.make_row(
        check, day, value, started=STARTED, finished=FINISHED, window=WINDOW, times="day", **extra
    )


def test_make_row_verdicts_values_and_times():
    count = Check(id="a", kind="observability", signal="logs", query="q", expect="<= 2")
    zero = row(count, date(2026, 12, 9), Decimal("0"))
    assert zero["value"] == 0
    assert isinstance(zero["value"], int)
    assert zero["verdict"] == "pass"
    failed = row(count, date(2026, 12, 9), Decimal("2.5"))
    assert failed["value"] == 2.5
    assert failed["verdict"] == "fail"
    manual = Check(id="m", kind="manual", question="ok?")
    answered = row(manual, date(2026, 12, 9), False, by="ana")
    assert answered["verdict"] == "fail"
    assert answered["expect"] is None
    assert answered["by"] == "ana"
    assert zero["started"].endswith("Z")
    assert zero["day"] == "2026-12-09"
    assert zero["check"] == "a"


def test_put_row_replaces_the_same_day_and_check(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path))
    path = tmp_path / "TS-5.results.jsonl"
    check = Check(id="a", kind="observability", signal="logs", query="q", expect="== 0")
    observeresults.put_row(path, row(check, date(2026, 12, 10), Decimal(0)))
    observeresults.put_row(path, row(check, date(2026, 12, 9), Decimal(1)))
    observeresults.put_row(path, row(check, date(2026, 12, 9), Decimal(0)))
    rows = observeresults.load_rows(path)
    assert [(r["day"], r["check"]) for r in rows] == [("2026-12-09", "a"), ("2026-12-10", "a")]
    assert rows[0]["verdict"] == "pass"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert len(path.read_text().splitlines()) == 2


def test_put_row_locks_the_read_and_the_replace(tmp_path, monkeypatch):
    """Two writers at once: the second reads only after the first has replaced the file."""
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path))
    path = tmp_path / "TS-5.results.jsonl"
    first = row(Check(id="a", kind="manual", question="ok?"), date(2026, 12, 9), True)
    second = row(Check(id="b", kind="manual", question="ok?"), date(2026, 12, 9), True)
    real = observeresults.load_rows
    loaded = threading.Event()

    def slow_load(target):
        found = real(target)
        if threading.current_thread().name == "first":
            loaded.set()
            time.sleep(0.3)
        return found

    monkeypatch.setattr(observeresults, "load_rows", slow_load)
    writer = threading.Thread(target=observeresults.put_row, args=(path, first), name="first")
    writer.start()
    assert loaded.wait(5)
    observeresults.put_row(path, second)
    writer.join(5)
    assert [each["check"] for each in real(path)] == ["a", "b"]
    lock = tmp_path / "TS-5.results.jsonl.lock"
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600


def test_results_path_is_beside_the_plan(tmp_path):
    assert observeresults.results_path(tmp_path / "TS-5.toml") == tmp_path / "TS-5.results.jsonl"


def test_load_rows_absent_and_bad_line(tmp_path):
    path = tmp_path / "TS-5.results.jsonl"
    assert observeresults.load_rows(path) == []
    path.write_text(json.dumps({"day": "x"}) + "\nnot json\n")
    with pytest.raises(Invalid) as caught:
        observeresults.load_rows(path)
    assert str(caught.value) == f"{path} line 2: not JSON"


def test_put_row_refuses_a_row_without_day_or_check(tmp_path):
    with pytest.raises(Invalid):
        observeresults.put_row(tmp_path / "TS-5.results.jsonl", {"day": "2026-12-09"})


def test_make_row_refuses_a_value_of_the_wrong_kind():
    manual = Check(id="m", kind="manual", question="ok?")
    with pytest.raises(Invalid):
        row(manual, date(2026, 12, 9), Decimal(1))
    counted = Check(id="a", kind="database", sql="s", expect="== 0", database="replica")
    with pytest.raises(Invalid):
        row(counted, date(2026, 12, 9), True)
