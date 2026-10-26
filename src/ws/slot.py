"""Runs a heavy command in one of N slots (file locks) so parallel agents do not exhaust memory."""

import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

from ws.config import cache_dir

DEFAULT_SLOTS = 2
EXIT_CANNOT_EXECUTE = 126
EXIT_NOT_FOUND = 127
EXIT_INTERRUPTED = 130


def parse_slots(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1:
        raise ValueError(f"slots must be an integer >= 1, got {text!r}")
    return value


def default_slots() -> int:
    value = os.environ.get("WS_SLOTS")
    if not value:
        return DEFAULT_SLOTS
    try:
        return parse_slots(value)
    except ValueError as exc:
        raise ValueError(f"WS_SLOTS: {exc}") from exc


def default_lock_dir() -> Path:
    return cache_dir() / "slots"


def _try_lock(path: Path) -> int | None:
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def _acquire(lock_dir: Path, slots: int, poll: float) -> int:
    while True:
        for number in range(1, slots + 1):
            fd = _try_lock(lock_dir / f"slot-{number}.lock")
            if fd is not None:
                return fd
        time.sleep(poll)


def _run(cmd: list[str]) -> int:
    try:
        proc = subprocess.Popen(cmd)
    except OSError as exc:
        print(f"ws slot: cannot run {cmd[0]!r}: {exc.strerror}", file=sys.stderr)
        return EXIT_NOT_FOUND if isinstance(exc, FileNotFoundError) else EXIT_CANNOT_EXECUTE
    interrupted = False
    while True:
        try:
            code = proc.wait()
            break
        except KeyboardInterrupt:
            # The child got the same Ctrl+C from the terminal; the slot stays taken until it exits.
            interrupted = True
    if interrupted:
        return EXIT_INTERRUPTED
    return 128 - code if code < 0 else code


def run_in_slot(cmd: list[str], slots: int, lock_dir: Path, poll: float = 1.0) -> int:
    """Wait for a free slot, run cmd with inherited stdio and return its exit code.

    The slot is the flock on an open file descriptor, held until the command ends; the kernel
    releases it even if this process dies. A command killed by a signal returns 128 + signal.
    """
    if not cmd:
        raise ValueError("empty command")
    lock_dir.mkdir(parents=True, exist_ok=True)
    try:
        fd = _acquire(lock_dir, slots, poll)
        try:
            return _run(cmd)
        finally:
            os.close(fd)
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
