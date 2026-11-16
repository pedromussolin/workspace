"""Every document `ws observe` reads, writes or prints validates against its contract."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from test_observe_cli import (
    current_hash,
    rows,
    setup_env,
    tool_result,
    write_plan,
    write_result,
    ws,
    ws_json,
)

from ws import observe_cli, observedef
from ws.contracts import validate
from ws.observestatus import day_window

DAY = date(2026, 12, 9)


@pytest.fixture
def env(tmp_path, monkeypatch):
    return setup_env(tmp_path, monkeypatch)


def test_documents_match_their_schemas(env, capsys):
    path = write_plan()
    code, plan_document, _ = ws_json(capsys, "show", "TS-5", "--json")
    assert code == 0
    assert validate(plan_document, "observe-plan") == []

    assert ws(capsys, "run", "TS-5")[0] == 0
    assert ws(capsys, "record", "TS-5", "--check", "file-vs-db", "--yes")[0] == 0
    target = write_result(path, tool_result(path))
    assert ws(capsys, "record", "TS-5", "--result", str(target))[0] == 0
    written = rows(path)
    assert {row["times"] for row in written} == {"run", "record", "tool"}
    for row in written:
        assert validate(row, "observe-result") == []
    hash_ = current_hash(path, "sweep-calls")
    typed = ["--check", "sweep-calls", "--value", "2", "--hash", hash_]
    assert ws(capsys, "record", "TS-5", *typed)[0] == 0
    for row in rows(path):
        assert validate(row, "observe-result") == []

    code, status, _ = ws_json(capsys, "status", "--json")
    assert code == 0
    assert validate(status, "observe-status") == []

    printed = [
        (["run", "TS-5"], "observe-run"),
        (["run", "TS-5", "--day", "2026-12-12"], "observe-run"),
        (["record", "TS-5", "--check", "file-vs-db", "--no"], "observe-record"),
        (["record", "TS-5", "--result", str(target)], "observe-record"),
        (["record", "TS-5", "--check", "file-vs-db", "--day", "x", "--yes"], None),
        (["fallback", "TS-5"], "observe-fallback"),
        (["check", "TS-5"], "observe-check"),
        (["close", "TS-5"], "observe-close"),
        (["close", "TS-5", "--force"], "observe-close"),
        (["show", "TS-5", "--json"], "observe-plan"),
        (["run", "TS-5"], "observe-run"),
        (["record", "TS-5", "--check", "file-vs-db", "--no"], "observe-record"),
    ]
    for argv, contract in printed:
        code, out, err = ws(capsys, *argv)
        if contract is None:
            assert code == 1 and out == "" and err
            continue
        document = json.loads(out)
        assert document["version"] == 1, argv
        assert validate(document, contract) == [], argv

    _, plan = observedef.load_plan(path)
    window = day_window(DAY, plan.switched_off, plan.timezone, frozenset())
    hashes = {check.id: observedef.check_hash(check) for check in plan.checks}
    request = observe_cli.observability_request(plan, DAY, window, hashes)
    assert validate(request, "observability-request") == []
    assert [count["check"] for count in request["counts"]] == ["sweep-calls"]

    check = next(check for check in plan.checks if check.kind == "database")
    bounds = {
        "day": "2026-12-09",
        "day_from": "2026-12-09T03:00:00Z",
        "day_to": "2026-12-10T03:00:00Z",
    }
    database_request = observe_cli.database_request(check, bounds, 120)
    assert validate(database_request, "database-request") == []
    assert database_request["bounds"] == bounds
    started = datetime(2026, 12, 10, 12, 0, tzinfo=UTC)
    finished = datetime(2026, 12, 10, 12, 0, 3, tzinfo=UTC)
    result = observe_cli.database_result(check, Decimal("1.5"), started, finished)
    assert validate(result, "database-result") == []
    assert result["started"] == "2026-12-10T12:00:00Z"


@pytest.mark.parametrize(
    ("argv", "contract"),
    [
        (["run", "TS-5"], "observe-run"),
        (["record", "TS-5", "--check", "file-vs-db", "--yes"], "observe-record"),
        (["fallback", "TS-5"], "observe-fallback"),
        (["check", "TS-5"], "observe-check"),
        (["close", "TS-5", "--force"], "observe-close"),
    ],
)
def test_an_output_that_breaks_its_contract_is_a_problem(env, capsys, monkeypatch, argv, contract):
    write_plan()
    real = observe_cli.contracts.validate

    def broken(document, name):
        return ["$.x: broken on purpose"] if name == contract else real(document, name)

    monkeypatch.setattr(observe_cli.contracts, "validate", broken)
    code, out, err = ws_json(capsys, *argv)
    assert code == 1
    assert out["problems"][-1] == "$.x: broken on purpose"
    assert "ws observe: $.x: broken on purpose" in err
