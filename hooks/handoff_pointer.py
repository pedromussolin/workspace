"""SessionStart hook: points a new chat at the handoff files written in the last days.

Paths and one-line titles only, never content, so it costs about 150 tokens. It never blocks a
session: every path exits 0, and a failure prints nothing and leaves one line in the error log.

Standard library only; it never imports or runs `ws`. It reads `config.toml` and the data folder
itself, honoring the `WS_CONFIG_DIR`, `WS_DATA_DIR` and `WS_CACHE_DIR` overrides the tests use.
"""

import glob
import json
import os
import signal
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

DEFAULT_MAX_AGE_DAYS = 7
DEFAULT_MAX_LISTED = 3
DEADLINE = 2.0
HEAD_LINES = 10
TITLE_LIMIT = 120
CLOSED_MARK = "Status: encerrado"
ERROR_LOG_LINES = 200
HEADER = (
    "Recent handoffs (newest first). If the user's request continues one, read it in full "
    "before acting; otherwise ignore them:"
)


class _Deadline(Exception):
    pass


def _home_relative(name: str, var: str, *parts: str) -> Path:
    override = os.environ.get(var)
    return Path(override) if override else Path.home().joinpath(*parts)


def _config_dir() -> Path:
    return _home_relative("config", "WS_CONFIG_DIR", ".config", "workspace")


def _data_dir() -> Path:
    return _home_relative("data", "WS_DATA_DIR", ".local", "share", "workspace")


def _cache_dir() -> Path:
    return _home_relative("cache", "WS_CACHE_DIR", ".cache", "workspace")


def log_error(what: str) -> None:
    """One line `<iso time> handoff_pointer <what>`; never any content."""
    try:
        log = _cache_dir() / "hooks" / "errors.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        lines = [*lines[-(ERROR_LOG_LINES - 1) :], f"{stamp} handoff_pointer {what}"]
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def _positive(value: object, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return default


def _settings() -> tuple[list[str], int, int]:
    """`[handoff]` of config.toml: extra_globs, max_age_days, max_listed; defaults when unusable."""
    try:
        data = tomllib.loads((_config_dir() / "config.toml").read_text(encoding="utf-8"))
        table = data.get("handoff", {})
        table = table if isinstance(table, dict) else {}
    except (OSError, ValueError):
        table = {}
    globs = table.get("extra_globs", [])
    if not (isinstance(globs, list) and all(isinstance(item, str) for item in globs)):
        globs = []
    return (
        globs,
        _positive(table.get("max_age_days"), DEFAULT_MAX_AGE_DAYS),
        _positive(table.get("max_listed"), DEFAULT_MAX_LISTED),
    )


def _head(path: str) -> tuple[str, bool]:
    """The H1 and whether the file is closed, from its first lines."""
    title, closed = "", False
    with open(path, encoding="utf-8", errors="replace") as handle:
        for _ in range(HEAD_LINES):
            line = handle.readline()
            if not line:
                break
            if not title and line.startswith("# "):
                title = line[2:].strip()
            if line.strip() == CLOSED_MARK:
                closed = True
    return title, closed


def recent_handoffs(
    data_dir: Path, extra_globs: list[str], *, limit: int, max_age_days: int, now: float
) -> list[tuple[Path, float, str]]:
    """The newest open handoff files as (path, mtime, H1), within `max_age_days` of `now`."""
    patterns = [str(data_dir / "projects" / "*" / "HANDOFF-*.md")]
    patterns += [os.path.expanduser(item) for item in extra_globs]
    mtimes: dict[str, float] = {}
    for pattern in patterns:
        for name in glob.glob(pattern):
            try:
                mtimes.setdefault(name, os.stat(name).st_mtime)
            except OSError:
                continue
    oldest = now - max_age_days * 86400
    found = []
    for name, mtime in sorted(mtimes.items(), key=lambda item: item[1], reverse=True):
        if mtime < oldest:
            continue
        try:
            title, closed = _head(name)
        except OSError:
            continue
        if closed:
            continue
        found.append((Path(name), mtime, title))
        if len(found) == limit:
            break
    return found


def _shown(path: Path) -> str:
    text, home = str(path), str(Path.home())
    return "~" + text[len(home) :] if text.startswith(home + os.sep) else text


def _cut(title: str) -> str:
    return title if len(title) <= TITLE_LIMIT else title[: TITLE_LIMIT - 1] + "…"


def render(found: list[tuple[Path, float, str]]) -> str:
    lines = [HEADER]
    for path, mtime, title in found:
        when = datetime.fromtimestamp(mtime).strftime("%d/%m %H:%M")
        lines.append(f"- {_shown(path)} ({when}): {_cut(title)}")
    return "\n".join(lines)


def _on_alarm(signum, frame) -> None:
    raise _Deadline


def main() -> int:
    signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, DEADLINE)
    failure = None
    text = None
    try:
        globs, max_age, listed = _settings()
        found = recent_handoffs(
            _data_dir(), globs, limit=listed, max_age_days=max_age, now=time.time()
        )
        text = render(found) if found else None
    except _Deadline:
        failure = "Deadline"
    except Exception as error:
        failure = type(error).__name__
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    if failure:
        log_error(failure)
        return 0
    if text:
        try:
            answer = {
                "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}
            }
            sys.stdout.write(json.dumps(answer, ensure_ascii=False))
        except Exception as error:
            log_error(type(error).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
