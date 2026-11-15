import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ws import cli, config, gittools


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def commit(repo: Path, filename: str, content: str, *messages: str) -> str:
    (repo / filename).write_text(content)
    git(repo, "add", filename)
    message_args = [arg for message in messages for arg in ("-m", message)]
    git(repo, "commit", "-q", *message_args)
    return git(repo, "rev-parse", "HEAD")


def branch_from_main(repo: Path, name: str) -> None:
    git(repo, "switch", "-q", "-c", name, "main")


@pytest.fixture
def repo(tmp_path) -> Path:
    path = tmp_path / "acme"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "commit.gpgsign", "false")
    commit(path, "a.txt", "base\n", "chore: initial commit")
    return path


@pytest.fixture
def conflicting_branches(repo) -> None:
    for name, content in (("feat/one", "one\n"), ("feat/two", "two\n")):
        branch_from_main(repo, name)
        commit(repo, "a.txt", content, f"feat: {name} edits a")
        git(repo, "switch", "-q", "main")


def write_script(directory: Path, name: str, body: str, mode: int = 0o755) -> None:
    directory.mkdir(exist_ok=True)
    script = directory / name
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(mode)


def test_assemble_rewrites_subject_keeps_body(repo):
    git(repo, "config", "branch.autoSetupMerge", "always")
    branch_from_main(repo, "wip")
    commit(repo, "b.txt", "b\n", "wip: add b", "Body line one.\n\nBody line two.")
    commit(repo, "c.txt", "c\n", "feat: add c")

    subjects = gittools.assemble(repo, "main", "wip", "final", {"wip: add b": "feat: add b"})

    assert subjects == ["feat: add b", "feat: add c"]
    assert git(repo, "branch", "--show-current") == "final"
    assert git(repo, "log", "-1", "--format=%B", "final~1") == (
        "feat: add b\n\nBody line one.\n\nBody line two."
    )
    assert git(repo, "diff", "wip", "final") == ""
    assert git(repo, "log", "--format=%s", "main..wip").splitlines()[1] == "wip: add b"
    assert git(repo, "for-each-ref", "--format=%(upstream)", "refs/heads/final") == ""


def test_assemble_rejects_long_subject(repo):
    long_subject = "feat: " + "x" * 67
    exact_subject = "feat: " + "y" * 66
    assert (len(long_subject), len(exact_subject)) == (73, 72)
    branch_from_main(repo, "wip")
    commit(repo, "b.txt", "b\n", long_subject)
    commit(repo, "c.txt", "c\n", exact_subject)

    with pytest.raises(gittools.SubjectTooLong) as exc:
        gittools.assemble(repo, "main", "wip", "final", {})

    assert exc.value.subjects == [long_subject]
    assert git(repo, "branch", "--list", "final") == ""
    assert git(repo, "branch", "--show-current") == "wip"

    subjects = gittools.assemble(repo, "main", "wip", "final", {long_subject: "feat: short"})
    assert subjects == ["feat: short", exact_subject]


def test_assemble_stops_on_conflict(repo):
    branch_from_main(repo, "wip")
    wip_sha = commit(repo, "a.txt", "wip\n", "feat: wip edits a")
    git(repo, "switch", "-q", "main")
    commit(repo, "a.txt", "main\n", "feat: main edits a")

    with pytest.raises(gittools.CherryPickConflict) as exc:
        gittools.assemble(repo, "main", "wip", "final", {})

    assert exc.value.sha == wip_sha
    assert git(repo, "branch", "--show-current") == "final"
    assert gittools.conflicted_files(repo) == ["a.txt"]
    assert git(repo, "rev-parse", "--verify", "CHERRY_PICK_HEAD") == wip_sha


