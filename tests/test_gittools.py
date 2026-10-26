import json
import os
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


def test_cli_defaults_repo_to_current_git_toplevel(repo, monkeypatch, capsys):
    branch_from_main(repo, "feat/x")
    commit(repo, "x.txt", "x\n", "feat: add x")
    git(repo, "switch", "-q", "main")
    (repo / "sub").mkdir()
    monkeypatch.chdir(repo / "sub")

    code = cli.main(["git", "merge-rehearsal", "--base", "main", "feat/x"])

    assert code == 0
    assert (config.cache_dir() / "merge-rehearsal" / "acme").is_dir()
