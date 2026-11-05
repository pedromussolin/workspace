import subprocess
import tomllib
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from ws.boardconfig import BoardConfig, parse_board
from ws.codeposition import fetch, positions

TODAY = date(2026, 11, 5)
BOARD = """\
fetch = false
{extra}

[[environments]]
name = "sandbox"
branches = ["sandbox", "staging"]
status = "validation"

[[environments]]
name = "master"
branches = ["master", "main"]
status = "ready_deploy"

[[environments]]
name = "production"
status = "done"
deploy_repo = "{{repo}}-argocd"
deploy_branch = "master"
image_tag = 'prod-([0-9a-f]{{7,40}})'

[statuses]
in_progress = "Em andamento"
validation = "In Validation"
ready_deploy = "Ready Deploy"
done = "Concluído"

{tables}
"""

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


def board(extra: str = "", tables: str = "") -> BoardConfig:
    text = BOARD.format(extra=extra, tables=tables)
    return parse_board(tomllib.loads(text), Path("config.toml"))


@pytest.fixture
def commit(git: Git, monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    def make(repo: Path, subject: str, day: str = "2026-10-20") -> None:
        stamp = f"{day}T12:00:00"
        monkeypatch.setenv("GIT_AUTHOR_DATE", stamp)
        monkeypatch.setenv("GIT_COMMITTER_DATE", stamp)
        git(repo, "commit", "-q", "--allow-empty", "-m", subject)

    return make


@pytest.fixture
def push(git: Git) -> Callable[[Path, str], None]:
    def run(repo: Path, branch: str) -> None:
        git(repo, "push", "-q", "origin", branch)

    return run


@pytest.fixture
def merge(git: Git, monkeypatch: pytest.MonkeyPatch) -> Callable[[Path, str, str], None]:
    def run(repo: Path, source: str, into: str) -> None:
        monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-10-21T12:00:00")
        monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-10-21T12:00:00")
        exists = git(repo, "rev-parse", "--verify", "-q", into, check=False).returncode == 0
        git(repo, "checkout", "-q", *([into] if exists else ["-b", into, "master"]))
        git(repo, "merge", "-q", "--no-ff", "-m", f"Merge {source}", source)

    return run


@pytest.fixture
def branch(git: Git) -> Callable[[Path, str], None]:
    def run(repo: Path, name: str) -> None:
        git(repo, "checkout", "-q", "-b", name, "master")

    return run


def test_branch_commit_only_is_in_progress(clone, branch, commit, push):
    repo = clone("demo-api")
    branch(repo, "feature/TS-101-x")
    commit(repo, "feat: TS-101 x")
    push(repo, "feature/TS-101-x")
    result, _ = positions([repo], {"TS-101"}, board(), TODAY, set())
    position = result["TS-101"]
    assert (position.rung, position.environment) == (1, None)
    assert position.holding.branch.endswith("feature/TS-101-x")
    assert position.holding.reached is None
    assert position.repos == ("demo-api",)


def test_local_only_commit_is_in_progress(clone, branch, commit):
    repo = clone("demo-api")
    branch(repo, "feature/TS-101-x")
    commit(repo, "feat: TS-101 x")
    result, _ = positions([repo], {"TS-101"}, board(), TODAY, set())
    assert result["TS-101"].rung == 1


def test_empty_branch_has_no_position(clone, branch, push):
    repo = clone("demo-api")
    branch(repo, "feature/TS-102-y")
    push(repo, "feature/TS-102-y")
    result, _ = positions([repo], {"TS-102"}, board(), TODAY, set())
    assert "TS-102" not in result


def test_in_sandbox_is_validation(clone, branch, commit, merge, push):
    repo = clone("demo-api")
    branch(repo, "feature/TS-101-x")
    commit(repo, "feat: TS-101 x")
    merge(repo, "feature/TS-101-x", "sandbox")
    push(repo, "sandbox")
    result, _ = positions([repo], {"TS-101"}, board(), TODAY, set())
    position = result["TS-101"]
    assert (position.rung, position.environment) == (2, "sandbox")
    assert position.holding.reached == "sandbox"


def test_merge_commits_do_not_count(clone, branch, commit, merge, git):
    repo = clone("demo-api")
    branch(repo, "feature/x")
    commit(repo, "feat: x")
    merge(repo, "feature/x", "master")
    git(repo, "commit", "-q", "--amend", "--allow-empty", "-m", "Merge TS-104 into master")
    result, _ = positions([repo], {"TS-104"}, board(), TODAY, set())
    assert "TS-104" not in result


def test_hotfix_without_sandbox_reaches_master(clone, commit, push):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 hotfix")
    push(repo, "master")
    result, _ = positions([repo], {"TS-101"}, board(), TODAY, set())
    assert (result["TS-101"].rung, result["TS-101"].environment) == (3, "master")
    assert result["TS-101"].limited is True


def test_repo_override_branch_name(clone, branch, commit, merge, push):
    repo = clone("demo-api")
    branch(repo, "feature/TS-101-x")
    commit(repo, "feat: TS-101 x")
    merge(repo, "feature/TS-101-x", "homolog")
    push(repo, "homolog")
    cfg = board(tables='[repos."demo-api".branches]\nsandbox = ["homolog"]')
    result, _ = positions([repo], {"TS-101"}, cfg, TODAY, set())
    assert (result["TS-101"].rung, result["TS-101"].environment) == (2, "sandbox")


def test_key_prefix_does_not_match(clone, branch, commit, merge, push):
    repo = clone("demo-api")
    branch(repo, "feature/TS-150-a")
    commit(repo, "feat: TS-150 a")
    merge(repo, "feature/TS-150-a", "sandbox")
    push(repo, "sandbox")
    branch(repo, "feature/TS-15-b")
    commit(repo, "feat: TS-15 b")
    push(repo, "feature/TS-15-b")
    result, _ = positions([repo], {"TS-150", "TS-15"}, board(), TODAY, set())
    assert result["TS-150"].rung == 2
    assert result["TS-15"].rung == 1


def test_commit_older_than_lookback_is_ignored(clone, branch, commit):
    repo = clone("demo-api")
    branch(repo, "feature/TS-101-x")
    commit(repo, "feat: TS-101 x", day="2026-09-06")
    cfg = board(extra="lookback_days = 30")
    result, _ = positions([repo], {"TS-101"}, cfg, TODAY, set())
    assert result == {}


def test_stale_repo_marks_position_stale(clone, branch, commit):
    repo = clone("demo-api")
    branch(repo, "feature/TS-101-x")
    commit(repo, "feat: TS-101 x")
    fresh, _ = positions([repo], {"TS-101"}, board(), TODAY, set())
    stale, _ = positions([repo], {"TS-101"}, board(), TODAY, {"demo-api"})
    assert fresh["TS-101"].stale is False
    assert stale["TS-101"].stale is True


def test_repo_without_remote_is_one_warning(clone):
    first = clone("notes-a", remote=False)
    second = clone("notes-b", remote=False)
    healthy = clone("demo-api")
    _, warnings = positions([second, healthy, first], set(), board(), TODAY, set())
    assert warnings == ["no remote 'origin' (only prove in progress): notes-a, notes-b"]


def test_personal_repo_commit_only_proves_in_progress(clone, commit):
    personal = clone("notes", remote=False)
    commit(personal, "chore: TS-105 notes")
    result, _ = positions([personal], {"TS-105"}, board(), TODAY, set())
    assert result["TS-105"].rung == 1
    assert result["TS-105"].holding is None


def test_direct_deploy_repo_master_is_production(clone, commit, push):
    repo = clone("demo-api-argocd")
    commit(repo, "chore(TS-107): bump")
    push(repo, "master")
    cfg = board(extra='direct_deploy_repos = ["*-argocd"]')
    result, _ = positions([repo], {"TS-107"}, cfg, TODAY, set())
    assert (result["TS-107"].rung, result["TS-107"].environment) == (4, "production")
    plain, _ = positions([repo], {"TS-107"}, board(), TODAY, set())
    assert plain["TS-107"].rung == 3
    assert plain["TS-107"].limited is True
    assert result["TS-107"].limited is False


def test_git_failure_in_one_repo_is_a_warning(clone, commit, git):
    broken = clone("demo-api")
    commit(broken, "feat: TS-101 x")
    (broken / ".git" / "HEAD").write_text("garbage")
    healthy = clone("demo-web")
    commit(healthy, "feat: TS-101 y")
    result, warnings = positions([broken, healthy], {"TS-101"}, board(), TODAY, set())
    assert result["TS-101"].repos == ("demo-web",)
    assert any(line.startswith("repo demo-api: left out (") for line in warnings)
