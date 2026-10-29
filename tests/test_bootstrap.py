import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

from ws import config, dictionary
from ws.bootstrap import ASK_RULES, SetupResult, run_setup
from ws.cli import main

HOOK_SCRIPT = "block_co_authored_by.py"
BYPASS_SCRIPT = "block_hook_bypass.py"
GATE_SCRIPT = "approval_gate.py"
GATE_MATCHER = "Bash|mcp__.*"
LEGACY_CARD_SCRIPT = "hooks/ask_card_apply.py"
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


@pytest.fixture(autouse=True)
def _hooks_dir(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "claude" / "hooks" / "workspace"
    monkeypatch.setenv("WS_CLAUDE_HOOKS_DIR", str(path))
    return path


def _copy_command(script: str) -> str:
    return f'python3 -I "{config.claude_hooks_dir() / script}"'


def _hook_entry(script: str, matcher: str = "Bash") -> dict:
    return {"matcher": matcher, "hooks": [{"type": "command", "command": _copy_command(script)}]}


def _registered_gates() -> dict:
    return {
        "hooks": {
            "PreToolUse": [
                _hook_entry(GATE_SCRIPT, GATE_MATCHER),
                _hook_entry(HOOK_SCRIPT),
                _hook_entry(BYPASS_SCRIPT),
            ]
        },
        "permissions": {"deny": [DENY_RULE], "ask": list(ASK_RULES)},
    }


def _link_state(folder: Path) -> dict[str, tuple[str, int]]:
    return {p.name: (os.readlink(p), p.lstat().st_ino) for p in folder.iterdir()}


def _setup(env: Env, check: bool = False) -> SetupResult:
    return run_setup(env.repo, env.config, env.skills_target, env.settings, check=check)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> Env:
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
    (config / "config.toml").write_text("[jira]\n", encoding="utf-8")

    settings = tmp_path / "claude" / "settings.json"
    settings.parent.mkdir()
    _write_settings(settings, _registered_gates())

    sandbox_bin = tmp_path / "sandbox-bin"
    sandbox_bin.mkdir()
    for tool in ("bwrap", "socat"):
        (sandbox_bin / tool).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (sandbox_bin / tool).chmod(0o755)
    monkeypatch.setenv("PATH", f"{sandbox_bin}{os.pathsep}{os.environ['PATH']}")

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
        f"{fresh / 'names.toml'} is missing; the secrets hook fails closed without it",
        f'{fresh / "config.toml"} is missing; see "Local config" in README.md',
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
    assert "Claude applies this block after you approve" in header
    entries = block["hooks"]["PreToolUse"]
    assert [entry["hooks"][0]["command"] for entry in entries] == [
        _copy_command(script) for script in (GATE_SCRIPT, HOOK_SCRIPT, BYPASS_SCRIPT)
    ]
    assert [entry["matcher"] for entry in entries] == [GATE_MATCHER, "Bash", "Bash"]
    assert block["permissions"] == {"deny": [DENY_RULE], "ask": list(ASK_RULES)}
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
    del gates["permissions"]["deny"]
    _write_settings(env.settings, gates)

    _, block = _needs_block(_setup(env))

    assert block == {"permissions": {"deny": [DENY_RULE]}}


def test_ask_rules_cover_the_card_apply_command_and_every_atlassian_write_tool():
    assert "Bash(ws card apply:*)" in ASK_RULES
    assert len(ASK_RULES) == len(set(ASK_RULES))
    for tool in (
        "createJiraIssue",
        "editJiraIssue",
        "transitionJiraIssue",
        "addCommentToJiraIssue",
        "addOrEditJiraIssueComment",
        "addWorklogToJiraIssue",
        "createIssueLink",
        "executeWrite",
        "executeDestructive",
    ):
        matching = [rule for rule in ASK_RULES if rule.endswith(f"__{tool}")]
        assert len(matching) >= 2, tool
        assert all(rule.startswith("mcp__") for rule in matching)


def test_the_block_holds_only_the_missing_ask_rules(env):
    gates = _registered_gates()
    gates["permissions"]["ask"] = ASK_RULES[:3]
    _write_settings(env.settings, gates)

    result = _setup(env)

    assert len(result.needs) == 1
    _, block = _needs_block(result)
    assert block == {"permissions": {"ask": list(ASK_RULES[3:])}}


def test_the_block_holds_no_ask_rule_that_is_already_there(env):
    gates = _registered_gates()
    del gates["permissions"]["deny"]
    gates["permissions"]["ask"] = ["Read(~/other)", *ASK_RULES]
    _write_settings(env.settings, gates)

    _, block = _needs_block(_setup(env))

    assert block == {"permissions": {"deny": [DENY_RULE]}}


def test_the_block_holds_every_ask_rule_when_none_is_there(env):
    gates = _registered_gates()
    del gates["permissions"]["ask"]
    _write_settings(env.settings, gates)

    _, block = _needs_block(_setup(env))

    assert block == {"permissions": {"ask": list(ASK_RULES)}}


def test_the_block_holds_only_the_missing_bypass_gate(env):
    gates = _registered_gates()
    del gates["hooks"]["PreToolUse"][2]
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
    assert len(block["hooks"]["PreToolUse"]) == 3
    assert block["permissions"] == {"deny": [DENY_RULE], "ask": list(ASK_RULES)}
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
    assert len(block["hooks"]["PreToolUse"]) == 3


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
    for tool in ("bwrap", "socat"):
        (bin_dir / tool).symlink_to(env.repo.parent / "sandbox-bin" / tool)
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
    assert "Claude applies this block after you approve" in out


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


def test_setup_reports_missing_config_toml(env):
    (env.config / "config.toml").unlink()

    problems = _setup(env).needs

    assert problems == [f'{env.config / "config.toml"} is missing; see "Local config" in README.md']


def test_setup_reports_missing_sandbox_tools(env, monkeypatch):
    real_which = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name, *args, **kwargs: None if name in ("bwrap", "socat") else real_which(name),
    )

    problems = _setup(env).needs

    assert len(problems) == 1
    assert "sudo apt-get install -y bubblewrap socat" in problems[0]
    assert "only to run the evals" in problems[0]


