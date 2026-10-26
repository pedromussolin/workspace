import os
import subprocess
import sys
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


ZEROS = "0" * 40


def run_pre_push(repo, local_sha, remote_sha=ZEROS, remote="origin", local_ref="refs/heads/main"):
    """The pre-push hook with the lines git feeds it; nothing is pushed anywhere."""
    stdin = f"{local_ref} {local_sha} refs/heads/main {remote_sha}\n"
    return subprocess.run(
        [HOOKS_DIR / "pre-push", remote], cwd=repo, input=stdin, capture_output=True, text=True
    )


def head(repo, git):
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def test_a_commit_with_a_new_word_warns_and_goes_through(repo, git, ws_config):
    result = commit(repo, git, "notes.md", "talk with Zorblax\n")
    assert result.returncode == 0, output(result)
    assert "notes.md:1" in output(result)
    assert "Zorblax" in output(result)
    assert "The commit goes through" in output(result)
    assert git(repo, "log", "--oneline").stdout.count("\n") == 1


def test_a_commit_without_new_words_does_not_warn(repo, git, ws_config):
    result = commit(repo, git, "notes.md", "talk with Apex and the team\n")
    assert result.returncode == 0, output(result)
    assert "new word" not in output(result)


def test_a_message_with_a_new_word_warns_and_goes_through(repo, git, ws_config):
    result = commit(repo, git, "notes.md", "fine\n", message="fix: integra o Quuxmark")
    assert result.returncode == 0, output(result)
    assert "Quuxmark: message:1" in output(result)


def test_the_warning_does_not_change_the_secrets_verdict(repo, git, ws_config):
    result = commit(repo, git, "notes.md", "talk with Acme and Zorblax\n")
    assert result.returncode != 0
    assert "real-name: Acme" in output(result)
    assert "Zorblax" not in output(result)


def test_a_failure_of_the_warning_is_printed_and_does_not_block(repo, git, ws_config):
    result = commit(repo, git, ".known-words", "Celery Beat\n")
    assert result.returncode == 0, output(result)
    assert "new-word warning failed" in output(result)
    assert ".known-words line 1" in output(result)


