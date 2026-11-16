"""Postgres through psql, in a throwaway Docker container by default, with the user's pgpass.

`ws` never opens the pgpass file: Docker mounts it read-only and libpq reads it. Each query runs
under a statement timeout in a read-only transaction that is rolled back, after a check that the
server is a read replica, wrapped as `SELECT (<sql>)::numeric` so that rows, two columns or text
fail on the server. psql's stderr may hold values from the rows: it is matched against `REASONS`,
turned into a fixed text and dropped.
"""

import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ws.database.guard import PLACEHOLDER, PLACEHOLDERS, split
from ws.database.port import Refused, Rules, Setup, Unreachable

# `dblink` is a prefix too: `dblink_exec` writes through another connection, outside the
# read-only transaction. `uescape` would let `U&"..."` spell any name without a backslash.
# `query_to_`, `cursor_to_`, `ts_stat` and `ts_rewrite` run SQL held in a literal, where the guard
# does not look; `table_to_`, `schema_to_` and `database_to_` dump whole tables or schemas.
REFUSED = Rules(
    words=(
        "copy",
        "do",
        "vacuum",
        "analyze",
        "listen",
        "notify",
        "prepare",
        "discard",
        "load",
        "comment",
        "set_config",
        "nextval",
        "setval",
        "dblink",
        "uescape",
        "ts_stat",
        "ts_rewrite",
    ),
    prefixes=(
        "pg_",
        "lo_",
        "dblink",
        "query_to_",
        "cursor_to_",
        "database_to_",
        "schema_to_",
        "table_to_",
    ),
    marks=("\\", "$"),
)
NOT_REPLICA = "ws-not-a-replica"
KEYS = (
    "engine",
    "timeout_seconds",
    "replica_only",
    "host",
    "port",
    "name",
    "user",
    "pgpass",
    "runner",
    "image",
    "docker_args",
)
RUNNERS = ("docker", "local")
DEFAULT_TIMEOUT = 120
DEFAULT_PGPASS = "~/.pgpass"
DEFAULT_IMAGE = "postgres:16"
PGPASS_IN_CONTAINER = "/tmp/pgpass"
PGPASS_VARIABLE = "PGPASSFILE"
TIMEOUT_MARGIN = 30
PLAIN = re.compile(r"[^\s-]\S*")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
MOMENT = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})", re.ASCII
)

TIMED_OUT = "the query timed out"
UNREACHABLE = "the database is unreachable; check the VPN and the port"
LOGIN = "the database refused the login; check the pgpass entry"
ONE_NUMBER = "the query must return one number"
NOT_A_NUMBER = "the query result is not a number"
WRITE = "the query tried to write; only reads are allowed"
REASONS: tuple[tuple[str, type[Exception], str], ...] = (
    ("statement timeout", Unreachable, TIMED_OUT),
    (
        "conflict with recovery",
        Unreachable,
        "the replica canceled the query while applying changes; run it again",
    ),
    ("Cannot connect to the Docker daemon", Setup, "Docker is not running"),
    ("Docker daemon socket", Setup, "Docker refused access to its socket; check the docker group"),
    (
        "No such image",
        Setup,
        "the image {image} is not on this machine; pull it once: docker pull {image}",
    ),
    (
        "Error response from daemon",
        Setup,
        "Docker could not start the container; check the image and docker_args",
    ),
    ("could not connect", Unreachable, UNREACHABLE),
    ("could not translate host", Unreachable, UNREACHABLE),
    ("Connection refused", Unreachable, UNREACHABLE),
    ("timeout expired", Unreachable, UNREACHABLE),
    ("password authentication failed", Setup, LOGIN),
    ("no password supplied", Setup, LOGIN),
    ("FATAL", Setup, "the database refused the connection; check host, name and user"),
    ("more than one row", Refused, ONE_NUMBER),
    ("must return only one column", Refused, ONE_NUMBER),
    ("invalid input syntax for type numeric", Refused, NOT_A_NUMBER),
    ("invalid input syntax", Refused, "the query compares a value of the wrong type"),
    ("cannot cast", Refused, NOT_A_NUMBER),
    ("read-only transaction", Refused, WRITE),
    ("during recovery", Refused, WRITE),
    ("data-modifying statement", Refused, WRITE),
    ("INTO is not allowed here", Refused, WRITE),
    ("syntax error", Refused, "the database found a syntax error in the query"),
    ("does not exist", Refused, "the query names a table, column or function that does not exist"),
    ("permission denied", Unreachable, "the database refused the query: permission denied"),
)
UNKNOWN_FAILURE = "the database refused the query"


