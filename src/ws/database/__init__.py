"""Databases by name: the engine comes from `[database.<name>] engine` in config.toml.

Every query `ws` runs goes through `scalar`: the neutral guard with the engine's rules, one run at a
time under a lock in the data dir, and an answer of exactly one number.
"""

import fcntl
import importlib
import os
import pkgutil
import re
from decimal import Decimal
from pathlib import Path

from ws.config import data_dir
from ws.database import guard
from ws.database.port import Busy, Database, Refused, Setup
from ws.userconfig import ConfigInvalid, ConfigMissing, load_table

NUMBER = re.compile(r"-?\d+(\.\d+)?", re.ASCII)
LOCK_NAME = "observe.lock"


def engines() -> tuple[str, ...]:
    return tuple(
        sorted(
            module.name.removesuffix("_adapter")
            for module in pkgutil.iter_modules(__path__)
            if module.name.endswith("_adapter")
        )
    )


def open_database(name: str) -> Database:
    try:
        entry = load_table("database").get(name)
    except ConfigMissing:
        entry = None
    except ConfigInvalid as error:
        raise Setup(str(error)) from None
    if not isinstance(entry, dict):
        raise Setup(f"[database.{name}] is missing in config.toml")
    known = engines()
    engine = entry.get("engine")
    if engine not in known:
        raise Setup(f"database.{name}.engine must be one of: {', '.join(known)}")
    return importlib.import_module(f"ws.database.{engine}_adapter").from_config(name, entry)


def scalar(db: Database, sql: str, bounds: dict[str, str], *, lock: Path | None = None) -> Decimal:
    """The one number the query returns; only the placeholders it uses reach the database."""
    text, used = guard.guard(sql, db.rules)
    missing = [name for name in used if name not in bounds]
    if missing:
        raise Refused(f"the query uses :{missing[0]}, which has no value in this run")
    path = lock or data_dir() / LOCK_NAME
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Busy("another ws observe run holds the database lock") from None
        answer = db.scalar_text(text, {name: bounds[name] for name in used}, db.timeout)
    finally:
        os.close(descriptor)
    number = _number(answer)
    # The traceback keeps this frame alive: an answer that is not a number may hold row values.
    del answer
    if isinstance(number, str):
        raise Refused(number)
    return number


def _number(answer: str) -> Decimal | str:
    """The number, or the reason to refuse it; it never raises, so no traceback keeps its frame."""
    value = answer.strip()
    if not value:
        return "the query returned null; wrap the aggregate in coalesce(..., 0)"
    if not NUMBER.fullmatch(value):
        return "the query must return one number"
    return Decimal(value)