def test_assemble_reports_an_empty_pick(repo):
    branch_from_main(repo, "wip")
    wip_sha = commit(repo, "b.txt", "b\n", "wip: add b")
    git(repo, "switch", "-q", "main")
    commit(repo, "b.txt", "b\n", "feat: add b on main")

    with pytest.raises(gittools.EmptyCherryPick) as exc:
        gittools.assemble(repo, "main", "wip", "final", {})

    assert exc.value.sha == wip_sha
    assert git(repo, "branch", "--show-current") == "final"
    assert gittools.conflicted_files(repo) == []
    assert git(repo, "rev-parse", "--verify", "CHERRY_PICK_HEAD") == wip_sha


def test_assemble_refuses_merge_commits_before_switching(repo):
    branch_from_main(repo, "side")
    commit(repo, "s.txt", "s\n", "feat: add s")
    branch_from_main(repo, "wip")
    commit(repo, "w.txt", "w\n", "feat: add w")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")

    with pytest.raises(gittools.GitError, match="merge commits"):
        gittools.assemble(repo, "main", "wip", "final", {})

    assert git(repo, "branch", "--list", "final") == ""
    assert git(repo, "branch", "--show-current") == "wip"


def test_assemble_refuses_a_dirty_work_tree_before_switching(repo):
    branch_from_main(repo, "wip")
    commit(repo, "b.txt", "b\n", "feat: add b")
    (repo / "untracked.txt").write_text("not tracked\n")
    (repo / "a.txt").write_text("changed\n")

    with pytest.raises(gittools.GitError, match="uncommitted"):
        gittools.assemble(repo, "main", "wip", "final", {})

    assert git(repo, "branch", "--list", "final") == ""
    assert git(repo, "branch", "--show-current") == "wip"
    git(repo, "checkout", "--", "a.txt")
    assert gittools.assemble(repo, "main", "wip", "final", {}) == ["feat: add b"]


def test_assemble_refuses_staged_changes_before_switching(repo):
    branch_from_main(repo, "wip")
    commit(repo, "b.txt", "b\n", "feat: add b")
    (repo / "a.txt").write_text("changed\n")
    git(repo, "add", "a.txt")

    with pytest.raises(gittools.GitError, match="uncommitted"):
        gittools.assemble(repo, "main", "wip", "final", {})

    assert git(repo, "branch", "--list", "final") == ""


def test_assemble_subjects_may_be_keyed_by_sha(repo):
    branch_from_main(repo, "wip")
    first = commit(repo, "b.txt", "b\n", "wip")
    second = commit(repo, "c.txt", "c\n", "wip")
    commit(repo, "d.txt", "d\n", "wip: add d")

    subjects = gittools.assemble(
        repo,
        "main",
        "wip",
        "final",
        {first: "feat: add b", second[:8].upper(): "feat: add c", "wip: add d": "feat: add d"},
    )

    assert subjects == ["feat: add b", "feat: add c", "feat: add d"]


def test_assemble_sha_key_wins_over_subject_key(repo):
    branch_from_main(repo, "wip")
    commit(repo, "b.txt", "b\n", "wip")
    second = commit(repo, "c.txt", "c\n", "wip")

    subjects = gittools.assemble(
        repo, "main", "wip", "final", {"wip": "feat: generic", second[:7]: "feat: specific"}
    )

    assert subjects == ["feat: generic", "feat: specific"]


def test_rehearsal_clean_merge_runs_check(repo, tmp_path, capsys):
    for name, filename in (("feat/x", "x.txt"), ("feat/y", "y.txt")):
        branch_from_main(repo, name)
        commit(repo, filename, "content\n", f"feat: add {filename}")
        git(repo, "switch", "-q", "main")
    worktree = tmp_path / "rehearsal"

    code = gittools.merge_rehearsal(
        repo, "main", ["feat/x", "feat/y"], worktree, None, "test -f x.txt && test -f y.txt"
    )

    assert code == 0
    assert capsys.readouterr().out.splitlines() == ["ok feat/x", "ok feat/y"]
    assert git(repo, "branch", "--show-current") == "main"

    again = gittools.merge_rehearsal(repo, "main", ["feat/x"], worktree, None, "test ! -f y.txt")
    assert again == 0
    assert gittools.merge_rehearsal(repo, "main", ["feat/x"], worktree, None, "exit 3") == 3
    assert gittools.merge_rehearsal(repo, "main", ["feat/x"], worktree, None, None) == 0