@dataclass(frozen=True)
class Postgres:
    name: str
    timeout: int
    replica_only: bool
    host: str
    port: int
    database: str
    user: str
    pgpass: Path
    runner: str
    image: str
    docker_args: tuple[str, ...]
    rules: Rules = REFUSED
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run

    def command(self, bounds: dict[str, str]) -> list[str]:
        """The argv; each bound becomes a psql variable, once it is an ISO date or moment."""
        for bound, value in bounds.items():
            _check_bound(bound, value)
        psql = [
            "psql",
            "-X",
            "-q",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            self.host,
            "-p",
            str(self.port),
            "-U",
            self.user,
            "-d",
            self.database,
            "-f",
            "-",
        ]
        for bound in PLACEHOLDERS:
            if bound in bounds:
                psql += ["-v", f"{bound}={bounds[bound]}"]
        if self.runner == "local":
            return psql
        return [
            "docker",
            "run",
            "--rm",
            "-i",
            "--pull=never",
            *self.docker_args,
            "-v",
            f"{self.pgpass}:{PGPASS_IN_CONTAINER}:ro",
            "-e",
            f"{PGPASS_VARIABLE}={PGPASS_IN_CONTAINER}",
            self.image,
            *psql,
        ]

    def script(self, sql: str, timeout: int | None = None) -> str:
        """What psql reads on stdin; `timeout` defaults to the configured one."""
        seconds = self.timeout if timeout is None else timeout
        query = f"SELECT ({_quote_placeholders(sql)})::numeric;"
        lines = [f"SET statement_timeout = '{int(seconds)}s';", "BEGIN TRANSACTION READ ONLY;"]
        if self.replica_only:
            lines += [
                "SELECT pg_is_in_recovery() AS ws_replica \\gset",
                "\\if :ws_replica",
                query,
                "\\else",
                f"\\echo {NOT_REPLICA}",
                "\\endif",
            ]
        else:
            lines.append(query)
        lines.append("ROLLBACK;")
        return "\n".join(lines) + "\n"

    def scalar_text(self, sql: str, bounds: dict[str, str], timeout: int) -> str:
        if not self.pgpass.is_file():
            raise Setup(f"database.{self.name}.pgpass names no file; create it or fix the path")
        outcome = self._call(self.command(bounds), self.script(sql, timeout), timeout)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome.returncode != 0:
            failure = _reason(outcome.stderr, self.image)
            # The traceback keeps this frame alive: drop the stderr before raising.
            del outcome
            raise failure
        if outcome.stdout.strip() == NOT_REPLICA:
            raise Setup(f"database.{self.name} is not a read replica")
        return outcome.stdout

    def _call(
        self, argv: list[str], script: str, timeout: int
    ) -> subprocess.CompletedProcess | Exception:
        """The run, or the error to raise once outside this `except`, so no error keeps the
        original one (and its captured output) as `__context__`."""
        environment = None
        if self.runner == "local":
            environment = {**os.environ, PGPASS_VARIABLE: str(self.pgpass)}
        try:
            return self.run(
                argv,
                input=script,
                capture_output=True,
                text=True,
                timeout=timeout + TIMEOUT_MARGIN,
                env=environment,
            )
        except FileNotFoundError:
            return Setup(f"{argv[0]} not found")
        except subprocess.TimeoutExpired:
            return Unreachable(TIMED_OUT)


