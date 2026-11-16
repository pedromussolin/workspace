import ast
import json
from pathlib import Path

import pytest
from test_board_cli import BOARD, board_file, run

import ws
from ws import tracker, userconfig
from ws.tracker.errors import TrackerSetup

SRC = Path(ws.__file__).parent


def provider_reads(source: str) -> list[int]:
    """Lines reading the provider settings: `x.jira` or `getattr(x, "jira")`."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr == "jira":
            lines.append(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "jira"
        ):
            lines.append(node.lineno)
    return lines


def scan_core() -> tuple[list[str], int]:
    offenders, visited = [], 0
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative.parts[0] == "tracker":
            continue
        visited += 1
        for line in provider_reads(path.read_text(encoding="utf-8")):
            offenders.append(f"{relative}:{line}")
    return offenders, visited


def test_scan_flags_provider_reads():
    assert provider_reads("x = config.jira\n") == [1]
    assert provider_reads('y = getattr(config, "jira")\n') == [1]
    assert provider_reads("from ws.tracker.jira import writer\nz = config.tracker_settings\n") == []


def test_no_core_module_reads_config_jira():
    offenders, visited = scan_core()
    assert visited > 30
    assert offenders == [], offenders


def test_adapter_and_writer_read_the_neutral_settings():
    for name in ("adapter.py", "writer.py"):
        text = (SRC / "tracker" / "jira" / name).read_text(encoding="utf-8")
        assert provider_reads(text) == []


def test_board_names_a_card_key_neutrally(tmp_path, capsys):
    bad = {"key": "ts-101", "to_name": "Concluído"}
    code, _, err = run(capsys, "drafts", "--board", str(board_file(tmp_path, [bad])))
    assert code == 2
    assert "not a task key" in err
    assert "Jira" not in err


def test_board_status_without_a_tracker_kind_fails_on_the_kind(ws_config, tmp_path, capsys):
    (ws_config / "config.toml").write_text(
        f'[standup]\nrepo_roots = ["{tmp_path}"]\n' + BOARD.format(fetch="false"),
        encoding="utf-8",
    )
    cards = tmp_path / "cards.json"
    cards.write_text(json.dumps({"platform": "x", "cards": []}), encoding="utf-8")

    code, _, err = run(capsys, "status", "--cards", str(cards))

    assert code == 2
    assert "[tracker] kind is not set" in err
    assert "tracker.None" not in err


@pytest.mark.parametrize(
    ("text", "named", "not_named"),
    [
        ('[jira]\nsite = "ftp://x"\n', "jira.site", "tracker.jira"),
        ('[tracker]\nkind = "jira"\n[tracker.jira]\nsite = "ftp://x"\n', "tracker.jira.site", None),
    ],
)
def test_the_link_error_names_the_table_the_site_is_in(
    ws_config, monkeypatch, text, named, not_named
):
    monkeypatch.setattr(userconfig, "_deprecation_shown", False)
    (ws_config / "config.toml").write_text(text, encoding="utf-8")

    with pytest.raises(TrackerSetup) as raised:
        tracker.card_url_template()

    assert named in str(raised.value)
    assert not_named is None or not_named not in str(raised.value)
