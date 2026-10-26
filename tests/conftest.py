import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from ws.names import NamesTable, load_names

NAMES_TOML = """\
blocked_domains = ["acme-corp.example"]

[[names]]
real = "Acme Capital"
analog = "Summit Partners"

[[names]]
real = "Acme"
analog = "Apex"
aliases = ["ACME Corp"]

[[names]]
real = "Brilliant"
analog = "Brillo"
case_sensitive = true

[[names]]
real = "Méridia"
analog = "Meridiana"
"""


@pytest.fixture
def names_toml(tmp_path: Path) -> Path:
    path = tmp_path / "names-config" / "names.toml"
    path.parent.mkdir()
    path.write_text(NAMES_TOML, encoding="utf-8")
    return path


@pytest.fixture
def table(names_toml: Path) -> NamesTable:
    return load_names(names_toml)


@pytest.fixture
def ws_config(names_toml: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("WS_CONFIG_DIR", str(names_toml.parent))
    return names_toml.parent


@pytest.fixture(autouse=True)
def ws_dictionaries(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Both dictionaries in a fake data dir, with made-up words, so no test reads the real ones.

    Returns the `dict/` folder; a test overwrites or removes its files to change what is known.
    """
    data = tmp_path_factory.mktemp("ws-data")
    folder = data / "dict"
    folder.mkdir()
    (folder / "american-english").write_text("gadget\nsprocket\n", encoding="utf-8")
    (folder / "brazilian").write_text("engrenagem\nparafuso\n", encoding="utf-8")
    monkeypatch.setenv("WS_DATA_DIR", str(data))
    monkeypatch.setenv("WS_SYSTEM_DICT_DIR", str(data / "no-system-dict"))
    return folder


@pytest.fixture
def git(monkeypatch: pytest.MonkeyPatch) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Runs git in a repo without reading the user's git config."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    def run(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        command = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com"]
        return subprocess.run(
            [*command, "-C", str(repo), *args], capture_output=True, text=True, check=check
        )

    return run


@pytest.fixture
def repo(tmp_path: Path, git: Callable[..., subprocess.CompletedProcess[str]]) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q")
    return path
