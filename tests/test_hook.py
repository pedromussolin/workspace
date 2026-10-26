import os
import subprocess
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1] / ".githooks"
HOOKS = ("pre-commit", "pre-merge-commit", "commit-msg", "pre-push")


def run(repo, git, *args):
    """Runs git with the repo's hooks; a hook found through core.hooksPath must stop it."""
    return git(repo, "-c", f"core.hooksPath={HOOKS_DIR}", *args, check=False)


def output(result):
    return result.stdout + result.stderr


def commit(repo, git, name, content, message="chore: x"):
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)
    return run(repo, git, "commit", "-q", "-m", message)


def quiet_commit(repo, git, name, content, message="chore: x"):
    """A commit that no hook sees, as if made with --no-verify or by another tool."""
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.mark.parametrize("hook", HOOKS)
def test_hook_file_is_executable(hook):
    assert os.access(HOOKS_DIR / hook, os.X_OK)


@pytest.mark.parametrize("hook", HOOKS)
def test_hooks_fail_closed_and_run_ws_without_syncing_the_environment(hook):
    text = (HOOKS_DIR / hook).read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text
    assert "uv " not in text
    if hook != "pre-merge-commit":
        assert 'PYTHONPATH="$project/src"' in text


def test_commit_with_a_real_name_is_blocked(repo, git, ws_config):
    assert not (repo / ".githooks").exists(), "the hook must find ws from its own path"
    result = commit(repo, git, "notes.md", "meeting with Acme\n")
    assert result.returncode != 0
    assert "notes.md:1: real-name: Acme" in output(result)
    assert git(repo, "log", "--oneline", check=False).returncode != 0


def test_commit_with_the_analog_succeeds(repo, git, ws_config):
    result = commit(repo, git, "notes.md", "meeting with Apex\n")
    assert result.returncode == 0, output(result)
    assert git(repo, "log", "--oneline").stdout.count("\n") == 1


def test_hook_blocks_without_a_names_table(repo, git, tmp_path, monkeypatch):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    result = commit(repo, git, "notes.md", "meeting with Apex\n")
    assert result.returncode != 0
    assert "names table not found" in output(result)


def test_commit_message_with_a_real_name_is_blocked(repo, git, ws_config):
    result = commit(repo, git, "notes.md", "fine\n", message="fix: integração com Acme")
    assert result.returncode != 0
    assert "message:1: real-name: Acme" in output(result)
    assert git(repo, "log", "--oneline", check=False).returncode != 0


def test_commit_message_with_the_analog_succeeds(repo, git, ws_config):
    result = commit(repo, git, "notes.md", "fine\n", message="fix: integração com Apex")
    assert result.returncode == 0, output(result)


def test_commit_message_from_a_file_with_a_co_author_trailer_is_blocked(repo, git, ws_config):
    (repo / "notes.md").write_text("fine\n", encoding="utf-8")
    git(repo, "add", "notes.md")
    message = repo.parent / "msg.txt"
    message.write_text("feat: x\n\nCo-Authored-By: Someone <someone@example.com>\n")
    result = run(repo, git, "commit", "-q", "-F", str(message))
    assert result.returncode != 0
    assert "message:3: co-authored-by" in output(result)
    assert git(repo, "log", "--oneline", check=False).returncode != 0