def test_the_approval_gate_is_one_of_the_registered_gates(env):
    gates = _registered_gates()
    gates["hooks"]["PreToolUse"].pop(0)
    _write_settings(env.settings, gates)

    result = _setup(env)

    _, block = _needs_block(result)
    [entry] = block["hooks"]["PreToolUse"]
    assert entry["hooks"][0]["command"] == _copy_command(GATE_SCRIPT)
    assert entry["matcher"] == GATE_MATCHER


def test_card_gate_problems_name_what_is_missing(tmp_path):
    from ws.bootstrap import card_gate_problems

    settings = tmp_path / "settings.json"
    assert "not found" in card_gate_problems(settings)[0]

    settings.write_text("{not json", encoding="utf-8")
    assert "not a valid" in card_gate_problems(settings)[0]

    settings.write_text("{}", encoding="utf-8")
    assert len(card_gate_problems(settings)) == 2

    gates = _registered_gates()
    gates["permissions"]["ask"].remove("Bash(ws card apply:*)")
    settings.write_text(json.dumps(gates), encoding="utf-8")
    [problem] = card_gate_problems(settings)
    assert "Bash(ws card apply:*)" in problem

    gates = _registered_gates()
    gates["hooks"]["PreToolUse"].pop(0)
    settings.write_text(json.dumps(gates), encoding="utf-8")
    [problem] = card_gate_problems(settings)
    assert GATE_SCRIPT in problem

    settings.write_text(json.dumps(_registered_gates()), encoding="utf-8")
    assert card_gate_problems(settings) == []


def _settings_with_entry(entry: dict) -> dict:
    gates = _registered_gates()
    gates["hooks"]["PreToolUse"] = [
        e for e in gates["hooks"]["PreToolUse"] if GATE_SCRIPT not in json.dumps(e)
    ]
    gates["hooks"]["PreToolUse"].append(entry)
    return gates


def _entry(command: str, matcher: str | None = "Bash", kind: str = "command") -> dict:
    entry: dict = {"hooks": [{"type": kind, "command": command}]}
    if matcher is not None:
        entry["matcher"] = matcher
    return entry


def _with_copy(entry: dict) -> dict:
    """Fill `{dir}` in the command with the hooks copy folder of the test."""
    if not isinstance(entry["hooks"], list):
        return entry
    folder = str(config.claude_hooks_dir())
    hooks = [{**h, "command": h["command"].replace("{dir}", folder)} for h in entry["hooks"]]
    return {**entry, "hooks": hooks}


