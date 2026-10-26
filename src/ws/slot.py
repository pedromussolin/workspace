"""Runs a heavy command in one of N slots (file locks) so parallel agents do not exhaust memory."""

import fcntl
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from ws.config import cache_dir

DEFAULT_SLOTS = 2
EXIT_CANNOT_EXECUTE = 126
EXIT_NOT_FOUND = 127
EXIT_INTERRUPTED = 130
FORWARDED_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)


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


class _Forwarder:
    """Passes the signals ws slot receives on to the child, so the slot lasts as long as it does."""

    def __init__(self) -> None:
        self.child: subprocess.Popen[bytes] | None = None
        self.received: list[int] = []

    def __call__(self, signum: int, frame: object) -> None:
        self.received.append(signum)
        if self.child is not None:
            self.child.send_signal(signum)

    def attach(self, child: subprocess.Popen[bytes]) -> None:
        self.child = child
        for signum in list(self.received):
            child.send_signal(signum)


def _run(cmd: list[str], lock_fd: int) -> int:
    forwarder = _Forwarder()
    previous = {}
    if threading.current_thread() is threading.main_thread():
        previous = {signum: signal.signal(signum, forwarder) for signum in FORWARDED_SIGNALS}
    try:
        try:
            proc = subprocess.Popen(cmd, pass_fds=(lock_fd,))
        except OSError as exc:
            print(f"ws slot: cannot run {cmd[0]!r}: {exc.strerror}", file=sys.stderr)
            return EXIT_NOT_FOUND if isinstance(exc, FileNotFoundError) else EXIT_CANNOT_EXECUTE
        forwarder.attach(proc)
        code = proc.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler if handler is not None else signal.SIG_DFL)
    if signal.SIGINT in forwarder.received:
        return EXIT_INTERRUPTED
    return 128 - code if code < 0 else code


def run_in_slot(cmd: list[str], slots: int, lock_dir: Path, poll: float = 1.0) -> int:
    """Wait for a free slot, run cmd with inherited stdio and return its exit code.

    The slot is the flock on an open file descriptor that the command inherits, so it stays taken
    until the command ends, even if this process is killed. SIGTERM, SIGHUP and SIGINT are
    forwarded to the command and this process waits for it. A command killed by a signal returns
    128 + signal; an interrupted run (SIGINT) returns 130.
    """
    if not cmd:
        raise ValueError("empty command")
    lock_dir.mkdir(parents=True, exist_ok=True)
    try:
        fd = _acquire(lock_dir, slots, poll)
        try:
            return _run(cmd, fd)
        finally:
            os.close(fd)
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
