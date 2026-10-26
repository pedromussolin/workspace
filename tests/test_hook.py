import os
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1] / ".githooks"


def commit(repo, git, name, content):
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)
    return git(
        repo, "-c", f"core.hooksPath={HOOKS_DIR}", "commit", "-q", "-m", "chore: x", check=False
    )


def test_hook_file_is_executable():
    assert os.access(HOOKS_DIR / "pre-commit", os.X_OK)


def test_commit_with_a_real_name_is_blocked(repo, git, ws_config):
    assert not (repo / ".githooks").exists(), "the hook must find ws from its own path"
    result = commit(repo, git, "notes.md", "meeting with Acme\n")
    assert result.returncode != 0
    assert "notes.md:1: real-name: Acme" in result.stdout + result.stderr
    assert git(repo, "log", "--oneline", check=False).returncode != 0


def test_commit_with_the_analog_succeeds(repo, git, ws_config):
    result = commit(repo, git, "notes.md", "meeting with Apex\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(repo, "log", "--oneline").stdout.count("\n") == 1


def test_hook_blocks_without_a_names_table(repo, git, tmp_path, monkeypatch):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    result = commit(repo, git, "notes.md", "meeting with Apex\n")
    assert result.returncode != 0
    assert "names table not found" in result.stdout + result.stderr
