import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

from ws import dictionary
from ws.bootstrap import SetupResult, run_setup
from ws.cli import main

HOOK_SCRIPT = "hooks/block_co_authored_by.py"
BYPASS_SCRIPT = "hooks/block_hook_bypass.py"
DENY_RULE = "Read(~/.config/workspace/credentials)"
HOOK_NAMES = ("pre-commit", "pre-merge-commit", "commit-msg", "pre-push")


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


def _setup(env: Env, check: bool = False) -> SetupResult:
    return run_setup(env.repo, env.config, env.skills_target, env.settings, check=check)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


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
    config.chmod(0o700)
    (config / "names.toml").write_text("[names]\n", encoding="utf-8")
    (config / "names.toml").chmod(0o600)

    settings = tmp_path / "claude" / "settings.json"
    settings.parent.mkdir()
    _write_settings(settings, _registered_gates())

    return Env(repo, config, tmp_path / "home" / "skills", settings)


def test_sets_hooks_path(env):
    result = _setup(env)

    assert _git(env.repo, "config", "core.hooksPath") == ".githooks"
    assert result.needs == []
    assert any(line.startswith("git hooks path: set core.hooksPath") for line in result.fixed)


def _write_hooks(repo: Path, modes: dict[str, int]) -> None:
    hooks = repo / ".githooks"
    hooks.mkdir()
    for name, mode in modes.items():
        (hooks / name).write_text("#!/bin/sh\n", encoding="utf-8")
        (hooks / name).chmod(mode)


def test_accepts_executable_hooks(env):
    _write_hooks(env.repo, {"pre-commit": 0o755, "commit-msg": 0o755})

    result = _setup(env)

    assert result.needs == []
    assert not any("hook " in line for line in result.fixed)


def test_makes_the_four_known_hooks_executable(env):
    _write_hooks(env.repo, dict.fromkeys(HOOK_NAMES, 0o644))
    (env.repo / ".githooks" / "pre-push").chmod(0o640)

    result = _setup(env)

    assert result.needs == []
    for name in HOOK_NAMES:
        hook = env.repo / ".githooks" / name
        assert os.access(hook, os.X_OK)
        assert f"hook {hook}: chmod +x" in result.fixed
    assert _mode(env.repo / ".githooks" / "pre-commit") == 0o755
    assert _mode(env.repo / ".githooks" / "pre-push") == 0o750 | 0o111


def test_looks_only_at_the_four_known_hook_names(env):
    _write_hooks(env.repo, {"pre-commit": 0o755, "helper.sh": 0o600, "pre-rebase": 0o644})

    result = _setup(env)

    assert result.needs == []
    assert _mode(env.repo / ".githooks" / "helper.sh") == 0o600
    assert _mode(env.repo / ".githooks" / "pre-rebase") == 0o644
    assert not any("helper.sh" in line or "pre-rebase" in line for line in result.fixed)


def test_a_hook_that_cannot_be_made_executable_needs_the_user(env, monkeypatch):
    _write_hooks(env.repo, {"pre-commit": 0o644, "pre-push": 0o644})
    stuck = env.repo / ".githooks" / "pre-push"
    real_chmod = Path.chmod

    def chmod(self, mode, **kwargs):
        if self == stuck:
            raise PermissionError("operation not permitted")
        return real_chmod(self, mode, **kwargs)

    monkeypatch.setattr(Path, "chmod", chmod)

    result = _setup(env)

    assert os.access(env.repo / ".githooks" / "pre-commit", os.X_OK)
    assert len(result.needs) == 1
    assert str(stuck) in result.needs[0]
    assert "chmod +x failed" in result.needs[0]
    assert "operation not permitted" in result.needs[0]
    assert not any(str(stuck) in line for line in result.fixed)


def test_reports_hooks_path_that_resolves_elsewhere(env, tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(tmp_path / "elsewhere"))

    problems = _setup(env).needs

    assert len(problems) == 1
    assert str(tmp_path / "elsewhere") in problems[0]
    assert str((env.repo / ".githooks").resolve()) in problems[0]


