"""`ws observe`: the command, with a fake database, a fixed clock and no tool or tracker reached."""

import getpass
import json
import stat
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from importlib import resources
from pathlib import Path

import pytest
from fake_tracker import FakeTracker, make_card

from ws import bootstrap, cli, database, humans, observe_cli, observedef
from ws.database import open_database as real_open_database
from ws.database.port import Busy, Refused, Rules, Setup, Unreachable
from ws.observeresults import load_rows, results_path
from ws.privatefile import private_folder
from ws.tracker import port
from ws.tracker.port import TrackerError, TrackerSetup

REAL_TODAY = observe_cli._today
OBSERVABILITY = '[observability]\nprovider = "datadog"\n'
REPLICA = """\
[database.replica]
engine = "postgres"
host = "db.invalid"
port = 5432
name = "app"
user = "reader"
"""
CONFIG = OBSERVABILITY + "\n" + REPLICA
QUERY = "service:batch-closer @job:sweep"
SQL = "select count(*) from batches where status = 'open' and updated_at < :day_to"
HEADER = """\
version = 1
task = "TS-5"
job = "fechamento de lotes"
switched_off = 2026-12-08
days = 5
"""
SWEEP = f"""
[[checks]]
id = "sweep-calls"
kind = "observability"
signal = "traces"
query = "{QUERY}"
expect = "== 0"
"""
MANUAL = """
[[checks]]
id = "file-vs-db"
kind = "manual"
question = "O arquivo do dia bate com o banco?"
"""


def database_check(check_id: str = "open-batches", sql: str = SQL, expect: str = "== 0") -> str:
    return (
        f'\n[[checks]]\nid = "{check_id}"\nkind = "database"\n'
        f"sql = '''{sql}'''\nexpect = \"{expect}\"\n"
    )


PLAN = HEADER + SWEEP + database_check() + MANUAL
STUCK = database_check("stuck-files", "select count(*) from files where stuck")
WINDOW = ["2026-12-09T03:00:00Z", "2026-12-10T03:00:00Z"]


@dataclass
class FakeDatabase:
    """Answers by a fragment of the SQL; an exception as the answer is raised."""

    answers: dict
    name: str = "replica"
    timeout: int = 120
    rules: Rules = Rules()
    calls: list = field(default_factory=list)

    def scalar_text(self, sql: str, bounds: dict[str, str], timeout: int) -> str:
        self.calls.append((sql, bounds, timeout))
        for fragment, answer in self.answers.items():
            if fragment in sql:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        raise AssertionError("the fake has no answer for this query")


class Clock:
    def __init__(self, start: datetime):
        self.moment = start

    def __call__(self) -> datetime:
        current = self.moment
        self.moment += timedelta(seconds=1)
        return current


@dataclass
class Env:
    root: Path
    fake: FakeDatabase
    opened: list
    gate: list
    monkeypatch: pytest.MonkeyPatch

    def set_today(self, day: date) -> None:
        self.monkeypatch.setattr(observe_cli, "_today", lambda timezone=None: day)

    def write_config(self, text: str) -> None:
        (self.root / "config" / "config.toml").write_text(text, encoding="utf-8")


def no_tracker():
    raise TrackerSetup("no task tracker in the tests")


