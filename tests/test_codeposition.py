import subprocess
import tomllib
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from ws import codeposition
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
    result, warnings = positions([repo], {"TS-107"}, cfg, TODAY, set())
    assert (result["TS-107"].rung, result["TS-107"].environment) == (4, "production")
    assert warnings == []
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


@pytest.fixture
def tags(clone, git, commit, push) -> Callable[..., Path]:
    """A deploy repo whose master holds one values file per entry of `files`."""

    def make(files: dict[str, str], name: str = "demo-api-argocd") -> Path:
        deploy = clone(name)
        for filename, content in files.items():
            (deploy / filename).write_text(content, encoding="utf-8")
        git(deploy, "add", ".")
        commit(deploy, "chore: bump tags")
        push(deploy, "master")
        return deploy

    return make


def head(git: Git, repo: Path, ref: str = "HEAD") -> str:
    return git(repo, "rev-parse", ref).stdout.strip()[:7]


def values(sha: str) -> str:
    return f"image:\n  tag: prod-{sha}\n"


def test_in_master_not_deployed_is_ready_deploy(clone, git, commit, push, tags):
    repo = clone("demo-api")
    old = head(git, repo)
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    deploy = tags({"values.yaml": values(old)})
    result, _ = positions([repo, deploy], {"TS-101"}, board(), TODAY, set())
    position = result["TS-101"]
    assert (position.rung, position.environment) == (3, "master")
    assert position.holding.reached == "master"
    assert position.limited is False


def test_in_every_production_tag_is_done(clone, git, commit, push, tags):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    new = head(git, repo)
    deploy = tags({"a.yaml": values(new), "b.yaml": values(new)})
    result, warnings = positions([repo, deploy], {"TS-101"}, board(), TODAY, set())
    assert (result["TS-101"].rung, result["TS-101"].environment) == (4, "production")
    assert result["TS-101"].holding is None
    assert warnings == []


def test_one_stale_tag_holds_the_card(clone, git, commit, push, tags):
    repo = clone("demo-api")
    old = head(git, repo)
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    new = head(git, repo)
    deploy = tags({"a.yaml": values(new), "b.yaml": values(old)})
    result, _ = positions([repo, deploy], {"TS-101"}, board(), TODAY, set())
    assert result["TS-101"].rung == 3
    assert result["TS-101"].holding.reached == "master"
    assert result["TS-101"].holding.tag == f"prod-{old}"


def test_tag_of_another_app_is_ignored(clone, git, commit, push, tags):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    new = head(git, repo)
    deploy = tags({"a.yaml": values(new), "b.yaml": values(new), "c.yaml": values("deadbee")})
    result, _ = positions([repo, deploy], {"TS-101"}, board(), TODAY, set())
    assert result["TS-101"].rung == 4


def test_unmerged_commit_holds_the_card(clone, git, branch, commit, push, tags):
    repo = clone("demo-api")
    commit(repo, "fix: TS-103 a")
    push(repo, "master")
    new = head(git, repo)
    branch(repo, "feature/TS-103-b")
    commit(repo, "fix: TS-103 b")
    push(repo, "feature/TS-103-b")
    deploy = tags({"a.yaml": values(new)})
    result, _ = positions([repo, deploy], {"TS-103"}, board(), TODAY, set())
    position = result["TS-103"]
    assert position.rung == 1
    assert position.holding.branch.endswith("feature/TS-103-b")


def test_personal_repo_commit_does_not_hold_a_deployed_card(clone, git, commit, push, tags):
    repo = clone("demo-api")
    commit(repo, "fix: TS-105 a")
    push(repo, "master")
    personal = clone("notes", remote=False)
    commit(personal, "chore: TS-105 notes")
    deploy = tags({"a.yaml": values(head(git, repo))})
    result, _ = positions([repo, personal, deploy], {"TS-105"}, board(), TODAY, set())
    assert result["TS-105"].rung == 4
    assert result["TS-105"].repos == ("demo-api", "notes")


