import dataclasses
import subprocess
from pathlib import Path

import pytest

from ws.database import guard as neutral_guard
from ws.database.port import Database, Refused, Setup, Unreachable
from ws.database.postgres_adapter import NOT_REPLICA, REASONS, REFUSED, Postgres, from_config

BOUNDS = {
    "day": "2026-12-09",
    "day_from": "2026-12-09T00:00:00-03:00",
    "day_to": "2026-12-10T00:00:00Z",
}


class FakeRun:
    """Stands in for `subprocess.run`: records each call and answers without starting anything."""

    def __init__(self, stdout="0\n", stderr="", returncode=0, raises=None):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.raises = raises
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


def table(path: Path, **extra) -> dict:
    return {
        "engine": "postgres",
        "host": "db.invalid",
        "port": 5432,
        "name": "app",
        "user": "reader",
        "pgpass": str(path),
        **extra,
    }


@pytest.fixture
def pgpass(tmp_path: Path) -> Path:
    path = tmp_path / "pgpass"
    path.write_text("not a real entry\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def database(path: Path, run: FakeRun | None = None, **extra) -> Postgres:
    opened = from_config("replica", table(path, **extra))
    return opened if run is None else dataclasses.replace(opened, run=run)


def test_from_config_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    opened = from_config(
        "replica",
        {"engine": "postgres", "host": "db.invalid", "port": 5432, "name": "app", "user": "r"},
    )
    assert isinstance(opened, Database)
    assert opened.name == "replica"
    assert opened.database == "app"
    assert opened.timeout == 120
    assert opened.replica_only is True
    assert opened.pgpass == tmp_path / "home" / ".pgpass"
    assert opened.runner == "docker"
    assert opened.image == "postgres:16"
    assert opened.docker_args == ()
    assert opened.rules == REFUSED
    assert opened.run is subprocess.run


def test_refused_rules_cover_the_engine():
    assert "\\" in REFUSED.marks and "$" in REFUSED.marks
    assert {"pg_", "lo_"} <= set(REFUSED.prefixes)
    assert {"copy", "do", "set_config", "nextval", "setval", "dblink", "uescape"} <= set(
        REFUSED.words
    )
    assert "dblink" in REFUSED.prefixes
    assert {"query_to_", "cursor_to_", "database_to_", "schema_to_", "table_to_"} <= set(
        REFUSED.prefixes
    )
    assert {"ts_stat", "ts_rewrite", "gin_clean_pending_list"} <= set(REFUSED.words)
    assert "brin_" in REFUSED.prefixes


@pytest.mark.parametrize(
    "sql",
    [
        "select brin_summarize_new_values('t_brin_idx')",
        "select brin_summarize_range('t_brin_idx', 0)",
        "select brin_desummarize_range('t_brin_idx', 0)",
        "select ('t_brin_idx').\"brin_summarize_new_values\"",
        "select gin_clean_pending_list('t_gin_idx')",
        "select ('t_gin_idx').\"gin_clean_pending_list\"",
    ],
)
def test_postgres_rules_refuse_index_maintenance(sql):
    with pytest.raises(Refused):
        neutral_guard.guard(sql, REFUSED)


@pytest.mark.parametrize(
    "sql",
    [
        'select (1.5)."pg_sleep"',
        'select (12345)."pg_terminate_backend"',
        "select ('/etc/hostname').\"pg_read_file\"",
        "select ('sq').\"nextval\"",
        "select ('conn').\"dblink_connect\"",
        "select query_to_xml('select pg_sleep(1)', true, false, '')",
        "select length(query_to_xmlschema('select 1', true, false, '')::text)",
        "select length(query_to_xml_and_xmlschema('select 1', true, false, '')::text)",
        "select length(cursor_to_xml('c', 1, true, false, '')::text)",
        "select count(*) from ts_stat('select to_tsvector(pg_sleep(1)::text)')",
        "select numnode(ts_rewrite('a'::tsquery, 'select a, b from t'))",
        "select length(table_to_xml('t', true, false, '')::text)",
        "select length(schema_to_xml('public', true, false, '')::text)",
        "select length(database_to_xml(true, false, '')::text)",
        'select (1)."QUERY_TO_XML"',
    ],
)
def test_postgres_rules_refuse_attribute_calls_and_sql_strings(sql):
    with pytest.raises(Refused):
        neutral_guard.guard(sql, REFUSED)


@pytest.mark.parametrize(
    "sql",
    [
        "select pg_sleep(1)",
        "select lo_import('/etc/passwd')",
        "select count(*) from t where a = $$x$$",
        "select count(*) from t where a = $1",
        "select 1 \\gexec",
        "select count(*) from t where a = E'\\'' or true",
        "select nextval('s')",
        "select setval('s', 1)",
        "select set_config('statement_timeout', '0', false)",
        "select dblink('conn', 'select 1')",
        "select dblink_exec('conn', 'delete from t')",
        "select \"dblink_exec\"('conn', 'delete from t')",
        "select U&\"!0070g_sleep\" UESCAPE '!' (1)",
        "select count(*) from t where do",
        "select count(*) from t where a = :'HOST'",
        'select count(*) from t where a = :"x"',
    ],
)
def test_postgres_rules_refuse_through_the_guard(sql):
    with pytest.raises(Refused):
        neutral_guard.guard(sql, REFUSED)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT count(*) FROM t WHERE x IN (4, 80)",
        "SELECT sum(amount) FROM t WHERE status = 'open'",
        "SELECT coalesce(sum(v), 0)::numeric FROM t WHERE u >= :day_from AND u < :day_to",
        "SELECT count(*) FROM \"pg_like_name\" WHERE note = 'pg_sleep(1); delete'",
        "WITH open AS (SELECT id FROM batches WHERE closed_at IS NULL) SELECT count(*) FROM open",
        "SELECT count(*) FROM t WHERE replace(code, '.', '') = '123'",
        'SELECT count(*) FROM t WHERE "comment" IS NOT NULL',
        'SELECT count(*) FROM t WHERE "pg_x" > 0',
    ],
)
def test_postgres_rules_keep_plain_reads(sql):
    assert neutral_guard.guard(sql, REFUSED)[0] == sql


