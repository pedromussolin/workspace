import ast
from pathlib import Path

from test_board_cli import board_file, run

import ws

SRC = Path(ws.__file__).parent
ALIASES = {"jira.py", "adf.py", "cardrules.py"}


def test_no_core_module_reads_config_jira():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative.parts[0] == "tracker" or relative.name in ALIASES:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr == "jira":
                offenders.append(f"{relative}:{node.lineno}")
    assert offenders == [], offenders


def test_adapter_and_writer_read_the_neutral_settings():
    for name in ("adapter.py", "writer.py"):
        text = (SRC / "tracker" / "jira" / name).read_text(encoding="utf-8")
        assert "config.jira" not in text


def test_board_names_a_card_key_neutrally(tmp_path, capsys):
    bad = {"key": "ts-101", "to_name": "Concluído"}
    code, _, err = run(capsys, "drafts", "--board", str(board_file(tmp_path, [bad])))
    assert code == 2
    assert "not a task key" in err
    assert "Jira" not in err
