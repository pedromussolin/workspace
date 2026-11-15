import json
import stat
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


def test_results_path_is_beside_the_plan(tmp_path):
    assert observeresults.results_path(tmp_path / "TS-5.toml") == tmp_path / "TS-5.results.jsonl"


def test_load_rows_absent_and_bad_line(tmp_path):
    path = tmp_path / "TS-5.results.jsonl"
    assert observeresults.load_rows(path) == []
    path.write_text(json.dumps({"day": "x"}) + "\nnot json\n")
    with pytest.raises(Invalid) as caught:
        observeresults.load_rows(path)
    assert str(caught.value) == f"{path} line 2: not JSON"
