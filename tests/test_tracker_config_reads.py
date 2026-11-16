import ast
from pathlib import Path

from test_board_cli import board_file, run

import ws

SRC = Path(ws.__file__).parent
ALIASES = {Path("jira.py"), Path("adf.py"), Path("cardrules.py")}


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
        if relative.parts[0] == "tracker" or relative in ALIASES:
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
