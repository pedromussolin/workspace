"""The tracker boundary: only the adapter package names the provider's modules and REST paths.

Each scan is first run on a small source that breaks its rule, so a scanner that finds nothing
cannot pass by accident.
"""

import ast
import importlib.util
import re
from pathlib import Path

import pytest

import ws
from ws.tracker import ADAPTERS

SRC = Path(ws.__file__).parent
HOOKS = SRC.parent.parent / "hooks"
TRACKER = SRC / "tracker"
ADAPTER_PACKAGES = {"ws.tracker.jira", *ADAPTERS.values()}
OLD_PATHS = (
    "ws.jira",
    "ws.adf",
    "ws.cardrules",
    "ws.tracker.jira_adapter",
    "ws.tracker.jira_discover",
)
NEUTRAL = ("__init__.py", "port.py", "write.py", "errors.py", "vocab.py")
PROVIDER_LINK = re.compile(r"/rest/api|/browse/")


def _resolve(node: ast.ImportFrom, package: str | None) -> str | None:
    if not node.level:
        return node.module
    if package is None:
        return None
    parts = package.split(".")
    base = parts[: len(parts) - node.level + 1]
    return ".".join([*base, node.module] if node.module else base)


def imported(source: str, package: str | None = None) -> list[tuple[int, str]]:
    """Each module a source imports, with its line, at any depth (lazy imports too).

    `from a import b` counts as `a` and `a.b`; relative forms resolve inside `package`;
    `importlib.import_module` and `__import__` count when given a literal string.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _resolve(node, package)
            if module:
                found.append((node.lineno, module))
                found.extend((node.lineno, f"{module}.{alias.name}") for alias in node.names)
        elif (
            isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                or (isinstance(node.func, ast.Name) and node.func.id == "__import__")
            )
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.append((node.lineno, node.args[0].value))
    return found


def _is_adapter(name: str) -> bool:
    if any(name == old or name.startswith(f"{old}.") for old in OLD_PATHS):
        return True
    return any(name.startswith(package) for package in ADAPTER_PACKAGES)


def adapter_imports(source: str, package: str | None = None) -> list[str]:
    return [f"{line}: {name}" for line, name in imported(source, package) if _is_adapter(name)]


def _package(path: Path) -> str | None:
    """The package a file of `src/ws` imports relative to; None for the hooks."""
    if not path.is_relative_to(SRC):
        return None
    parts = ("ws", *path.relative_to(SRC).with_suffix("").parts)
    return ".".join(parts[:-1])


def _sources(*roots: Path, skip: Path | None = None) -> list[Path]:
    return [
        path
        for root in roots
        for path in sorted(root.rglob("*.py"))
        if skip is None or not path.is_relative_to(skip)
    ]


def _label(path: Path) -> str:
    return str(path.relative_to(SRC.parent.parent))


@pytest.mark.parametrize(
    ("source", "package"),
    [
        ("import ws.jira\n", None),
        ("from ws import jira\n", None),
        ("from ws import adf\n", None),
        ("from ws import cardrules\n", None),
        ("from ws.cardrules import fold\n", None),
        ("from ws.tracker import jira\n", None),
        ("import ws.tracker.jira_adapter\n", None),
        ("from ws.tracker.jira_discover import discover_toml\n", None),
        ("from ws.tracker.jira import writer\n", None),
        ("from ws.tracker.jira.client import JiraClient\n", None),
        ("def f():\n    from ws.tracker.jira import writer\n", None),
        ("from .jira import writer\n", "ws.tracker"),
        ("from . import jira\n", "ws.tracker"),
        ("from ..tracker.jira import rules\n", "ws.release"),
        ("import importlib\nimportlib.import_module('ws.tracker.jira')\n", None),
    ],
)
def test_the_import_scan_flags_each_way_of_naming_the_adapter(source, package):
    assert adapter_imports(source, package)


@pytest.mark.parametrize(
    "source",
    [
        "from ws.tracker import port, write\n",
        "from ws import card, cardstart\n",
        "import importlib\nimportlib.import_module(ADAPTERS[kind])\n",
        'ADAPTERS = {"jira": "ws.tracker.jira"}\n',
    ],
)
def test_the_import_scan_lets_neutral_imports_and_string_dispatch_pass(source):
    assert adapter_imports(source, "ws") == []


def test_no_module_outside_tracker_imports_the_jira_adapter():
    assert adapter_imports("from ws.tracker.jira import writer\n") == [
        "1: ws.tracker.jira",
        "1: ws.tracker.jira.writer",
    ]

    files = _sources(SRC, HOOKS, skip=TRACKER)
    offenders = [
        f"{_label(path)}:{found}"
        for path in files
        for found in adapter_imports(path.read_text(encoding="utf-8"), _package(path))
    ]

    assert len(files) > 40
    assert any(path.is_relative_to(HOOKS) for path in files)
    assert offenders == []


def test_neutral_tracker_modules_import_no_adapter():
    lazy = "def _adapter(kind):\n    from .jira import adapter\n    return adapter\n"
    assert adapter_imports(lazy, "ws.tracker") == [
        "2: ws.tracker.jira",
        "2: ws.tracker.jira.adapter",
    ]

    offenders = [
        f"{name}:{found}"
        for name in NEUTRAL
        for found in adapter_imports((TRACKER / name).read_text(encoding="utf-8"), "ws.tracker")
    ]

    assert offenders == []
    assert ADAPTERS and all(isinstance(target, str) for target in ADAPTERS.values())


def provider_links(text: str) -> list[int]:
    """Lines holding a REST path or a browse link of the provider."""
    return [
        number for number, line in enumerate(text.splitlines(), 1) if PROVIDER_LINK.search(line)
    ]


def test_no_rest_path_or_browse_link_outside_the_adapter():
    assert provider_links('x = 1\nPATH = "/rest/api/3/issue"\n') == [2]
    assert provider_links('link = f"{site}/browse/{key}"\n') == [1]
    assert provider_links("x = 1\n") == []

    files = _sources(SRC, HOOKS, skip=TRACKER / "jira")
    offenders = [
        f"{_label(path)}:{line}"
        for path in files
        for line in provider_links(path.read_text(encoding="utf-8"))
    ]

    assert len(files) > 40
    assert any(path.is_relative_to(TRACKER) for path in files)
    assert offenders == []


def present(names) -> list[str]:
    """The module names that still import from this checkout."""
    return [name for name in names if importlib.util.find_spec(name) is not None]


def test_old_jira_module_paths_are_gone():
    assert present(["ws.card", "ws.tracker.jira.client", "ws.nothing_here"]) == [
        "ws.card",
        "ws.tracker.jira.client",
    ]

    files = [SRC / "jira.py", SRC / "adf.py", SRC / "cardrules.py"]
    files += [TRACKER / "jira_adapter.py", TRACKER / "jira_discover.py"]

    assert present(OLD_PATHS) == []
    assert [path.name for path in files if path.exists()] == []


def card_core_imports(source: str, package: str | None = None) -> list[str]:
    return [
        f"{line}: {name}"
        for line, name in imported(source, package)
        if name == "ws.card" or name.startswith("ws.card.")
    ]


def test_the_tracker_package_does_not_import_the_card_core():
    assert card_core_imports("def f():\n    from ws import card\n") == ["2: ws.card"]
    assert card_core_imports("from ws import cardstart, carddraft\n") == []

    files = _sources(TRACKER)
    offenders = [
        f"{_label(path)}:{found}"
        for path in files
        for found in card_core_imports(path.read_text(encoding="utf-8"), _package(path))
    ]

    assert TRACKER / "jira" / "adapter.py" in files
    assert offenders == []