def test_reports_repo_that_is_not_a_git_repository(env, tmp_path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    result = run_setup(not_a_repo, env.config, env.skills_target, env.settings)
    assert len(result.needs) == 1
    assert result.needs[0].startswith("git hooks path:")


def test_links_skills(env):
    result = _setup(env)

    assert result.needs == []
    for name in ("alpha", "beta"):
        link = env.skills_target / name
        assert link.is_symlink()
        assert link.resolve() == (env.repo / "skills" / name).resolve()
        assert f"skill {name}: link {link}" in result.fixed
    assert sorted(p.name for p in env.skills_target.iterdir()) == ["alpha", "beta"]


def test_second_run_is_noop(env):
    assert _setup(env).needs == []
    links = _link_state(env.skills_target)
    private_mode = (env.config / "private").stat().st_mode

    second = _setup(env)

    assert second == SetupResult()
    assert _link_state(env.skills_target) == links
    assert (env.config / "private").stat().st_mode == private_mode
    assert _git(env.repo, "config", "core.hooksPath") == ".githooks"


def test_conflicting_skill_untouched(env):
    conflict = env.skills_target / "alpha"
    conflict.mkdir(parents=True)
    (conflict / "mine.txt").write_text("keep me", encoding="utf-8")

    problems = _setup(env).needs

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

    problems = _setup(env).needs

    assert problems == [f"skill alpha: {link} exists and is not a link to this repo"]
    assert os.readlink(link) == str(elsewhere)


def test_broken_symlink_is_a_conflict(env, tmp_path):
    env.skills_target.mkdir(parents=True)
    link = env.skills_target / "alpha"
    link.symlink_to(tmp_path / "gone", target_is_directory=True)

    problems = _setup(env).needs

    assert problems == [f"skill alpha: {link} exists and is not a link to this repo"]
    assert os.readlink(link) == str(tmp_path / "gone")


def test_repo_without_skills_folder_is_fine(env):
    shutil.rmtree(env.repo / "skills")

    assert _setup(env).needs == []
    assert not env.skills_target.exists()


def test_does_not_create_the_skills_folder_when_there_is_no_skill(env):
    shutil.rmtree(env.repo / "skills")
    (env.repo / "skills").mkdir()
    (env.repo / "skills" / ".gitkeep").touch()

    assert _setup(env).needs == []
    assert not env.skills_target.exists()


def test_reports_missing_names_table(env):
    (env.config / "names.toml").unlink()

    problems = _setup(env).needs

    assert len(problems) == 1
    assert str(env.config / "names.toml") in problems[0]


def test_fixes_loose_credentials_mode(env):
    credentials = env.config / "credentials"
    credentials.write_text("token", encoding="utf-8")
    credentials.chmod(0o644)

    result = _setup(env)

    assert result.needs == []
    assert f"credentials {credentials}: chmod 600 (from 0644)" in result.fixed
    assert _mode(credentials) == 0o600


def test_accepts_credentials_mode_600(env):
    credentials = env.config / "credentials"
    credentials.write_text("token", encoding="utf-8")
    credentials.chmod(0o600)

    result = _setup(env)

    assert result.needs == []
    assert not any(line.startswith("credentials ") for line in result.fixed)


def test_creates_private_folder_with_mode_700(env):
    assert not (env.config / "private").exists()

    result = _setup(env)

    assert result.needs == []
    assert (env.config / "private").is_dir()
    assert _mode(env.config / "private") == 0o700
    assert f"private folder {env.config / 'private'}: create with mode 700" in result.fixed


def test_fixes_loose_names_table_mode(env):
    names = env.config / "names.toml"
    names.chmod(0o644)

    result = _setup(env)

    assert result.needs == []
    assert f"names table {names}: chmod 600 (from 0644)" in result.fixed
    assert _mode(names) == 0o600
    assert names.read_text(encoding="utf-8") == "[names]\n"


def test_fixes_loose_config_folder_mode(env):
    env.config.chmod(0o755)

    result = _setup(env)

    assert result.needs == []
    assert f"config folder {env.config}: chmod 700 (from 0755)" in result.fixed
    assert _mode(env.config) == 0o700


def test_fixes_loose_private_folder_mode(env):
    private = env.config / "private"
    private.mkdir()
    private.chmod(0o750)

    result = _setup(env)

    assert result.needs == []
    assert f"private folder {private}: chmod 700 (from 0750)" in result.fixed
    assert _mode(private) == 0o700


def test_a_mode_that_cannot_be_fixed_needs_the_user(env, monkeypatch):
    names = env.config / "names.toml"
    names.chmod(0o644)
    real_chmod = Path.chmod

    def chmod(self, mode, **kwargs):
        if self == names:
            raise PermissionError("operation not permitted")
        return real_chmod(self, mode, **kwargs)

    monkeypatch.setattr(Path, "chmod", chmod)

    result = _setup(env)

    assert len(result.needs) == 1
    assert str(names) in result.needs[0]
    assert "0644" in result.needs[0]
    assert "chmod 600 failed" in result.needs[0]
    assert not any("names table" in line for line in result.fixed)


def test_private_path_that_is_a_file_needs_the_user(env):
    (env.config / "private").write_text("x", encoding="utf-8")

    assert _setup(env).needs == [f"{env.config / 'private'} exists and is not a folder"]


def test_creates_a_missing_config_folder_with_mode_700(env, tmp_path):
    fresh = tmp_path / "fresh" / "workspace"

    result = run_setup(env.repo, fresh, env.skills_target, env.settings)

    assert result.needs == [
        f"{fresh / 'names.toml'} is missing; the secrets hook fails closed without it"
    ]
    assert f"config folder {fresh}: create with mode 700" in result.fixed
    assert _mode(fresh) == 0o700
    assert _mode(fresh / "private") == 0o700


def _needs_block(result: SetupResult) -> tuple[str, dict]:
    """The one `needs` item about the Claude gates: its first line and its JSON block."""
    (item,) = [need for need in result.needs if "Claude" in need]
    header, block = item.split("\n", 1)
    assert all(line.startswith("  ") for line in block.split("\n"))
    return header, json.loads(block)


def test_prints_one_merged_block_with_every_missing_claude_gate(env):
    _write_settings(env.settings, {"theme": "dark"})
    before = env.settings.read_bytes()

    result = _setup(env)

    assert len(result.needs) == 1
    header, block = _needs_block(result)
    assert str(env.settings) in header
    assert "ws never writes that file" in header
    assert "Claude applies this after you approve" in header
    entries = block["hooks"]["PreToolUse"]
    assert [entry["hooks"][0]["command"] for entry in entries] == [
        f'python3 -I "{env.repo / script}"' for script in (HOOK_SCRIPT, BYPASS_SCRIPT)
    ]
    assert all(entry["matcher"] == "Bash" for entry in entries)
    assert block["permissions"] == {"deny": [DENY_RULE]}
    assert env.settings.read_bytes() == before


def test_accepts_registered_claude_gates(env):
    gates = _registered_gates()
    gates["hooks"]["PreToolUse"].insert(
        0, {"matcher": "Read", "hooks": [{"type": "command", "command": "echo other"}]}
    )
    gates["permissions"]["deny"].insert(0, "Read(~/other)")
    _write_settings(env.settings, gates)

    assert _setup(env).needs == []


def test_the_block_holds_only_the_missing_deny_rule(env):
    gates = _registered_gates()
    del gates["permissions"]
    _write_settings(env.settings, gates)

    _, block = _needs_block(_setup(env))

    assert block == {"permissions": {"deny": [DENY_RULE]}}


def test_the_block_holds_only_the_missing_bypass_gate(env):
    gates = _registered_gates()
    del gates["hooks"]["PreToolUse"][1]
    _write_settings(env.settings, gates)

    _, block = _needs_block(_setup(env))

    assert list(block) == ["hooks"]
    (entry,) = block["hooks"]["PreToolUse"]
    assert BYPASS_SCRIPT in entry["hooks"][0]["command"]
    assert HOOK_SCRIPT not in entry["hooks"][0]["command"]


def test_missing_claude_settings_file_gets_the_whole_block(env):
    env.settings.unlink()

    result = _setup(env)

    assert len(result.needs) == 1
    header, block = _needs_block(result)
    assert str(env.settings) in header
    assert "not found" in header
    assert len(block["hooks"]["PreToolUse"]) == 2
    assert block["permissions"] == {"deny": [DENY_RULE]}
    assert not env.settings.exists()


def test_reports_invalid_claude_settings_json(env):
    env.settings.write_text("{not json", encoding="utf-8")

    problems = _setup(env).needs

    assert len(problems) == 1
    assert str(env.settings) in problems[0]
    assert env.settings.read_text(encoding="utf-8") == "{not json"


def test_unexpected_settings_shapes_count_as_missing_gates(env):
    _write_settings(env.settings, {"hooks": [], "permissions": "none"})

    result = _setup(env)

    assert len(result.needs) == 1
    _, block = _needs_block(result)
    assert len(block["hooks"]["PreToolUse"]) == 2


def test_run_setup_reads_settings_path_from_env(env, monkeypatch):
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(env.settings))

    assert run_setup(env.repo, env.config, env.skills_target).needs == []


