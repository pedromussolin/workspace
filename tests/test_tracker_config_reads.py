import ast
import json
from pathlib import Path

import pytest
from test_board_cli import BOARD, board_file, run
from test_card import create_draft, make_draft

import ws
from ws import tracker, userconfig
from ws.cli import main
from ws.tracker.errors import TrackerSetup

SRC = Path(ws.__file__).parent
SITE = 'site = "https://example.atlassian.net"\nemail = "dev@example.com"\n'
OLD_TABLE = "[jira]\n" + SITE
NEW_TABLE = '[tracker]\nkind = "jira"\n[tracker.jira]\n' + SITE
TABLES = pytest.mark.parametrize(
    ("text", "section"),
    [(OLD_TABLE, "jira"), (NEW_TABLE, "tracker.jira")],
    ids=["old-table", "new-table"],
)


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


@TABLES
def test_missing_card_settings_name_the_table_the_user_has(ws_config, capsys, text, section):
    (ws_config / "config.toml").write_text(text + 'project = "TS"\n', encoding="utf-8")

    assert main(["card", "check", str(create_draft())]) == 2

    err = capsys.readouterr().err
    assert (
        f"config.toml [{section}] is missing board_id, sprint_field, [{section}.types]; "
        'see the README section "Local config"; run ws tracker discover and paste its output '
        "into config.toml"
    ) in err


@TABLES
def test_an_invalid_project_names_the_table_the_user_has(ws_config, capsys, text, section):
    (ws_config / "config.toml").write_text(text + 'project = "1-x"\n', encoding="utf-8")
    draft = make_draft("c.md", "comment", "Oi.\n", key="TS-101")

    assert main(["card", "check", str(draft)]) == 2

    err = capsys.readouterr().err
    assert f"config.toml [{section}] project is not a valid project key" in err


@TABLES
def test_the_board_hint_names_the_table_the_overrides_are_in(
    ws_config, tmp_path, capsys, text, section
):
    (ws_config / "config.toml").write_text(
        text
        + f'[{section}.status_overrides]\n"Ready Deploy" = "ready_deploy"\n'
        + f'[standup]\nrepo_roots = ["{tmp_path}"]\n'
        + BOARD.format(fetch="false"),
        encoding="utf-8",
    )
    cards = tmp_path / "cards.json"
    cards.write_text(json.dumps({"platform": "x", "cards": []}), encoding="utf-8")

    code, _, err = run(capsys, "status", "--cards", str(cards))

    assert code == 2
    assert f"does not map back to validation in [{section}.status_overrides];" in err