def test_postgres_command_mounts_pgpass_read_only(pgpass):
    opened = database(pgpass, docker_args=["--network", "host"])
    argv = opened.command({"day_from": BOUNDS["day_from"], "day_to": BOUNDS["day_to"]})
    assert argv[:5] == ["docker", "run", "--rm", "-i", "--pull=never"]
    assert f"{pgpass}:/tmp/pgpass:ro" in argv
    assert argv[argv.index(f"{pgpass}:/tmp/pgpass:ro") - 1] == "-v"
    assert "PGPASSFILE=/tmp/pgpass" in argv
    image = argv.index("postgres:16")
    assert argv.index("--network") < image
    assert argv[image + 1 :] == [
        "psql",
        "-X",
        "-q",
        "-A",
        "-t",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        "db.invalid",
        "-p",
        "5432",
        "-U",
        "reader",
        "-d",
        "app",
        "-f",
        "-",
        "-v",
        f"day_from={BOUNDS['day_from']}",
        "-v",
        f"day_to={BOUNDS['day_to']}",
    ]


def test_postgres_command_local_runner(pgpass):
    opened = database(pgpass, runner="local")
    argv = opened.command({"day": BOUNDS["day"]})
    assert argv[0] == "psql"
    assert "docker" not in argv
    assert str(pgpass) not in argv
    assert argv[-2:] == ["-v", "day=2026-12-09"]


@pytest.mark.parametrize(
    "bounds",
    [
        {"day": "2026-12-9"},
        {"day": "2026-13-01"},
        {"day": "2026-12-09; drop"},
        {"day_to": "2026-12-10T00:00:00"},
        {"day_to": "2026-12-10 00:00:00-03:00"},
        {"day_to": "2026-12-10T00:00:00-03:00\n\\! id"},
        {"day": 20261209},
        {"ON_ERROR_STOP": "2026-12-09"},
        {"other": "2026-12-09"},
    ],
)
def test_postgres_command_refuses_bad_bounds(pgpass, bounds):
    with pytest.raises(ValueError):
        database(pgpass).command(bounds)


def test_postgres_script_is_read_only_and_wrapped(pgpass):
    script = database(pgpass).script("select count(*) from t where u < :day_to")
    assert script.index("SET statement_timeout = '120s';") < script.index(
        "BEGIN TRANSACTION READ ONLY;"
    )
    assert "SELECT pg_is_in_recovery() AS ws_replica \\gset" in script
    assert "\\if :ws_replica" in script
    assert f"\\echo {NOT_REPLICA}" in script
    assert "\\endif" in script
    assert "SELECT (select count(*) from t where u < :'day_to')::numeric;" in script
    assert script.rstrip().endswith("ROLLBACK;")
    wrapped = script.index("SELECT (select")
    assert script.index("\\if") < wrapped < script.index("\\else") < script.index("ROLLBACK")


def test_postgres_script_quotes_every_placeholder_in_code_only(pgpass):
    script = database(pgpass).script(
        "select count(*) from t where d = :day and u >= :day_from and a = ':day_to' "
        "and b::numeric > 0"
    )
    assert "where d = :'day' and u >= :'day_from' and a = ':day_to' and b::numeric > 0" in script


