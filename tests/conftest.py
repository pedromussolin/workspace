import json
import os
import subprocess
import sys
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


@pytest.fixture(autouse=True)
def no_real_apt(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """A guard first on PATH: a test that reaches the real `apt-get` fails instead of downloading.

    `fake_apt` goes in front of it for the tests that exercise the download.
    """
    guard = tmp_path_factory.mktemp("apt-guard") / "apt-get"
    guard.write_text("#!/bin/sh\necho 'tests must not run the real apt-get' >&2\nexit 99\n")
    guard.chmod(0o755)
    monkeypatch.setenv("PATH", f"{guard.parent}{os.pathsep}{os.environ['PATH']}")


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


FAKE_APT_GET = """\
#!{python}
import json, os, pathlib, sys

DICTIONARIES = {{"wamerican": "flange\\ngizmo\\n", "wbrazilian": "porca\\narruela\\n"}}
with open(os.environ["FAKE_TOOLS_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({{"tool": "apt-get", "args": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
if os.environ.get("FAKE_APT_FAIL"):
    print("W: some warning", file=sys.stderr)
    print("E: Unable to locate package wamerican", file=sys.stderr)
    sys.exit(100)
assert sys.argv[1] == "download", sys.argv
for package in sys.argv[2:]:
    pathlib.Path(f"{{package}}_1.0_all.deb").write_text(DICTIONARIES[package], encoding="utf-8")
"""

FAKE_DPKG = """\
#!{python}
import json, os, pathlib, sys

FILENAMES = {{"wamerican": "american-english", "wbrazilian": "brazilian"}}
with open(os.environ["FAKE_TOOLS_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({{"tool": "dpkg", "args": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
if os.environ.get("FAKE_DPKG_FAIL"):
    print("dpkg-deb: error: not a Debian format archive", file=sys.stderr)
    sys.exit(2)
assert sys.argv[1] == "-x", sys.argv
deb, destination = pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
target = destination / "usr" / "share" / "dict" / FILENAMES[deb.name.split("_")[0]]
target.parent.mkdir(parents=True)
mode = os.environ.get("FAKE_DPKG_MODE", "")
if mode == "empty":
    target.write_text("", encoding="utf-8")
elif mode == "symlink":
    target.symlink_to(os.environ["FAKE_DPKG_LINK"])
else:
    target.write_text(deb.read_text(encoding="utf-8"), encoding="utf-8")
"""


class FakeApt:
    """Fake `apt-get` and `dpkg` first on PATH: no test ever reaches the network."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.log = folder / "calls.jsonl"

    def calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def fake_apt(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> FakeApt:
    """The fake tools, working: `apt-get download` leaves one .deb per package, `dpkg -x` unpacks.

    Set FAKE_APT_FAIL, FAKE_DPKG_FAIL or FAKE_DPKG_MODE (`empty`, `symlink` with FAKE_DPKG_LINK)
    to make them fail.
    """
    fake = FakeApt(tmp_path_factory.mktemp("fake-apt"))
    for name, template in (("apt-get", FAKE_APT_GET), ("dpkg", FAKE_DPKG)):
        script = fake.folder / name
        script.write_text(template.format(python=sys.executable), encoding="utf-8")
        script.chmod(0o755)
    monkeypatch.setenv("FAKE_TOOLS_LOG", str(fake.log))
    monkeypatch.setenv("PATH", f"{fake.folder}{os.pathsep}{os.environ['PATH']}")
    return fake