def test_deploy_repo_master_commit_does_not_hold(clone, git, commit, push, tags):
    repo = clone("demo-api")
    commit(repo, "fix: TS-106 a")
    push(repo, "master")
    deploy = tags({"a.yaml": values(head(git, repo))})
    commit(deploy, "chore(TS-106): bump")
    push(deploy, "master")
    result, _ = positions([repo, deploy], {"TS-106"}, board(), TODAY, set())
    assert result["TS-106"].rung == 4


def test_missing_deploy_repo_warns_only_for_repos_with_keys(clone, commit, push, tags):
    repo = clone("demo-api")
    commit(repo, "fix: TS-108 a")
    push(repo, "master")
    other = clone("other-api")
    _, warnings = positions([repo, other], {"TS-108"}, board(), TODAY, set())
    assert warnings == ["deploy demo-api: demo-api-argocd not found"]
    deploy = tags({"a.yaml": values("deadbee")})
    _, warnings = positions([repo, other, deploy], {"TS-108"}, board(), TODAY, set())
    assert warnings == ["deploy demo-api: no image tag of this repo in demo-api-argocd"]


def test_repo_override_deploy_repo(clone, git, commit, push, tags):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    deploy = tags({"a.yaml": values(head(git, repo))}, name="deploys")
    cfg = board(tables='[repos."demo-api"]\ndeploy_repo = "deploys"')
    result, warnings = positions([repo, deploy], {"TS-101"}, cfg, TODAY, set())
    assert result["TS-101"].rung == 4
    assert warnings == []


def test_stash_does_not_hold_a_deployed_card(clone, git, commit, push, tags):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    deploy = tags({"a.yaml": values(head(git, repo))})
    (repo / "scratch.txt").write_text("wip", encoding="utf-8")
    git(repo, "add", "scratch.txt")
    git(repo, "stash", "push", "-q", "-m", "wip TS-101")
    result, _ = positions([repo, deploy], {"TS-101"}, board(), TODAY, set())
    assert result["TS-101"].rung == 4


def test_grep_failure_in_deploy_repo_is_its_own_warning(
    clone, git, commit, push, tags, monkeypatch
):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    deploy = tags({"a.yaml": values(head(git, repo))})
    real = codeposition._run

    def failing(path, *args, **kwargs):
        if args[0] == "grep":
            return subprocess.CompletedProcess(args, 2, "", "fatal: grep exploded\n")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(codeposition, "_run", failing)
    result, warnings = positions([repo, deploy], {"TS-101"}, board(), TODAY, set())
    assert warnings == ["deploy demo-api: fatal: grep exploded"]
    assert result["TS-101"].rung == 3


def test_missing_deploy_branch_is_no_image_tag(clone, commit, push, tags):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    deploy = tags({"a.yaml": values("deadbee")})
    text = BOARD.format(extra="", tables="").replace(
        'deploy_branch = "master"', 'deploy_branch = "nope"'
    )
    cfg = parse_board(tomllib.loads(text), Path("config.toml"))
    _, warnings = positions([repo, deploy], {"TS-101"}, cfg, TODAY, set())
    assert warnings == ["deploy demo-api: no image tag of this repo in demo-api-argocd"]


def test_holding_branch_failure_keeps_the_card(clone, branch, commit, push, monkeypatch):
    repo = clone("demo-api")
    branch(repo, "feature/TS-101-x")
    commit(repo, "feat: TS-101 x")
    push(repo, "feature/TS-101-x")
    real = codeposition._git_out

    def failing(path, *args, **kwargs):
        if args[0] == "branch":
            raise RuntimeError("branch exploded")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(codeposition, "_git_out", failing)
    result, warnings = positions([repo], {"TS-101"}, board(), TODAY, set())
    assert result["TS-101"].rung == 1
    assert result["TS-101"].holding.branch is None
    assert "repo demo-api: holding branch unknown (branch exploded)" in warnings
