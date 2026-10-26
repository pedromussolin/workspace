import _thread
import fcntl
import os
import signal
import subprocess
import sys
import threading
import time

import pytest

from ws import slot
from ws.cli import main

RECORD_INTERVAL = """
import os, sys, time
with open(sys.argv[1], "a") as f:
    f.write(f"{os.getpid()} start {time.time()}\\n")
time.sleep(0.6)
with open(sys.argv[1], "a") as f:
    f.write(f"{os.getpid()} end {time.time()}\\n")
"""

CHECK_SLOT_IS_LOCKED = """
import fcntl, sys
fd = open(sys.argv[1], "w")
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(0)
sys.exit(1)
"""

QUIET_ON_SIGINT = """
import signal, sys, time
signal.signal(signal.SIGINT, lambda *_: sys.exit(5))
print("ready", flush=True)
time.sleep(30)
"""


def py(code: str, *args: str) -> list[str]:
    return [sys.executable, "-c", code, *args]


def lock_is_free(path) -> bool:
    with open(path, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True


def test_runs_command_and_returns_code(tmp_path):
    code = slot.run_in_slot(py("raise SystemExit(3)"), 1, tmp_path / "slots", poll=0.05)
    assert code == 3


def test_creates_lock_dir_with_parents(tmp_path):
    lock_dir = tmp_path / "a" / "b" / "slots"
    assert slot.run_in_slot(py("pass"), 1, lock_dir, poll=0.05) == 0
    assert (lock_dir / "slot-1.lock").exists()


def test_slot_is_held_while_command_runs(tmp_path):
    lock_dir = tmp_path / "slots"
    lock = lock_dir / "slot-1.lock"
    code = slot.run_in_slot(py(CHECK_SLOT_IS_LOCKED, str(lock)), 1, lock_dir, poll=0.05)
    assert code == 0


@pytest.mark.parametrize(
    ("cmd", "expected"),
    [
        (py("pass"), 0),
        (py("raise SystemExit(1)"), 1),
        (["ws-no-such-command-acme"], 127),
    ],
)
def test_slot_is_released_after_any_outcome(tmp_path, cmd, expected):
    lock_dir = tmp_path / "slots"
    assert slot.run_in_slot(cmd, 1, lock_dir, poll=0.05) == expected
    assert lock_is_free(lock_dir / "slot-1.lock")


def test_slot_is_released_when_spawn_raises(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "Popen", boom)
    lock_dir = tmp_path / "slots"
    with pytest.raises(RuntimeError):
        slot.run_in_slot(["anything"], 1, lock_dir, poll=0.05)
    assert lock_is_free(lock_dir / "slot-1.lock")


def test_command_not_found_reports_on_stderr(tmp_path, capsys):
    assert slot.run_in_slot(["ws-no-such-command-acme"], 1, tmp_path, poll=0.05) == 127
    assert "ws-no-such-command-acme" in capsys.readouterr().err


def test_command_killed_by_signal_returns_128_plus_signal(tmp_path):
    cmd = py("import os, signal; os.kill(os.getpid(), signal.SIGTERM)")
    assert slot.run_in_slot(cmd, 1, tmp_path, poll=0.05) == 128 + signal.SIGTERM


def test_empty_command_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        slot.run_in_slot([], 1, tmp_path)


def test_uses_second_slot_when_first_is_taken(tmp_path):
    lock_dir = tmp_path / "slots"
    lock_dir.mkdir()
    result: list[int] = []
    with open(lock_dir / "slot-1.lock", "w") as taken:
        fcntl.flock(taken, fcntl.LOCK_EX)
        cmd = py(CHECK_SLOT_IS_LOCKED, str(lock_dir / "slot-2.lock"))
        worker = threading.Thread(
            target=lambda: result.append(slot.run_in_slot(cmd, 2, lock_dir, poll=0.05)),
            daemon=True,
        )
        worker.start()
        worker.join(timeout=5)
    assert result == [0]


def test_waits_for_a_free_slot_then_runs(tmp_path):
    lock_dir = tmp_path / "slots"
    lock_dir.mkdir()
    result: list[int] = []
    taken = open(lock_dir / "slot-1.lock", "w")
    fcntl.flock(taken, fcntl.LOCK_EX)
    worker = threading.Thread(
        target=lambda: result.append(slot.run_in_slot(py("pass"), 1, lock_dir, poll=0.05)),
        daemon=True,
    )
    worker.start()
    worker.join(timeout=0.3)
    assert worker.is_alive()
    taken.close()
    worker.join(timeout=5)
    assert result == [0]


def test_ctrl_c_while_waiting_for_a_slot_returns_130(tmp_path):
    lock_dir = tmp_path / "slots"
    lock_dir.mkdir()
    with open(lock_dir / "slot-1.lock", "w") as taken:
        fcntl.flock(taken, fcntl.LOCK_EX)
        timer = threading.Timer(0.2, _thread.interrupt_main)
        timer.start()
        try:
            assert slot.run_in_slot(py("pass"), 1, lock_dir, poll=0.05) == 130
        finally:
            timer.cancel()


def test_ctrl_c_while_command_runs_returns_130_without_traceback(tmp_path):
    env = {**os.environ, "WS_CACHE_DIR": str(tmp_path)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "ws", "slot", "-n", "1", "--", *py(QUIET_ON_SIGINT)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    assert proc.stdout.readline().strip() == "ready"
    os.killpg(proc.pid, signal.SIGINT)
    _, stderr = proc.communicate(timeout=10)
    assert proc.returncode == 130
    assert "Traceback" not in stderr


def test_one_slot_serializes(tmp_path):
    record = tmp_path / "record.txt"
    env = {**os.environ, "WS_CACHE_DIR": str(tmp_path)}
    cmd = [sys.executable, "-m", "ws", "slot", "-n", "1", "--", *py(RECORD_INTERVAL, str(record))]
    started = time.monotonic()
    procs = [subprocess.Popen(cmd, env=env) for _ in range(2)]
    assert [p.wait(timeout=10) for p in procs] == [0, 0]
    assert time.monotonic() - started < 3

    marks: dict[str, dict[str, float]] = {}
    for line in record.read_text().splitlines():
        pid, kind, stamp = line.split()
        marks.setdefault(pid, {})[kind] = float(stamp)
    first, second = sorted(marks.values(), key=lambda m: m["start"])
    assert len(marks) == 2
    assert first["end"] <= second["start"]


def test_parse_slots_accepts_positive_integers():
    assert slot.parse_slots("3") == 3


@pytest.mark.parametrize("text", ["0", "-1", "two", ""])
def test_parse_slots_rejects_the_rest(text):
    with pytest.raises(ValueError):
        slot.parse_slots(text)


def test_default_slots_comes_from_env(monkeypatch):
    monkeypatch.setenv("WS_SLOTS", "5")
    assert slot.default_slots() == 5


def test_default_slots_is_two_without_env(monkeypatch):
    monkeypatch.delenv("WS_SLOTS", raising=False)
    assert slot.default_slots() == 2


def test_default_slots_rejects_invalid_env(monkeypatch):
    monkeypatch.setenv("WS_SLOTS", "lots")
    with pytest.raises(ValueError, match="WS_SLOTS"):
        slot.default_slots()


def test_default_lock_dir_is_under_cache_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path))
    assert slot.default_lock_dir() == tmp_path / "slots"


