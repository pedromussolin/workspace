"""Pending previews shared by the commands that write only after a separate approval.

A preview stores a private record named by its code; the approval reads it back. No function here
reads the clock: callers pass `now`, so each command keeps its own patchable clock."""

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timedelta
from pathlib import Path

APPROVAL_WINDOW = timedelta(minutes=30)
CODE = re.compile(r"[0-9a-f]{12}")


def session_id() -> int:
    """The session of the shell that runs this command. Claude Code runs each Bash call in its own
    session, so a preview and an approval in one command line share it and are refused."""
    return os.getsid(0)


def digest(material: object) -> str:
    text = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def ensure_store(folder: Path) -> None:
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)


def write_pending(folder: Path, code: str, record: dict) -> None:
    path = folder / f"{code}.json"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False)
        path.chmod(0o600)
    except (OSError, TypeError, ValueError):
        path.unlink(missing_ok=True)
        raise


def read_pending(
    folder: Path, code: str, *, now: datetime, preview: str
) -> tuple[dict | None, str | None]:
    """(record, None) usable; (None, None) absent; (None, reason) present but refused."""
    path = folder / f"{code}.json"
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, None
    except OSError as error:
        return None, f"cannot read the pending record: {error.strerror}"
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        return None, (
            f"the pending record {code} is not a private file of yours (owner, mode 600); "
            f"delete it and run {preview} again"
        )
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        created = datetime.fromisoformat(record["created_at"])
        if created.tzinfo is None:
            raise ValueError("no time zone")
    except (OSError, ValueError, KeyError, TypeError):
        return None, f"the pending record {code} is unreadable; run {preview} again"
    if created > now:
        return None, f"the pending record {code} is in the future; run {preview} again"
    record["_created"] = created
    return record, None


def purge_expired(folder: Path, *, now: datetime, preview: str) -> None:
    for path in folder.glob("*.json"):
        record, _ = read_pending(folder, path.stem, now=now, preview=preview)
        if record is None or now - record["_created"] > APPROVAL_WINDOW:
            path.unlink(missing_ok=True)
