import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

from ws.bootstrap import run_setup
from ws.cli import main

HOOK_SCRIPT = "hooks/block_co_authored_by.py"
BYPASS_SCRIPT = "hooks/block_hook_bypass.py"
DENY_RULE = "Read(~/.config/workspace/credentials)"


class Env(NamedTuple):
    repo: Path
    config: Path
    skills_target: Path
    settings: Path


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _write_settings(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _hook_entry(script: str) -> dict:
    command = f'python3 -I "$HOME/repos/acme/{script}"'
    return {"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}


def _registered_gates() -> dict:
    return {
        "hooks": {"PreToolUse": [_hook_entry(HOOK_SCRIPT), _hook_entry(BYPASS_SCRIPT)]},
        "permissions": {"deny": [DENY_RULE]},
    }


def _link_state(folder: Path) -> dict[str, tuple[str, int]]:
    return {p.name: (os.readlink(p), p.lstat().st_ino) for p in folder.iterdir()}


def _setup(env: Env) -> list[str]:
    return run_setup(env.repo, env.config, env.skills_target, env.settings)


@pytest.fixture
def env(tmp_path: Path) -> Env:
    repo = tmp_path / "repo"
    for name in ("alpha", "beta"):
        (repo / "skills" / name).mkdir(parents=True)
        (repo / "skills" / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    (repo / "skills" / ".gitkeep").touch()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)

    config = tmp_path / "config"
    config.mkdir()
    (config / "names.toml").write_text("[names]\n", encoding="utf-8")

    settings = tmp_path / "claude" / "settings.json"
    settings.parent.mkdir()
    _write_settings(settings, _registered_gates())

    return Env(repo, config, tmp_path / "home" / "skills", settings)


def test_sets_hooks_path(env):
    _setup(env)
    assert _git(env.repo, "config", "core.hooksPath") == ".githooks"


def _write_hooks(repo: Path, modes: dict[str, int]) -> None:
    hooks = repo / ".githooks"
    hooks.mkdir()
    for name, mode in modes.items():
        (hooks / name).write_text("#!/bin/sh\n", encoding="utf-8")
        (hooks / name).chmod(mode)


def test_accepts_executable_hooks(env):
    _write_hooks(env.repo, {"pre-commit": 0o755, "commit-msg": 0o755})

    assert _setup(env) == []


def test_reports_every_hook_file_that_is_not_executable(env):
    _write_hooks(
        env.repo,
        {"pre-commit": 0o755, "commit-msg": 0o644, "pre-push": 0o644, "helper.sh": 0o600},
    )

    problems = _setup(env)

    assert len(problems) == 3
    for name in ("commit-msg", "pre-push", "helper.sh"):
        assert any(str(env.repo / ".githooks" / name) in p for p in problems)
    assert all("not executable" in p and "chmod +x" in p for p in problems)
    assert not any("pre-commit" in p for p in problems)


def test_reports_hooks_path_that_resolves_elsewhere(env, tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(tmp_path / "elsewhere"))

    problems = _setup(env)

    assert len(problems) == 1
    assert str(tmp_path / "elsewhere") in problems[0]
    assert str((env.repo / ".githooks").resolve()) in problems[0]


def test_reports_repo_that_is_not_a_git_repository(env, tmp_path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    problems = run_setup(not_a_repo, env.config, env.skills_target, env.settings)
    assert len(problems) == 1
    assert problems[0].startswith("git hooks path:")


def test_links_skills(env):
    assert _setup(env) == []
    for name in ("alpha", "beta"):
        link = env.skills_target / name
        assert link.is_symlink()
        assert link.resolve() == (env.repo / "skills" / name).resolve()
    assert sorted(p.name for p in env.skills_target.iterdir()) == ["alpha", "beta"]


def test_second_run_is_noop(env):
    assert _setup(env) == []
    links = _link_state(env.skills_target)
    private_mode = (env.config / "private").stat().st_mode

    assert _setup(env) == []

    assert _link_state(env.skills_target) == links
    assert (env.config / "private").stat().st_mode == private_mode
    assert _git(env.repo, "config", "core.hooksPath") == ".githooks"


def test_conflicting_skill_untouched(env):
    conflict = env.skills_target / "alpha"
    conflict.mkdir(parents=True)
    (conflict / "mine.txt").write_text("keep me", encoding="utf-8")

    problems = _setup(env)

    assert problems == [f"skill alpha: {conflict} exists and is not a link to this repo"]
    assert not conflict.is_symlink()
    assert [p.name for p in conflict.iterdir()] == ["mine.txt"]
    assert (conflict / "mine.txt").read_text(encoding="utf-8") == "keep me"
    assert (env.skills_target / "beta").is_symlink()


def test_symlink_to_elsewhere_is_a_conflict(env, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    env.skills_target.mkdir(parents=True)
    link = env.skills_target / "alpha"
    link.symlink_to(elsewhere, target_is_directory=True)

    problems = _setup(env)

    assert problems == [f"skill alpha: {link} exists and is not a link to this repo"]
    assert os.readlink(link) == str(elsewhere)


def test_broken_symlink_is_a_conflict(env, tmp_path):
    env.skills_target.mkdir(parents=True)
    link = env.skills_target / "alpha"
    link.symlink_to(tmp_path / "gone", target_is_directory=True)

    problems = _setup(env)

    assert problems == [f"skill alpha: {link} exists and is not a link to this repo"]
    assert os.readlink(link) == str(tmp_path / "gone")


def test_repo_without_skills_folder_is_fine(env):
    shutil.rmtree(env.repo / "skills")

    assert _setup(env) == []


def test_reports_missing_names_table(env):
    (env.config / "names.toml").unlink()

    problems = _setup(env)

    assert len(problems) == 1
    assert str(env.config / "names.toml") in problems[0]


def test_reports_loose_credentials_mode(env):
    credentials = env.config / "credentials"
    credentials.write_text("token", encoding="utf-8")
    credentials.chmod(0o644)

    problems = _setup(env)

    assert len(problems) == 1
    assert str(credentials) in problems[0]
    assert "0644" in problems[0]
    assert credentials.stat().st_mode & 0o777 == 0o644


def test_accepts_credentials_mode_600(env):
    credentials = env.config / "credentials"
    credentials.write_text("token", encoding="utf-8")
    credentials.chmod(0o600)

    assert _setup(env) == []


def test_creates_private_folder_with_mode_700(env):
    assert not (env.config / "private").exists()

    assert _setup(env) == []

    assert (env.config / "private").is_dir()
    assert (env.config / "private").stat().st_mode & 0o777 == 0o700


def test_reports_missing_claude_gates(env):
    _write_settings(env.settings, {"theme": "dark"})
    before = env.settings.read_bytes()

    problems = _setup(env)

    assert len(problems) == 3
    *hook_problems, deny_problem = problems
    for script, hook_problem in zip((HOOK_SCRIPT, BYPASS_SCRIPT), hook_problems, strict=True):
        hook_json = json.loads(hook_problem.split("\n", 1)[1])
        entries = hook_json["hooks"]["PreToolUse"]
        assert len(entries) == 1
        assert entries[0]["matcher"] == "Bash"
        assert entries[0]["hooks"][0]["command"] == f'python3 -I "{env.repo / script}"'
    assert json.loads(deny_problem.split("\n", 1)[1]) == {"permissions": {"deny": [DENY_RULE]}}
    assert all(line.startswith("  ") for p in problems for line in p.split("\n")[1:])
    assert env.settings.read_bytes() == before


def test_accepts_registered_claude_gates(env):
    gates = _registered_gates()
    gates["hooks"]["PreToolUse"].insert(
        0, {"matcher": "Read", "hooks": [{"type": "command", "command": "echo other"}]}
    )
    gates["permissions"]["deny"].insert(0, "Read(~/other)")
    _write_settings(env.settings, gates)

    assert _setup(env) == []


def test_reports_only_the_missing_claude_gate(env):
    gates = _registered_gates()
    del gates["permissions"]
    _write_settings(env.settings, gates)

    problems = _setup(env)

    assert len(problems) == 1
    assert DENY_RULE in problems[0]


def test_reports_only_the_missing_bypass_gate(env):
    gates = _registered_gates()
    del gates["hooks"]["PreToolUse"][1]
    _write_settings(env.settings, gates)

    problems = _setup(env)

    assert len(problems) == 1
    assert BYPASS_SCRIPT in problems[0]
    assert HOOK_SCRIPT not in problems[0]


def test_reports_missing_claude_settings_file(env):
    env.settings.unlink()

    problems = _setup(env)

    assert len(problems) == 1
    assert str(env.settings) in problems[0]
    assert HOOK_SCRIPT in problems[0]
    assert BYPASS_SCRIPT in problems[0]
    assert DENY_RULE in problems[0]
    assert not env.settings.exists()


def test_reports_invalid_claude_settings_json(env):
    env.settings.write_text("{not json", encoding="utf-8")

    problems = _setup(env)

    assert len(problems) == 1
    assert str(env.settings) in problems[0]
    assert env.settings.read_text(encoding="utf-8") == "{not json"


def test_unexpected_settings_shapes_count_as_missing_gates(env):
    _write_settings(env.settings, {"hooks": [], "permissions": "none"})

    assert len(_setup(env)) == 3


def test_run_setup_reads_settings_path_from_env(env, monkeypatch):
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(env.settings))

    assert run_setup(env.repo, env.config, env.skills_target) == []


def _point_ws_at(env: Env, monkeypatch) -> None:
    monkeypatch.setenv("WS_REPO_ROOT", str(env.repo))
    monkeypatch.setenv("WS_CONFIG_DIR", str(env.config))
    monkeypatch.setenv("WS_CLAUDE_SKILLS_DIR", str(env.skills_target))
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(env.settings))


def test_cli_setup_prints_ok(env, monkeypatch, capsys):
    _point_ws_at(env, monkeypatch)

    assert main(["setup"]) == 0

    assert capsys.readouterr().out == "ok\n"
    assert (env.skills_target / "alpha").is_symlink()


def test_cli_setup_prints_problems_and_fails(env, monkeypatch, capsys):
    _point_ws_at(env, monkeypatch)
    (env.config / "names.toml").unlink()
    _write_settings(env.settings, {})

    assert main(["setup"]) == 1

    out = capsys.readouterr().out
    assert "ok" not in out.split("\n")
    assert str(env.config / "names.toml") in out
    assert HOOK_SCRIPT in out
    assert BYPASS_SCRIPT in out
    assert DENY_RULE in out
