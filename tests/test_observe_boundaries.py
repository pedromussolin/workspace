"""The neutral modules of `ws observe` import no adapter and name no provider."""

import ast
from pathlib import Path

import pytest

import ws
from ws import cli

SOURCE = Path(ws.__file__).parent
NEUTRAL = (
    "observe_cli.py",
    "observedef.py",
    "observeresults.py",
    "observestatus.py",
    "observereport.py",
    "contracts.py",
    "observability/__init__.py",
    "observability/port.py",
    "database/__init__.py",
    "database/port.py",
    "database/guard.py",
)
PROVIDER_WORDS = ("datadog", "postgres", "psql", "docker", "jira", "execute_code", "pg_")
SUBCOMMANDS = (
    "new",
    "check",
    "show",
    "run",
    "request",
    "fallback",
    "record",
    "status",
    "report",
    "close",
)


def neutral_files() -> list[Path]:
    files = {SOURCE / name for name in NEUTRAL} | set(SOURCE.glob("observe*.py"))
    return sorted(files)


def imported_names(tree: ast.AST) -> list[str]:
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append(module)
            names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names


def test_the_neutral_list_is_complete():
    assert all(path.is_file() for path in neutral_files())
    assert SOURCE / "observe_cli.py" in neutral_files()


@pytest.mark.parametrize("path", neutral_files(), ids=lambda path: str(path.relative_to(SOURCE)))
def test_neutral_modules_import_no_adapter(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for name in imported_names(tree):
        lowered = name.lower()
        assert not lowered.endswith("_adapter"), name
        assert "jira" not in lowered, name
        assert "deploycheck" not in lowered, name


@pytest.mark.parametrize("path", neutral_files(), ids=lambda path: str(path.relative_to(SOURCE)))
def test_neutral_modules_name_no_provider(path):
    text = path.read_text(encoding="utf-8").lower()
    assert [word for word in PROVIDER_WORDS if word in text] == []


@pytest.mark.parametrize("command", [(), *((name,) for name in SUBCOMMANDS)])
def test_help_is_neutral(capsys, command):
    with pytest.raises(SystemExit) as stopped:
        cli.build_parser().parse_args(["observe", *command, "--help"])
    assert stopped.value.code == 0
    text = capsys.readouterr().out.lower()
    assert "usage: ws observe" in text
    assert [word for word in PROVIDER_WORDS if word in text] == []