def test_rehearsal_conflict_without_resolution_returns_1(
    repo, conflicting_branches, tmp_path, capsys
):
    worktree = tmp_path / "rehearsal"

    code = gittools.merge_rehearsal(
        repo, "main", ["feat/one", "feat/two"], worktree, None, "exit 0"
    )

    assert code == 1
    assert capsys.readouterr().out.splitlines() == [
        "ok feat/one",
        "CONFLICT feat/two: a.txt",
        f"(worktree stopped at the conflict: {worktree})",
    ]
    assert gittools.conflicted_files(worktree) == ["a.txt"]


def test_rehearsal_applies_resolution_script(repo, conflicting_branches, tmp_path, capsys):
    resolutions = tmp_path / "resolutions"
    write_script(resolutions, "feat_two.sh", "printf 'merged\\n' > a.txt\ngit add a.txt\n")
    worktree = tmp_path / "rehearsal"

    code = gittools.merge_rehearsal(
        repo, "main", ["feat/one", "feat/two"], worktree, resolutions, "grep -q merged a.txt"
    )

    assert code == 0
    assert capsys.readouterr().out.splitlines() == [
        "ok feat/one",
        "resolved feat/two: a.txt",
    ]
    assert git(worktree, "status", "--porcelain") == ""
    assert git(worktree, "log", "-1", "--format=%P").count(" ") == 1


def test_rehearsal_ignores_non_executable_resolution(repo, conflicting_branches, tmp_path, capsys):
    resolutions = tmp_path / "resolutions"
    write_script(resolutions, "feat_two.sh", "git add a.txt\n", mode=0o644)

    code = gittools.merge_rehearsal(
        repo, "main", ["feat/one", "feat/two"], tmp_path / "rehearsal", resolutions, None
    )

    assert code == 1
    assert "CONFLICT feat/two: a.txt" in capsys.readouterr().out


def test_rehearsal_script_that_leaves_conflict_returns_1(
    repo, conflicting_branches, tmp_path, capsys
):
    resolutions = tmp_path / "resolutions"
    write_script(resolutions, "feat_two.sh", "printf 'merged\\n' > a.txt\n")

    code = gittools.merge_rehearsal(
        repo, "main", ["feat/one", "feat/two"], tmp_path / "rehearsal", resolutions, None
    )

    assert code == 1
    assert "CONFLICT feat/two: a.txt" in capsys.readouterr().out


def test_rehearsal_script_that_fails_is_a_conflict_even_if_it_staged_everything(
    repo, conflicting_branches, tmp_path, capsys
):
    resolutions = tmp_path / "resolutions"
    write_script(resolutions, "feat_two.sh", "printf 'merged\\n' > a.txt\ngit add a.txt\nexit 3\n")
    worktree = tmp_path / "rehearsal"

    code = gittools.merge_rehearsal(
        repo, "main", ["feat/one", "feat/two"], worktree, resolutions, "exit 0"
    )

    assert code == 1
    assert capsys.readouterr().out.splitlines() == [
        "ok feat/one",
        "CONFLICT feat/two: a.txt",
        "(resolution script feat_two.sh exited with code 3)",
        f"(worktree stopped at the conflict: {worktree})",
    ]
    assert git(worktree, "rev-parse", "--verify", "MERGE_HEAD")


def make_other_repo(tmp_path: Path) -> Path:
    other = tmp_path / "elsewhere" / "acme"
    other.mkdir(parents=True)
    git(other, "init", "-q", "-b", "main")
    git(other, "config", "user.name", "Test")
    git(other, "config", "user.email", "test@example.com")
    commit(other, "a.txt", "base\n", "chore: initial commit")
    return other