def test_postgres_script_without_replica_check(pgpass):
    script = database(pgpass, replica_only=False, timeout_seconds=30).script("select 1")
    assert "\\if" not in script
    assert "pg_is_in_recovery" not in script
    assert NOT_REPLICA not in script
    assert "SET statement_timeout = '30s';" in script
    assert "BEGIN TRANSACTION READ ONLY;" in script
    assert "SELECT (select 1)::numeric;" in script
    assert script.rstrip().endswith("ROLLBACK;")


def test_postgres_runs_once_with_the_script_on_stdin(pgpass):
    run = FakeRun(stdout="0\n")
    opened = database(pgpass, run)
    sql = "select count(*) from t where u < :day_to"
    assert opened.scalar_text(sql, {"day_to": BOUNDS["day_to"]}, 120) == "0\n"
    assert len(run.calls) == 1
    argv, kwargs = run.calls[0]
    assert argv == opened.command({"day_to": BOUNDS["day_to"]})
    assert kwargs["input"] == opened.script(sql)
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 150


def test_postgres_timeout_argument_drives_both_timeouts(pgpass):
    run = FakeRun()
    database(pgpass, run).scalar_text("select 1", {}, 10)
    _, kwargs = run.calls[0]
    assert kwargs["timeout"] == 40
    assert "SET statement_timeout = '10s';" in kwargs["input"]


def test_postgres_local_runner_names_the_pgpass_in_the_environment(pgpass, monkeypatch):
    monkeypatch.setenv("WS_TEST_MARK", "kept")
    run = FakeRun()
    database(pgpass, run, runner="local").scalar_text("select 1", {}, 120)
    _, kwargs = run.calls[0]
    assert kwargs["env"]["PGPASSFILE"] == str(pgpass)
    assert kwargs["env"]["WS_TEST_MARK"] == "kept"


def test_postgres_docker_runner_keeps_the_environment(pgpass):
    run = FakeRun()
    database(pgpass, run).scalar_text("select 1", {}, 120)
    _, kwargs = run.calls[0]
    assert kwargs.get("env") is None


def test_postgres_not_a_replica_is_setup(pgpass):
    run = FakeRun(stdout=f"{NOT_REPLICA}\n")
    with pytest.raises(Setup) as caught:
        database(pgpass, run).scalar_text("select 1", {}, 120)
    assert str(caught.value) == "database.replica is not a read replica"


def test_reasons_are_ordered_by_first_match():
    for index, (fragment, _, _) in enumerate(REASONS):
        earlier = [item[0].lower() for item in REASONS[:index]]
        assert not any(seen in fragment.lower() for seen in earlier), fragment


@pytest.mark.parametrize(("fragment", "kind", "text"), REASONS, ids=[r[0] for r in REASONS])
def test_postgres_stderr_becomes_a_fixed_reason(pgpass, fragment, kind, text):
    stderr = f'psql:<stdin>:7: ERROR:  {fragment}: "ABC123"\nDETAIL: row ABC123\n'
    run = FakeRun(stdout="", stderr=stderr, returncode=3)
    with pytest.raises(kind) as caught:
        database(pgpass, run).scalar_text("select 1", {}, 120)
    error = caught.value
    assert type(error) is kind
    assert str(error) == text.format(image="postgres:16")
    assert "ABC123" not in str(error)
    assert "ABC123" not in repr(error.args)
    assert error.__context__ is None
    assert error.__cause__ is None
    assert "ABC123" not in adapter_locals(error)


def adapter_locals(error: BaseException) -> str:
    """The locals the traceback keeps in the adapter's frames, the fake runner left out."""
    kept = []
    trace = error.__traceback__
    while trace is not None:
        frame = trace.tb_frame
        if frame.f_code.co_filename.endswith("postgres_adapter.py"):
            kept += [repr(value) for name, value in frame.f_locals.items() if name != "self"]
        trace = trace.tb_next
    return "\n".join(kept)


@pytest.mark.parametrize(
    ("stderr", "kind"),
    [
        ('ERROR:  invalid input syntax for type numeric: "ABC123"', Refused),
        ("ERROR:  more than one row returned by a subquery used as an expression", Refused),
        ("ERROR:  subquery must return only one column", Refused),
        ("ERROR:  canceling statement due to statement timeout", Unreachable),
        ('psql: error: could not translate host name "db.invalid" to address', Unreachable),
        ('psql: error: FATAL:  password authentication failed for user "reader"', Setup),
        ("docker: Cannot connect to the Docker daemon at unix:///var/run/docker.sock.", Setup),
        ("permission denied while trying to connect to the Docker daemon socket", Setup),
        ('ERROR:  permission denied for table "ABC123"', Unreachable),
        ('ERROR:  syntax error at or near "ABC123"', Refused),
        ('ERROR:  invalid input syntax for type date: "ABC123"', Refused),
        ('ERROR:  invalid input syntax for type integer: "ABC123"', Refused),
        (
            "ERROR:  WITH clause containing a data-modifying statement must be at the top level",
            Refused,
        ),
        ("ERROR:  SELECT ... INTO is not allowed here", Refused),
        ("docker: Error response from daemon: No such image: postgres:16", Setup),
    ],
)
def test_postgres_known_messages(pgpass, stderr, kind):
    run = FakeRun(stdout="", stderr=stderr, returncode=1)
    with pytest.raises(kind) as caught:
        database(pgpass, run).scalar_text("select 1", {}, 120)
    assert type(caught.value) is kind
    assert "ABC123" not in str(caught.value)
    assert caught.value.__context__ is None