def _break_everything(env: Env) -> None:
    _write_hooks(env.repo, dict.fromkeys(HOOK_NAMES, 0o644))
    env.config.chmod(0o755)
    (env.config / "names.toml").chmod(0o644)
    (env.config / "credentials").write_text("token", encoding="utf-8")
    (env.config / "credentials").chmod(0o666)
    _write_settings(env.settings, {})


def _snapshot(env: Env) -> dict:
    paths = [*env.repo.rglob("*"), *env.config.rglob("*"), env.config, env.settings]
    return {
        "modes": {str(path): _mode(path) for path in paths if path.exists()},
        "skills": env.skills_target.exists(),
        "settings": env.settings.read_bytes(),
        "hooks_path": subprocess.run(
            ["git", "-C", str(env.repo), "config", "--local", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
        ).stdout,
    }


def test_check_changes_nothing_and_lists_what_setup_would_fix(env, ws_dictionaries, fake_apt):
    _break_everything(env)
    for path in ws_dictionaries.iterdir():
        path.unlink()
    before = _snapshot(env)

    result = _setup(env, check=True)

    assert _snapshot(env) == before
    assert not env.skills_target.exists()
    assert not (env.config / "private").exists()
    assert not ws_dictionaries.parent.joinpath("dict", "brazilian").exists()
    assert fake_apt.calls() == [], "check does not use the network"
    assert f"git hooks path: set core.hooksPath to .githooks in {env.repo}" in result.fixed
    for name in HOOK_NAMES:
        assert f"hook {env.repo / '.githooks' / name}: chmod +x" in result.fixed
    assert f"config folder {env.config}: chmod 700 (from 0755)" in result.fixed
    assert f"names table {env.config / 'names.toml'}: chmod 600 (from 0644)" in result.fixed
    assert f"credentials {env.config / 'credentials'}: chmod 600 (from 0666)" in result.fixed
    assert f"private folder {env.config / 'private'}: create with mode 700" in result.fixed
    assert any(line.startswith("skill alpha: link") for line in result.fixed)
    assert any(
        line.startswith("dictionaries: download wamerican and wbrazilian") for line in result.fixed
    )
    assert len(result.needs) == 1 and "Claude Code gates missing" in result.needs[0]


def test_check_on_a_clean_setup_has_nothing_to_say(env):
    assert _setup(env).needs == []

    assert _setup(env, check=True) == SetupResult()


def test_check_still_reports_what_only_the_user_can_settle(env):
    (env.config / "names.toml").unlink()
    env.settings.unlink()

    result = _setup(env, check=True)

    assert any("names.toml" in need for need in result.needs)
    assert any("not found" in need for need in result.needs)


def test_a_missing_dictionary_is_downloaded_without_root(env, ws_dictionaries, fake_apt):
    for path in ws_dictionaries.iterdir():
        path.unlink()

    result = _setup(env)

    target = dictionary.data_path()
    assert result.needs == []
    assert f"dictionaries: download wamerican and wbrazilian into {target}" in result.fixed
    assert dictionary.missing() == []
    assert dictionary.load() == {"flange", "gizmo", "porca", "arruela"}
    assert fake_apt.calls()[0]["args"] == ["download", "wamerican", "wbrazilian"]


def test_dictionaries_that_are_already_there_are_not_downloaded(env, fake_apt):
    result = _setup(env)

    assert not any(line.startswith("dictionaries:") for line in result.fixed)
    assert fake_apt.calls() == []


def test_the_system_dictionaries_count_too(env, ws_dictionaries, fake_apt, monkeypatch, tmp_path):
    system = tmp_path / "system-dict"
    system.mkdir()
    (system / "american-english").write_text("system\n", encoding="utf-8")
    (system / "brazilian").write_text("sistema\n", encoding="utf-8")
    monkeypatch.setenv("WS_SYSTEM_DICT_DIR", str(system))
    for path in ws_dictionaries.iterdir():
        path.unlink()

    result = _setup(env)

    assert not any(line.startswith("dictionaries:") for line in result.fixed)
    assert fake_apt.calls() == []


def test_a_failed_download_needs_the_user_and_the_other_steps_still_run(
    env, ws_dictionaries, fake_apt, monkeypatch
):
    for path in ws_dictionaries.iterdir():
        path.unlink()
    monkeypatch.setenv("FAKE_APT_FAIL", "1")

    result = _setup(env)

    assert len(result.needs) == 1
    assert "dictionaries not installed" in result.needs[0]
    assert "Unable to locate package" in result.needs[0]
    assert "sudo apt-get install wamerican wbrazilian" in result.needs[0]
    assert (env.skills_target / "alpha").is_symlink()
    assert _git(env.repo, "config", "core.hooksPath") == ".githooks"
    assert not any(line.startswith("dictionaries:") for line in result.fixed)


def test_missing_apt_needs_the_user_with_the_manual_command(
    env, ws_dictionaries, tmp_path, monkeypatch
):
    for path in ws_dictionaries.iterdir():
        path.unlink()
    real_git = shutil.which("git")
    bin_dir = tmp_path / "only-git"
    bin_dir.mkdir()
    (bin_dir / "git").symlink_to(real_git)
    monkeypatch.setenv("PATH", str(bin_dir))

    result = _setup(env)

    assert len(result.needs) == 1
    assert "apt-get or dpkg was not found" in result.needs[0]
    assert "sudo apt-get install wamerican wbrazilian" in result.needs[0]
    assert (env.skills_target / "alpha").is_symlink()


def _point_ws_at(env: Env, monkeypatch) -> None:
    monkeypatch.setenv("WS_REPO_ROOT", str(env.repo))
    monkeypatch.setenv("WS_CONFIG_DIR", str(env.config))
    monkeypatch.setenv("WS_CLAUDE_SKILLS_DIR", str(env.skills_target))
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(env.settings))


