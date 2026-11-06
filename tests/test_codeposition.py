import subprocess
import tomllib
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from ws import boardproofs, codeposition
from ws.boardconfig import BoardConfig, parse_board
from ws.codeposition import fetch, positions

TODAY = date(2026, 11, 5)
BOARD = """\
fetch = false
default_profile = "gitops"
{extra}

[[profiles.gitops.environments]]
name = "sandbox"
status = "validation"
proof = "branch"
branches = ["sandbox", "staging"]

[[profiles.gitops.environments]]
name = "master"
status = "ready_deploy"
proof = "branch"
branches = ["master", "main"]

[[profiles.gitops.environments]]
name = "production"
status = "done"
proof = "file"
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
HOMOLOG = """
[[profiles.homolog.environments]]
name = "sandbox"
status = "validation"
proof = "branch"
branches = ["homolog"]

[repos."demo-api"]
profile = "homolog"
"""
DIRECT = """
[[profiles.direct.environments]]
name = "production"
status = "done"
proof = "branch"
branches = ["master"]

[repos."*-argocd"]
profile = "direct"
"""
OTHER_DEPLOY = """
[[profiles.other-deploy.environments]]
name = "master"
status = "ready_deploy"
proof = "branch"
branches = ["master"]

[[profiles.other-deploy.environments]]
name = "production"
status = "done"
proof = "file"
deploy_repo = "deploys"
image_tag = 'prod-([0-9a-f]{7,40})'

[repos."demo-api"]
profile = "other-deploy"
"""
RELEASE = """
[[profiles.release.environments]]
name = "main"
status = "ready_deploy"
proof = "branch"
branches = ["master"]

[[profiles.release.environments]]
name = "production"
status = "done"
proof = "tag"
tag = "v*"

[repos."demo-api"]
profile = "release"
"""
API = """
[[profiles.api.environments]]
name = "main"
status = "ready_deploy"
proof = "branch"
branches = ["master"]

[[profiles.api.environments]]
name = "production"
status = "done"
proof = "command"
command = ["~/bin/deployed-sha", "{repo}", "{env}"]
timeout = 2

[repos."demo-api"]
profile = "api"
"""
TRUNK = """
[[profiles.trunk.environments]]
name = "trunk"
status = "ready_deploy"
proof = "branch"
branches = ["master"]

[repos."demo-web"]
profile = "trunk"
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
    errors = fetch([broken, healthy, personal], board())
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
    push(repo, "master:sandbox")
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
    cfg = board(tables=HOMOLOG)
    result, _ = positions([repo], {"TS-101"}, cfg, TODAY, set())
    assert (result["TS-101"].rung, result["TS-101"].environment) == (2, "sandbox")


def test_inactive_environment_proves_nothing(clone, branch, commit, merge, push):
    repo = clone("demo-api")
    branch(repo, "feature/TS-101-x")
    commit(repo, "feat: TS-101 x")
    merge(repo, "feature/TS-101-x", "sandbox")
    push(repo, "sandbox")
    cfg = board(tables='[repos."demo-*"]\ninactive = ["sandbox"]')
    result, _ = positions([repo], {"TS-101"}, cfg, TODAY, set())
    assert (result["TS-101"].rung, result["TS-101"].environment) == (1, None)


def test_environment_name_comes_from_the_repo_profile(clone, commit, push):
    repo = clone("demo-web")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    result, _ = positions([repo], {"TS-101"}, board(tables=TRUNK), TODAY, set())
    assert (result["TS-101"].rung, result["TS-101"].environment) == (3, "trunk")
    assert result["TS-101"].limited is True


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


def test_profile_with_master_as_production(clone, commit, push):
    repo = clone("demo-api-argocd")
    commit(repo, "chore(TS-107): bump")
    push(repo, "master")
    cfg = board(tables=DIRECT)
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


def test_unresolved_tag_among_resolved_ones_holds_the_environment(
    clone, git, commit, push, tags
):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    new = head(git, repo)
    deploy = tags({"a.yaml": values(new), "b.yaml": values(new), "c.yaml": values("deadbee")})
    result, warnings = positions([repo, deploy], {"TS-101"}, board(), TODAY, set())
    assert warnings == ["deploy demo-api: tag prod-deadbee not found in this repo"]
    assert (result["TS-101"].rung, result["TS-101"].limited) == (3, True)


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
    cfg = board(tables=OTHER_DEPLOY)
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
    real = boardproofs.run_git

    def failing(path, *args, **kwargs):
        if args[0] == "grep":
            return subprocess.CompletedProcess(args, 2, "", "fatal: grep exploded\n")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(boardproofs, "run_git", failing)
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
    real = codeposition.git_out

    def failing(path, *args, **kwargs):
        if args[0] == "branch":
            raise RuntimeError("branch exploded")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(codeposition, "git_out", failing)
    result, warnings = positions([repo], {"TS-101"}, board(), TODAY, set())
    assert result["TS-101"].rung == 1
    assert result["TS-101"].holding.branch is None
    assert "repo demo-api: holding branch unknown (branch exploded)" in warnings


def test_fetch_never_prompts_for_credentials(clone, monkeypatch):
    repo = clone("demo-api")
    seen = []
    real = subprocess.run

    def spy(command, *args, **kwargs):
        if "fetch" in command:
            seen.append(kwargs.get("env"))
        return real(command, *args, **kwargs)

    monkeypatch.setattr(codeposition.subprocess, "run", spy)
    assert fetch([repo], board()) == {}
    assert len(seen) == 1
    assert seen[0]["GIT_TERMINAL_PROMPT"] == "0"
    assert seen[0]["PATH"]


