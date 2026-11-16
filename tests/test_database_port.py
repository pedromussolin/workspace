import fcntl
import os
import stat
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import pytest

from ws.database import engines, open_database, scalar
from ws.database.port import Busy, Database, Refused, Rules, Setup

BOUNDS = {
    "day": "2026-12-09",
    "day_from": "2026-12-09T00:00:00-03:00",
    "day_to": "2026-12-10T00:00:00-03:00",
}

REPLICA = """\
[database.replica]
engine = "postgres"
host = "db.invalid"
port = 5432
name = "app"
user = "reader"
"""


@dataclass
class FakeDatabase:
    answer: str = "42\n"
    name: str = "replica"
    timeout: int = 120
    rules: Rules = Rules()
    calls: list = field(default_factory=list)

    def scalar_text(self, sql: str, bounds: dict[str, str], timeout: int) -> str:
        self.calls.append((sql, bounds, timeout))
        return self.answer


@pytest.fixture
def folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "config").mkdir()
    return tmp_path


def write_config(folders: Path, text: str) -> None:
    (folders / "config" / "config.toml").write_text(text, encoding="utf-8")


def test_engines_lists_the_adapters():
    assert engines() == ("postgres",)


def test_open_database_by_engine(folders):
    write_config(folders, REPLICA)
    database = open_database("replica")
    assert isinstance(database, Database)
    assert database.name == "replica"
    assert database.timeout == 120


def test_open_database_unknown_engine(folders):
    write_config(folders, REPLICA.replace('"postgres"', '"nope"'))
    with pytest.raises(Setup) as caught:
        open_database("replica")
    assert str(caught.value) == "database.replica.engine must be one of: postgres"


def test_open_database_without_engine(folders):
    write_config(folders, '[database.replica]\nhost = "db.invalid"\n')
    with pytest.raises(Setup, match="^database.replica.engine must be one of: postgres$"):
        open_database("replica")


@pytest.mark.parametrize("text", [None, "", "[database.other]\nengine = 'postgres'\n"])
def test_open_database_missing_table(folders, text):
    if text is not None:
        write_config(folders, text)
    with pytest.raises(Setup) as caught:
        open_database("replica")
    assert str(caught.value) == "[database.replica] is missing in config.toml"


def test_open_database_malformed_config_is_setup(folders):
    write_config(folders, "[database.replica\n")
    with pytest.raises(Setup):
        open_database("replica")


@pytest.mark.parametrize(
    ("answer", "value"),
    [("42\n", Decimal("42")), ("12.50", Decimal("12.50")), (" -3\n", Decimal("-3"))],
)
def test_scalar_parses_one_number(folders, answer, value):
    database = FakeDatabase(answer=answer)
    assert scalar(database, "select count(*) from t", {}) == value


def test_scalar_null_asks_for_coalesce(folders):
    with pytest.raises(Refused) as caught:
        scalar(FakeDatabase(answer=""), "select sum(a) from t", {})
    assert str(caught.value) == "the query returned null; wrap the aggregate in coalesce(..., 0)"
    with pytest.raises(Refused, match="coalesce"):
        scalar(FakeDatabase(answer="\n"), "select sum(a) from t", {})


@pytest.mark.parametrize(
    "answer", ["1\n2\n", "1|2", "abc", "1.", ".5", "1e5", "NaN", "Infinity", "١٢", "secret-value"]
)
def test_scalar_refuses_anything_but_one_number(folders, answer):
    with pytest.raises(Refused) as caught:
        scalar(FakeDatabase(answer=answer), "select count(*) from t", {})
    assert str(caught.value) == "the query must return one number"


@pytest.mark.parametrize(
    "sql",
    [
        "select 1; select 2",
        "delete from t",
        "with x as (delete from t returning 1) select count(*) from x",
        "select 1 into t2",
        "select 1 -- x",
        "select count(*) from t where u < :other",
        "select vacuum_now()",
    ],
)
def test_scalar_refuses_before_running(folders, sql):
    database = FakeDatabase(rules=Rules(prefixes=("vacuum",)))
    with pytest.raises(Refused):
        scalar(database, sql, BOUNDS)
    assert database.calls == []
    assert not (folders / "data" / "observe.lock").exists()


def test_scalar_lock_busy(folders):
    lock = folders / "held.lock"
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        database = FakeDatabase()
        with pytest.raises(Busy) as caught:
            scalar(database, "select count(*) from t", {}, lock=lock)
        assert str(caught.value) == "another ws observe run holds the database lock"
        assert database.calls == []
    finally:
        os.close(descriptor)


def test_scalar_default_lock_is_private_and_released(folders):
    database = FakeDatabase()
    assert scalar(database, "select count(*) from t", {}) == Decimal("42")
    lock = folders / "data" / "observe.lock"
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600
    descriptor = os.open(lock, os.O_RDWR)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(descriptor)


def test_scalar_releases_the_lock_after_a_failure(folders):
    lock = folders / "run.lock"
    with pytest.raises(Refused):
        scalar(FakeDatabase(answer="x"), "select count(*) from t", {}, lock=lock)
    database = FakeDatabase()
    assert scalar(database, "select count(*) from t", {}, lock=lock) == Decimal("42")


def test_scalar_passes_only_the_placeholders_used(folders):
    database = FakeDatabase()
    scalar(database, "select count(*) from t where u < :day_to;", BOUNDS)
    assert database.calls == [
        ("select count(*) from t where u < :day_to", {"day_to": BOUNDS["day_to"]}, 120)
    ]
    database = FakeDatabase()
    scalar(database, "select count(*) from t", BOUNDS)
    assert database.calls == [("select count(*) from t", {}, 120)]


def test_scalar_refuses_a_placeholder_without_value(folders):
    database = FakeDatabase()
    with pytest.raises(Refused) as caught:
        scalar(database, "select count(*) from t where u < :day_to", {"day": "2026-12-09"})
    assert str(caught.value) == "the query uses :day_to, which has no value in this run"
    assert database.calls == []