def setup_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    (tmp_path / "config").mkdir()
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(tmp_path / "claude" / "settings.json"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fake = FakeDatabase({"from batches": "0\n", "from files": "0\n"})
    opened: list[str] = []
    gate: list[Path] = []

    def open_fake(name: str) -> FakeDatabase:
        opened.append(name)
        return fake

    def no_gate_problems(path: Path) -> list[str]:
        gate.append(path)
        return []

    monkeypatch.setattr(database, "open_database", open_fake)
    monkeypatch.setattr(observe_cli, "_today", lambda timezone=None: date(2026, 12, 10))
    monkeypatch.setattr(observe_cli, "_now", Clock(datetime(2026, 12, 10, 12, 0, tzinfo=UTC)))
    monkeypatch.setattr(humans, "by_hand", lambda: False)
    monkeypatch.setattr(bootstrap, "observe_gate_problems", no_gate_problems)
    monkeypatch.setattr(port, "open_tracker", no_tracker)
    monkeypatch.setattr(getpass, "getuser", lambda: "tester")
    env = Env(tmp_path, fake, opened, gate, monkeypatch)
    env.write_config(CONFIG)
    return env


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    return setup_env(tmp_path, monkeypatch)


def ws(capsys, *argv: str) -> tuple[int, str, str]:
    code = cli.main(["observe", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def ws_json(capsys, *argv: str) -> tuple[int, dict, str]:
    code, out, err = ws(capsys, *argv)
    return code, json.loads(out), err


def write_plan(text: str = PLAN, project: str = "demo", task: str = "TS-5") -> Path:
    path = observedef.plan_path(project, task)
    private_folder(path.parent)
    path.write_text(text.replace('task = "TS-5"', f'task = "{task}"'), encoding="utf-8")
    path.chmod(0o600)
    return path


def rows(path: Path) -> list[dict]:
    return load_rows(results_path(path))


def current_hash(path: Path, check_id: str) -> str:
    _, plan = observedef.load_plan(path)
    return observedef.check_hash(next(check for check in plan.checks if check.id == check_id))


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


NEW = ["--project", "demo", "--job", "fechamento de lotes", "--switched-off", "2026-12-08"]


def test_new_writes_a_private_plan(env, capsys):
    code, out, _ = ws_json(capsys, "new", "TS-5", *NEW)
    assert code == 0
    path = observedef.plan_path("demo", "TS-5")
    assert out == {"task": "TS-5", "project": "demo", "path": str(path)}
    assert mode(path) == 0o600
    assert mode(path.parent) == 0o700
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {
        "version": 1,
        "task": "TS-5",
        "job": "fechamento de lotes",
        "switched_off": date(2026, 12, 8),
        "days": 5,
        "timezone": "America/Sao_Paulo",
    }
    code, _, err = ws(capsys, "new", "TS-5", *NEW)
    assert code == 1
    assert err.startswith("ws observe: ") and "exists" in err


@pytest.mark.parametrize(
    "change",
    [
        {0: "ts-5"},
        {"--project": "Demo"},
        {"--switched-off": "2026-13-01"},
        {"--switched-off": "20261208"},
        {"--job": "  "},
        {"--days": "0"},
        {"--days": "x"},
        {"--days": "31"},
        {"--timezone": "No/Such_Zone"},
    ],
)
def test_new_refuses_bad_input(env, capsys, change):
    argv = ["TS-6", *NEW, "--days", "5", "--timezone", "America/Sao_Paulo"]
    for key, value in change.items():
        index = 0 if key == 0 else argv.index(key) + 1
        argv[index] = value
    code, out, err = ws(capsys, "new", *argv)
    assert code == 1
    assert out == ""
    assert err.startswith("ws observe: ")
    assert not (env.root / "data" / "projects").exists()


def test_check_validates_and_tightens(env, capsys):
    path = write_plan()
    path.chmod(0o644)
    code, out, _ = ws_json(capsys, "check", "TS-5")
    assert code == 0
    assert out["problems"] == []
    assert out["checks"] == ["sweep-calls", "open-batches", "file-vs-db"]
    assert f"{path}: mode 644 set to 600" in out["warnings"]
    assert mode(path) == 0o600
    assert env.opened == ["replica"]
    assert env.fake.calls == []


def test_check_refuses_a_write_and_a_duplicate(env, capsys):
    hidden = "with x as (delete from batches returning 1) select count(*) from x"
    write_plan(HEADER + database_check(sql=hidden))
    code, out, err = ws_json(capsys, "check", "TS-5")
    assert code == 1
    assert out["problems"] == ['open-batches: "delete" is not allowed outside a literal']
    assert "open-batches" in err
    write_plan(HEADER + database_check() + database_check())
    code, out, _ = ws_json(capsys, "check", "TS-5")
    assert code == 1
    assert "duplicate open-batches" in out["problems"][0]


def test_check_uses_the_rules_of_the_database(env, capsys):
    write_plan()
    env.fake.rules = Rules(words=("batches",))
    code, out, _ = ws_json(capsys, "check", "TS-5")
    assert code == 1
    assert out["problems"] == [
        'open-batches: "batches" is not allowed outside a literal; '
        'quote it and drop the table qualifier: "batches"'
    ]


def test_check_with_the_real_adapter_rules(env, capsys, monkeypatch):
    monkeypatch.setattr(database, "open_database", real_open_database)
    write_plan(HEADER + database_check(sql="select count(*) from pg_stat_activity"))
    code, out, _ = ws_json(capsys, "check", "TS-5")
    assert code == 1
    assert out["problems"] == ["open-batches: words starting with pg_ are not allowed"]


def test_check_without_the_database_config_uses_the_neutral_rules(env, capsys, monkeypatch):
    monkeypatch.setattr(database, "open_database", real_open_database)
    env.write_config(OBSERVABILITY)
    write_plan()
    code, out, _ = ws_json(capsys, "check", "TS-5")
    assert code == 0
    assert out["warnings"] == [
        "database replica: [database.replica] is missing in config.toml; "
        "its checks were guarded by the neutral rules only"
    ]


def test_show_json_is_the_contract(env, capsys):
    path = write_plan()
    code, out, _ = ws_json(capsys, "show", "TS-5", "--json")
    assert code == 0
    assert out == observedef.plan_document(tomllib.loads(path.read_text(encoding="utf-8")))
    code, text, _ = ws(capsys, "show", "TS-5")
    assert code == 0
    assert "open-batches (database)" in text
    assert SQL not in text


def test_run_records_database_checks(env, capsys):
    path = write_plan()
    code, out, err = ws_json(capsys, "run", "TS-5")
    assert code == 0, err
    assert out["task"] == "TS-5"
    assert out["day"] == "2026-12-09"
    assert out["day_number"] == 1
    assert out["window"] == WINDOW
    assert out["recorded"] == [{"check": "open-batches", "value": 0, "verdict": "pass"}]
    [row] = rows(path)
    assert row["check"] == "open-batches"
    assert row["verdict"] == "pass"
    assert row["times"] == "run"
    assert row["window"] == WINDOW
    assert row["started"] == "2026-12-10T12:00:00Z"
    assert row["finished"] == "2026-12-10T12:00:01Z"
    assert "by" not in row
    result = path.parent / "TS-5.2026-12-09.result.json"
    assert out["version"] == 1
    assert out["observability"] == {
        "tool": "execute_code",
        "checks": ["sweep-calls"],
        "next": "ws observe request TS-5 --day 2026-12-09",
        "record": f"ws observe record TS-5 --result {result}",
        "fallback": "ws observe fallback TS-5 --day 2026-12-09",
        "result_path": str(result),
    }
    assert out["ask"] == [
        {
            "check": "file-vs-db",
            "question": "O arquivo do dia bate com o banco?",
            "yes": "ws observe record TS-5 --check file-vs-db --day 2026-12-09 --yes",
            "no": "ws observe record TS-5 --check file-vs-db --day 2026-12-09 --no",
        }
    ]
    assert out["problems"] == [] and out["warnings"] == []
    [(_, bounds, timeout)] = env.fake.calls
    assert bounds == {"day_to": "2026-12-10T03:00:00Z"}
    assert timeout == 120
    assert env.gate == [env.root / "claude" / "settings.json"]


def test_run_rerun_same_day_replaces(env, capsys):
    path = write_plan()
    assert ws(capsys, "run", "TS-5")[0] == 0
    env.fake.answers["from batches"] = "3\n"
    code, out, _ = ws_json(capsys, "run", "TS-5")
    assert code == 0
    assert out["recorded"] == [{"check": "open-batches", "value": 3, "verdict": "fail"}]
    [row] = rows(path)
    assert (row["value"], row["verdict"]) == (3, "fail")


def test_run_asks_only_what_has_no_current_row(env, capsys):
    write_plan()
    assert ws(capsys, "record", "TS-5", "--check", "file-vs-db", "--yes")[0] == 0
    code, out, _ = ws_json(capsys, "run", "TS-5", "--check", "file-vs-db")
    assert code == 0
    assert out["ask"] == []
    assert out["observability"] is None
    assert env.fake.calls == []


@pytest.mark.parametrize(
    ("day", "today", "named"),
    [
        ("2026-12-12", date(2026, 12, 10), "the next one is 2026-12-14"),
        ("2026-12-25", date(2026, 12, 28), "the next one is 2026-12-28"),
        ("2026-12-10", date(2026, 12, 10), "the latest closed day is 2026-12-09"),
        ("2026-12-08", date(2026, 12, 10), "day 1 is 2026-12-09"),
        ("2026-12-32", date(2026, 12, 10), "--day"),
    ],
)
def test_run_refuses_weekend_holiday_and_open_days(env, capsys, day, today, named):
    path = write_plan()
    env.set_today(today)
    code, out, err = ws(capsys, "run", "TS-5", "--day", day)
    assert code == 1
    assert named in err
    assert env.fake.calls == []
    assert not results_path(path).exists()


def test_run_refuses_an_unknown_check(env, capsys):
    path = write_plan()
    code, _, err = ws(capsys, "run", "TS-5", "--check", "nope")
    assert code == 1
    assert "unknown check nope" in err
    assert env.fake.calls == []
    assert not results_path(path).exists()


def test_run_snapshot_sql_warns_on_a_past_day(env, capsys):
    write_plan(HEADER + database_check(sql="select count(*) from batches where status = 'open'"))
    env.set_today(date(2026, 12, 14))
    code, out, _ = ws_json(capsys, "run", "TS-5", "--day", "2026-12-09")
    assert code == 0
    assert out["warnings"] == [
        "open-batches reads the current state; its value for 2026-12-09 is as of now"
    ]
    code, out, _ = ws_json(capsys, "run", "TS-5")
    assert out["day"] == "2026-12-11"
    assert out["warnings"] == []


def test_run_failures_keep_going_and_rank(env, capsys):
    path = write_plan(HEADER + database_check() + STUCK)
    unreachable = "the database is unreachable; check the VPN and the port"
    env.fake.answers["from batches"] = Unreachable(unreachable)
    code, out, err = ws_json(capsys, "run", "TS-5")
    assert code == 3
    assert [row["check"] for row in rows(path)] == ["stuck-files"]
    assert out["problems"] == [f"open-batches: {unreachable}"]
    assert f"ws observe: open-batches: {unreachable}" in err

    env.fake.calls.clear()
    env.fake.answers["from batches"] = Setup("the database runner is not available")
    code, out, _ = ws_json(capsys, "run", "TS-5")
    assert code == 2
    assert len(env.fake.calls) == 1

    env.fake.answers["from batches"] = Refused("the query must return one number")
    env.fake.answers["from files"] = Unreachable("the query timed out")
    assert ws(capsys, "run", "TS-5")[0] == 3

    env.fake.answers["from files"] = "0\n"
    code, out, _ = ws_json(capsys, "run", "TS-5")
    assert code == 1
    assert out["recorded"] == [{"check": "stuck-files", "value": 0, "verdict": "pass"}]

    env.fake.answers["from batches"] = Busy("another ws observe run holds the database lock")
    assert ws(capsys, "run", "TS-5")[0] == 1


@pytest.mark.parametrize("answer", ["", "\n", "12|7\n", "secret-text\n", "1\n2\n"])
def test_run_refuses_anything_but_one_number(env, capsys, answer):
    path = write_plan(HEADER + database_check())
    env.fake.answers["from batches"] = answer
    code, out, err = ws(capsys, "run", "TS-5")
    assert code == 1
    assert not results_path(path).exists()
    if answer.strip():
        assert answer.strip() not in out + err


@pytest.mark.parametrize(
    ("sql", "accepted"),
    [
        ("select count(*) from batches; select 1", False),
        ("select count(*) from batches where note = 'a;b'", True),
        ('select count(*) from batches where "odd;name" = 1', True),
        ("with x as (delete from batches returning 1) select count(*) from x", False),
        ("select count(*) into kept from batches", False),
    ],
)
def test_run_refuses_bad_sql_before_any_query(env, capsys, sql, accepted):
    path = write_plan(HEADER + STUCK + database_check(sql=sql))
    code, out, _ = ws_json(capsys, "run", "TS-5")
    if accepted:
        assert code == 0
        assert len(env.fake.calls) == 2
        return
    assert code == 1
    assert env.fake.calls == []
    assert not results_path(path).exists()
    assert out["problems"][0].startswith("open-batches: ")


def test_run_needs_the_gate_before_a_database_query(env, capsys, monkeypatch):
    path = write_plan()
    missing = "permissions.ask lacks the rule for this command"
    monkeypatch.setattr(bootstrap, "observe_gate_problems", lambda settings: [missing])
    code, _, err = ws(capsys, "run", "TS-5")
    assert code == 2
    assert missing in err and "ws setup" in err
    assert env.fake.calls == []
    assert not results_path(path).exists()
    code, out, _ = ws_json(capsys, "run", "TS-5", "--check", "file-vs-db")
    assert code == 0
    assert out["ask"][0]["check"] == "file-vs-db"
    monkeypatch.setattr(humans, "by_hand", lambda: True)
    assert ws(capsys, "run", "TS-5")[0] == 0
    assert len(env.fake.calls) == 1


def test_request_prints_the_program_verbatim(env, capsys, monkeypatch):
    path = write_plan()
    monkeypatch.setattr(bootstrap, "observe_gate_problems", lambda settings: ["no gate"])
    code, out, err = ws(capsys, "request", "TS-5", "--day", "2026-12-09")
    assert code == 0, err
    template = resources.files("ws.data").joinpath("datadog_count.js").read_text(encoding="utf-8")
    assert out.startswith(template.splitlines()[0] + "\n")
    [line] = [text for text in out.splitlines() if text.startswith("const P = ")]
    params = json.loads(line.removeprefix("const P = ").removesuffix(";"))
    assert params == {
        "version": 1,
        "task": "TS-5",
        "day": "2026-12-09",
        "counts": [
            {
                "check": "sweep-calls",
                "signal": "traces",
                "query": QUERY,
                "from": WINDOW[0],
                "to": WINDOW[1],
                "hash": current_hash(path, "sweep-calls"),
            }
        ],
    }
    assert env.fake.calls == []
    assert ws(capsys, "request", "TS-5")[1] == out


def test_request_needs_an_observability_check(env, capsys):
    write_plan(HEADER + database_check())
    code, _, err = ws(capsys, "request", "TS-5")
    assert code == 1
    assert "no observability check" in err


def test_fallback_prints_classic_calls(env, capsys):
    path = write_plan()
    code, out, _ = ws_json(capsys, "fallback", "TS-5")
    assert code == 0
    assert out["version"] == 1
    assert out["task"] == "TS-5"
    assert out["day"] == "2026-12-09"
    assert out["problems"] == []
    [call] = out["calls"]
    assert call["check"] == "sweep-calls"
    assert call["tool"] == "aggregate_spans"
    assert call["arguments"]["from"] == WINDOW[0]
    assert call["arguments"]["to"] == WINDOW[1]
    hash_ = current_hash(path, "sweep-calls")
    assert out["record"] == [
        {
            "check": "sweep-calls",
            "hash": hash_,
            "command": (
                f"ws observe record TS-5 --check sweep-calls --day 2026-12-09 --hash {hash_} "
                "--value <N>"
            ),
        }
    ]


def tool_result(path: Path, **changes) -> dict:
    document = {
        "version": 1,
        "task": "TS-5",
        "day": "2026-12-09",
        "provider": "any",
        "counts": [
            {
                "check": "sweep-calls",
                "hash": current_hash(path, "sweep-calls"),
                "value": 0,
                "started": "2026-12-10T12:30:00Z",
                "finished": "2026-12-10T12:30:02Z",
            }
        ],
        "failed": [],
    }
    document.update(changes)
    return document


def write_result(path: Path, document: dict | None, text: str | None = None) -> Path:
    target = path.parent / "TS-5.2026-12-09.result.json"
    target.write_text(json.dumps(document) if text is None else text, encoding="utf-8")
    target.chmod(0o644)
    return target


def test_record_result_checks_hashes(env, capsys):
    path = write_plan()
    stale = tool_result(path)
    stale["counts"][0]["hash"] = "000000000000"
    target = write_result(path, stale)
    code, out, _ = ws_json(capsys, "record", "TS-5", "--result", str(target))
    assert code == 1
    assert out["problems"] == [
        "sweep-calls changed since the request; run ws observe request again"
    ]
    assert rows(path) == []
    assert mode(target) == 0o600

    target = write_result(path, tool_result(path))
    code, out, _ = ws_json(capsys, "record", "TS-5", "--result", str(target))
    assert code == 0
    assert out["recorded"] == [{"check": "sweep-calls", "value": 0, "verdict": "pass"}]
    [row] = rows(path)
    assert row["times"] == "tool"
    assert row["started"] == "2026-12-10T12:30:00Z"
    assert row["finished"] == "2026-12-10T12:30:02Z"
    assert row["window"] == WINDOW
    assert mode(target) == 0o600

    echo = f"query {QUERY} failed\nsecond line"
    failed = [{"check": "sweep-calls", "reason": echo}, {"check": QUERY, "reason": "x"}]
    target = write_result(path, tool_result(path, counts=[], failed=failed))
    code, out, err = ws_json(capsys, "record", "TS-5", "--result", str(target))
    assert code == 0
    assert out["warnings"] == [
        "sweep-calls: the observability tool gave no count; run ws observe fallback for it",
        "a check with an unknown id: the observability tool gave no count; "
        "run ws observe fallback for it",
    ]
    assert QUERY not in json.dumps(out) + err
    assert len(rows(path)) == 1


@pytest.mark.parametrize(
    ("change", "text", "named", "parsed"),
    [
        ({"task": "TS-6"}, None, "TS-6", True),
        ({"day": "2026-12-10"}, None, "the latest closed day is 2026-12-09", True),
        ({"day": "09/12/2026"}, None, "day", True),
        ({"failed": None}, None, "$.failed", True),
        ({"version": 2}, None, "$.version", True),
        ({}, "{not json", "not JSON", False),
        ({}, '{"value": NaN}', "not JSON", False),
        ({}, "[]", "not a JSON object", False),
        ({}, " " * (1024 * 1024 + 1), "larger than 1 MiB", False),
    ],
)
def test_record_result_refuses_a_bad_document(env, capsys, change, text, named, parsed):
    path = write_plan()
    target = write_result(path, tool_result(path, **change), text)
    code, out, err = ws(capsys, "record", "TS-5", "--result", str(target))
    assert code == 1
    assert named in err
    assert rows(path) == []
    assert mode(target) == (0o600 if parsed else 0o644)


@pytest.mark.parametrize(
    ("count", "named"),
    [
        ({"check": "open-batches"}, "open-batches is not an observability check of TS-5"),
        ({"check": "nope"}, "nope is not an observability check of TS-5"),
        ({"check": QUERY}, "a check with an unknown id is not an observability check"),
        ({"started": "yesterday"}, "sweep-calls: started"),
        ({"finished": "2026-12-10T12:30:02"}, "sweep-calls: finished"),
        ({"value": -1}, "sweep-calls: the count must be a finite number, zero or more"),
        ({"value": -0.5}, "sweep-calls: the count must be a finite number, zero or more"),
    ],
)
def test_record_result_refuses_a_bad_count(env, capsys, count, named):
    path = write_plan()
    document = tool_result(path)
    document["counts"][0].update(count)
    code, out, err = ws_json(
        capsys, "record", "TS-5", "--result", str(write_result(path, document))
    )
    assert code == 1
    assert named in out["problems"][0]
    assert QUERY not in json.dumps(out) + err
    assert rows(path) == []


def test_record_result_refuses_an_infinite_count(env, capsys):
    path = write_plan()
    text = json.dumps(tool_result(path)).replace('"value": 0', '"value": 1e400')
    assert "1e400" in text
    code, out, _ = ws_json(
        capsys, "record", "TS-5", "--result", str(write_result(path, None, text))
    )
    assert code == 1
    assert out["problems"] == ["sweep-calls: the count must be a finite number, zero or more"]
    assert rows(path) == []


def test_record_result_changes_no_mode_outside_the_plan_folder(env, capsys):
    path = write_plan()
    outside = env.root / "elsewhere.json"
    outside.write_text(json.dumps(tool_result(path)), encoding="utf-8")
    outside.chmod(0o644)
    code, _, _ = ws(capsys, "record", "TS-5", "--result", str(outside))
    assert code == 0
    assert len(rows(path)) == 1
    assert mode(outside) == 0o644

    script = env.root / "script.sh"
    script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    script.chmod(0o755)
    code, _, err = ws(capsys, "record", "TS-5", "--result", str(script))
    assert code == 1
    assert "not JSON" in err
    assert mode(script) == 0o755


def test_record_result_never_follows_a_symlink(env, capsys):
    path = write_plan()
    target = env.root / "elsewhere.json"
    target.write_text(json.dumps(tool_result(path)), encoding="utf-8")
    target.chmod(0o755)
    link = path.parent / "TS-5.2026-12-09.result.json"
    link.symlink_to(target)
    code, _, err = ws(capsys, "record", "TS-5", "--result", str(link))
    assert code == 1
    assert "a symbolic link" in err
    assert mode(target) == 0o755
    assert rows(path) == []

    folder = path.parent / "a-folder.json"
    folder.mkdir()
    code, _, err = ws(capsys, "record", "TS-5", "--result", str(folder))
    assert code == 1
    assert "not a regular file" in err


def test_record_one_rules(env, capsys):
    path = write_plan()
    code, _, err = ws(capsys, "record", "TS-5", "--check", "open-batches", "--value", "0")
    assert code == 1
    assert "database checks are recorded by ws observe run" in err

    code, out, _ = ws_json(capsys, "record", "TS-5", "--check", "file-vs-db", "--yes")
    assert code == 0
    [row] = rows(path)
    assert (row["value"], row["verdict"], row["by"], row["times"]) == (
        True,
        "pass",
        "tester",
        "record",
    )
    assert row["day"] == "2026-12-09"

    code, out, _ = ws_json(
        capsys,
        "record",
        "TS-5",
        "--check",
        "file-vs-db",
        "--day",
        "2026-12-09",
        "--no",
        "--by",
        "ana",
    )
    assert code == 0
    [row] = rows(path)
    assert (row["value"], row["verdict"], row["by"]) == (False, "fail", "ana")

    hash_ = current_hash(path, "sweep-calls")
    code, out, _ = ws_json(
        capsys, "record", "TS-5", "--check", "sweep-calls", "--value", "0", "--hash", hash_
    )
    assert code == 0
    recorded = {row["check"]: row for row in rows(path)}
    assert recorded["sweep-calls"]["times"] == "record"
    assert recorded["sweep-calls"]["value"] == 0
    assert recorded["sweep-calls"]["started"] == recorded["sweep-calls"]["finished"]


@pytest.mark.parametrize(
    ("argv", "named"),
    [
        (["--check", "sweep-calls", "--value", "0", "--hash", "000000000000"], "changed since"),
        (["--check", "sweep-calls", "--value", "0"], "--hash"),
        (["--check", "sweep-calls", "--yes"], "sweep-calls is an observability check"),
        (["--check", "file-vs-db", "--value", "1"], "file-vs-db is a manual check"),
        (["--check", "file-vs-db", "--yes", "--no"], "exactly one of"),
        (["--check", "file-vs-db"], "exactly one of"),
        (["--check", "sweep-calls", "--value", "-1", "--hash", "x"], "--value"),
        (["--check", "nope", "--yes"], "unknown check nope"),
        (["--check", "file-vs-db", "--yes", "--day", "2026-12-12"], "not a business day"),
        (["--check", "file-vs-db", "--yes", "--by", "a\nb"], "--by"),
        (["--result", "x.json", "--check", "file-vs-db"], "--result"),
        ([], "--result FILE or --check ID"),
    ],
)
def test_record_one_refusals(env, capsys, argv, named):
    path = write_plan()
    code, _, err = ws(capsys, "record", "TS-5", *argv)
    assert code == 1
    assert named in err
    assert rows(path) == []


def test_an_edited_plan_makes_old_rows_stale(env, capsys):
    path = write_plan()
    old = current_hash(path, "sweep-calls")
    assert ws(capsys, "run", "TS-5")[0] == 0
    path.write_text(PLAN.replace('expect = "== 0"', 'expect = "<= 1"'), encoding="utf-8")
    code, out, _ = ws_json(capsys, "status", "--json")
    assert out["plans"][0]["stale"] == [{"day": "2026-12-09", "check": "open-batches"}]
    code, _, err = ws(
        capsys, "record", "TS-5", "--check", "sweep-calls", "--value", "0", "--hash", old
    )
    assert code == 1
    assert "sweep-calls changed since the request" in err


def test_a_late_plan_backfills_with_day(env, capsys):
    write_plan(HEADER + database_check())
    env.set_today(date(2026, 12, 15))
    _, out, _ = ws_json(capsys, "status", "--json")
    assert out["plans"][0]["missing_days"] == ["2026-12-09", "2026-12-10", "2026-12-11"]
    for day in ("2026-12-09", "2026-12-10"):
        assert ws(capsys, "run", "TS-5", "--day", day)[0] == 0
    _, out, _ = ws_json(capsys, "status", "--json")
    assert out["plans"][0]["missing_days"] == ["2026-12-11"]
    assert out["plans"][0]["streak"] == 0


def test_status_json_text_and_problems(env, capsys):
    write_plan()
    write_plan(project="other", task="TS-6")
    code, out, _ = ws_json(capsys, "status", "--json")
    assert code == 0
    assert out["today"] == "2026-12-10"
    assert out["problems"] == []
    assert [(p["project"], p["task"]) for p in out["plans"]] == [
        ("demo", "TS-5"),
        ("other", "TS-6"),
    ]
    code, out, _ = ws_json(capsys, "status", "--project", "demo", "--json")
    assert [p["task"] for p in out["plans"]] == ["TS-5"]
    code, text, _ = ws(capsys, "status", "--project", "demo")
    assert code == 0
    assert "TS-5 (fechamento de lotes): dia 1 de 5" in text

    broken = observedef.plan_path("other", "TS-6")
    broken.write_text("version = 1\ntask = [", encoding="utf-8")
    code, out, _ = ws_json(capsys, "status", "--json")
    assert code == 1
    assert [p["task"] for p in out["plans"]] == ["TS-5"]
    assert str(broken) in out["problems"][0]
    code, text, err = ws(capsys, "status")
    assert code == 1
    assert "TS-5" in text and "TS-6" not in text
    assert str(broken) in err

    assert ws(capsys, "status", "--project", "Bad")[0] == 1


def test_status_refuses_a_plan_named_after_another_task(env, capsys):
    write_plan()
    other = observedef.plan_path("demo", "TS-6")
    other.write_text(PLAN, encoding="utf-8")
    code, out, _ = ws_json(capsys, "status", "--json")
    assert code == 1
    assert [p["task"] for p in out["plans"]] == ["TS-5"]
    assert "does not match the file name" in out["problems"][0]


def test_report_with_and_without_the_tracker(env, capsys, monkeypatch):
    write_plan()
    assert ws(capsys, "run", "TS-5")[0] == 0
    code, out, err = ws(capsys, "report", "TS-5")
    assert code == 0
    assert out.startswith("# Observação TS-5: fechamento de lotes\n")
    assert err.startswith("ws observe: warning: ") and "no task tracker in the tests" in err

    tracker = FakeTracker([make_card("TS-5", title="Desligar o fechamento de lotes")])
    monkeypatch.setattr(port, "open_tracker", lambda: tracker)
    code, out, err = ws(capsys, "report", "TS-5")
    assert code == 0
    assert out.startswith("# Observação TS-5: Desligar o fechamento de lotes\n")
    assert err == ""
    assert tracker.reads == ["TS-5"]

    for error in (TrackerError("timed out"), OSError("network is down")):

        def failing(error=error):
            raise error

        monkeypatch.setattr(port, "open_tracker", failing)
        code, out, err = ws(capsys, "report", "TS-5")
        assert code == 0
        assert out.startswith("# Observação TS-5: fechamento de lotes\n")
        assert "warning" in err

    monkeypatch.setattr(port, "open_tracker", lambda: FakeTracker([]))
    code, out, err = ws(capsys, "report", "TS-5")
    assert code == 0
    assert "TS-5 was not found" in err


def test_two_plans_need_project(env, capsys):
    write_plan()
    write_plan(project="other")
    for argv in (
        ["run", "TS-5"],
        ["show", "TS-5"],
        ["check", "TS-5"],
        ["report", "TS-5"],
        ["close", "TS-5", "--force"],
    ):
        code, _, err = ws(capsys, *argv)
        assert code == 1
        assert "TS-5 has plans in demo, other; pass --project" in err
    assert env.fake.calls == []
    code, out, _ = ws_json(capsys, "run", "TS-5", "--project", "other")
    assert code == 0
    assert out["observability"]["next"] == (
        "ws observe request TS-5 --project other --day 2026-12-09"
    )
    other = observedef.plan_path("other", "TS-5").parent / "TS-5.2026-12-09.result.json"
    assert out["observability"]["record"] == (
        f"ws observe record TS-5 --project other --result {other}"
    )
    assert out["observability"]["fallback"] == (
        "ws observe fallback TS-5 --project other --day 2026-12-09"
    )
    assert out["ask"][0]["yes"] == (
        "ws observe record TS-5 --project other --check file-vs-db --day 2026-12-09 --yes"
    )


def test_unknown_provider_exits_2(env, capsys):
    path = write_plan()
    env.write_config('[observability]\nprovider = "nope"\n\n' + REPLICA)
    code, out, err = ws_json(capsys, "run", "TS-5")
    assert code == 2
    assert "nope" in err
    assert env.fake.calls == []
    assert not results_path(path).exists()
    for command in ("request", "fallback"):
        code, _, err = ws(capsys, command, "TS-5")
        assert code == 2
        assert "nope" in err
    assert ws(capsys, "run", "TS-5", "--check", "open-batches")[0] == 0


def test_bad_holidays_config_exits_2(env, capsys):
    write_plan()
    env.write_config(CONFIG + '\n[workdays]\nholidays = ["25/12"]\n')
    for argv in (["run", "TS-5"], ["status"], ["request", "TS-5"], ["report", "TS-5"]):
        code, _, err = ws(capsys, *argv)
        assert code == 2, argv
        assert "workdays.holidays" in err
    assert env.fake.calls == []


def test_outputs_never_carry_queries_or_rows(env, capsys):
    write_plan()
    env.fake.answers["from batches"] = "7\n"
    texts = []
    for argv in (["run", "TS-5"], ["status"], ["status", "--json"], ["report", "TS-5"]):
        code, out, err = ws(capsys, *argv)
        assert code == 0
        texts.append(out + err)
    for text in texts:
        assert SQL not in text
        assert QUERY not in text
        assert "from batches" not in text


def test_today_is_the_plan_zones(env, capsys, monkeypatch):
    monkeypatch.setattr(observe_cli, "_today", REAL_TODAY)
    monkeypatch.setattr(observe_cli, "_now", lambda: datetime(2026, 12, 11, 1, 0, tzinfo=UTC))
    assert observe_cli._today("America/Sao_Paulo") == date(2026, 12, 10)
    assert observe_cli._today("UTC") == date(2026, 12, 11)
    write_plan()
    in_utc = PLAN.replace("days = 5\n", 'days = 5\ntimezone = "UTC"\n')
    write_plan(in_utc, project="other", task="TS-6")
    code, out, _ = ws_json(capsys, "status", "--json")
    assert code == 0
    assert {p["task"]: p["due_day"] for p in out["plans"]} == {
        "TS-5": "2026-12-09",
        "TS-6": "2026-12-10",
    }
    assert ws_json(capsys, "run", "TS-5")[1]["day"] == "2026-12-09"
    assert ws_json(capsys, "run", "TS-6")[1]["day"] == "2026-12-10"
    assert ws_json(capsys, "fallback", "TS-6")[1]["day"] == "2026-12-10"
    code, out, _ = ws(capsys, "report", "TS-6")
    assert code == 0 and "dia 2 de 5" in out


LOGS = """
[[checks]]
id = "job-errors"
kind = "observability"
signal = "logs"
query = "service:batch-closer status:error"
expect = "== 0"
"""


def program_counts(text: str) -> list[str]:
    [line] = [each for each in text.splitlines() if each.startswith("const P = ")]
    params = json.loads(line.removeprefix("const P = ").removesuffix(";"))
    return [count["check"] for count in params["counts"]]


def test_a_check_subset_reaches_the_request(env, capsys):
    write_plan(PLAN + LOGS)
    code, out, _ = ws_json(capsys, "run", "TS-5")
    assert out["observability"]["checks"] == ["sweep-calls", "job-errors"]
    assert out["observability"]["next"] == "ws observe request TS-5 --day 2026-12-09"
    code, out, _ = ws_json(capsys, "run", "TS-5", "--check", "job-errors")
    assert code == 0
    assert out["observability"]["checks"] == ["job-errors"]
    assert out["observability"]["next"] == (
        "ws observe request TS-5 --day 2026-12-09 --check job-errors"
    )
    assert out["observability"]["fallback"] == (
        "ws observe fallback TS-5 --day 2026-12-09 --check job-errors"
    )
    assert ws_json(capsys, "run", "TS-5", "--check", "file-vs-db")[1]["observability"] is None

    code, text, _ = ws(capsys, "request", "TS-5", "--day", "2026-12-09", "--check", "job-errors")
    assert code == 0
    assert program_counts(text) == ["job-errors"]
    assert program_counts(ws(capsys, "request", "TS-5")[1]) == ["sweep-calls", "job-errors"]
    code, out, _ = ws_json(capsys, "fallback", "TS-5", "--check", "job-errors")
    assert [call["check"] for call in out["calls"]] == ["job-errors"]
    assert [item["check"] for item in out["record"]] == ["job-errors"]

    for command in ("request", "fallback"):
        code, _, err = ws(capsys, command, "TS-5", "--check", "open-batches")
        assert code == 1
        assert "open-batches is not an observability check of TS-5" in err
        code, _, err = ws(capsys, command, "TS-5", "--check", "nope")
        assert code == 1
        assert "unknown check nope" in err


DAYS = ("2026-12-09", "2026-12-10", "2026-12-11", "2026-12-14", "2026-12-15")


def done_plan(env: Env, capsys) -> Path:
    path = write_plan(HEADER + MANUAL)
    env.set_today(date(2026, 12, 16))
    for day in DAYS:
        argv = ["record", "TS-5", "--check", "file-vs-db", "--day", day, "--yes"]
        assert ws(capsys, *argv)[0] == 0
    return path


def test_close_a_done_plan(env, capsys):
    path = done_plan(env, capsys)
    assert ws_json(capsys, "status", "--json")[1]["plans"][0]["state"] == "done"
    code, out, err = ws_json(capsys, "close", "TS-5")
    assert code == 0, err
    assert out == {
        "version": 1,
        "task": "TS-5",
        "project": "demo",
        "path": str(path),
        "closed": "2026-12-16",
        "problems": [],
        "warnings": [],
    }
    assert mode(path) == 0o600
    assert 'days = 5\nclosed = "2026-12-16"\n' in path.read_text(encoding="utf-8")

    code, out, _ = ws_json(capsys, "status", "--json")
    assert code == 0
    assert out["plans"] == []
    assert ws(capsys, "status")[1] == "nenhuma observação\n"

    env.set_today(date(2026, 12, 18))
    code, text, _ = ws(capsys, "report", "TS-5")
    assert code == 0
    assert "observação encerrada em 16/12/2026" in text
    assert "**Resultado:** pode desligar de vez: 5 dias úteis seguidos ok" in text
    assert "6 · 16/12" not in text
    code, shown, _ = ws_json(capsys, "show", "TS-5", "--json")
    assert code == 0
    assert shown["closed"] == "2026-12-16"
    assert "closed 2026-12-16" in ws(capsys, "show", "TS-5")[1]

    code, out, _ = ws_json(capsys, "close", "TS-5")
    assert code == 1
    assert out["problems"] == ["TS-5 was closed on 2026-12-16"]


def test_close_refuses_a_plan_that_is_not_done(env, capsys):
    path = write_plan()
    text = path.read_text(encoding="utf-8")
    code, out, err = ws_json(capsys, "close", "TS-5")
    assert code == 1
    assert out["closed"] is None
    assert out["problems"] == [
        "TS-5 is not done (observing, day 1 of 5); pass --force to close it anyway"
    ]
    assert "--force" in err
    assert path.read_text(encoding="utf-8") == text

    code, out, _ = ws_json(capsys, "close", "TS-5", "--force")
    assert code == 0
    assert out["closed"] == "2026-12-10"
    assert out["warnings"] == ["TS-5 was closed before it was done (observing)"]
    assert mode(path) == 0o600


def test_a_closed_plan_records_nothing(env, capsys):
    path = write_plan()
    assert ws(capsys, "close", "TS-5", "--force")[0] == 0
    target = write_result(path, tool_result(path))
    refused = "TS-5 was closed on 2026-12-10; it records nothing more"
    for argv in (
        ["run", "TS-5"],
        ["record", "TS-5", "--check", "file-vs-db", "--yes"],
        ["record", "TS-5", "--result", str(target)],
    ):
        code, out, _ = ws_json(capsys, *argv)
        assert code == 1, argv
        assert out["problems"] == [refused]
    for command in ("request", "fallback"):
        code, out, err = ws(capsys, command, "TS-5")
        assert code == 1
        assert out == ""
        assert refused in err
    assert rows(path) == []
    assert env.fake.calls == []
    assert ws(capsys, "check", "TS-5")[0] == 0