def test_postgres_missing_image_says_how_to_pull_it(pgpass):
    stderr = "docker: Error response from daemon: No such image: postgres:16-alpine\n"
    run = FakeRun(stdout="", stderr=stderr, returncode=125)
    with pytest.raises(Setup) as caught:
        database(pgpass, run, image="postgres:16-alpine").scalar_text("select 1", {}, 120)
    assert str(caught.value) == (
        "the image postgres:16-alpine is not on this machine; "
        "pull it once: docker pull postgres:16-alpine"
    )


def test_postgres_unknown_failure_is_unreachable(pgpass):
    run = FakeRun(stdout="ABC123\n", stderr="something new: ABC123", returncode=2)
    with pytest.raises(Unreachable) as caught:
        database(pgpass, run).scalar_text("select 1", {}, 120)
    assert str(caught.value) == "the database refused the query"
    assert caught.value.__context__ is None


def test_postgres_missing_runner_pgpass_or_timeout(pgpass, tmp_path):
    run = FakeRun(raises=FileNotFoundError(2, "No such file", "docker"))
    with pytest.raises(Setup) as caught:
        database(pgpass, run).scalar_text("select 1", {}, 120)
    assert str(caught.value) == "docker not found"
    assert caught.value.__context__ is None

    run = FakeRun(raises=FileNotFoundError(2, "No such file", "psql"))
    with pytest.raises(Setup, match="^psql not found$"):
        database(pgpass, run, runner="local").scalar_text("select 1", {}, 120)

    run = FakeRun()
    with pytest.raises(Setup) as caught:
        database(tmp_path / "absent", run).scalar_text("select 1", {}, 120)
    assert "database.replica.pgpass" in str(caught.value)
    assert run.calls == []

    run = FakeRun()
    with pytest.raises(Setup):
        database(tmp_path, run).scalar_text("select 1", {}, 120)
    assert run.calls == []

    expired = subprocess.TimeoutExpired(["docker"], 150, output="ABC123", stderr="ABC123")
    run = FakeRun(raises=expired)
    with pytest.raises(Unreachable) as caught:
        database(pgpass, run).scalar_text("select 1", {}, 120)
    assert str(caught.value) == "the query timed out"
    assert caught.value.__context__ is None
    assert "ABC123" not in adapter_locals(caught.value)


@pytest.mark.parametrize(
    ("extra", "key"),
    [
        ({"color": "blue"}, "color"),
        ({"port": "x"}, "port"),
        ({"port": 0}, "port"),
        ({"port": 70000}, "port"),
        ({"port": True}, "port"),
        ({"docker_args": "x"}, "docker_args"),
        ({"docker_args": ["--rm", 1]}, "docker_args"),
        ({"timeout_seconds": 0}, "timeout_seconds"),
        ({"timeout_seconds": 601}, "timeout_seconds"),
        ({"timeout_seconds": "120"}, "timeout_seconds"),
        ({"replica_only": "yes"}, "replica_only"),
        ({"runner": "ssh"}, "runner"),
        ({"host": ""}, "host"),
        ({"host": "-oProxyCommand=x"}, "host"),
        ({"host": "db invalid"}, "host"),
        ({"user": 5}, "user"),
        ({"name": ""}, "name"),
        ({"image": "--privileged"}, "image"),
        ({"pgpass": "relative/pgpass"}, "pgpass"),
        ({"pgpass": "/tmp/a:b"}, "pgpass"),
        ({"engine": "other"}, "engine"),
    ],
)
def test_postgres_from_config_refuses_bad_keys(pgpass, extra, key):
    with pytest.raises(Setup) as caught:
        from_config("replica", {**table(pgpass), **extra})
    assert f"database.replica.{key}" in str(caught.value)


@pytest.mark.parametrize("key", ["host", "port", "name", "user"])
def test_postgres_from_config_requires_the_connection_keys(pgpass, key):
    entry = table(pgpass)
    del entry[key]
    with pytest.raises(Setup, match=f"database.replica.{key}"):
        from_config("replica", entry)
