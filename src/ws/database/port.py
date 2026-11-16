"""The database port: what `ws observe` asks of a database, whatever the engine is.

An adapter answers one guarded query with the raw text of its single value; `ws.database.scalar`
guards the SQL, holds the lock and turns that text into one number. No error carries text the
database sent back, since it may hold values from the rows.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class Setup(Exception):
    """The database is not configured or reachable by configuration (exit 2)."""


class Unreachable(Exception):
    """The database did not answer, timed out or refused to run the query (exit 3)."""


class Refused(Exception):
    """The query is not allowed, or its answer is not one number (exit 1)."""


class Busy(Exception):
    """Another run holds the database lock (exit 1)."""


@dataclass(frozen=True)
class Rules:
    """Refusals an engine adds to the neutral guard.

    `words` and `prefixes` apply to the code outside literals, compared lowercased; `marks` apply
    to the whole text, literals included, because they open quoting the neutral split cannot follow.
    """

    words: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()
    marks: tuple[str, ...] = ()


@runtime_checkable
class Database(Protocol):
    name: str
    timeout: int
    rules: Rules

    def scalar_text(self, sql: str, bounds: dict[str, str], timeout: int) -> str: ...
