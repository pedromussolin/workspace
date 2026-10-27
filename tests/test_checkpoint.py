import json
import subprocess
from pathlib import Path

import pytest

from ws import checkpoint
from ws.cli import main
from ws.standup import _section

GOOD_CONTINUE = """\
Status: ativo

# Continuar em outro chat

## Onde parei

Feito o parser; falta ligar ao comando.

## Branches e worktrees

Nenhuma.

## Próximo passo

Ligar o parser ao comando `demo run`.
"""


@pytest.fixture(autouse=True)
def identity(monkeypatch):
    for who in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{who}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{who}_EMAIL", "test@example.com")


@pytest.fixture
def remote(tmp_path, git):
    bare = tmp_path / "remote.git"
    bare.mkdir()
    git(bare, "init", "-q", "--bare", "-b", "main")
    return bare


def _clone(tmp_path, git, remote, name):
    path = tmp_path / name
    subprocess.run(["git", "clone", "-q", str(remote), str(path)], check=True)
    git(path, "checkout", "-q", "-B", "main")
    return path


@pytest.fixture
def work(tmp_path, git, remote, monkeypatch):
    path = _clone(tmp_path, git, remote, "work")
    project = path / "projects" / "demo"
    project.mkdir(parents=True)
    (project / "CONTINUE.md").write_text(GOOD_CONTINUE, encoding="utf-8")
    (project / "decisions.md").write_text("# Decisões\n", encoding="utf-8")
    (path / "README.md").write_text("root\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "chore: inicio")
    git(path, "push", "-q", "-u", "origin", "main")
    monkeypatch.setenv("WS_REPO_ROOT", str(path))
    return path


@pytest.fixture
def other(tmp_path, git, remote, work):
    return _clone(tmp_path, git, remote, "other")


def _write(work, text):
    (work / "projects" / "demo" / "CONTINUE.md").write_text(text, encoding="utf-8")


def _edit(work):
    _write(work, GOOD_CONTINUE.replace("Feito o parser", "Feito o parser e o teste"))


def _problems(slug="demo"):
    return checkpoint.check(slug)["problems"]


def test_placeholders_equal_the_template():
    template = (Path(__file__).parents[1] / "templates/project/CONTINUE.md").read_text("utf-8")
    for heading, placeholder in checkpoint.REQUIRED_SECTIONS.items():
        assert _section(template, heading) == placeholder


def test_check_passes_on_a_good_project(work):
    assert checkpoint.check("demo") == {"ok": True, "problems": []}


@pytest.mark.parametrize("slug", ["../x", "Demo", "-a", "a/b", "", "a_b"])
def test_invalid_slug_is_refused(work, slug):
    with pytest.raises(checkpoint.CheckpointError):
        checkpoint.check(slug)


def test_missing_project_and_symlink_are_refused(work, tmp_path):
    with pytest.raises(checkpoint.CheckpointError):
        checkpoint.check("nope")
    (work / "projects" / "link").symlink_to(tmp_path)
    with pytest.raises(checkpoint.CheckpointError):
        checkpoint.check("link")


def test_check_without_continue(work):
    (work / "projects" / "demo" / "CONTINUE.md").unlink()
    assert any("no CONTINUE.md" in p for p in _problems())


def test_check_missing_section(work):
    _write(work, GOOD_CONTINUE.replace("## Próximo passo", "## Outra"))
    assert any("no '## Próximo passo'" in p for p in _problems())


def test_check_empty_section(work):
    _write(work, GOOD_CONTINUE.replace("Ligar o parser ao comando `demo run`.", ""))
    assert any("'## Próximo passo' is empty" in p for p in _problems())


def test_check_placeholder_section(work):
    _write(
        work,
        GOOD_CONTINUE.replace(
            "Feito o parser; falta ligar ao comando.",
            ("O que foi feito e o que está em andamento,\ncom a data."),
        ),
    )
    assert any("'## Onde parei' is still the template" in p for p in _problems())


def test_check_next_step_limits(work):
    many = "\n".join(f"linha {i}" for i in range(16))
    _write(work, GOOD_CONTINUE.replace("Ligar o parser ao comando `demo run`.", many))
    assert any("16 lines" in p for p in _problems())
    fifteen = "\n".join(f"linha {i}" for i in range(15))
    _write(work, GOOD_CONTINUE.replace("Ligar o parser ao comando `demo run`.", fifteen))
    assert _problems() == []
    _write(work, GOOD_CONTINUE.replace("Ligar o parser ao comando `demo run`.", "x" * 1501))
    assert any("1501 characters" in p for p in _problems())
    _write(work, GOOD_CONTINUE.replace("Ligar o parser ao comando `demo run`.", "x" * 1500))
    assert _problems() == []


def test_check_without_decisions(work):
    (work / "projects" / "demo" / "decisions.md").unlink()
    assert any("no decisions.md" in p for p in _problems())


def test_cli_check_exit_codes(work, capsys):
    assert main(["checkpoint", "check", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    (work / "projects" / "demo" / "decisions.md").unlink()
    assert main(["checkpoint", "check", "demo"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    assert main(["checkpoint", "check", "../x"]) == 1


def test_diff_lists_files_and_refuses_large_and_binary(work):
    _edit(work)
    evidence = work / "projects" / "demo" / "evidence"
    evidence.mkdir()
    (evidence / "big.txt").write_text("x" * (200 * 1024 + 1))
    (evidence / "pic.png").write_bytes(b"\x89PNG\0\0")
    (evidence / "small.txt").write_text("ok")
    result = checkpoint.diff("demo")
    paths = {f["path"] for f in result["files"]}
    assert "projects/demo/CONTINUE.md" in paths
    assert "projects/demo/evidence/small.txt" in paths
    assert "CONTINUE.md" in result["diffstat"]
    refused = {r["path"]: r["reason"] for r in result["refused"]}
    assert set(refused) == {
        "projects/demo/evidence/big.txt",
        "projects/demo/evidence/pic.png",
    }
    included = checkpoint.diff("demo", ["evidence/big.txt", "projects/demo/evidence/pic.png"])
    assert included["refused"] == []


def test_commit_bad_message_refused_before_committing(work, git):
    _edit(work)
    for message in ("sem prefixo", "docs: " + "a" * 70, "docs:"):
        with pytest.raises(checkpoint.CheckpointError):
            checkpoint.commit("demo", message)
    assert git(work, "rev-list", "--count", "HEAD").stdout.strip() == "1"
    assert git(work, "diff", "--cached", "--quiet", check=False).returncode == 0


def test_commit_invalid_slug(work):
    with pytest.raises(checkpoint.CheckpointError):
        checkpoint.commit("../x", "docs: a")


def test_commit_refused_off_main(work, git):
    _edit(work)
    git(work, "checkout", "-q", "-b", "feature")
    with pytest.raises(checkpoint.CheckpointError, match="main"):
        checkpoint.commit("demo", "docs: a")
    git(work, "checkout", "-q", "--detach")
    with pytest.raises(checkpoint.CheckpointError, match="main"):
        checkpoint.commit("demo", "docs: a")


def test_commit_refused_when_check_fails(work):
    (work / "projects" / "demo" / "decisions.md").unlink()
    with pytest.raises(checkpoint.CheckpointError, match="decisions.md"):
        checkpoint.commit("demo", "docs: a")


def test_commit_refused_with_modified_file_outside(work):
    _edit(work)
    (work / "README.md").write_text("changed\n")
    with pytest.raises(checkpoint.CheckpointError, match="README.md"):
        checkpoint.commit("demo", "docs: a")


def test_commit_refused_with_untracked_and_staged_outside(work, git):
    _edit(work)
    (work / "new.txt").write_text("x")
    with pytest.raises(checkpoint.CheckpointError, match="new.txt"):
        checkpoint.commit("demo", "docs: a")
    (work / "new.txt").unlink()
    (work / "README.md").write_text("changed\n")
    git(work, "add", "README.md")
    with pytest.raises(checkpoint.CheckpointError, match="README.md"):
        checkpoint.commit("demo", "docs: a")


def test_commit_refused_for_new_large_file_without_include(work, git):
    _edit(work)
    evidence = work / "projects" / "demo" / "evidence"
    evidence.mkdir()
    (evidence / "pic.png").write_bytes(b"\0\0")
    with pytest.raises(checkpoint.CheckpointError, match="pic.png"):
        checkpoint.commit("demo", "docs: a")
    assert git(work, "rev-list", "--count", "HEAD").stdout.strip() == "1"
    checkpoint.commit("demo", "docs: a", ["evidence/pic.png"])
    assert "pic.png" in git(work, "show", "--stat", "HEAD").stdout


def test_commit_stages_only_the_project_and_pushes(work, git, remote):
    _edit(work)
    (work / "projects" / "demo" / "notes.md").write_text("n\n")
    ignored = work / "ignored.log"
    (work / ".gitignore").write_text("ignored.log\n")
    git(work, "add", ".gitignore")
    git(work, "commit", "-q", "-m", "chore: ignore")
    ignored.write_text("noise")
    result = checkpoint.commit("demo", "docs: fecha a iteração")
    assert result == {"committed": True, "pushed": True}
    files = git(work, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert sorted(files) == ["projects/demo/CONTINUE.md", "projects/demo/notes.md"]
    assert (
        git(remote, "log", "-1", "--format=%s", "main").stdout.strip() == "docs: fecha a iteração"
    )
    assert git(remote, "rev-parse", "main").stdout == git(work, "rev-parse", "HEAD").stdout


def test_pull_runs_after_the_commit(work, other, git, remote):
    (other / "README.md").write_text("from other\n")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "chore: outro")
    git(other, "push", "-q", "origin", "main")
    _edit(work)
    checkpoint.commit("demo", "docs: a")
    log = git(work, "log", "--format=%s", "-3").stdout.split("\n")
    assert log[:2] == ["docs: a", "chore: outro"]
    assert git(remote, "rev-parse", "main").stdout == git(work, "rev-parse", "HEAD").stdout


def test_conflict_aborts_rebase_and_keeps_the_commit(work, other, git, remote):
    (other / "projects/demo/CONTINUE.md").write_text(GOOD_CONTINUE.replace("Feito", "Outro"))
    git(other, "commit", "-q", "-am", "docs: outro")
    git(other, "push", "-q", "origin", "main")
    _edit(work)
    with pytest.raises(checkpoint.CheckpointError, match="projects/demo/CONTINUE.md"):
        checkpoint.commit("demo", "docs: a")
    assert not (work / ".git" / "rebase-merge").exists()
    assert not (work / ".git" / "rebase-apply").exists()
    assert git(work, "log", "-1", "--format=%s").stdout.strip() == "docs: a"
    assert git(work, "status", "--porcelain").stdout == ""
    assert git(remote, "log", "-1", "--format=%s", "main").stdout.strip() == "docs: outro"


def test_check_runs_again_after_the_pull(work, other, git, remote):
    (other / "projects/demo/decisions.md").unlink()
    git(other, "commit", "-q", "-am", "chore: remove")
    git(other, "push", "-q", "origin", "main")
    _edit(work)
    with pytest.raises(checkpoint.CheckpointError, match="decisions.md"):
        checkpoint.commit("demo", "docs: a")
    assert git(remote, "log", "-1", "--format=%s", "main").stdout.strip() == "chore: remove"


def test_nothing_to_commit_pushes_a_pending_commit(work, git, remote):
    _edit(work)
    git(work, "commit", "-q", "-am", "docs: pendente")
    result = checkpoint.commit("demo", "docs: b")
    assert result == {"committed": False, "pushed": True}
    assert git(remote, "log", "-1", "--format=%s", "main").stdout.strip() == "docs: pendente"
    assert git(work, "rev-list", "--count", "HEAD").stdout.strip() == "2"


def test_pre_push_refusal_keeps_the_commit_local(work, git, remote):
    hook = work / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\necho 'new word: zorgblat' >&2\nexit 1\n")
    hook.chmod(0o755)
    _edit(work)
    with pytest.raises(checkpoint.CheckpointError, match="zorgblat"):
        checkpoint.commit("demo", "docs: a")
    assert git(work, "log", "-1", "--format=%s").stdout.strip() == "docs: a"
    assert git(remote, "log", "-1", "--format=%s", "main").stdout.strip() == "chore: inicio"
    hook.unlink()
    assert checkpoint.commit("demo", "docs: b") == {"committed": False, "pushed": True}


def test_commit_hook_refusal_is_printed(work, git):
    hook = work / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'blocked by hook' >&2\nexit 1\n")
    hook.chmod(0o755)
    _edit(work)
    with pytest.raises(checkpoint.CheckpointError, match="blocked by hook"):
        checkpoint.commit("demo", "docs: a")


def test_cli_commit_and_diff(work, capsys):
    _edit(work)
    assert main(["checkpoint", "diff", "demo"]) == 0
    assert "CONTINUE.md" in capsys.readouterr().out
    assert main(["checkpoint", "commit", "demo", "-m", "docs: a"]) == 0
    assert json.loads(capsys.readouterr().out) == {"committed": True, "pushed": True}
    assert main(["checkpoint", "commit", "demo", "-m", "ruim"]) == 1
