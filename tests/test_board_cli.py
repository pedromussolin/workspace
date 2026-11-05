import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from ws.cli import main

Git = Callable[..., subprocess.CompletedProcess[str]]

BOARD = """
[board]
fetch = {fetch}

[[board.environments]]
name = "sandbox"
branches = ["sandbox"]
status = "validation"

[[board.environments]]
name = "master"
branches = ["master"]
status = "ready_deploy"

[[board.environments]]
name = "production"
status = "done"
deploy_repo = "{{repo}}-argocd"
deploy_branch = "master"
image_tag = 'prod-([0-9a-f]{{7,40}})'

[board.statuses]
in_progress = "Em andamento"
validation = "In Validation"
ready_deploy = "Ready Deploy"
done = "Concluído"
"""


def card(key: str, status: str = "In Progress", **extra) -> dict:
    return {
        "key": key,
        "title": f"title {key}",
        "status_name": status,
        "status_category": "indeterminate",
        "epic_key": None,
        "epic_title": None,
        "reporter_is_me": True,
        "updated": "2026-11-01T10:00:00+00:00",
        **extra,
    }


@pytest.fixture
def world(tmp_path: Path, ws_config: Path, git: Git, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    roots = tmp_path / "roots"
    roots.mkdir()

    def write_config(board: bool = True, fetch: bool = False) -> None:
        text = (
            '[jira]\nsite = "https://example.atlassian.net"\nemail = "dev@example.com"\n'
            f'[standup]\nrepo_roots = ["{roots}"]\n'
        )
        if board:
            text += BOARD.format(fetch=str(fetch).lower())
        (ws_config / "config.toml").write_text(text, encoding="utf-8")

    def init(name: str) -> Path:
        path = roots / name
        path.mkdir()
        git(path, "init", "-q", "-b", "master")
        bare = tmp_path / "remotes" / f"{name}.git"
        bare.mkdir(parents=True)
        git(bare, "init", "-q", "--bare")
        git(path, "remote", "add", "origin", str(bare))
        return path

    def commit(path: Path, subject: str) -> None:
        monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-10-20T12:00:00")
        monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-10-20T12:00:00")
        git(path, "commit", "-q", "--allow-empty", "-m", subject)
        git(path, "push", "-q", "origin", "master")

    api = init("demo-api")
    commit(api, "fix: TS-101 x")
    sha = git(api, "rev-parse", "HEAD").stdout.strip()[:7]
    deploy = init("demo-api-argocd")
    (deploy / "values.yaml").write_text(f"image:\n  tag: prod-{sha}\n", encoding="utf-8")
    git(deploy, "add", ".")
    commit(deploy, "chore: bump tag")

    def cards(*items: dict, path: str = "cards.json") -> Path:
        target = tmp_path / path
        target.write_text(json.dumps({"platform": "jira", "cards": list(items)}), encoding="utf-8")
        return target

    write_config()
    return type("World", (), {"write_config": write_config, "cards": cards, "api": api, "git": git})


def run(capsys, *argv: str) -> tuple[int, str, str]:
    code = main(["board", *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def standard_cards(world, **epic):
    return world.cards(card("TS-101", is_epic=False), card("TS-102", is_epic=True, **epic))


def test_status_prints_the_move_and_skips_the_epic(world, capsys):
    code, out, _ = run(
        capsys, "status", "--cards", str(standard_cards(world)), "--today", "2026-11-05"
    )
    assert code == 0
    result = json.loads(out)
    assert [(m["key"], m["from"], m["to"], m["to_name"]) for m in result["moves"]] == [
        ("TS-101", "in_progress", "done", "Concluído")
    ]
    assert result["held"] == result["limited"] == result["to_confirm"] == []
    assert result["warnings"] == []


def test_status_without_board_table_exits_2(world, capsys):
    world.write_config(board=False)
    code, out, err = run(capsys, "status", "--cards", str(standard_cards(world)))
    assert code == 2
    assert out == ""
    assert "[board]" in err
    assert "docs/specs/2026-11-05-board-sync-design.md" in err


def test_status_without_config_file_exits_2(world, ws_config, capsys):
    (ws_config / "config.toml").unlink()
    code, _, err = run(capsys, "status", "--cards", str(standard_cards(world)))
    assert code == 2
    assert "config.toml" in err


def test_status_with_unreadable_cards_exits_2(world, tmp_path, capsys):
    code, _, err = run(capsys, "status", "--cards", str(tmp_path / "missing.json"))
    assert code == 2
    assert "missing.json" in err


def test_status_without_is_epic_warns_once(world, capsys):
    cards = world.cards(card("TS-101"), card("TS-102"))
    _, out, _ = run(capsys, "status", "--cards", str(cards), "--today", "2026-11-05")
    warnings = json.loads(out)["warnings"]
    assert (
        warnings.count("cards without is_epic: epics known only as parents; run ws task list again")
        == 1
    )


def test_status_fetch_failure_is_a_warning_and_marks_stale(world, tmp_path, capsys):
    world.write_config(fetch=True)
    world.git(world.api, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    code, out, _ = run(
        capsys, "status", "--cards", str(standard_cards(world)), "--today", "2026-11-05"
    )
    assert code == 0
    result = json.loads(out)
    assert any(w.startswith("fetch demo-api: ") for w in result["warnings"])
    assert [m["stale"] for m in result["moves"]] == [True]


def test_status_does_not_fetch_when_the_config_says_no(world, tmp_path, capsys):
    world.git(world.api, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    _, out, _ = run(
        capsys, "status", "--cards", str(standard_cards(world)), "--today", "2026-11-05"
    )
    assert not any(w.startswith("fetch ") for w in json.loads(out)["warnings"])


def test_status_ignored_repo_is_never_read(world, ws_config, capsys):
    text = (ws_config / "config.toml").read_text(encoding="utf-8")
    (ws_config / "config.toml").write_text(
        text.replace("[board]\n", '[board]\nignore_repos = ["demo-api"]\n', 1), encoding="utf-8"
    )
    _, out, _ = run(
        capsys, "status", "--cards", str(standard_cards(world)), "--today", "2026-11-05"
    )
    assert json.loads(out)["moves"] == []