def from_config(name: str, table: dict) -> Postgres:
    for key in table:
        if key not in KEYS:
            raise Setup(f"database.{name}.{key} is not a known key; use: {', '.join(KEYS)}")
    if table.get("engine") != "postgres":
        raise Setup(f'database.{name}.engine must be "postgres" for this adapter')
    timeout = table.get("timeout_seconds", DEFAULT_TIMEOUT)
    if not _integer_between(timeout, 1, 600):
        raise Setup(f"database.{name}.timeout_seconds must be an integer from 1 to 600")
    replica_only = table.get("replica_only", True)
    if not isinstance(replica_only, bool):
        raise Setup(f"database.{name}.replica_only must be true or false")
    port = table.get("port")
    if not _integer_between(port, 1, 65535):
        raise Setup(f"database.{name}.port must be an integer from 1 to 65535")
    runner = table.get("runner", "docker")
    if runner not in RUNNERS:
        raise Setup(f"database.{name}.runner must be one of: {', '.join(RUNNERS)}")
    docker_args = table.get("docker_args", [])
    if not isinstance(docker_args, list) or not all(isinstance(arg, str) for arg in docker_args):
        raise Setup(f"database.{name}.docker_args must be a list of strings")
    return Postgres(
        name=name,
        timeout=timeout,
        replica_only=replica_only,
        host=_plain(name, table, "host"),
        port=port,
        database=_plain(name, table, "name"),
        user=_plain(name, table, "user"),
        pgpass=_pgpass(name, table),
        runner=runner,
        image=_plain(name, table, "image", DEFAULT_IMAGE),
        docker_args=tuple(docker_args),
    )


def _integer_between(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _plain(name: str, table: dict, key: str, default: str | None = None) -> str:
    """A value that goes into the argv: no spaces, and never read as an option."""
    value = table.get(key, default)
    if not isinstance(value, str) or not PLAIN.fullmatch(value):
        raise Setup(
            f"database.{name}.{key} must be a non-empty text without spaces, not starting with -"
        )
    return value


def _pgpass(name: str, table: dict) -> Path:
    value = table.get("pgpass", DEFAULT_PGPASS)
    path = Path(value).expanduser() if isinstance(value, str) and value else None
    if path is None or not path.is_absolute() or ":" in str(path):
        raise Setup(f"database.{name}.pgpass must be an absolute path (~ allowed) without :")
    return path


def _check_bound(bound: str, value: str) -> None:
    if bound not in PLACEHOLDERS:
        raise ValueError(f"unknown bound {bound!r}")
    if isinstance(value, str) and DAY.fullmatch(value):
        date.fromisoformat(value)
    elif isinstance(value, str) and MOMENT.fullmatch(value):
        datetime.fromisoformat(value)
    else:
        raise ValueError(f"bound {bound} must be an ISO date or an ISO date-time with offset")


def _quote_placeholders(sql: str) -> str:
    """`:day` becomes `:'day'`, so psql inserts the value as a quoted literal (a bare
    `2026-12-09` would be arithmetic); literals and identifiers stay as they are."""
    return "".join(
        PLACEHOLDER.sub(_quoted, text) if kind == "code" else text for kind, text in split(sql)
    )


def _quoted(match: re.Match) -> str:
    return f":'{match.group(1)}'" if match.group(1) in PLACEHOLDERS else match.group()


def _reason(stderr: str | None, image: str) -> Exception:
    """The fixed text for a failure; only the configured image name is filled in, never stderr."""
    lowered = (stderr or "").lower()
    for fragment, kind, text in REASONS:
        if fragment.lower() in lowered:
            return kind(text.format(image=image))
    return Unreachable(UNKNOWN_FAILURE)
