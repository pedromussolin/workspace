"""The daily results rows (`<TASK>.results.jsonl`, beside the plan, mode 600)."""

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ws.observedef import PRIVATE_FILE, RESULTS_SUFFIX, Check, Invalid, check_hash, meets
from ws.privatefile import private_file

LOCK_SUFFIX = ".lock"


def results_path(plan: Path) -> Path:
    return plan.with_name(f"{plan.stem}{RESULTS_SUFFIX}")


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            raise Invalid(f"{path} line {number}: not JSON") from None
        if not isinstance(row, dict):
            raise Invalid(f"{path} line {number}: not JSON")
        rows.append(row)
    return rows


def utc_text(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def make_row(
    check: Check,
    day: date,
    value: Decimal | bool,
    *,
    started: datetime,
    finished: datetime,
    window: tuple[datetime, datetime],
    times: str,
    by: str | None = None,
) -> dict:
    if (check.kind == "manual") != isinstance(value, bool):
        raise Invalid(f"{check.id}: a {check.kind} check cannot take {value!r}")
    if isinstance(value, bool):
        stored: int | float | bool = value
        passed = value is True
    else:
        stored = number(value)
        passed = meets(value, check.expect)
    row = {
        "version": 1,
        "day": day.isoformat(),
        "check": check.id,
        "kind": check.kind,
        "value": stored,
        "expect": check.expect,
        "verdict": "pass" if passed else "fail",
        "started": utc_text(started),
        "finished": utc_text(finished),
        "window": [utc_text(window[0]), utc_text(window[1])],
        "hash": check_hash(check),
        "times": times,
    }
    if by is not None:
        row["by"] = by
    return row


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """An exclusive lock on `<results>.lock`, beside the results: two runs of one plan at once
    would each read the rows, add one and replace the file, and the first row would be lost."""
    lock = path.with_name(path.name + LOCK_SUFFIX)
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, PRIVATE_FILE)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def put_row(path: Path, row: dict) -> None:
    if "day" not in row or "check" not in row:
        raise Invalid("row: day and check are required")
    key = (row["day"], row["check"])
    with _locked(path):
        rows = [r for r in load_rows(path) if (r.get("day"), r.get("check")) != key]
        rows.append(row)
        rows.sort(key=lambda r: (str(r.get("day", "")), str(r.get("check", ""))))
        with private_file(path) as stream:
            for each in rows:
                stream.write((json.dumps(each, ensure_ascii=False, sort_keys=True) + "\n").encode())