def test_rehearsal_refuses_a_worktree_of_another_repo(repo, tmp_path):
    worktree = tmp_path / "rehearsal"
    assert gittools.merge_rehearsal(repo, "main", [], worktree, None, None) == 0
    other = make_other_repo(tmp_path)

    with pytest.raises(gittools.GitError, match="not a worktree of"):
        gittools.merge_rehearsal(other, "main", [], worktree, None, None)

    assert git(worktree, "rev-parse", "--git-common-dir") == str(repo / ".git")


def test_rehearsal_refuses_a_folder_that_is_not_a_worktree(repo, tmp_path):
    folder = tmp_path / "plain"
    folder.mkdir()
    (folder / "notes.txt").write_text("mine\n")

    with pytest.raises(gittools.GitError, match="not a worktree of"):
        gittools.merge_rehearsal(repo, "main", [], folder, None, None)

    assert (folder / "notes.txt").read_text() == "mine\n"


def test_rehearsal_refuses_the_main_work_tree(repo):
    with pytest.raises(gittools.GitError, match="main work tree"):
        gittools.merge_rehearsal(repo, "main", [], repo, None, None)

    assert git(repo, "branch", "--show-current") == "main"


def test_rehearsal_recreates_a_worktree_deleted_by_hand(repo, tmp_path):
    worktree = tmp_path / "rehearsal"
    assert gittools.merge_rehearsal(repo, "main", [], worktree, None, None) == 0
    shutil.rmtree(worktree)

    assert gittools.merge_rehearsal(repo, "main", [], worktree, None, "test -f a.txt") == 0


def test_rehearsal_uses_an_existing_empty_folder(repo, tmp_path):
    worktree = tmp_path / "rehearsal"
    worktree.mkdir()

    assert gittools.merge_rehearsal(repo, "main", [], worktree, None, "test -f a.txt") == 0


def test_rehearsal_unknown_branch_raises(repo, tmp_path):
    with pytest.raises(gittools.GitError):
        gittools.merge_rehearsal(repo, "main", ["feat/missing"], tmp_path / "rehearsal", None, None)


def test_cli_assemble_applies_subjects_file(repo, tmp_path, capsys):
    branch_from_main(repo, "wip")
    commit(repo, "b.txt", "b\n", "wip: add b")
    subjects_file = tmp_path / "subjects.json"
    subjects_file.write_text(json.dumps({"wip: add b": "feat: add b"}))

    code = cli.main(
        [
            "git",
            "assemble",
            "--repo",
            str(repo),
            "--base",
            "main",
            "--from",
            "wip",
            "--to",
            "final",
            "--subjects",
            str(subjects_file),
        ]
    )

    assert code == 0
    assert capsys.readouterr().out.splitlines() == ["feat: add b"]
    assert git(repo, "log", "-1", "--format=%s", "final") == "feat: add b"


def test_cli_assemble_conflict_exits_1(repo, capsys):
    branch_from_main(repo, "wip")
    wip_sha = commit(repo, "a.txt", "wip\n", "feat: wip edits a")
    git(repo, "switch", "-q", "main")
    commit(repo, "a.txt", "main\n", "feat: main edits a")

    code = cli.main(
        ["git", "assemble", "--repo", str(repo), "--base", "main", "--from", "wip", "--to", "final"]
    )

    err = capsys.readouterr().err
    assert code == 1
    assert wip_sha in err
    assert "a.txt" in err
    assert "git cherry-pick --continue" in err
    assert "git cherry-pick --abort" in err


def test_cli_assemble_empty_pick_suggests_skip(repo, capsys):
    branch_from_main(repo, "wip")
    wip_sha = commit(repo, "b.txt", "b\n", "wip: add b")
    git(repo, "switch", "-q", "main")
    commit(repo, "b.txt", "b\n", "feat: add b on main")

    code = cli.main(
        ["git", "assemble", "--repo", str(repo), "--base", "main", "--from", "wip", "--to", "final"]
    )

    err = capsys.readouterr().err
    assert code == 1
    assert wip_sha in err
    assert "git cherry-pick --skip" in err
    assert "--continue" not in err


