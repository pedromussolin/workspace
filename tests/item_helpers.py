import shutil
from pathlib import Path

import pytest

from ws.identity import dev_id

ME = dev_id("dev@example.com")
ANA = dev_id("ana@example.com")
TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "item"

CONFIG = f"""[jira]
site = "https://example.atlassian.net"
email = "dev@example.com"
project = "TS"

[jira.types]
task = "3"
bug = "4"
hotfix = "5"
improvement = "6"
feature = "7"
epic = "8"
initiative = "9"

[jira.links]
blocks = "Blocks"
relates = "Relates"

[people."{ANA}"]
jira = "acc-ana"
"""
README = "# Demo\n\n<!-- ws:items -->\n<!-- /ws:items -->\n\nDepois.\n"


@pytest.fixture
def item_repo(tmp_path: Path, ws_config: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("WS_REPO_ROOT", str(tmp_path))
    shutil.copytree(TEMPLATES, tmp_path / "templates" / "item")
    project = tmp_path / "projects" / "demo"
    (project / "tasks").mkdir(parents=True)
    (project / "project.toml").write_text('epics = ["TS-100", "TS-111"]\n', encoding="utf-8")
    (project / "README.md").write_text(README, encoding="utf-8")
    config = ws_config / "config.toml"
    if not config.exists():
        config.write_text(CONFIG, encoding="utf-8")
    return tmp_path


def write_item(root: Path, name: str, front: str, body: str = "# 01 — Algo\n") -> Path:
    path = root / "projects" / "demo" / "tasks" / name
    path.write_text(f"+++\n{front}\n+++\n{body}", encoding="utf-8")
    return path