def test_cli_runs_command_and_returns_its_code(monkeypatch, tmp_path):
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path))
    argv = ["slot", "-n", "1", "--", *py("raise SystemExit(4)")]
    assert main(argv) == 4


def test_cli_passes_n_and_command_to_run_in_slot(monkeypatch, tmp_path):
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path))
    calls = []
    monkeypatch.setattr(slot, "run_in_slot", lambda *args: calls.append(args) or 0)
    assert main(["slot", "-n", "4", "--", "make", "-j2"]) == 0
    assert calls == [(["make", "-j2"], 4, tmp_path / "slots")]


def test_cli_uses_ws_slots_when_n_is_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("WS_SLOTS", "3")
    calls = []
    monkeypatch.setattr(slot, "run_in_slot", lambda *args: calls.append(args) or 0)
    assert main(["slot", "--", "true"]) == 0
    assert calls == [(["true"], 3, tmp_path / "slots")]


def test_cli_invalid_ws_slots_exits_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("WS_SLOTS", "0")
    assert main(["slot", "--", "true"]) == 2
    assert "WS_SLOTS" in capsys.readouterr().err


def test_cli_requires_a_command():
    with pytest.raises(SystemExit) as exc:
        main(["slot", "-n", "1", "--"])
    assert exc.value.code == 2


@pytest.mark.parametrize("n", ["0", "-2", "x"])
def test_cli_rejects_invalid_n(n):
    with pytest.raises(SystemExit) as exc:
        main(["slot", "-n", n, "--", "true"])
    assert exc.value.code == 2