def test_cli_assemble_dirty_work_tree_exits_1(repo, capsys):
    branch_from_main(repo, "wip")
    commit(repo, "b.txt", "b\n", "feat: add b")
    (repo / "a.txt").write_text("changed\n")

    code = cli.main(
        ["git", "assemble", "--repo", str(repo), "--base", "main", "--from", "wip", "--to", "final"]
    )

    assert code == 1
    assert "uncommitted" in capsys.readouterr().err


def test_cli_assemble_long_subject_exits_1(repo, capsys):
    long_subject = "feat: " + "x" * 67
    branch_from_main(repo, "wip")
    commit(repo, "b.txt", "b\n", long_subject)

    code = cli.main(
        ["git", "assemble", "--repo", str(repo), "--base", "main", "--from", "wip", "--to", "final"]
    )

    assert code == 1
    assert long_subject in capsys.readouterr().err


def test_cli_merge_rehearsal_uses_default_worktree(repo, capsys):
    branch_from_main(repo, "feat/x")
    commit(repo, "x.txt", "x\n", "feat: add x")
    git(repo, "switch", "-q", "main")

    code = cli.main(
        [
            "git",
            "merge-rehearsal",
            "--repo",
            str(repo),
            "--base",
            "main",
            "--check",
            "test -f x.txt",
            "feat/x",
        ]
    )

    assert code == 0
    assert capsys.readouterr().out.splitlines() == ["ok feat/x"]
    assert (config.cache_dir() / "merge-rehearsal" / "acme" / "x.txt").is_file()


def test_cli_merge_rehearsal_help_says_no_dependencies_are_installed(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["git", "merge-rehearsal", "--help"])

    assert exc.value.code == 0
    assert "no dependencies installed" in " ".join(capsys.readouterr().out.split())


def test_cli_merge_rehearsal_foreign_worktree_exits_1(repo, tmp_path, capsys):
    worktree = tmp_path / "rehearsal"
    assert gittools.merge_rehearsal(repo, "main", [], worktree, None, None) == 0
    other = make_other_repo(tmp_path)

    code = cli.main(
        [
            "git",
            "merge-rehearsal",
            "--repo",
            str(other),
            "--base",
            "main",
            "--worktree",
            str(worktree),
            "feat/x",
        ]
    )

    assert code == 1
    assert "not a worktree of" in capsys.readouterr().err


def test_cli_defaults_repo_to_current_git_toplevel(repo, monkeypatch, capsys):
    branch_from_main(repo, "feat/x")
    commit(repo, "x.txt", "x\n", "feat: add x")
    git(repo, "switch", "-q", "main")
    (repo / "sub").mkdir()
    monkeypatch.chdir(repo / "sub")

    code = cli.main(["git", "merge-rehearsal", "--base", "main", "feat/x"])

    assert code == 0
    assert (config.cache_dir() / "merge-rehearsal" / "acme").is_dir()


@pytest.fixture
def cloned(tmp_path, repo) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.com")
    git(work, "config", "commit.gpgsign", "false")
    return origin, work


def test_dirty_ignores_untracked_files(repo):
    assert gittools.dirty(repo) is False
    (repo / "new.txt").write_text("x\n")
    assert gittools.dirty(repo) is False
    (repo / "a.txt").write_text("changed\n")
    assert gittools.dirty(repo) is True


def test_fetch_then_has_ref(cloned):
    origin, work = cloned
    commit(work, "b.txt", "b\n", "feat: b")
    git(work, "push", "-q", "origin", "main")
    other = origin.parent / "other"
    subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True)
    git(other, "config", "user.name", "Test")
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "commit.gpgsign", "false")
    sha = commit(other, "c.txt", "c\n", "feat: c")
    git(other, "push", "-q", "origin", "main")

    assert gittools.has_ref(work, sha) is False
    gittools.fetch(work, "origin")
    assert git(work, "rev-parse", "origin/main") == sha
    assert gittools.has_ref(work, "origin/main") is True
    assert gittools.has_ref(work, "origin/nope") is False


