import json
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from ws import board_cli, carddraft
from ws.cli import main
from ws.config import data_dir

Git = Callable[..., subprocess.CompletedProcess[str]]

BOARD = """
[board]
fetch = {fetch}
default_profile = "gitops"

[[board.profiles.gitops.environments]]
name = "sandbox"
status = "validation"
proof = "branch"
branches = ["sandbox"]

[[board.profiles.gitops.environments]]
name = "master"
status = "ready_deploy"
proof = "branch"
branches = ["master"]

[[board.profiles.gitops.environments]]
name = "production"
status = "done"
proof = "file"
deploy_repo = "{{repo}}-argocd"
deploy_branch = "master"
image_tag = 'prod-([0-9a-f]{{7,40}})'

[board.statuses]
in_progress = "Em andamento"
validation = "In Validation"
ready_deploy = "Ready Deploy"
done = "Concluído"
"""


OVERRIDES = {"In Validation": "validation", "Ready Deploy": "ready_deploy"}


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

    def write_config(board: bool = True, fetch: bool = False, overrides=OVERRIDES) -> None:
        text = (
            '[jira]\nsite = "https://example.atlassian.net"\nemail = "dev@example.com"\n'
            "[jira.status_overrides]\n"
            + "".join(f'"{name}" = "{status}"\n' for name, status in overrides.items())
            + f'[standup]\nrepo_roots = ["{roots}"]\n'
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
        text + '\n[board.repos."demo-api"]\nignore = true\n', encoding="utf-8"
    )
    _, out, _ = run(
        capsys, "status", "--cards", str(standard_cards(world)), "--today", "2026-11-05"
    )
    assert json.loads(out)["moves"] == []


BACKWARDS = (
    "does not map back to {0} in [jira.status_overrides]; "
    "a card in it would be read wrong and could move backwards"
)


@pytest.mark.parametrize(
    ("overrides", "status", "name"),
    [
        ({"Ready Deploy": "ready_deploy"}, "validation", "In Validation"),
        ({"In Validation": "validation", "Ready Deploy": "done"}, "ready_deploy", "Ready Deploy"),
        ({**OVERRIDES, "Em andamento": "todo"}, "in_progress", "Em andamento"),
        ({**OVERRIDES, "Concluído": "in_progress"}, "done", "Concluído"),
    ],
)
def test_status_name_that_does_not_map_back_exits_2(world, capsys, overrides, status, name):
    world.write_config(overrides=overrides)
    code, out, err = run(capsys, "status", "--cards", str(standard_cards(world)))
    assert code == 2
    assert out == ""
    assert err == f'ws board status: board.statuses.{status} "{name}" {BACKWARDS.format(status)}\n'


def test_status_names_mapped_by_category_are_fine(world, capsys):
    world.write_config(overrides={**OVERRIDES, "Em andamento": "in_progress"})
    code, _, _ = run(
        capsys, "status", "--cards", str(standard_cards(world)), "--today", "2026-11-05"
    )
    assert code == 0


def board_file(tmp_path: Path, moves: list[dict]) -> Path:
    path = tmp_path / "board.json"
    path.write_text(json.dumps({"moves": moves}), encoding="utf-8")
    return path


MOVE = {"key": "TS-101", "to_name": "Concluído"}


def test_drafts_writes_one_move_draft_per_move(tmp_path, capsys):
    code, out, _ = run(capsys, "drafts", "--board", str(board_file(tmp_path, [MOVE])))
    assert code == 0
    answer = json.loads(out)
    assert answer["count"] == 1
    folder = Path(answer["folder"])
    assert folder.name.startswith("sync-")
    draft = carddraft.parse_draft((folder / "move-TS-101.md").read_bytes())
    assert draft.op == "move"
    assert draft.values == {"key": "TS-101", "to": "Concluído"}
    assert (folder / "move-TS-101.md").read_text(encoding="utf-8") == (
        '+++\nop = "move"\nkey = "TS-101"\nto = "Concluído"\n+++\n'
    )


def test_drafts_without_moves_creates_nothing(tmp_path, capsys):
    code, out, _ = run(capsys, "drafts", "--board", str(board_file(tmp_path, [])))
    assert code == 0
    assert json.loads(out) == {"folder": None, "count": 0}
    assert not (tmp_path / "cards").exists()


@pytest.mark.parametrize(
    "bad",
    [
        {"key": "ts-101", "to_name": "Concluído"},
        {"key": "../x", "to_name": "Concluído"},
        {"key": "TS-101", "to_name": ""},
        {"key": "TS-101"},
    ],
)
def test_drafts_invalid_move_exits_2_and_writes_nothing(tmp_path, capsys, bad):
    code, out, err = run(capsys, "drafts", "--board", str(board_file(tmp_path, [MOVE, bad])))
    assert code == 2
    assert out == ""
    assert err
    assert not (data_dir() / "cards" / "drafts").exists() or not list(
        (data_dir() / "cards" / "drafts").iterdir()
    )


def test_drafts_with_unreadable_board_exits_2(tmp_path, capsys):
    code, _, err = run(capsys, "drafts", "--board", str(tmp_path / "missing.json"))
    assert code == 2
    assert "missing.json" in err


def test_drafts_same_second_is_exit_1(tmp_path, capsys, monkeypatch):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 5, 12, 0, 0)

    monkeypatch.setattr(board_cli, "datetime", Frozen)
    path = board_file(tmp_path, [MOVE])
    assert run(capsys, "drafts", "--board", str(path))[0] == 0
    code, _, err = run(capsys, "drafts", "--board", str(path))
    assert code == 1
    assert "sync-20261105-120000" in err


def test_drafts_two_moves_for_one_card_exit_2(tmp_path, capsys):
    code, _, err = run(capsys, "drafts", "--board", str(board_file(tmp_path, [MOVE, MOVE])))
    assert code == 2
    assert "same card" in err
