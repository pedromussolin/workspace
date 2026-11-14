"""Test world of `ws release`: throwaway git repos, each with a bare `origin`.

A test module gets the fixtures with `pytest_plugins = ["release_helpers"]` and imports the
constants and `World` by name. Fixtures: `world` (a `World`) and `fixed_today`. Nothing here
touches a real repo or the network: every path lives under `tmp_path`, git ignores the user's
and the system's config, and the `origin` of every clone is a bare repo in a sibling folder.

Layout under `tmp_path/world`:
  origins/<name>.git   bare origin           (World.origin)
  repos/<name>         clone, on master      (World.clone)
  config/config.toml   `[jira]` and `[release.repos.*]`
  data/                `WS_DATA_DIR`; release folders live in data/projects/demo/release-DAY
  root/                `WS_REPO_ROOT`
"""

import os
import subprocess
from datetime import date
from pathlib import Path

import pytest

TODAY = date(2026, 11, 13)
DAY = "20261120"
SITE = "https://example.atlassian.net"
REV_BASE = "aaa000000001"
SLUG = "demo"
IDENTITY = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}
MIGRATIONS = "migrations/versions"
TEMPLATE = "## Tarefa\n\n## Como validei\n"


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> date:
    """`ws.release.text.today()` answers TODAY; every command test requests it."""
    from ws.release import text

    monkeypatch.setattr(text, "today", lambda: TODAY)
    return TODAY


def _toml_list(values: list[str]) -> str:
    return "[" + ", ".join(f'"{v}"' for v in values) + "]"


class World:
    """Two repos, `repo-a` (alembic) and `repo-b` (PR template), with origins and clones."""

    def __init__(self, root: Path, env: dict[str, str]):
        self.root = root
        self.env = env
        self.repos = root / "repos"
        self.origins = root / "origins"
        self.data = root / "data"
        self.config_dir = root / "config"
        for name in ("repo-a", "repo-b"):
            self._create(name)
        self._write_config()

    def clone(self, name: str) -> Path:
        return self.repos / name

    def origin(self, name: str) -> Path:
        return self.origins / f"{name}.git"

    def git(self, name: str, *args: str) -> str:
        """Runs git in the clone of `name` and returns stdout (stripped); raises on failure."""
        return self._run(self.clone(name), *args)

    def commit(
        self, name: str, branch: str, path: str, text: str, subject: str, *, push: bool = True
    ) -> str:
        """Checks out `branch`, writes `path`, commits, optionally pushes; returns the sha."""
        if self.git(name, "symbolic-ref", "--short", "HEAD") != branch:
            self.git(name, "checkout", "-q", branch)
        file = self.clone(name) / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")
        self.git(name, "add", "--", path)
        self.git(name, "commit", "-q", "-m", subject)
        if push:
            self.git(name, "push", "-q", "origin", branch)
        return self.git(name, "rev-parse", "HEAD")

    def branch(self, name: str, new: str, start: str, *, push: bool = True) -> None:
        """Creates `new` at `start` (no tracking) and leaves it checked out."""
        self.git(name, "checkout", "-q", "--no-track", "-b", new, start)
        if push:
            self.git(name, "push", "-q", "origin", new)

    def migration(self, name: str, branch: str, rev: str, down: str | None) -> str:
        """Adds `migrations/versions/<rev>.py` on `branch` (committed and pushed)."""
        down_text = "None" if down is None else f'"{down}"'
        text = f'revision = "{rev}"\ndown_revision = {down_text}\n'
        return self.commit(name, branch, f"{MIGRATIONS}/{rev}.py", text, f"feat: migration {rev}")

    def release_dir(self, day: str = DAY) -> Path:
        return self.data / "projects" / SLUG / f"release-{day}"

    def write_release(self, include: dict[str, list[str]], day: str = DAY) -> None:
        """Writes `release.toml`: `repos` in the given order and `[include]` per repo."""
        folder = self.release_dir(day)
        folder.mkdir(parents=True, exist_ok=True)
        lines = [f"repos = {_toml_list(list(include))}", "", "[include]"]
        lines += [f"{repo} = {_toml_list(branches)}" for repo, branches in include.items()]
        (folder / "release.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_pr(
        self,
        file: str,
        title: str,
        tasks: list[str],
        body: str,
        day: str = DAY,
        **front: list[str],
    ) -> Path:
        """Writes `pr/<file>.md`: TOML front matter between `+++` lines, then the body."""
        path = self.release_dir(day) / "pr" / f"{file}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        head = [f'title = "{title}"', f"tasks = {_toml_list(tasks)}"]
        head += [f"{key} = {_toml_list(values)}" for key, values in front.items()]
        path.write_text("+++\n" + "\n".join(head) + "\n+++\n" + body, encoding="utf-8")
        return path

    def refs(self, name: str) -> dict[str, str]:
        """Every ref of the bare origin: full ref name -> sha."""
        out = self._run(self.origin(name), "for-each-ref", "--format=%(refname) %(objectname)")
        return dict(line.split(" ") for line in out.splitlines())

    def _run(self, repo: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
            env=self.env,
        )
        return result.stdout.strip()

    def _create(self, name: str) -> None:
        origin = self.origin(name)
        origin.mkdir(parents=True)
        self._run(origin, "init", "-q", "--bare", "-b", "master")
        clone = self.clone(name)
        clone.mkdir(parents=True)
        self._run(clone, "init", "-q", "-b", "master")
        self.git(name, "remote", "add", "origin", str(origin))
        if name == "repo-a":
            self.commit(
                name,
                "master",
                f"{MIGRATIONS}/0001_base.py",
                f'revision = "{REV_BASE}"\ndown_revision = None\n',
                "chore: base",
            )
            ones = [("feature/TS-101-one", "one.txt"), ("feature/TS-102-two", "two.txt")]
        else:
            self.commit(name, "master", ".github/pull_request_template.md", TEMPLATE, "chore: base")
            ones = [("feature/TS-201-only", "only.txt")]
        for branch, path in ones:
            self.branch(name, branch, "master")
            self.commit(name, branch, path, f"{path}\n", f"feat: {path}")
        self.branch(name, "sandbox", "master")
        self.commit(name, "sandbox", "sandbox-only.txt", "sandbox\n", "chore: sandbox")
        self.git(name, "checkout", "-q", "master")
        self.git(name, "fetch", "-q", "origin")

    def _write_config(self) -> None:
        self.config_dir.mkdir(parents=True)
        text = f'[jira]\nsite = "{SITE}"\nemail = "dev@example.com"\n\n'
        text += '[release]\nsandbox_branch = "sandbox"\nbase_branch = "master"\n'
        for name in ("repo-a", "repo-b"):
            text += f'\n[release.repos.{name}]\nslug = "acme/{name}"\npath = "{self.clone(name)}"\n'
            if name == "repo-a":
                text += f'alembic = "{MIGRATIONS}"\n'
        (self.config_dir / "config.toml").write_text(text, encoding="utf-8")


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    root = tmp_path / "world"
    env = {
        **os.environ,
        **IDENTITY,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    for key, value in {
        "WS_CONFIG_DIR": str(root / "config"),
        "WS_DATA_DIR": str(root / "data"),
        "WS_REPO_ROOT": str(root / "root"),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        **IDENTITY,
    }.items():
        monkeypatch.setenv(key, value)
    return World(root, env)
