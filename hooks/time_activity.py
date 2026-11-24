"""UserPromptSubmit hook: records that the user was working on a card, for the time report.

On every prompt it appends one `activity` event to the month file of the time log
(`<data dir>/timelog/<YYYY-MM>.jsonl`): the local time, the repo and branch of the session's
working directory and the card ref taken from the branch name (`<kind>/<PROJ>-<n>-...`), or null
outside a card branch. `ws time report` turns runs of these events into hours.

It finds the branch by reading `.git/HEAD` (following a worktree's `gitdir` file), so it spawns
nothing. It never blocks a prompt and never prints: every path exits 0, and a failure leaves one
line in the error log.

Standard library only; it never imports or runs `ws`. It honors the `WS_DATA_DIR` and
`WS_CACHE_DIR` overrides the tests use.
"""

import json
import os
import re
import signal
import sys
from datetime import datetime
from pathlib import Path

DEADLINE = 1.0
EVENT_VERSION = 1
MAX_DEPTH = 64
ERROR_LOG_LINES = 200
CARD_BRANCH = re.compile(r"[^/]+/([A-Z][A-Z0-9_]*-[1-9]\d*)(?:-|$)")
SESSION_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")
HEAD_PREFIX = "ref: refs/heads/"


class _Deadline(Exception):
    pass


def _data_dir() -> Path:
    override = os.environ.get("WS_DATA_DIR")
    return Path(override) if override else Path.home() / ".local" / "share" / "workspace"


def _cache_dir() -> Path:
    override = os.environ.get("WS_CACHE_DIR")
    return Path(override) if override else Path.home() / ".cache" / "workspace"


def log_error(what: str) -> None:
    """One line `<iso time> time_activity <what>`; never the prompt."""
    try:
        log = _cache_dir() / "hooks" / "errors.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        lines = [*lines[-(ERROR_LOG_LINES - 1) :], f"{stamp} time_activity {what}"]
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _find_git(start: Path) -> tuple[Path, Path] | None:
    """The folder that holds `.git` and the git directory itself, walking up from `start`."""
    folder = start
    for _ in range(MAX_DEPTH):
        marker = folder / ".git"
        if marker.is_dir():
            return folder, marker
        if marker.is_file():
            pointer = _read(marker)
            if pointer.startswith("gitdir:"):
                target = Path(pointer[len("gitdir:") :].strip())
                return folder, target if target.is_absolute() else folder / target
            return None
        if folder.parent == folder:
            return None
        folder = folder.parent
    return None


def _repo_name(folder: Path, git_dir: Path) -> str:
    """The main repo's folder name; a worktree's `commondir` leads back to it."""
    try:
        common = (git_dir / _read(git_dir / "commondir")).resolve()
        if common.name == ".git":
            return common.parent.name
    except OSError:
        pass
    return folder.name


def locate(cwd: Path) -> tuple[str | None, str | None]:
    """(repo name, branch) of `cwd`; (None, None) outside a repo, branch None on a detached HEAD."""
    found = _find_git(cwd)
    if found is None:
        return None, None
    folder, git_dir = found
    repo = _repo_name(folder, git_dir)
    try:
        head = _read(git_dir / "HEAD")
    except OSError:
        return repo, None
    return repo, head[len(HEAD_PREFIX) :] if head.startswith(HEAD_PREFIX) else None


def card_of(branch: str | None) -> str | None:
    match = CARD_BRANCH.match(branch or "")
    return match.group(1) if match else None


def build_event(payload: dict, now: datetime) -> dict:
    cwd = payload.get("cwd")
    repo, branch = locate(Path(cwd if isinstance(cwd, str) and cwd else os.getcwd()))
    session = payload.get("session_id")
    return {
        "v": EVENT_VERSION,
        "event": "activity",
        "card": card_of(branch),
        "at": now.isoformat(timespec="seconds"),
        "source": "hook",
        "repo": repo,
        "branch": branch,
        "session": session if isinstance(session, str) and SESSION_ID.fullmatch(session) else None,
    }


def append(event: dict, now: datetime) -> None:
    """One line in the month file; the folder is private (0700) and the file too (0600)."""
    folder = _data_dir() / "timelog"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    line = json.dumps(event, ensure_ascii=False) + "\n"
    descriptor = os.open(
        folder / f"{now:%Y-%m}.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600
    )
    try:
        os.write(descriptor, line.encode("utf-8"))
    finally:
        os.close(descriptor)


def _on_alarm(signum, frame) -> None:
    raise _Deadline


def record(payload: object) -> None:
    if not isinstance(payload, dict):
        return
    now = datetime.now().astimezone()
    append(build_event(payload, now), now)


def main() -> int:
    signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, DEADLINE)
    failure = None
    try:
        record(json.loads(sys.stdin.read()))
    except _Deadline:
        failure = "Deadline"
    except Exception as error:
        failure = type(error).__name__
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    if failure:
        log_error(failure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
