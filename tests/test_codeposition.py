import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from ws.codeposition import fetch

Git = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def clone(tmp_path: Path, git: Git) -> Callable[[str], Path]:
    """A repo under roots/ with a bare remote under remotes/ and one pushed first commit."""

    def make(name: str, remote: bool = True) -> Path:
        path = tmp_path / "roots" / name
        path.mkdir(parents=True)
        git(path, "init", "-q", "-b", "master")
        git(path, "commit", "-q", "--allow-empty", "-m", "initial")
        if remote:
            bare = tmp_path / "remotes" / f"{name}.git"
            bare.mkdir(parents=True)
            git(bare, "init", "-q", "--bare")
            git(path, "remote", "add", "origin", str(bare))
            git(path, "push", "-q", "origin", "master")
        return path

    return make


def test_fetch_failure_is_reported_and_no_remote_is_silent(clone, git, tmp_path):
    broken = clone("demo-api")
    git(broken, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    healthy = clone("demo-web")
    personal = clone("notes", remote=False)
    errors = fetch([broken, healthy, personal], "origin")
    assert list(errors) == ["demo-api"]
    assert errors["demo-api"]