def test_the_commit_msg_hook_alone_blocks_without_a_names_table(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    message = tmp_path / "msg.txt"
    message.write_text("fix: x\n", encoding="utf-8")
    result = subprocess.run(
        [HOOKS_DIR / "commit-msg", message], cwd=repo, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "names table not found" in output(result)


def test_the_commit_msg_hook_alone_needs_the_message_file(repo, ws_config):
    result = subprocess.run([HOOKS_DIR / "commit-msg"], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0


def editor(tmp_path, monkeypatch, body):
    script = tmp_path / "editor.sh"
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("GIT_EDITOR", str(script))


def test_comment_lines_of_the_editor_template_are_not_checked(
    repo, git, ws_config, tmp_path, monkeypatch
):
    editor(tmp_path, monkeypatch, r"printf 'fix: x\n\n# Acme is in a comment\n' > $1")
    (repo / "notes.md").write_text("fine\n", encoding="utf-8")
    git(repo, "add", "notes.md")
    result = run(repo, git, "commit", "-q")
    assert result.returncode == 0, output(result)
    assert git(repo, "log", "-1", "--format=%B").stdout.strip() == "fix: x"


def test_verbose_commit_does_not_check_the_diff_under_the_scissors_line(
    repo, git, ws_config, tmp_path, monkeypatch
):
    quiet_commit(repo, git, "notes.md", "meeting with Acme\n")
    editor(
        tmp_path,
        monkeypatch,
        r"{ printf 'fix: mascara\n\n'; cat $1; } > $1.new; mv $1.new $1",
    )
    (repo / "notes.md").write_text("meeting with Apex\n", encoding="utf-8")
    git(repo, "add", "notes.md")
    result = run(repo, git, "commit", "-q", "-v")
    assert result.returncode == 0, output(result)
    assert git(repo, "log", "-1", "--format=%s").stdout.strip() == "fix: mascara"


def diverge(repo, git, side_name, side_content):
    quiet_commit(repo, git, "base.md", "fine\n", message="base")
    base_branch = git(repo, "branch", "--show-current").stdout.strip()
    git(repo, "switch", "-q", "-c", "side")
    quiet_commit(repo, git, side_name, side_content, message="side")
    git(repo, "switch", "-q", base_branch)
    quiet_commit(repo, git, "main.md", "fine\n", message="main")


def test_merge_that_brings_a_real_name_is_blocked(repo, git, ws_config):
    diverge(repo, git, "side.md", "Acme\n")
    result = run(repo, git, "merge", "--no-ff", "-m", "chore: junta", "side")
    assert result.returncode != 0
    assert "side.md:1: real-name: Acme" in output(result)
    assert git(repo, "log", "--merges", "--oneline").stdout == ""


def test_clean_merge_succeeds(repo, git, ws_config):
    diverge(repo, git, "side.md", "fine\n")
    result = run(repo, git, "merge", "--no-ff", "-m", "chore: junta", "side")
    assert result.returncode == 0, output(result)
    assert git(repo, "log", "--merges", "--oneline").stdout.count("\n") == 1


def test_merge_blocks_without_a_names_table(repo, git, tmp_path, monkeypatch):
    diverge(repo, git, "side.md", "fine\n")
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    result = run(repo, git, "merge", "--no-ff", "-m", "chore: junta", "side")
    assert result.returncode != 0
    assert git(repo, "log", "--merges", "--oneline").stdout == ""


@pytest.fixture
def remote(tmp_path, repo, git):
    path = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(path))
    git(repo, "remote", "add", "origin", str(path))
    return path


def remote_refs(remote, git):
    return git(remote, "for-each-ref", "--format=%(refname)").stdout.split()


def push(repo, git, *args):
    return run(repo, git, "push", "-q", *args)


def test_push_with_a_real_name_in_a_commit_is_blocked(repo, git, ws_config, remote):
    quiet_commit(repo, git, "notes.md", "meeting with Acme\n")
    result = push(repo, git, "origin", "HEAD:refs/heads/main")
    assert result.returncode != 0
    assert "notes.md:1: real-name: Acme" in output(result)
    assert remote_refs(remote, git) == []


def test_push_with_a_real_name_in_a_message_is_blocked(repo, git, ws_config, remote):
    quiet_commit(repo, git, "notes.md", "fine\n", message="fix: integração com Méridia")
    result = push(repo, git, "origin", "HEAD:refs/heads/main")
    assert result.returncode != 0
    assert "message:1: real-name: Méridia" in output(result)
    assert remote_refs(remote, git) == []


def test_push_with_a_company_e_mail_is_blocked(repo, git, ws_config, remote, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "pat@acme-corp.example")
    quiet_commit(repo, git, "notes.md", "fine\n")
    monkeypatch.delenv("GIT_AUTHOR_EMAIL")
    result = push(repo, git, "origin", "HEAD:refs/heads/main")
    assert result.returncode != 0
    assert "author:1: blocked-domain: acme-corp.example" in output(result)
    assert remote_refs(remote, git) == []


def test_clean_push_lands(repo, git, ws_config, remote):
    quiet_commit(repo, git, "notes.md", "fine\n")
    result = push(repo, git, "origin", "HEAD:refs/heads/main")
    assert result.returncode == 0, output(result)
    assert remote_refs(remote, git) == ["refs/heads/main"]


def test_only_the_new_commits_of_an_existing_remote_branch_are_checked(
    repo, git, ws_config, remote
):
    quiet_commit(repo, git, "notes.md", "meeting with Acme\n")
    assert git(repo, "push", "-q", "origin", "HEAD:refs/heads/main").returncode == 0
    quiet_commit(repo, git, "other.md", "fine\n")
    assert push(repo, git, "origin", "HEAD:refs/heads/main").returncode == 0
    quiet_commit(repo, git, "third.md", "Méridia\n")
    result = push(repo, git, "origin", "HEAD:refs/heads/main")
    assert result.returncode != 0
    assert "third.md:1: real-name: Méridia" in output(result)
    assert "notes.md" not in output(result)


def test_a_new_branch_checks_only_what_the_remote_does_not_have_yet(repo, git, ws_config, remote):
    quiet_commit(repo, git, "notes.md", "meeting with Acme\n")
    branch = git(repo, "branch", "--show-current").stdout.strip()
    assert git(repo, "push", "-q", "origin", branch).returncode == 0
    git(repo, "switch", "-q", "-c", "feature")
    quiet_commit(repo, git, "feature.md", "fine\n")
    result = push(repo, git, "origin", "feature")
    assert result.returncode == 0, output(result)
    quiet_commit(repo, git, "bad.md", "Acme\n")
    assert push(repo, git, "origin", "feature").returncode != 0


def test_the_scan_baseline_leaves_accepted_history_out(repo, git, ws_config, remote):
    accepted = quiet_commit(repo, git, "notes.md", "meeting with Acme\n")
    quiet_commit(repo, git, "other.md", "fine\n")
    assert push(repo, git, "origin", "HEAD:refs/heads/main").returncode != 0
    git(repo, "config", "ws.scanBaseline", accepted)
    result = push(repo, git, "origin", "HEAD:refs/heads/main")
    assert result.returncode == 0, output(result)
    quiet_commit(repo, git, "bad.md", "Méridia\n")
    assert push(repo, git, "origin", "HEAD:refs/heads/main").returncode != 0


def test_a_scan_baseline_that_does_not_resolve_blocks_the_push(repo, git, ws_config, remote):
    quiet_commit(repo, git, "notes.md", "fine\n")
    git(repo, "config", "ws.scanBaseline", "no-such-ref")
    result = push(repo, git, "origin", "HEAD:refs/heads/main")
    assert result.returncode != 0
    assert remote_refs(remote, git) == []


def test_deleting_a_remote_branch_is_not_scanned(repo, git, ws_config, remote):
    quiet_commit(repo, git, "notes.md", "meeting with Acme\n")
    assert git(repo, "push", "-q", "origin", "HEAD:refs/heads/old").returncode == 0
    result = push(repo, git, "origin", "--delete", "old")
    assert result.returncode == 0, output(result)
    assert remote_refs(remote, git) == []


def test_a_remote_commit_not_known_locally_falls_back_to_the_new_branch_scan(
    repo, git, ws_config, remote, tmp_path
):
    quiet_commit(repo, git, "notes.md", "fine\n")
    assert push(repo, git, "origin", "HEAD:refs/heads/main").returncode == 0
    git(tmp_path, "clone", "-q", "-b", "main", str(remote), "other")
    quiet_commit(tmp_path / "other", git, "theirs.md", "fine\n")
    git(tmp_path / "other", "push", "-q", "origin", "HEAD:refs/heads/main")
    quiet_commit(repo, git, "mine.md", "fine\n")
    result = push(repo, git, "--force", "origin", "HEAD:refs/heads/main")
    assert result.returncode == 0, output(result)


def test_push_blocks_without_a_names_table(repo, git, tmp_path, monkeypatch, remote):
    quiet_commit(repo, git, "notes.md", "fine\n")
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    result = push(repo, git, "origin", "HEAD:refs/heads/main")
    assert result.returncode != 0
    assert "names table not found" in output(result)
    assert remote_refs(remote, git) == []