def test_cli_setup_prints_what_it_fixed_and_ok(env, monkeypatch, capsys):
    _point_ws_at(env, monkeypatch)
    (env.config / "names.toml").chmod(0o644)

    assert main(["setup"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "ok"
    assert f"fixed: names table {env.config / 'names.toml'}: chmod 600 (from 0644)" in lines
    assert any(line.startswith("fixed: skill alpha: link") for line in lines)
    assert not any(line.startswith("needs you:") for line in lines)
    assert (env.skills_target / "alpha").is_symlink()


def test_cli_setup_prints_ok_alone_when_nothing_is_left_to_do(env, monkeypatch, capsys):
    _point_ws_at(env, monkeypatch)
    assert main(["setup"]) == 0
    capsys.readouterr()

    assert main(["setup"]) == 0

    assert capsys.readouterr().out == "ok\n"


def test_cli_setup_prints_needs_you_lines_and_fails(env, monkeypatch, capsys):
    _point_ws_at(env, monkeypatch)
    (env.config / "names.toml").unlink()
    _write_settings(env.settings, {})

    assert main(["setup"]) == 1

    out = capsys.readouterr().out
    lines = out.splitlines()
    assert "ok" not in lines
    needs = [line for line in lines if line.startswith("needs you: ")]
    assert len(needs) == 2
    assert f"needs you: {env.config / 'names.toml'} is missing" in out
    assert out.count('"PreToolUse"') == 1, "one merged block, not one per gate"
    assert HOOK_SCRIPT in out
    assert BYPASS_SCRIPT in out
    assert DENY_RULE in out
    assert "Claude applies this after you approve" in out


def test_cli_setup_check_is_read_only_and_exits_1_when_there_is_something_to_fix(
    env, monkeypatch, capsys, fake_apt
):
    _point_ws_at(env, monkeypatch)
    before = _snapshot(env)

    assert main(["setup", "--check"]) == 1

    out = capsys.readouterr().out
    assert any(line.startswith("would fix: skill alpha: link") for line in out.splitlines())
    assert "fixed:" not in out.replace("would fix:", "")
    assert "ok" not in out.splitlines()
    assert _snapshot(env) == before
    assert not env.skills_target.exists()
    assert fake_apt.calls() == []


def test_cli_setup_check_exits_0_once_everything_is_in_place(env, monkeypatch, capsys):
    _point_ws_at(env, monkeypatch)
    assert main(["setup"]) == 0
    capsys.readouterr()

    assert main(["setup", "--check"]) == 0

    assert capsys.readouterr().out == "ok\n"