def test_a_crash_of_the_warning_process_does_not_block(repo, git, ws_config, tmp_path, monkeypatch):
    fake = tmp_path / "bin" / "python3"
    fake.parent.mkdir()
    fake.write_text(
        f'#!/bin/sh\ncase "$*" in *"names check"*) exit 3;; esac\nexec {sys.executable} "$@"\n',
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
    result = commit(repo, git, "notes.md", "talk with Zorblax\n", message="fix: x")
    assert result.returncode == 0, output(result)
    assert "the new-word warning failed" in output(result)


def test_push_with_a_new_word_is_blocked_with_the_list(repo, git, ws_config):
    sha = quiet_commit(repo, git, "notes.md", "talk with Zorblax\n", message="fix: o Quuxmark")
    result = run_pre_push(repo, sha)
    assert result.returncode != 0
    assert f"Zorblax: {sha[:10]}:notes.md:1" in output(result)
    assert f"Quuxmark: {sha[:10]}:message:1" in output(result)
    assert "2 new word(s)" in output(result)
    assert "The push is blocked" in output(result)


def test_push_passes_once_the_word_is_in_known_words_of_the_pushed_commit(repo, git, ws_config):
    quiet_commit(repo, git, "notes.md", "talk with Zorblax\n")
    assert run_pre_push(repo, head(repo, git)).returncode != 0
    (repo / ".known-words").write_text("# harmless\nZorblax\n", encoding="utf-8")
    assert run_pre_push(repo, head(repo, git)).returncode != 0, "uncommitted does not count"
    sha = quiet_commit(repo, git, ".known-words", "# harmless\nZorblax\n", message="chore: x")
    result = run_pre_push(repo, sha)
    assert result.returncode == 0, output(result)


def test_push_passes_once_the_word_is_masked_out_of_the_commit(repo, git, ws_config):
    quiet_commit(repo, git, "notes.md", "talk with Zorblax\n")
    assert run_pre_push(repo, head(repo, git)).returncode != 0
    (repo / "notes.md").write_text("talk with Apex\n", encoding="utf-8")
    git(repo, "add", "notes.md")
    git(repo, "commit", "-q", "--amend", "-m", "chore: x")
    result = run_pre_push(repo, head(repo, git))
    assert result.returncode == 0, output(result)


def test_push_knows_the_words_of_the_remote_state(repo, git, ws_config):
    remote_sha = quiet_commit(repo, git, "notes.md", "the Quuxmark team\n")
    sha = quiet_commit(repo, git, "more.md", "Quuxmark and Zorblax\n")
    result = run_pre_push(repo, sha, remote_sha)
    assert result.returncode != 0
    assert "Zorblax" in output(result)
    assert "Quuxmark" not in output(result)


def test_a_new_branch_takes_the_vocabulary_from_the_remote_main(repo, git, ws_config):
    base = quiet_commit(repo, git, "notes.md", "the Quuxmark team\n")
    git(repo, "update-ref", "refs/remotes/origin/main", base)
    sha = quiet_commit(repo, git, "more.md", "Quuxmark and Zorblax\n")
    result = run_pre_push(repo, sha)
    assert result.returncode != 0
    assert "Zorblax" in output(result)
    assert "Quuxmark" not in output(result)


def test_without_any_remote_state_every_new_capitalized_word_counts(repo, git, ws_config):
    sha = quiet_commit(repo, git, "notes.md", "Before the Quuxmark team\n")
    result = run_pre_push(repo, sha)
    assert result.returncode != 0
    assert "Before" in output(result)
    assert "Quuxmark" in output(result)


def test_a_remote_sha_that_is_not_known_here_falls_back_to_the_remote_main(repo, git, ws_config):
    base = quiet_commit(repo, git, "notes.md", "the Quuxmark team\n")
    git(repo, "update-ref", "refs/remotes/origin/main", base)
    sha = quiet_commit(repo, git, "more.md", "Quuxmark\n")
    assert run_pre_push(repo, sha, "1" * 40).returncode == 0


def test_push_fails_closed_when_the_new_word_check_cannot_run(repo, git, ws_config):
    sha = quiet_commit(repo, git, ".known-words", "Celery Beat\n")
    result = run_pre_push(repo, sha)
    assert result.returncode != 0
    assert ".known-words line 1" in output(result)
    assert "blocking" in output(result)


def test_push_runs_both_checks_and_reports_both(repo, git, ws_config):
    sha = quiet_commit(repo, git, "notes.md", "Acme and Zorblax\n")
    result = run_pre_push(repo, sha)
    assert result.returncode != 0
    assert "notes.md:1: real-name: Acme" in output(result)
    assert "Zorblax" in output(result)


def test_the_scan_baseline_leaves_accepted_commits_out_of_the_word_check(repo, git, ws_config):
    accepted = quiet_commit(repo, git, "notes.md", "talk with Zorblax\n")
    sha = quiet_commit(repo, git, "other.md", "fine\n")
    assert run_pre_push(repo, sha).returncode != 0
    git(repo, "config", "ws.scanBaseline", accepted)
    result = run_pre_push(repo, sha)
    assert result.returncode == 0, output(result)


def test_every_range_of_a_push_is_checked(repo, git, ws_config):
    first = quiet_commit(repo, git, "notes.md", "fine\n")
    second = quiet_commit(repo, git, "more.md", "Zorblax\n")
    stdin = (
        f"refs/heads/one {first} refs/heads/one {ZEROS}\n"
        f"refs/heads/two {second} refs/heads/two {ZEROS}\n"
    )
    result = subprocess.run(
        [HOOKS_DIR / "pre-push", "origin"],
        cwd=repo,
        input=stdin,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Zorblax" in output(result)


def test_deleting_a_branch_has_no_words_to_check(repo, git, ws_config):
    quiet_commit(repo, git, "notes.md", "Zorblax\n")
    assert run_pre_push(repo, ZEROS, head(repo, git)).returncode == 0
