"""A world for the `ws time` tests: a fixed zone and clock, temp git repos, the time log, a fake
tracker and the config that ties them together. No network, no real tracker."""

import json
import os
import subprocess
import time
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fake_tracker import FakeTracker, make_card
from item_helpers import CONFIG

from ws.cli import main
from ws.config import data_dir

NOW = datetime.fromisoformat("2026-11-27T18:00:00-03:00")
EMAIL = "dev@example.com"
COMPANY = 'version = 1\n\n[estimate]\nunplanned_labels = ["intruder-ops"]\n'
FLOOR = 528
MONDAY, TUESDAY, WEDNESDAY, THURSDAY = "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26"
HOLIDAY, SATURDAY, SUNDAY = "2026-11-20", "2026-11-21", "2026-11-22"


@pytest.fixture
def zone():
    """The local zone is UTC-3 with no daylight saving, whatever machine runs the tests."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = "BRT3"
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


def git_run(repo: Path, *args: str, when: str | None = None) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    if when:
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
    subprocess.run(
        ["git", "-c", "user.name=Test", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env=env,
    )


def init_repo(path: Path, email: str | None = EMAIL) -> Path:
    path.mkdir(parents=True)
    git_run(path, "init", "-q")
    if email:
        git_run(path, "config", "user.email", email)
    return path


def commit(
    repo: Path, message: str, when: str, *, branch: str | None = None, files: dict | None = None
) -> None:
    """One commit at `when` (ISO with offset), on `branch` when given, touching `files`."""
    if branch:
        git_run(repo, "checkout", "-q", "-B", branch)
    for name, text in (files or {}).items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git_run(repo, "add", name)
    git_run(repo, "commit", "-q", "--allow-empty", "-m", message, when=when)


def stamp(day: str, clock: str) -> str:
    return f"{day}T{clock}:00-03:00"


def item_text(card: str | None) -> str:
    front = f'card = "{card}"\n' if card else ""
    return f'+++\n{front}type = "task"\n+++\n# 01 - Algo\n'


def mark(event: str, card: str, day: str, clock: str) -> dict:
    return {"v": 1, "event": event, "card": card, "at": stamp(day, clock), "source": "manual"}


def activity(card: str | None, day: str, clock: str, repo: str = "acme-api") -> dict:
    return {
        "v": 1,
        "event": "activity",
        "card": card,
        "at": stamp(day, clock),
        "source": "hook",
        "repo": repo,
        "branch": f"feature/{card}-x" if card else "main",
    }


def write_log(*lines: dict | str, month: str = "2026-11") -> Path:
    folder = data_dir() / "timelog"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{month}.jsonl"
    text = "".join((line if isinstance(line, str) else json.dumps(line)) + "\n" for line in lines)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    return path


def cards():
    start = date(2026, 11, 23)
    return [
        make_card("TS-1", start=start),
        make_card("TS-2", start=start),
        make_card("TS-3", start=start),
        make_card("TS-4", start=start),
        make_card("TS-5", start=start),
        make_card("TS-9", start=start, labels=("intruder-ops",)),
    ]


@pytest.fixture
def world(tmp_path, ws_config, monkeypatch, zone):
    repos = tmp_path / "repos"
    repos.mkdir()
    workspace = init_repo(tmp_path / "workspace")
    monkeypatch.setenv("WS_REPO_ROOT", str(workspace))
    (ws_config / "card-policies").mkdir()
    (ws_config / "card-policies" / "acme-like.toml").write_text(COMPANY, encoding="utf-8")
    config = ws_config / "config.toml"
    config.write_text(
        CONFIG + f'\n[card]\npolicy = "acme-like"\n\n[standup]\nrepo_roots = ["{repos}"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("ws.timelog._now", lambda: NOW)
    api = init_repo(repos / "acme-api")

    def tracker(items=None, **options):
        fake = FakeTracker(cards() if items is None else items, **options)
        monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: fake)
        return fake

    def set_time(text: str) -> None:
        config.write_text(config.read_text(encoding="utf-8") + "\n[time]\n" + text)

    return SimpleNamespace(
        repos=repos,
        workspace=workspace,
        api=api,
        config=config,
        tracker=tracker,
        set_time=set_time,
        drafts=data_dir() / "cards" / "drafts",
    )


def run(capsys, *argv: str):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, json.loads(out.out) if out.out.strip() else None, out.err


def report(capsys, *argv: str):
    return run(capsys, "time", "report", *argv)


def day_of(document: dict, day: str) -> dict:
    (found,) = [item for item in document["days"] if item["date"] == day]
    return found


def row(document: dict, day: str, ref: str) -> dict:
    (found,) = [item for item in day_of(document, day)["cards"] if item["ref"] == ref]
    return found


def minutes(document: dict, day: str) -> dict[str, int]:
    return {item["ref"]: item["minutes"] for item in day_of(document, day)["cards"]}