GATE = "{dir}/" + GATE_SCRIPT


@pytest.mark.parametrize(
    "entry",
    [
        _entry(f'python3 -I "{GATE}"'),
        _entry(f"python3 {GATE}"),
        _entry(f"python {GATE}"),
        _entry(f"/usr/bin/python3.12 -I {GATE}"),
        _entry(f'python3 -I "{GATE}"', matcher="Write|Bash"),
        _entry(f'python3 -I "{GATE}"', matcher="Bash|Edit"),
        _entry(f'python3 -I "{GATE}"', matcher=GATE_MATCHER),
        _entry(f'python3 -I "{GATE}"', matcher="*"),
        _entry(f'python3 -I "{GATE}"', matcher=""),
        _entry(f'python3 -I "{GATE}"', matcher=None),
    ],
)
def test_a_real_registration_of_the_gate_from_the_copy_is_accepted(tmp_path, entry):
    from ws.bootstrap import card_gate_problems

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(_settings_with_entry(_with_copy(entry))), encoding="utf-8")

    assert card_gate_problems(settings) == []


@pytest.mark.parametrize(
    "entry",
    [
        _entry(f"echo {GATE}", matcher="Write"),
        _entry(f"echo {GATE}"),
        _entry(f'python3 -I "{GATE}"', matcher="Write"),
        _entry(f'python3 -I "{GATE}"', matcher="Bashful"),
        _entry(f'python3 -I "{GATE}"', matcher="bash"),
        _entry(f'python3 -I "{GATE}"', matcher="("),
        _entry(f'python3 -I "{GATE}"', kind="prompt"),
        _entry(f'echo "python3 {GATE}"'),
        _entry(f"python3 -I {GATE}; echo"),
        _entry(f"python3 -I {GATE}.bak"),
        _entry(f"python3 -I {GATE} --dry"),
        _entry(f"cat {GATE}"),
        _entry("python3 -I 'unterminated"),
        _entry('python3 -I "/srv/ws/hooks/approval_gate.py"'),
        _entry('python3 -I "/srv/other/approval_gate.py"'),
        {"matcher": "Bash", "hooks": "none"},
        {"matcher": ["Bash"], "hooks": [{"type": "command", "command": f"python3 {GATE}"}]},
    ],
)
def test_a_forged_or_misplaced_gate_entry_does_not_count(tmp_path, entry):
    from ws.bootstrap import card_gate_problems

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(_settings_with_entry(_with_copy(entry))), encoding="utf-8")

    [problem] = card_gate_problems(settings)
    assert GATE_SCRIPT in problem


def test_setup_asks_again_for_a_forged_gate_entry(env):
    entry = _with_copy(_entry(f"echo {GATE}", "Write"))
    _write_settings(env.settings, _settings_with_entry(entry))

    result = _setup(env)

    _, block = _needs_block(result)
    assert [e["hooks"][0]["command"] for e in block["hooks"]["PreToolUse"]] == [
        _copy_command(GATE_SCRIPT)
    ]


MCP_PUSH = "mcp__plugin_github_github__push_files"


@pytest.mark.parametrize(
    ("matcher", "covers_mcp"),
    [
        (GATE_MATCHER, True),
        ("mcp__.*|Bash", True),
        ("*", True),
        (None, True),
        ("Bash", False),
        ("Bash|mcp__plugin_gitkraken.*", False),
        ("mcp__.*", False),
    ],
)
def test_the_gate_matcher_must_cover_bash_and_mcp_tools(env, matcher, covers_mcp):
    gates = _registered_gates()
    gates["hooks"]["PreToolUse"][0] = _entry(_copy_command(GATE_SCRIPT), matcher)
    _write_settings(env.settings, gates)

    needs = _setup(env).needs

    if covers_mcp:
        assert needs == []
    else:
        assert any("does not cover" in need for need in needs)
        _, block = _needs_block(SetupResult(needs=needs))
        assert block["hooks"]["PreToolUse"][0]["matcher"] == GATE_MATCHER
    assert re.fullmatch(GATE_MATCHER, MCP_PUSH)


