import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "time_activity.py"
SPEC = importlib.util.spec_from_file_location("time_activity", HOOK)
time_activity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(time_activity)

SESSION = "abc-123"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path


def make_repo(root: Path, name: str = "acme-api", head: str = "ref: refs/heads/feature/TS-12-x"):
    repo = root / name
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text(head + "\n", encoding="utf-8")
    return repo


def make_worktree(repo: Path, folder: Path, branch: str) -> Path:
    admin = repo / ".git" / "worktrees" / folder.name
    admin.mkdir(parents=True)
    (admin / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    folder.mkdir(parents=True)
    (folder / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
    return folder


def run_main(monkeypatch, payload: object) -> int:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    return time_activity.main()


def events(env: Path) -> list[dict]:
    lines = []
    for item in sorted((env / "data" / "timelog").glob("*.jsonl")):
        lines += [json.loads(line) for line in item.read_text(encoding="utf-8").splitlines()]
    return lines


def test_appends_one_activity_event(env, monkeypatch, capsys):
    repo = make_repo(env)

    assert run_main(monkeypatch, {"cwd": str(repo), "session_id": SESSION}) == 0

    [event] = events(env)
    assert event.pop("at")
    assert event == {
        "v": 1,
        "event": "activity",
        "card": "TS-12",
        "source": "hook",
        "repo": "acme-api",
        "branch": "feature/TS-12-x",
        "session": SESSION,
    }
    assert capsys.readouterr().out == ""


def test_time_is_local_iso_with_offset_in_the_month_file(env, monkeypatch):
    repo = make_repo(env)

    run_main(monkeypatch, {"cwd": str(repo), "session_id": SESSION})

    [event] = events(env)
    moment = datetime.fromisoformat(event["at"])
    assert moment.utcoffset() is not None
    assert [item.name for item in (env / "data" / "timelog").iterdir()] == [f"{moment:%Y-%m}.jsonl"]


def test_appends_never_rewrites(env, monkeypatch):
    repo = make_repo(env)

    run_main(monkeypatch, {"cwd": str(repo), "session_id": "one"})
    run_main(monkeypatch, {"cwd": str(repo), "session_id": "two"})

    assert [event["session"] for event in events(env)] == ["one", "two"]


def test_subfolder_of_the_repo_finds_the_branch(env, monkeypatch):
    repo = make_repo(env)
    deep = repo / "src" / "pkg"
    deep.mkdir(parents=True)

    run_main(monkeypatch, {"cwd": str(deep), "session_id": SESSION})

    [event] = events(env)
    assert (event["repo"], event["card"]) == ("acme-api", "TS-12")


def test_worktree_uses_its_own_branch_and_the_main_repo_name(env, monkeypatch):
    repo = make_repo(env, head="ref: refs/heads/main")
    tree = make_worktree(repo, env / "trees" / "agent-9", "fix/TS-7-bug")

    run_main(monkeypatch, {"cwd": str(tree), "session_id": SESSION})

    [event] = events(env)
    assert (event["repo"], event["branch"], event["card"]) == ("acme-api", "fix/TS-7-bug", "TS-7")


def test_worktree_with_a_relative_gitdir_pointer(env, monkeypatch):
    repo = make_repo(env, head="ref: refs/heads/main")
    tree = env / "acme-api" / "trees" / "w1"
    admin = repo / ".git" / "worktrees" / "w1"
    admin.mkdir(parents=True)
    (admin / "HEAD").write_text("ref: refs/heads/chore/TS-3-z\n", encoding="utf-8")
    tree.mkdir(parents=True)
    (tree / ".git").write_text("gitdir: ../../.git/worktrees/w1\n", encoding="utf-8")

    run_main(monkeypatch, {"cwd": str(tree), "session_id": SESSION})

    [event] = events(env)
    assert (event["branch"], event["card"]) == ("chore/TS-3-z", "TS-3")


def test_detached_head_has_no_card_and_no_branch(env, monkeypatch):
    repo = make_repo(env, head="3f2a9c1d" * 5)

    run_main(monkeypatch, {"cwd": str(repo), "session_id": SESSION})

    [event] = events(env)
    assert (event["card"], event["branch"], event["repo"]) == (None, None, "acme-api")


def test_branch_without_a_card_has_null_card(env, monkeypatch):
    repo = make_repo(env, head="ref: refs/heads/main")

    run_main(monkeypatch, {"cwd": str(repo), "session_id": SESSION})

    [event] = events(env)
    assert (event["card"], event["branch"]) == (None, "main")


def test_cwd_outside_a_repo_is_still_recorded_with_nulls(env, monkeypatch):
    outside = env / "plain"
    outside.mkdir()

    run_main(monkeypatch, {"cwd": str(outside), "session_id": SESSION})

    [event] = events(env)
    assert (event["card"], event["repo"], event["branch"]) == (None, None, None)


@pytest.mark.parametrize(
    "branch,card",
    [
        ("feature/TS-5431-algo", "TS-5431"),
        ("hotfix/AB_C2-9", "AB_C2-9"),
        ("feature/TS-0-x", None),
        ("feature/TS-05-x", None),
        ("feature/TS-12x", None),
        ("feature/ts-12-x", None),
        ("TS-12-x", None),
        ("main", None),
        (None, None),
    ],
)
def test_card_of(branch, card):
    assert time_activity.card_of(branch) == card


def test_missing_or_odd_session_id_becomes_null(env, monkeypatch):
    repo = make_repo(env)

    run_main(monkeypatch, {"cwd": str(repo)})
    run_main(monkeypatch, {"cwd": str(repo), "session_id": "bad id/../x"})

    assert [event["session"] for event in events(env)] == [None, None]


def test_missing_cwd_falls_back_to_the_process_folder(env, monkeypatch):
    repo = make_repo(env)
    monkeypatch.chdir(repo)

    run_main(monkeypatch, {"session_id": SESSION})

    [event] = events(env)
    assert event["card"] == "TS-12"


def test_folder_and_file_are_private(env, monkeypatch):
    repo = make_repo(env)

    run_main(monkeypatch, {"cwd": str(repo), "session_id": SESSION})

    folder = env / "data" / "timelog"
    [month] = folder.iterdir()
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert stat.S_IMODE(month.stat().st_mode) == 0o600


def test_unwritable_folder_is_silent_and_exits_zero(env, monkeypatch, capsys):
    repo = make_repo(env)
    folder = env / "data" / "timelog"
    folder.mkdir(parents=True)
    folder.chmod(0o500)
    try:
        if os.access(folder, os.W_OK):
            pytest.skip("running with permission to write anywhere")
        assert run_main(monkeypatch, {"cwd": str(repo), "session_id": SESSION}) == 0
    finally:
        folder.chmod(0o700)

    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
    log = (env / "cache" / "hooks" / "errors.log").read_text(encoding="utf-8")
    assert log.splitlines()[-1].endswith(" time_activity PermissionError")


@pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", "null"])
def test_bad_input_exits_zero_and_prints_nothing(env, monkeypatch, capsys, raw):
    assert run_main(monkeypatch, raw) == 0

    assert capsys.readouterr().out == ""
    assert not (env / "data" / "timelog").exists() or events(env) == []


def test_deadline_stops_a_slow_run(env, monkeypatch):
    repo = make_repo(env)
    monkeypatch.setattr(time_activity, "DEADLINE", 0.2)
    monkeypatch.setattr(time_activity, "build_event", lambda *a, **k: time.sleep(5))

    started = time.monotonic()
    assert run_main(monkeypatch, {"cwd": str(repo), "session_id": SESSION}) == 0

    assert time.monotonic() - started < 3
    log = (env / "cache" / "hooks" / "errors.log").read_text(encoding="utf-8")
    assert "time_activity Deadline" in log


def test_runs_as_the_registered_command(env):
    repo = make_repo(env)
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(HOOK)],
        input=json.dumps({"cwd": str(repo), "session_id": SESSION}),
        capture_output=True,
        text=True,
        env={**os.environ, "WS_DATA_DIR": str(env / "data"), "WS_CACHE_DIR": str(env / "cache")},
        timeout=20,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    [event] = events(env)
    assert event["card"] == "TS-12"
