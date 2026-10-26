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