def test_a_registration_that_still_points_at_the_repo_is_reported_with_its_replacement(env):
    gates = _registered_gates()
    gates["hooks"]["PreToolUse"][1] = _entry(f'python3 -I "{env.repo}/hooks/{HOOK_SCRIPT}"')
    gates["hooks"]["PreToolUse"].append(_entry(f'python3 -I "{env.repo}/{LEGACY_CARD_SCRIPT}"'))
    _write_settings(env.settings, gates)

    result = _setup(env)

    stale = [need for need in result.needs if need.startswith("stale hook registration")]
    assert len(stale) == 2
    assert f"{env.repo}/hooks/{HOOK_SCRIPT} is replaced by {_copy_command(HOOK_SCRIPT)}" in stale[1]
    assert (
        f"{env.repo}/{LEGACY_CARD_SCRIPT} is replaced by {_copy_command(GATE_SCRIPT)}" in stale[0]
    )
    _, block = _needs_block(
        SetupResult(needs=[n for n in result.needs if not n.startswith("stale")])
    )
    assert [e["hooks"][0]["command"] for e in block["hooks"]["PreToolUse"]] == [
        _copy_command(HOOK_SCRIPT)
    ]


def test_a_home_variable_in_the_registered_path_is_expanded(env, monkeypatch):
    monkeypatch.setenv("HOME", str(env.settings.parent))
    gates = _registered_gates()
    gates["hooks"]["PreToolUse"][1] = _entry(f'python3 -I "$HOME/hooks/workspace/{HOOK_SCRIPT}"')
    _write_settings(env.settings, gates)

    assert _setup(env).needs == []


def test_the_new_ask_rules_cover_the_github_and_gitkraken_writes():
    for tool in (
        "add_comment_to_pending_review",
        "add_issue_comment",
        "add_reply_to_pull_request_comment",
        "create_branch",
        "create_or_update_file",
        "create_pull_request",
        "create_repository",
        "delete_file",
        "delete_repository",
        "fork_repository",
        "issue_write",
        "merge_pull_request",
        "pull_request_review_write",
        "push_files",
        "request_copilot_review",
        "run_secret_scanning",
        "sub_issue_write",
        "update_issue_comment",
        "update_pull_request",
        "update_pull_request_branch",
    ):
        assert f"mcp__plugin_github_github__{tool}" in ASK_RULES, tool
    for tool in (
        "git_push",
        "issues_add_comment",
        "issues_create",
        "pull_request_create",
        "pull_request_create_review",
    ):
        assert f"mcp__plugin_gitkraken_gitkraken__{tool}" in ASK_RULES, tool
    assert "mcp__plugin_github_github__get_file_contents" not in ASK_RULES


def _gate_config(env: Env, text: str) -> list[str]:
    (env.config / "config.toml").write_text(text, encoding="utf-8")
    return _setup(env).needs


def test_the_gate_table_is_optional_and_accepts_the_two_keys(env):
    assert _gate_config(env, "[jira]\n") == []
    assert (
        _gate_config(
            env,
            '[gate]\npush_without_asking = ["~/repos/workspace", "/srv/x"]\n'
            'personal_github_owners = ["someone"]\n',
        )
        == []
    )
    assert _gate_config(env, "[gate]\n") == []


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ('[gate]\npush_without_asking = "~/repos/workspace"\n', "push_without_asking"),
        ("[gate]\npush_without_asking = [1]\n", "push_without_asking"),
        ('[gate]\npersonal_github_owners = "someone"\n', "personal_github_owners"),
        ("[gate]\npersonal_github_owners = [true]\n", "personal_github_owners"),
    ],
)
def test_a_gate_key_of_the_wrong_type_is_reported(env, text, key):
    [problem] = _gate_config(env, text)

    assert f"[gate] {key} must be a list of strings" in problem


def test_a_gate_that_is_not_a_table_is_reported(env):
    [problem] = _gate_config(env, "gate = 3\n")

    assert "[gate] must be a table" in problem


def test_setup_does_not_write_the_gate_keys(env):
    before = (env.config / "config.toml").read_bytes()

    _setup(env)

    assert (env.config / "config.toml").read_bytes() == before