def test_fetch_failure_is_a_git_error(cloned, tmp_path):
    _, work = cloned
    git(work, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    with pytest.raises(gittools.GitError):
        gittools.fetch(work, "origin")


def test_head_names_the_branch_or_the_detached_sha(repo):
    assert gittools.head(repo) == ("main", False)
    sha = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-q", "--detach")
    assert gittools.head(repo) == (sha, True)


def test_local_and_remote_branches(cloned):
    _, work = cloned
    branch_from_main(work, "feat/local")
    git(work, "push", "-q", "origin", "feat/local:feat/remote")
    gittools.fetch(work, "origin")

    assert gittools.local_branches(work) == ["feat/local", "main"]
    assert gittools.remote_branches(work, "origin") == ["feat/remote", "main"]


def test_switch_new_does_not_track(cloned):
    _, work = cloned
    gittools.switch_new(work, "feat/x", "origin/main", track=False)
    assert gittools.head(work) == ("feat/x", False)
    assert (
        subprocess.run(
            ["git", "config", "branch.feat/x.merge"], cwd=work, capture_output=True, check=False
        ).stdout
        == b""
    )
    gittools.switch(work, "main")
    assert gittools.head(work) == ("main", False)


def test_switch_new_with_track_sets_the_upstream(cloned):
    _, work = cloned
    gittools.switch_new(work, "feat/x", "origin/main", track=True)
    assert git(work, "config", "branch.feat/x.merge") == "refs/heads/main"


def test_add_worktree_new_and_existing_branch(cloned, tmp_path):
    _, work = cloned
    new = tmp_path / "wt-new"
    gittools.add_worktree(work, new, "feat/new", "origin/main")
    assert git(new, "branch", "--show-current") == "feat/new"
    assert (
        subprocess.run(
            ["git", "config", "branch.feat/new.merge"], cwd=work, capture_output=True, check=False
        ).stdout
        == b""
    )

    branch_from_main(work, "feat/old")
    git(work, "switch", "-q", "main")
    old = tmp_path / "wt-old"
    gittools.add_worktree(work, old, "feat/old", None)
    assert git(old, "branch", "--show-current") == "feat/old"


def test_add_worktree_track_sets_the_upstream_whatever_the_config_and_remotes(cloned, tmp_path):
    origin, work = cloned
    git(work, "push", "-q", "origin", "main:feat/remote")
    second = tmp_path / "second.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(origin), str(second)], check=True)
    git(work, "remote", "add", "second", str(second))
    git(work, "fetch", "-q", "--all")
    git(work, "config", "branch.autoSetupMerge", "false")
    tree = tmp_path / "wt"

    gittools.add_worktree(work, tree, "feat/remote", "refs/remotes/origin/feat/remote", track=True)

    assert git(tree, "branch", "--show-current") == "feat/remote"
    assert git(work, "rev-parse", "--abbrev-ref", "feat/remote@{upstream}") == "origin/feat/remote"


def stop_in(repo: Path, *args: str) -> None:
    """Run a git command expected to stop half-way (a conflict, a failing exec)."""
    subprocess.run(["git", *args], cwd=repo, capture_output=True, check=False)


@pytest.mark.parametrize(
    ("setup", "operation"),
    [
        ([("switch", "-q", "feat/one"), ("rebase", "feat/two")], "a rebase"),
        ([("switch", "-q", "feat/one"), ("rebase", "--apply", "feat/two")], "a rebase"),
        ([("switch", "-q", "feat/one"), ("merge", "feat/two")], "a merge"),
        ([("switch", "-q", "feat/one"), ("cherry-pick", "feat/two")], "a cherry-pick"),
        ([("switch", "-q", "feat/one"), ("revert", "--no-edit", "feat/two")], "a revert"),
        ([("bisect", "start")], "a bisect"),
    ],
)
def test_operation_in_progress_names_what_the_repo_is_in_the_middle_of(
    repo, conflicting_branches, setup, operation
):
    assert gittools.operation_in_progress(repo) is None
    for args in setup:
        stop_in(repo, *args)

    assert gittools.operation_in_progress(repo) == operation


def test_operation_in_progress_sees_a_rebase_stopped_on_a_clean_tree(repo):
    commit(repo, "b.txt", "b\n", "feat: b")
    stop_in(repo, "rebase", "--exec", "false", "--root")

    assert gittools.dirty(repo) is False
    assert gittools.operation_in_progress(repo) == "a rebase"


def test_worktree_of_finds_the_checkout(cloned, tmp_path):
    _, work = cloned
    linked = tmp_path / "wt"
    gittools.add_worktree(work, linked, "feat/wt", "origin/main")

    assert gittools.worktree_of(work, "feat/wt") == linked.resolve()
    assert gittools.worktree_of(work, "main") == work.resolve()
    assert gittools.worktree_of(work, "feat/none") is None


@pytest.fixture
def fetch_call(monkeypatch) -> dict:
    """The keyword arguments `git fetch` ran with; the fetch itself times out, other git runs."""
    seen: dict = {}
    real_run = subprocess.run
    for name in ("GIT_SSH_COMMAND", "GIT_SSH"):
        monkeypatch.delenv(name, raising=False)

    def fake_run(command, **kwargs):
        if "fetch" not in command:
            return real_run(command, **kwargs)
        seen.update(kwargs)
        raise subprocess.TimeoutExpired(cmd="git fetch", timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    return seen


def test_fetch_times_out_as_a_git_error_without_prompting(repo, fetch_call):
    with pytest.raises(gittools.GitError, match="timed out"):
        gittools.fetch(repo, "origin")
    assert fetch_call["timeout"] == 60
    assert fetch_call["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert fetch_call["env"]["GIT_SSH_COMMAND"] == "ssh -o BatchMode=yes"


WINDOWS_SSH = "/mnt/c/Windows/System32/OpenSSH/ssh.exe"


@pytest.mark.parametrize(
    ("environment", "config", "expected"),
    [
        ({}, f'"{WINDOWS_SSH}" -i ~/.ssh/work', f'"{WINDOWS_SSH}" -i ~/.ssh/work -o BatchMode=yes'),
        (
            {"GIT_SSH_COMMAND": "ssh -i /k/env"},
            "ssh -i /k/config",
            "ssh -i /k/env -o BatchMode=yes",
        ),
        ({"GIT_SSH_COMMAND": "plink -batch"}, None, "plink -batch"),
        ({}, "ssh -i key; echo hi", None),
        ({}, "ssh 'unclosed", None),
        ({"GIT_SSH": WINDOWS_SSH}, None, f"{WINDOWS_SSH} -o BatchMode=yes"),
        ({"GIT_SSH": "/usr/bin/plink"}, None, None),
    ],
)
def test_fetch_keeps_the_users_ssh_command(
    repo, fetch_call, monkeypatch, environment, config, expected
):
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    if config is not None:
        git(repo, "config", "core.sshCommand", config)

    with pytest.raises(gittools.GitError):
        gittools.fetch(repo, "origin")

    assert fetch_call["env"].get("GIT_SSH_COMMAND") == expected
    assert fetch_call["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert fetch_call["timeout"] == 60


def test_switch_refuses_a_branch_name_that_looks_like_an_option(repo):
    with pytest.raises(gittools.GitError, match="option"):
        gittools.switch(repo, "--detach")
    with pytest.raises(gittools.GitError, match="option"):
        gittools.switch_new(repo, "-x", "main", track=False)
    assert gittools.head(repo) == ("main", False)
