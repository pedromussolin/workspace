"""UserPromptSubmit hook: warns when the context of the session passes a limit.

It measures the last usable usage entry of the transcript and, once per band (the first at
`warn_at`, then every `step` above it), tells the model to propose a handoff at the next natural
pause, and shows the user one line. It never blocks a prompt: every path exits 0, and a failure
prints nothing and leaves one line in the error log.

Standard library only; it never imports or runs `ws`. It reads `config.toml` and writes its state
itself, honoring the `WS_CONFIG_DIR` and `WS_CACHE_DIR` overrides the tests use.
"""

import json
import os
import re
import signal
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

USER_NOTICE = True
DEFAULT_WARN_AT = 300_000
DEFAULT_STEP = 100_000
DEADLINE = 2.0
CHUNK = 1 << 20
MAX_READ = 16 << 20
NO_USAGE_SIZE = 1 << 20
SESSION_ID = re.compile(r"[A-Za-z0-9-]{1,64}")
STATE_MAX_AGE = 7 * 24 * 3600
SWEEP_EVERY = 24 * 3600
ERROR_LOG_LINES = 200
USAGE_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


class _Deadline(Exception):
    pass


def _cache_dir() -> Path:
    override = os.environ.get("WS_CACHE_DIR")
    return Path(override) if override else Path.home() / ".cache" / "workspace"


def _config_dir() -> Path:
    override = os.environ.get("WS_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".config" / "workspace"


def log_error(what: str) -> None:
    """One line `<iso time> context_watch <what>`; never the prompt or the transcript."""
    try:
        log = _cache_dir() / "hooks" / "errors.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        lines = [*lines[-(ERROR_LOG_LINES - 1) :], f"{stamp} context_watch {what}"]
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def _usage_total(entry: object) -> int | None:
    """The context of one transcript entry, None when it is not a usable main-session reply."""
    if not isinstance(entry, dict) or entry.get("type") != "assistant" or entry.get("isSidechain"):
        return None
    message = entry.get("message")
    if not isinstance(message, dict) or message.get("model") == "<synthetic>":
        return None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    total = 0
    for field in USAGE_FIELDS:
        value = usage.get(field, 0)
        if isinstance(value, int) and not isinstance(value, bool):
            total += value
    return total if total > 0 else None


def context_tokens(transcript: Path, max_bytes: int = MAX_READ) -> int | None:
    """Tokens of the last usable entry, reading from the end in 1 MB chunks up to `max_bytes`."""
    with transcript.open("rb") as handle:
        position = handle.seek(0, os.SEEK_END)
        floor = max(0, position - max_bytes)
        carry = b""
        while position > floor:
            start = max(floor, position - CHUNK)
            handle.seek(start)
            data = handle.read(position - start) + carry
            position = start
            pieces = data.split(b"\n")
            carry = pieces[0] if position > floor else b""
            complete = pieces[1:] if position > floor else pieces
            for line in reversed(complete):
                if b'"usage"' not in line or b'"assistant"' not in line:
                    continue
                try:
                    total = _usage_total(json.loads(line))
                except ValueError:
                    continue
                if total is not None:
                    return total
    return None


def band(tokens: int, warn_at: int, step: int) -> int:
    """0 below `warn_at`, 1 from it, and one more for every `step` above it."""
    if tokens < warn_at:
        return 0
    return 1 + (tokens - warn_at) // step


def _positive(value: object, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return default


def _limits() -> tuple[int, int]:
    try:
        data = tomllib.loads((_config_dir() / "config.toml").read_text(encoding="utf-8"))
        table = data.get("context_watch", {})
        table = table if isinstance(table, dict) else {}
    except (OSError, ValueError):
        table = {}
    return (
        _positive(table.get("warn_at"), DEFAULT_WARN_AT),
        _positive(table.get("step"), DEFAULT_STEP),
    )


def _read_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state), encoding="utf-8")
    os.replace(temporary, path)


def _sweep(folder: Path) -> None:
    """Removes the state of sessions untouched for 7 days, at most once a day."""
    marker = folder / ".swept"
    now = time.time()
    try:
        if now - marker.stat().st_mtime < SWEEP_EVERY:
            return
    except OSError:
        pass
    for item in folder.glob("*.json"):
        try:
            if now - item.stat().st_mtime > STATE_MAX_AGE:
                item.unlink()
        except OSError:
            continue
    marker.touch()


def _output(tokens: int) -> dict:
    thousands = tokens // 1000
    answer: dict = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                f"Context is at {thousands}k tokens. At the next natural pause (after the "
                "current step, never in the middle of an edit or with agents running), propose "
                "a handoff to the user (skill `handoff`). Do not start it without their yes, "
                "and do not compact."
            ),
        }
    }
    if USER_NOTICE:
        answer["systemMessage"] = (
            f"Contexto em {thousands} mil tokens: o Claude vai propor um handoff na próxima pausa."
        )
    return answer


def _on_alarm(signum, frame) -> None:
    raise _Deadline


def watch(payload: object) -> dict | None:
    """The hook output for one prompt, or None when there is nothing to say."""
    if not isinstance(payload, dict):
        return None
    session, transcript = payload.get("session_id"), payload.get("transcript_path")
    if not isinstance(session, str) or not SESSION_ID.fullmatch(session):
        return None
    if not isinstance(transcript, str) or not transcript:
        return None
    path = Path(transcript)
    if not path.is_file():
        return None
    folder = _cache_dir() / "context-watch"
    state_file = folder / f"{session}.json"
    state = _read_state(state_file)
    tokens = context_tokens(path)
    if tokens is None:
        if path.stat().st_size > NO_USAGE_SIZE and not state.get("no_usage_logged"):
            log_error("no-usage")
            _write_state(state_file, {**state, "no_usage_logged": True})
        return None
    warn_at, step = _limits()
    current = band(tokens, warn_at, step)
    last = state.get("band", 0) if isinstance(state.get("band", 0), int) else 0
    if current != last:
        _write_state(state_file, {**state, "band": current})
        _sweep(folder)
    return _output(tokens) if current > last else None


def main() -> int:
    signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, DEADLINE)
    failure = None
    answer = None
    try:
        answer = watch(json.loads(sys.stdin.read()))
    except _Deadline:
        failure = "Deadline"
    except Exception as error:
        failure = type(error).__name__
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    if failure:
        log_error(failure)
        return 0
    if answer:
        try:
            sys.stdout.write(json.dumps(answer, ensure_ascii=False))
        except Exception as error:
            log_error(type(error).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