def _fake_hooks(repo: Path) -> dict[str, bytes]:
    files = {
        "hooks/approval_gate.py": b"print('gate')\n",
        "hooks/block_co_authored_by.py": b"print('a')\n",
        "hooks/block_hook_bypass.py": b"print('b')\n",
        "hooks/ask_card_apply.py": b"print('old')\n",
        "hooks/gate/rules.py": b"X = 1\n",
        "hooks/gate/catalog.json": b'{"a": 1}\n',
        "hooks/gate/notes.md": b"not copied\n",
        "hooks/gate/deep/more.py": b"not copied\n",
        "hooks/__pycache__/x.pyc": b"\x00",
        "hooks/gate/__pycache__/y.pyc": b"\x00",
        "hooks/readme.txt": b"not copied\n",
    }
    for rel, data in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes(data)
    return files


COPIED = (
    "approval_gate.py",
    "block_co_authored_by.py",
    "block_hook_bypass.py",
    "gate/catalog.json",
    "gate/rules.py",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _copy_files(hooks_dir: Path) -> list[str]:
    return sorted(
        p.relative_to(hooks_dir).as_posix()
        for p in hooks_dir.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    )


def test_setup_copies_the_hooks_read_only_with_a_manifest(env, _hooks_dir):
    files = _fake_hooks(env.repo)

    result = _setup(env)

    assert _copy_files(_hooks_dir) == list(COPIED)
    for rel in COPIED:
        assert (_hooks_dir / rel).read_bytes() == files[f"hooks/{rel}"]
        assert _mode(_hooks_dir / rel) == 0o444
    assert not (_hooks_dir / "ask_card_apply.py").exists()
    manifest = json.loads((_hooks_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == {rel: _sha(files[f"hooks/{rel}"]) for rel in COPIED}
    assert _mode(_hooks_dir / "manifest.json") == 0o444
    assert _mode(_hooks_dir) == 0o755
    assert _mode(_hooks_dir / "gate") == 0o755
    assert any(line.startswith(f"hooks copy: create {_hooks_dir}") for line in result.fixed)
    assert _setup(env) == SetupResult()


def test_check_reports_a_missing_copy_and_writes_nothing(env, _hooks_dir):
    _fake_hooks(env.repo)

    result = _setup(env, check=True)

    assert not _hooks_dir.exists()
    assert any(line.startswith(f"hooks copy: create {_hooks_dir}") for line in result.fixed)


def _copy_in_place(env: Env) -> dict[str, bytes]:
    files = _fake_hooks(env.repo)
    assert _setup(env).needs == []
    return files


def test_a_stale_file_is_reported_and_fixed(env, _hooks_dir):
    _copy_in_place(env)
    (env.repo / "hooks/approval_gate.py").write_bytes(b"print('gate v2')\n")

    check = _setup(env, check=True)

    assert check.fixed[0] == "hooks copy approval_gate.py: stale; restore it from the repo"
    assert (_hooks_dir / "approval_gate.py").read_bytes() == b"print('gate')\n"
    _setup(env)
    assert (_hooks_dir / "approval_gate.py").read_bytes() == b"print('gate v2')\n"
    assert _mode(_hooks_dir / "approval_gate.py") == 0o444
    manifest = json.loads((_hooks_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["approval_gate.py"] == _sha(b"print('gate v2')\n")
    assert _setup(env) == SetupResult()


def test_an_edited_file_is_reported_as_edited_and_restored(env, _hooks_dir):
    files = _copy_in_place(env)
    target = _hooks_dir / "block_hook_bypass.py"
    target.chmod(0o644)
    target.write_bytes(b"import sys\nsys.exit(0)\n")

    check = _setup(env, check=True)

    assert check.fixed == [
        "hooks copy block_hook_bypass.py: edited after the copy "
        "(differs from the manifest); restore it from the repo"
    ]
    _setup(env)
    assert target.read_bytes() == files["hooks/block_hook_bypass.py"]
    assert _mode(target) == 0o444


def test_a_missing_file_is_copied_again(env, _hooks_dir):
    _copy_in_place(env)
    (_hooks_dir / "gate" / "rules.py").unlink()

    check = _setup(env, check=True)
    assert check.fixed == [
        f"hooks copy gate/rules.py: missing; copy it to {_hooks_dir / 'gate' / 'rules.py'}"
    ]

    _setup(env)
    assert (_hooks_dir / "gate" / "rules.py").read_bytes() == b"X = 1\n"


def test_an_extra_file_is_reported_and_removed(env, _hooks_dir):
    _copy_in_place(env)
    (_hooks_dir / "gate" / "planted.py").write_bytes(b"x\n")
    (_hooks_dir / "sitecustomize.py").write_bytes(b"x\n")

    check = _setup(env, check=True)

    assert check.fixed == [
        "hooks copy gate/planted.py: not in the repo; remove it",
        "hooks copy sitecustomize.py: not in the repo; remove it",
    ]
    _setup(env)
    assert _copy_files(_hooks_dir) == list(COPIED)


def test_a_symlink_in_the_copy_is_edited_and_replaced(env, _hooks_dir, tmp_path):
    files = _copy_in_place(env)
    target = _hooks_dir / "approval_gate.py"
    target.unlink()
    elsewhere = tmp_path / "elsewhere.py"
    elsewhere.write_bytes(files["hooks/approval_gate.py"])
    target.symlink_to(elsewhere)

    check = _setup(env, check=True)
    assert "edited" in check.fixed[0]

    _setup(env)
    assert not target.is_symlink()
    assert elsewhere.read_bytes() == files["hooks/approval_gate.py"]


def test_a_loose_mode_is_fixed(env, _hooks_dir):
    _copy_in_place(env)
    (_hooks_dir / "approval_gate.py").chmod(0o644)

    check = _setup(env, check=True)
    assert check.fixed == ["hooks copy approval_gate.py: chmod 444"]

    _setup(env)
    assert _mode(_hooks_dir / "approval_gate.py") == 0o444


def test_a_lost_or_forged_manifest_is_written_again(env, _hooks_dir):
    _copy_in_place(env)
    manifest = _hooks_dir / "manifest.json"
    manifest.unlink()

    assert _setup(env, check=True).fixed == [f"hooks copy: write the manifest {manifest}"]
    _setup(env)
    assert _setup(env) == SetupResult()

    manifest.chmod(0o644)
    manifest.write_text("[]", encoding="utf-8")
    assert _setup(env, check=True).fixed == [f"hooks copy: write the manifest {manifest}"]


def test_a_copy_without_a_manifest_reports_a_different_file_as_stale(env, _hooks_dir):
    _copy_in_place(env)
    (_hooks_dir / "manifest.json").unlink()
    (_hooks_dir / "approval_gate.py").chmod(0o644)
    (_hooks_dir / "approval_gate.py").write_bytes(b"x\n")

    check = _setup(env, check=True)

    assert check.fixed[0] == "hooks copy approval_gate.py: stale; restore it from the repo"


def test_a_copy_folder_that_is_a_file_needs_the_user(env, _hooks_dir):
    _fake_hooks(env.repo)
    _hooks_dir.parent.mkdir(parents=True, exist_ok=True)
    _hooks_dir.write_text("x", encoding="utf-8")

    result = _setup(env)

    assert f"hooks copy: {_hooks_dir} exists and is not a folder" in result.needs


def test_a_failed_copy_needs_the_user(env, _hooks_dir, monkeypatch):
    _fake_hooks(env.repo)

    def refuse(self, *args, **kwargs):
        raise PermissionError("read-only file system")

    monkeypatch.setattr(Path, "mkdir", refuse)
    result = _setup(env)

    assert any(
        "could not write in" in need and "read-only file system" in need for need in result.needs
    )


def test_a_repo_without_hooks_makes_no_copy(env, _hooks_dir):
    assert _setup(env).needs == []
    assert not _hooks_dir.exists()


def test_setup_reads_the_hooks_folder_from_the_environment(env, _hooks_dir, monkeypatch, tmp_path):
    _fake_hooks(env.repo)
    other = tmp_path / "other-hooks"
    monkeypatch.setenv("WS_CLAUDE_HOOKS_DIR", str(other))

    run_setup(env.repo, env.config, env.skills_target, env.settings)

    assert (other / "approval_gate.py").is_file()
    assert not _hooks_dir.exists()


def test_the_default_hooks_folder_is_under_the_claude_folder(monkeypatch):
    monkeypatch.delenv("WS_CLAUDE_HOOKS_DIR")

    assert config.claude_hooks_dir() == Path.home() / ".claude" / "hooks" / "workspace"