@pytest.fixture
def tag(git: Git, monkeypatch: pytest.MonkeyPatch) -> Callable[[Path, str, str, str], None]:
    """An annotated tag on `ref` created on `day`, so its creatordate is that day."""

    def make(repo: Path, name: str, ref: str, day: str) -> None:
        monkeypatch.setenv("GIT_COMMITTER_DATE", f"{day}T12:00:00")
        git(repo, "tag", "-a", name, "-m", name, ref)

    return make


def test_commit_before_the_newest_release_tag_is_done(clone, git, commit, push, tag):
    repo = clone("demo-api")
    tag(repo, "v2.0", "HEAD", "2026-10-01")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    tag(repo, "v1.0", "HEAD", "2026-10-22")
    commit(repo, "chore: after the release", day="2026-10-23")
    tag(repo, "build-7", "HEAD", "2026-10-24")
    result, warnings = positions([repo], {"TS-101"}, board(tables=RELEASE), TODAY, set())
    assert (result["TS-101"].rung, result["TS-101"].environment) == (4, "production")
    assert result["TS-101"].holding is None
    assert warnings == []


def test_commit_after_the_newest_release_tag_is_held_below(clone, commit, push, tag):
    repo = clone("demo-api")
    tag(repo, "v1.0", "HEAD", "2026-10-01")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    result, _ = positions([repo], {"TS-101"}, board(tables=RELEASE), TODAY, set())
    position = result["TS-101"]
    assert (position.rung, position.environment) == (3, "main")
    assert position.holding.reached == "main"
    assert position.holding.tag == "v1.0"
    assert position.limited is False


def test_repo_without_release_tag_proves_up_to_main_silently(clone, commit, push):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    result, warnings = positions([repo], {"TS-101"}, board(tables=RELEASE), TODAY, set())
    assert (result["TS-101"].rung, result["TS-101"].limited) == (3, True)
    assert warnings == []


def test_fetch_takes_tags_only_for_repos_with_a_tag_proof(clone, monkeypatch):
    released = clone("demo-api")
    plain = clone("demo-web")
    seen = {}
    real = subprocess.run

    def spy(command, *args, **kwargs):
        if "fetch" in command:
            seen[Path(command[command.index("-C") + 1]).name] = command
        return real(command, *args, **kwargs)

    monkeypatch.setattr(codeposition.subprocess, "run", spy)
    assert fetch([released, plain], board(tables=RELEASE)) == {}
    assert "--tags" in seen["demo-api"] and "--no-tags" not in seen["demo-api"]
    assert "--no-tags" in seen["demo-web"] and "--tags" not in seen["demo-web"]


@pytest.fixture
def deployed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """~/bin/deployed-sha: prints ~/deployed when called as `demo-api production`, else fails."""
    monkeypatch.setenv("HOME", str(tmp_path))
    script = tmp_path / "bin" / "deployed-sha"
    script.parent.mkdir()

    def make(body: str) -> None:
        script.write_text(
            "#!/bin/sh\n"
            '[ "$1" = demo-api ] && [ "$2" = production ] || { echo "bad args: $*" >&2; exit 9; }\n'
            f"{body}\n",
            encoding="utf-8",
        )
        script.chmod(0o755)

    return make


def test_command_printing_the_deployed_sha_is_done(clone, git, commit, push, deployed):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    deployed(f"echo; echo {head(git, repo)}; echo")
    result, warnings = positions([repo], {"TS-101"}, board(tables=API), TODAY, set())
    assert (result["TS-101"].rung, result["TS-101"].environment) == (4, "production")
    assert warnings == []


def test_command_older_sha_holds_the_card(clone, git, commit, push, deployed):
    repo = clone("demo-api")
    old = head(git, repo)
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    deployed(f"echo {old}")
    result, warnings = positions([repo], {"TS-101"}, board(tables=API), TODAY, set())
    assert result["TS-101"].rung == 3
    assert (result["TS-101"].holding.reached, result["TS-101"].holding.tag) == ("main", old)
    assert warnings == []


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("echo 'no deploy found' >&2; exit 1", "exit 1: no deploy found"),
        ("exec sleep 5", "timeout after 2s"),
        ("echo deadbee", "deadbee not found in this repo"),
        ("echo 'deployed: abc1234'", "'deployed: abc1234' is not a sha"),
    ],
)
def test_command_failure_is_a_warning_and_proves_nothing(
    clone, commit, push, deployed, body, error
):
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    deployed(body)
    result, warnings = positions([repo], {"TS-101"}, board(tables=API), TODAY, set())
    assert warnings == [f"proof demo-api/production: {error}"]
    assert (result["TS-101"].rung, result["TS-101"].limited) == (3, True)


def test_command_that_cannot_run_is_a_warning(clone, commit, push, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = clone("demo-api")
    commit(repo, "fix: TS-101 x")
    push(repo, "master")
    result, warnings = positions([repo], {"TS-101"}, board(tables=API), TODAY, set())
    assert len(warnings) == 1
    assert warnings[0].startswith("proof demo-api/production: ")
    assert str(tmp_path / "bin" / "deployed-sha") in warnings[0]
    assert result["TS-101"].rung == 3
