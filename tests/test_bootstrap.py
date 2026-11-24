import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

from ws import bootstrap, config, dictionary, userconfig
from ws.bootstrap import ASK_RULES, SetupResult, run_setup
from ws.cli import main

HOOK_SCRIPT = "block_co_authored_by.py"
BYPASS_SCRIPT = "block_hook_bypass.py"
WATCH_SCRIPT = "context_watch.py"
POINTER_SCRIPT = "handoff_pointer.py"
TIME_SCRIPT = "time_activity.py"
POINTER_MATCHER = "startup|clear|compact"
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
def _clean_environment(tmp_path: Path, monkeypatch) -> None:
    """The real session holds secrets and a real ~/.claude.json; neither may reach these tests."""
    for name in os.environ:
        if bootstrap.ENV_PATTERN.search(name):
            monkeypatch.delenv(name)
    monkeypatch.setenv("WS_CLAUDE_JSON", str(tmp_path / "claude.json"))
    monkeypatch.setenv("WS_CLAUDE_PLUGINS_DIR", str(tmp_path / "no-plugins"))
    monkeypatch.setenv("WS_BIN", str(tmp_path / "bin" / "ws"))


def _github_server(helper: str | None = None, **changes) -> dict:
    spec = {
        "type": "http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headersHelper": helper or f"{config.ws_executable()} mcp-headers github",
    }
    return {"mcpServers": {"github": {**spec, **changes}}}


def _write_claude_json(data: dict) -> None:
    config.claude_json_path().write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture(autouse=True)
def _hooks_dir(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "claude" / "hooks" / "workspace"
    monkeypatch.setenv("WS_CLAUDE_HOOKS_DIR", str(path))
    return path


@pytest.fixture(autouse=True)
def _answers(monkeypatch) -> list[str]:
    """What the user types at the question of the protected copy; `s` unless a test changes it."""
    answers = ["s"]
    monkeypatch.setattr("builtins.input", lambda prompt="": answers[0])
    return answers


def _copy_command(script: str) -> str:
    return f'python3 -I -B "{config.claude_hooks_dir() / script}"'


def _hook_entry(script: str, matcher: str | None = "Bash") -> dict:
    entry: dict = {"hooks": [{"type": "command", "command": _copy_command(script)}]}
    if matcher is not None:
        entry["matcher"] = matcher
    return entry


def _registered_gates() -> dict:
    return {
        "hooks": {
            "PreToolUse": [
                _hook_entry(GATE_SCRIPT, GATE_MATCHER),
                _hook_entry(HOOK_SCRIPT),
                _hook_entry(BYPASS_SCRIPT),
            ],
            "UserPromptSubmit": [_hook_entry(WATCH_SCRIPT, None), _hook_entry(TIME_SCRIPT, None)],
            "SessionStart": [_hook_entry(POINTER_SCRIPT, POINTER_MATCHER)],
        },
        "permissions": {"deny": [DENY_RULE], "ask": list(ASK_RULES)},
    }


def _link_state(folder: Path) -> dict[str, tuple[str, int]]:
    return {p.name: (os.readlink(p), p.lstat().st_ino) for p in folder.iterdir()}


def _setup(env: Env, check: bool = False, by_hand: bool = True) -> SetupResult:
    return run_setup(
        env.repo, env.config, env.skills_target, env.settings, check=check, by_hand=by_hand
    )


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
    (config / "config.toml").write_text(
        '[tracker]\nkind = "jira"\n[tracker.jira]\n', encoding="utf-8"
    )

    monkeypatch.setenv("WS_CONFIG_DIR", str(config))
    userconfig.save_token("github", "fake-value")
    _write_claude_json(_github_server())

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

    problems = [need for need in _setup(env).needs if "hooks path" in need]

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
    credentials.chmod(0o644)

    result = _setup(env)

    assert result.needs == []
    assert f"credentials {credentials}: chmod 600 (from 0644)" in result.fixed
    assert _mode(credentials) == 0o600


def test_accepts_credentials_mode_600(env):
    credentials = env.config / "credentials"
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
        "no usable GitHub token (none is stored); the GitHub MCP server needs one. "
        "Run in a terminal, outside Claude: ws config token github",
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
    (bin_dir / "python3").symlink_to(shutil.which("python3"))
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


def test_setup_reports_a_hook_python_without_tomllib(env, monkeypatch):
    real_run = subprocess.run

    def fake_run(command, *args, **kwargs):
        if command[:3] == ["python3", "-I", "-c"]:
            return subprocess.CompletedProcess(command, 1, "", "ModuleNotFoundError: tomllib")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)

    problems = _setup(env).needs

    assert len(problems) == 1
    assert "older than 3.11" in problems[0]


def test_setup_accepts_the_hook_python():
    assert subprocess.run(["python3", "-I", "-c", "import tomllib"], check=False).returncode == 0


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


def _entry(command: str, matcher: str | None = "Bash", kind: str = "command", timeout=None) -> dict:
    entry: dict = {"hooks": [{"type": kind, "command": command}]}
    if timeout is not None:
        entry["hooks"][0]["timeout"] = timeout
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
        _entry(f"python3 -I -B {GATE}"),
        _entry(f"python3 -IB {GATE}"),
        _entry(f"python3 -B -I {GATE}"),
        _entry(f"/usr/bin/python3.12 -I {GATE}"),
        _entry(f'python3 -I "{GATE}"', timeout=10),
        _entry(f'python3 -I "{GATE}"', timeout=30),
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
        _entry(f"python3 {GATE}"),
        _entry(f"python {GATE}"),
        _entry(f"python3 -c pass {GATE}"),
        _entry(f"python3 -I -c pass {GATE}"),
        _entry(f"python3 -S -I {GATE}"),
        _entry(f"python3 -B {GATE}"),
        _entry(f'python3 -I "{GATE}"', timeout=9),
        _entry(f'python3 -I "{GATE}"', timeout=0),
        _entry(f'python3 -I "{GATE}"', timeout="30"),
        _entry(f'python3 -I "{GATE}"', timeout=True),
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


def test_the_gate_table_is_optional_and_accepts_its_keys(env):
    assert _gate_config(env, '[tracker]\nkind = "jira"\n[tracker.jira]\n') == []
    assert (
        _gate_config(
            env,
            '[gate]\npush_without_asking = ["~/repos/workspace", "/srv/x"]\n'
            'personal_github_owners = ["someone"]\n'
            'environment_branches = ["master", "main"]\n'
            'direct_push_repos = ["*-argocd"]\n',
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
        ('[gate]\nenvironment_branches = "main"\n', "environment_branches"),
        ("[gate]\nenvironment_branches = [1]\n", "environment_branches"),
        ('[gate]\ndirect_push_repos = "*-argocd"\n', "direct_push_repos"),
        ("[gate]\ndirect_push_repos = [false]\n", "direct_push_repos"),
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
    assert _mode(_hooks_dir) == 0o555
    assert _mode(_hooks_dir / "gate") == 0o555
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
    (_hooks_dir / "gate").chmod(0o755)
    (_hooks_dir / "gate" / "rules.py").unlink()
    (_hooks_dir / "gate").chmod(0o555)

    check = _setup(env, check=True)
    assert check.fixed == [
        f"hooks copy gate/rules.py: missing; copy it to {_hooks_dir / 'gate' / 'rules.py'}"
    ]

    _setup(env)
    assert (_hooks_dir / "gate" / "rules.py").read_bytes() == b"X = 1\n"


def _plant(path: Path) -> None:
    path.parent.chmod(0o755)
    path.write_bytes(b"x\n")
    path.parent.chmod(0o555)


def test_an_extra_file_is_reported_and_removed(env, _hooks_dir):
    _copy_in_place(env)
    _plant(_hooks_dir / "gate" / "planted.py")
    _plant(_hooks_dir / "sitecustomize.py")

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
    _hooks_dir.chmod(0o755)
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
    _hooks_dir.chmod(0o755)
    manifest.unlink()
    _hooks_dir.chmod(0o555)

    assert _setup(env, check=True).fixed == [f"hooks copy: write the manifest {manifest}"]
    _setup(env)
    assert _setup(env) == SetupResult()

    manifest.chmod(0o644)
    manifest.write_text("[]", encoding="utf-8")
    assert _setup(env, check=True).fixed == [f"hooks copy: write the manifest {manifest}"]


def test_a_copy_without_a_manifest_reports_a_different_file_as_stale(env, _hooks_dir):
    _copy_in_place(env)
    _hooks_dir.chmod(0o755)
    (_hooks_dir / "manifest.json").unlink()
    _hooks_dir.chmod(0o555)
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

    run_setup(env.repo, env.config, env.skills_target, env.settings, by_hand=True)

    assert (other / "approval_gate.py").is_file()
    assert not _hooks_dir.exists()


def test_the_default_hooks_folder_is_under_the_claude_folder(monkeypatch):
    monkeypatch.delenv("WS_CLAUDE_HOOKS_DIR")

    assert config.claude_hooks_dir() == Path.home() / ".claude" / "hooks" / "workspace"


def _need(result: SetupResult, word: str) -> str:
    (item,) = [need for need in result.needs if word in need]
    return item


def test_secret_variables_get_one_snippet_with_names_and_never_values(env, monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY", "value-one-xyz")
    monkeypatch.setenv("my_password", "value-two-xyz")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "value-three-xyz")

    item = _need(_setup(env), "secret variables")

    header, block = item.split("\n", 1)
    assert "Claude Code sessions only" in header
    assert json.loads(block) == {
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "", "SERVICE_API_KEY": "", "my_password": ""}
    }
    assert "value-" not in item


def test_secret_variables_skip_other_names_empty_values_and_ws_and_claude_ones(env, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_MESSAGING_TOKEN", "x1")
    monkeypatch.setenv("WS_SOME_KEY", "x2")
    monkeypatch.setenv("EMPTY_TOKEN", "")
    monkeypatch.setenv("PYTHONPATH", "/somewhere")
    monkeypatch.setenv("EDITOR", "vim")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/run/agent.sock")

    assert _setup(env).needs == []


def test_a_pat_segment_is_a_secret_but_a_path_is_not(env, monkeypatch):
    monkeypatch.setenv("GITHUB_PAT", "x1")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/lib")

    block = json.loads(_need(_setup(env), "secret variables").split("\n", 1)[1])

    assert block == {"env": {"GITHUB_PAT": ""}}


def test_a_variable_the_claude_settings_already_blank_is_not_reported(env, monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY", "value-one-xyz")
    monkeypatch.setenv("OTHER_TOKEN", "value-two-xyz")
    gates = _registered_gates()
    gates["env"] = {"SERVICE_API_KEY": ""}
    _write_settings(env.settings, gates)

    block = json.loads(_need(_setup(env), "secret variables").split("\n", 1)[1])

    assert block == {"env": {"OTHER_TOKEN": ""}}


def test_check_reports_secret_variables_without_changing_the_settings(env, monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY", "value-one-xyz")
    before = env.settings.read_bytes()

    result = _setup(env, check=True)

    assert "SERVICE_API_KEY" in _need(result, "secret variables")
    assert env.settings.read_bytes() == before


def test_the_cli_prints_the_secret_variables_line_without_the_value(env, monkeypatch, capsys):
    monkeypatch.setenv("SERVICE_API_KEY", "value-one-xyz")
    monkeypatch.setenv("WS_REPO_ROOT", str(env.repo))
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(env.settings))
    monkeypatch.setenv("WS_CLAUDE_SKILLS_DIR", str(env.skills_target))

    assert main(["setup", "--check"]) == 1

    out = capsys.readouterr().out
    assert "needs you: secret variables in the environment: SERVICE_API_KEY." in out
    assert "value-one-xyz" not in out


def _github_command(result: SetupResult) -> tuple[str, dict]:
    item = _need(result, "GitHub MCP server")
    words = shlex.split(item.split("\n")[-1].strip())
    assert words[-2:] == ["--scope", "user"]
    return item, json.loads(words[words.index("add-json") + 2])


def test_a_correct_github_server_needs_nothing(env):
    assert _setup(env).needs == []


def test_a_github_helper_with_the_bare_command_name_is_accepted(env):
    _write_claude_json(_github_server("ws mcp-headers github"))

    assert _setup(env).needs == []


def test_a_missing_github_server_gets_the_command_with_the_absolute_ws_path(env, tmp_path):
    config.claude_json_path().unlink()

    item, spec = _github_command(_setup(env))

    assert "is missing" in item
    assert "remove" not in item
    assert spec == {
        "type": "http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headersHelper": f"{tmp_path / 'bin' / 'ws'} mcp-headers github",
    }
    assert not config.claude_json_path().exists()


def test_a_claude_json_without_the_github_server_is_missing_it(env):
    _write_claude_json({"mcpServers": {"other": {"type": "http", "url": "https://x.example/"}}})

    assert "is missing" in _need(_setup(env), "GitHub MCP server")


@pytest.mark.parametrize(
    "server",
    [
        _github_server(type="sse"),
        _github_server(url="https://api.githubcopilot.com/mcp/readonly"),
        _github_server("echo ws mcp-headers github"),
        _github_server("/tmp/ws mcp-headers github --extra"),
        _github_server("/tmp/other mcp-headers github"),
        _github_server("ws mcp-headers"),
    ],
)
def test_a_different_github_server_gets_remove_then_add(env, server):
    _write_claude_json(server)

    item, spec = _github_command(_setup(env))

    assert "is different" in item
    assert "claude mcp remove github --scope user && claude mcp add-json github" in item
    assert spec["type"] == "http"


def test_an_unreadable_claude_json_is_reported(env):
    config.claude_json_path().write_text("{not json", encoding="utf-8")

    assert "unreadable" in _need(_setup(env), "GitHub MCP server")


def test_without_a_github_token_setup_says_to_store_it_first(env):
    (env.config / "credentials").unlink()
    config.claude_json_path().unlink()

    result = _setup(env)

    assert "ws config token github" in _need(result, "usable GitHub token")
    assert not any("claude mcp" in need for need in result.needs)


def test_a_symlinked_credentials_file_is_not_trusted_as_a_github_token(env, tmp_path):
    real = tmp_path / "elsewhere"
    real.write_text((env.config / "credentials").read_text(encoding="utf-8"), encoding="utf-8")
    (env.config / "credentials").unlink()
    (env.config / "credentials").symlink_to(real)

    assert "symlink" in _need(_setup(env), "usable GitHub token")


def test_no_ws_executable_is_reported_instead_of_a_bare_command(env, monkeypatch):
    config.claude_json_path().unlink()
    monkeypatch.delenv("WS_BIN")
    monkeypatch.setenv("HOME", str(env.config))
    monkeypatch.setattr(shutil, "which", lambda name, *args, **kwargs: None)

    assert "ws executable was not found" in _need(_setup(env), "GitHub MCP server")


def test_ask_rules_cover_every_github_write_tool_of_the_user_scope_server():
    for tool in bootstrap.GITHUB_WRITE_TOOLS:
        assert f"mcp__github__{tool}" in ASK_RULES, tool
    assert "mcp__github__get_me" not in ASK_RULES
    assert len(ASK_RULES) == len(set(ASK_RULES))


def test_a_writable_copy_folder_is_locked_again(env, _hooks_dir):
    _copy_in_place(env)
    (_hooks_dir / "gate").chmod(0o755)

    check = _setup(env, check=True)

    assert check.fixed == ["hooks copy folder gate: chmod 555 (from 0755)"]
    assert _mode(_hooks_dir / "gate") == 0o755
    _setup(env)
    assert _mode(_hooks_dir / "gate") == 0o555
    assert _setup(env) == SetupResult()


@pytest.mark.parametrize("folder", ["__pycache__", "gate/__pycache__", "gate/shadow"])
def test_an_extra_folder_such_as_pycache_is_reported_and_removed(env, _hooks_dir, folder):
    _copy_in_place(env)
    parent = (_hooks_dir / folder).parent
    parent.chmod(0o755)
    (_hooks_dir / folder).mkdir()
    (_hooks_dir / folder / "rules.cpython-312.pyc").write_bytes(b"\x00")
    parent.chmod(0o555)

    check = _setup(env, check=True)

    assert check.fixed == [f"hooks copy {folder}: not in the repo; remove it"]
    _setup(env)
    assert not (_hooks_dir / folder).exists()
    assert _mode(_hooks_dir / "gate") == 0o555
    assert _setup(env) == SetupResult()


def test_an_empty_pycache_folder_is_reported_too(env, _hooks_dir):
    _copy_in_place(env)
    _hooks_dir.chmod(0o755)
    (_hooks_dir / "__pycache__").mkdir()
    _hooks_dir.chmod(0o555)

    assert _setup(env, check=True).fixed == ["hooks copy __pycache__: not in the repo; remove it"]


def test_the_printed_registration_isolates_python_and_sets_a_timeout(env):
    _write_settings(env.settings, {"theme": "dark"})

    _, block = _needs_block(_setup(env))

    for entry in block["hooks"]["PreToolUse"]:
        [hook] = entry["hooks"]
        assert hook["command"].startswith('python3 -I -B "')
        assert hook["timeout"] == 30


@pytest.mark.parametrize("script", [GATE_SCRIPT, HOOK_SCRIPT, BYPASS_SCRIPT])
@pytest.mark.parametrize("timeout", [1, 9, 9.5, 0, "30", True])
def test_a_short_timeout_on_one_of_our_hooks_is_a_problem_and_is_printed_again(
    env, script, timeout
):
    from ws.bootstrap import card_gate_problems

    gates = _registered_gates()
    for entry in gates["hooks"]["PreToolUse"]:
        if script in entry["hooks"][0]["command"]:
            entry["hooks"][0]["timeout"] = timeout
    _write_settings(env.settings, gates)

    problems = card_gate_problems(env.settings)
    result = _setup(env)

    assert any("timeout" in problem for problem in problems)
    assert any("timeout" in need for need in result.needs)
    _, block = _needs_block(result)
    [entry] = block["hooks"]["PreToolUse"]
    assert script in entry["hooks"][0]["command"]
    assert entry["hooks"][0]["timeout"] == 30


@pytest.mark.parametrize("timeout", [10, 30, 600])
def test_a_timeout_of_ten_seconds_or_more_is_accepted(env, timeout):
    from ws.bootstrap import card_gate_problems

    gates = _registered_gates()
    for entry in gates["hooks"]["PreToolUse"]:
        entry["hooks"][0]["timeout"] = timeout
    _write_settings(env.settings, gates)

    assert card_gate_problems(env.settings) == []
    assert _setup(env).needs == []


@pytest.mark.parametrize("filename", ["settings.json", "settings.local.json"])
def test_disable_all_hooks_is_a_problem_in_either_settings_file(env, filename):
    from ws.bootstrap import card_gate_problems

    gates = _registered_gates()
    if filename == "settings.json":
        gates["disableAllHooks"] = True
    else:
        _write_settings(env.settings.with_name(filename), {"disableAllHooks": True})
    _write_settings(env.settings, gates)

    [problem] = card_gate_problems(env.settings)
    [need] = _setup(env).needs

    assert "disableAllHooks" in problem
    assert filename in problem
    assert "disableAllHooks" in need
    assert filename in need


@pytest.mark.parametrize("value", [False, "true", None])
def test_disable_all_hooks_that_is_not_true_is_fine(env, value):
    from ws.bootstrap import card_gate_problems

    _write_settings(env.settings, _registered_gates())
    _write_settings(env.settings.with_name("settings.local.json"), {"disableAllHooks": value})

    assert card_gate_problems(env.settings) == []


def test_an_unreadable_local_settings_file_is_ignored(env):
    from ws.bootstrap import card_gate_problems

    _write_settings(env.settings, _registered_gates())
    env.settings.with_name("settings.local.json").write_text("{nope", encoding="utf-8")

    assert card_gate_problems(env.settings) == []


def _catalog_in_repo(env: Env, servers: dict) -> None:
    path = env.repo / "hooks" / "gate" / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "servers": servers}), encoding="utf-8")


def _mcp_needs(result: SetupResult) -> list[str]:
    return [need for need in result.needs if need.startswith("MCP servers the approval gate")]


def test_setup_warns_about_configured_mcp_servers_missing_from_the_catalog(env, tmp_path):
    _catalog_in_repo(env, {"github": {"pass": [], "ask": []}})
    claude = _github_server()
    claude["mcpServers"]["zeta-tool"] = {"command": "x", "args": ["never-printed"]}
    claude["claudeAiMcpEverConnected"] = ["claude.ai Some Service"]
    _write_claude_json(claude)

    result = _setup(env, check=True)

    assert _mcp_needs(result) == [
        "MCP servers the approval gate does not know: claude_ai_Some_Service, zeta-tool. "
        "Every call of theirs asks, reads included, until their tools are classified: "
        "run `ws gate catalog`."
    ]
    assert "never-printed" not in "".join(result.needs)


def test_setup_finds_the_servers_of_enabled_plugins(env, tmp_path, monkeypatch):
    _catalog_in_repo(env, {"github": {"pass": [], "ask": []}})
    plugins = tmp_path / "plugins"
    install = plugins / "cache" / "market" / "demo"
    (install).mkdir(parents=True)
    (install / ".mcp.json").write_text('{"demo-srv": {"url": "u"}}', encoding="utf-8")
    (plugins / "installed_plugins.json").write_text(
        json.dumps({"plugins": {"demo@market": [{"installPath": str(install)}]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("WS_CLAUDE_PLUGINS_DIR", str(plugins))
    _write_settings(env.settings, {**_registered_gates(), "enabledPlugins": {"demo@market": True}})

    assert "plugin_demo_demo-srv" in _mcp_needs(_setup(env))[0]


def test_setup_is_quiet_when_every_server_is_in_the_catalog(env):
    _catalog_in_repo(env, {"github": {"pass": [], "ask": []}})

    assert _mcp_needs(_setup(env)) == []


def test_setup_without_a_catalog_in_the_repo_skips_the_mcp_check(env):
    assert _mcp_needs(_setup(env)) == []


QUESTION = "Atualizar a cópia protegida dos hooks? [s/N] "
REVIEW = "run ws setup in your own terminal to review and apply"


def _ask_log(monkeypatch, answer: str) -> list[str]:
    asked: list[str] = []

    def reply(prompt: str = "") -> str:
        asked.append(prompt)
        return answer

    monkeypatch.setattr("builtins.input", reply)
    return asked


def _forbid_questions(monkeypatch) -> None:
    def refuse(prompt: str = "") -> str:
        raise AssertionError("setup asked a question")

    monkeypatch.setattr("builtins.input", refuse)


def _edit_in_repo(env: Env, rel: str, data: bytes) -> None:
    (env.repo / "hooks" / rel).write_bytes(data)


def test_an_agent_never_writes_the_copy_and_says_how_to_apply_it(env, _hooks_dir, monkeypatch):
    _copy_in_place(env)
    _forbid_questions(monkeypatch)
    _edit_in_repo(env, "gate/rules.py", b"X = 2\n")
    manifest = (_hooks_dir / "manifest.json").read_bytes()

    result = _setup(env, by_hand=False)

    assert (_hooks_dir / "gate" / "rules.py").read_bytes() == b"X = 1\n"
    assert (_hooks_dir / "manifest.json").read_bytes() == manifest
    [need] = [need for need in result.needs if need.startswith("hooks copy")]
    assert "gate/rules.py" in need
    assert need.endswith(REVIEW)
    assert not [line for line in result.fixed if "gate/rules.py" in line]


def test_an_agent_does_not_create_the_copy_either(env, _hooks_dir, monkeypatch):
    _fake_hooks(env.repo)
    _forbid_questions(monkeypatch)

    result = _setup(env, by_hand=False)

    assert not _hooks_dir.exists()
    assert any(need.endswith(REVIEW) for need in result.needs)


def test_an_agent_still_fixes_the_rest_of_setup(env, _hooks_dir, monkeypatch):
    _copy_in_place(env)
    _edit_in_repo(env, "gate/rules.py", b"X = 2\n")
    (_hooks_dir / "approval_gate.py").chmod(0o644)
    _plant(_hooks_dir / "sitecustomize.py")
    _git(env.repo, "config", "core.hooksPath", "elsewhere")

    result = _setup(env, by_hand=False)

    assert _mode(_hooks_dir / "approval_gate.py") == 0o444
    assert not (_hooks_dir / "sitecustomize.py").exists()
    assert _git(env.repo, "config", "core.hooksPath").strip() == ".githooks"
    assert any("gate/rules.py" in need for need in result.needs)


def test_without_by_hand_setup_asks_the_terminal_test(env, _hooks_dir, monkeypatch):
    _copy_in_place(env)
    _edit_in_repo(env, "gate/rules.py", b"X = 2\n")
    monkeypatch.setattr(bootstrap.humans, "by_hand", lambda: False)

    result = run_setup(env.repo, env.config, env.skills_target, env.settings)

    assert (_hooks_dir / "gate" / "rules.py").read_bytes() == b"X = 1\n"
    assert any(need.endswith(REVIEW) for need in result.needs)


def test_by_hand_prints_the_diff_of_each_changed_file_then_asks(
    env, _hooks_dir, monkeypatch, capsys
):
    _copy_in_place(env)
    asked = _ask_log(monkeypatch, "s")
    _edit_in_repo(env, "approval_gate.py", b"print('gate v2')\n")
    _edit_in_repo(env, "gate/rules.py", b"X = 1\nY = 2\n")
    capsys.readouterr()

    _setup(env)

    out = capsys.readouterr().out
    assert f"Cópia protegida dos hooks em {_hooks_dir}: 2 arquivo(s) mudam." in out
    assert "== approval_gate.py (desatualizado)" in out
    assert "--- copia/approval_gate.py\n+++ repo/approval_gate.py" in out
    assert "-print('gate')\n+print('gate v2')" in out
    assert "== gate/rules.py (desatualizado)" in out
    assert "+Y = 2" in out
    assert "block_hook_bypass.py" not in out
    assert asked == ["\n" + QUESTION]
    assert (_hooks_dir / "approval_gate.py").read_bytes() == b"print('gate v2')\n"


@pytest.mark.parametrize("answer", ["s", "sim", " SIM "])
def test_by_hand_writes_only_after_a_yes(env, _hooks_dir, monkeypatch, answer):
    _copy_in_place(env)
    _ask_log(monkeypatch, answer)
    _edit_in_repo(env, "gate/rules.py", b"X = 2\n")

    result = _setup(env)

    assert result.needs == []
    assert (_hooks_dir / "gate" / "rules.py").read_bytes() == b"X = 2\n"
    assert _setup(env) == SetupResult()


@pytest.mark.parametrize("answer", ["", "n", "não", "talvez"])
def test_by_hand_without_a_yes_leaves_the_copy_and_the_manifest(
    env, _hooks_dir, monkeypatch, answer
):
    _copy_in_place(env)
    _ask_log(monkeypatch, answer)
    _edit_in_repo(env, "gate/rules.py", b"X = 2\n")
    manifest = (_hooks_dir / "manifest.json").read_bytes()

    result = _setup(env)

    assert (_hooks_dir / "gate" / "rules.py").read_bytes() == b"X = 1\n"
    assert (_hooks_dir / "manifest.json").read_bytes() == manifest
    assert "hooks copy: not updated, the change was not approved" in result.needs


def test_an_interrupted_question_is_a_no(env, _hooks_dir, monkeypatch):
    _copy_in_place(env)
    _edit_in_repo(env, "gate/rules.py", b"X = 2\n")

    def interrupt(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", interrupt)

    _setup(env)

    assert (_hooks_dir / "gate" / "rules.py").read_bytes() == b"X = 1\n"


def test_the_catalog_diff_is_the_pretty_json(env, _hooks_dir, monkeypatch, capsys):
    _copy_in_place(env)
    _edit_in_repo(env, "gate/catalog.json", b'{"a":1,"servers":{"x":{"pass":["t"]}}}\n')
    capsys.readouterr()

    _setup(env)

    out = capsys.readouterr().out
    assert '-  "a": 1\n+  "a": 1,\n+  "servers": {\n+    "x": {\n' in out
    assert '{"a":1' not in out


def test_control_characters_of_the_repo_file_are_shown_escaped(env, _hooks_dir, capsys):
    _copy_in_place(env)
    _edit_in_repo(env, "gate/rules.py", b"X = 1  # \x1b[2K\x1b[1A\r\x07ok\n")
    capsys.readouterr()

    _setup(env)

    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "\r" not in out
    assert "\x07" not in out
    assert "\\x1b[2K\\x1b[1A\\x0d\\x07ok" in out


def test_nothing_to_change_asks_nothing(env, _hooks_dir, monkeypatch):
    _copy_in_place(env)
    _forbid_questions(monkeypatch)

    assert _setup(env) == SetupResult()


def test_check_never_asks_and_never_writes(env, _hooks_dir, monkeypatch):
    _copy_in_place(env)
    _forbid_questions(monkeypatch)
    _edit_in_repo(env, "gate/rules.py", b"X = 2\n")

    check = _setup(env, check=True)

    assert check.fixed[0] == "hooks copy gate/rules.py: stale; restore it from the repo"
    assert (_hooks_dir / "gate" / "rules.py").read_bytes() == b"X = 1\n"


def test_a_first_copy_by_hand_shows_every_file_as_new(env, _hooks_dir, capsys):
    _fake_hooks(env.repo)

    result = _setup(env)

    out = capsys.readouterr().out
    assert f"{_hooks_dir}: {len(COPIED)} arquivo(s) mudam." in out
    assert "== gate/rules.py (novo)" in out
    assert "+X = 1" in out
    assert result.needs == []
    assert (_hooks_dir / "gate" / "rules.py").is_file()


def _project_settings(env: Env, name: str, content: str = '{"disableAllHooks": true}') -> Path:
    path = env.repo / ".claude" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize("name", ["settings.json", "settings.local.json"])
def test_setup_reports_disable_all_hooks_in_the_project_settings(env, name):
    path = _project_settings(env, name)

    result = _setup(env, check=True)

    [need] = [need for need in result.needs if "disableAllHooks" in need]
    assert str(path) in need


def test_project_settings_that_keep_the_hooks_on_are_fine(env):
    _project_settings(env, "settings.json", '{"disableAllHooks": false}')
    _project_settings(env, "settings.local.json", "{not json")

    assert not [n for n in _setup(env, check=True).needs if "disableAllHooks" in n]


@pytest.mark.parametrize("name", ["settings.json", "settings.local.json"])
def test_card_gate_problems_report_disable_all_hooks_in_the_project_settings(
    env, monkeypatch, name
):
    monkeypatch.setenv("WS_REPO_ROOT", str(env.repo))
    assert bootstrap.card_gate_problems(env.settings) == []
    path = _project_settings(env, name)

    [problem] = bootstrap.card_gate_problems(env.settings)

    assert "disableAllHooks" in problem
    assert str(path) in problem


def test_release_gate_problems_name_what_is_missing(env, tmp_path, monkeypatch):
    from ws.bootstrap import RELEASE_ASK_RULES, release_gate_problems

    monkeypatch.setenv("WS_REPO_ROOT", str(env.repo))
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    problems = release_gate_problems(settings)
    assert len(problems) == 3
    for rule in RELEASE_ASK_RULES:
        assert any(rule in problem for problem in problems)
    assert any(GATE_SCRIPT in problem for problem in problems)

    settings.write_text(json.dumps(_registered_gates()), encoding="utf-8")
    assert release_gate_problems(settings) == []


def test_setup_prints_the_release_ask_rules(env):
    _write_settings(env.settings, {})

    _, block = _needs_block(_setup(env))

    assert "Bash(ws release publish:*)" in block["permissions"]["ask"]
    assert "Bash(ws release move:*)" in block["permissions"]["ask"]


def test_observe_gate_problems_name_what_is_missing(env, tmp_path, monkeypatch):
    from ws.bootstrap import OBSERVE_ASK_RULES, observe_gate_problems

    assert OBSERVE_ASK_RULES == ("Bash(ws observe run:*)",)
    monkeypatch.setenv("WS_REPO_ROOT", str(env.repo))
    settings = tmp_path / "settings.json"
    assert "not found" in observe_gate_problems(settings)[0]

    settings.write_text("{}", encoding="utf-8")
    problems = observe_gate_problems(settings)
    assert len(problems) == 2
    assert any("Bash(ws observe run:*)" in problem for problem in problems)
    assert any(GATE_SCRIPT in problem for problem in problems)

    gates = _registered_gates()
    gates["permissions"]["ask"].remove("Bash(ws observe run:*)")
    settings.write_text(json.dumps(gates), encoding="utf-8")
    [problem] = observe_gate_problems(settings)
    assert "Bash(ws observe run:*)" in problem

    settings.write_text(json.dumps(_registered_gates()), encoding="utf-8")
    assert observe_gate_problems(settings) == []


def test_setup_prints_the_observe_ask_rule(env):
    _write_settings(env.settings, {})

    _, block = _needs_block(_setup(env))

    assert "Bash(ws observe run:*)" in block["permissions"]["ask"]
    assert "Bash(ws observe run:*)" in ASK_RULES


def test_session_hooks_printed_under_their_events(env):
    _write_settings(env.settings, {"theme": "dark"})

    _, block = _needs_block(_setup(env))

    hooks = block["hooks"]
    assert list(hooks) == ["PreToolUse", "UserPromptSubmit", "SessionStart"]
    assert [hook["hooks"][0]["timeout"] for hook in hooks["PreToolUse"]] == [30, 30, 30]
    watch, activity = hooks["UserPromptSubmit"]
    assert "matcher" not in watch and "matcher" not in activity
    assert watch["hooks"] == [
        {"type": "command", "command": _copy_command(WATCH_SCRIPT), "timeout": 10}
    ]
    assert activity["hooks"] == [
        {"type": "command", "command": _copy_command(TIME_SCRIPT), "timeout": 10}
    ]
    [pointer] = hooks["SessionStart"]
    assert pointer["matcher"] == POINTER_MATCHER
    assert pointer["hooks"] == [
        {"type": "command", "command": _copy_command(POINTER_SCRIPT), "timeout": 10}
    ]


def test_the_block_holds_only_the_missing_session_hook(env):
    gates = _registered_gates()
    del gates["hooks"]["SessionStart"]
    _write_settings(env.settings, gates)

    _, block = _needs_block(_setup(env))

    assert list(block) == ["hooks"]
    assert list(block["hooks"]) == ["SessionStart"]


def test_session_hooks_registered_are_recognized(env):
    _write_settings(env.settings, _registered_gates())

    assert _setup(env).needs == []


def test_a_session_hook_under_the_wrong_event_is_not_registered(env):
    gates = _registered_gates()
    gates["hooks"]["PreToolUse"].append(_hook_entry(WATCH_SCRIPT, None))
    del gates["hooks"]["UserPromptSubmit"]
    _write_settings(env.settings, gates)

    _, block = _needs_block(_setup(env))

    assert list(block["hooks"]) == ["UserPromptSubmit"]


@pytest.mark.parametrize("matcher", ["startup", "startup|clear", "clear|compact", "resume"])
def test_session_start_matcher_must_cover_probes(env, matcher):
    gates = _registered_gates()
    gates["hooks"]["SessionStart"] = [_hook_entry(POINTER_SCRIPT, matcher)]
    _write_settings(env.settings, gates)

    result = _setup(env)

    assert any("does not cover" in need for need in result.needs)
    _, block = _needs_block(result)
    assert list(block["hooks"]) == ["SessionStart"]


@pytest.mark.parametrize("matcher", [None, "", "*", "startup|clear|compact|resume", ".*"])
def test_session_start_matcher_that_covers_the_probes_is_accepted(env, matcher):
    gates = _registered_gates()
    gates["hooks"]["SessionStart"] = [_hook_entry(POINTER_SCRIPT, matcher)]
    _write_settings(env.settings, gates)

    assert _setup(env).needs == []


@pytest.mark.parametrize("matcher", [None, "", "whatever"])
def test_user_prompt_submit_needs_no_matcher(env, matcher):
    gates = _registered_gates()
    gates["hooks"]["UserPromptSubmit"] = [
        _hook_entry(WATCH_SCRIPT, matcher),
        _hook_entry(TIME_SCRIPT, matcher),
    ]
    _write_settings(env.settings, gates)

    assert _setup(env).needs == []


SESSION_HOOKS = [
    (WATCH_SCRIPT, "UserPromptSubmit"),
    (TIME_SCRIPT, "UserPromptSubmit"),
    (POINTER_SCRIPT, "SessionStart"),
]


@pytest.mark.parametrize("script,event", SESSION_HOOKS)
def test_session_hook_pointing_at_repo_is_stale(env, script, event):
    gates = _registered_gates()
    repo_path = env.repo / "hooks" / script
    [entry] = [item for item in gates["hooks"][event] if script in item["hooks"][0]["command"]]
    entry["hooks"][0]["command"] = f'python3 -I -B "{repo_path}"'
    _write_settings(env.settings, gates)

    result = _setup(env)

    assert any("is replaced by" in need and script in need for need in result.needs)
    _, block = _needs_block(result)
    assert list(block["hooks"]) == [event]
    [printed] = block["hooks"][event]
    assert printed["hooks"][0]["command"] == _copy_command(script)


@pytest.mark.parametrize("script,event", SESSION_HOOKS)
def test_a_short_timeout_on_a_session_hook_is_a_problem(env, script, event):
    gates = _registered_gates()
    [entry] = [item for item in gates["hooks"][event] if script in item["hooks"][0]["command"]]
    entry["hooks"][0]["timeout"] = 5
    _write_settings(env.settings, gates)

    result = _setup(env)

    assert any("timeout" in need and script in need for need in result.needs)
    _, block = _needs_block(result)
    [printed] = block["hooks"][event]
    assert printed["hooks"][0]["timeout"] == 10
    assert script in printed["hooks"][0]["command"]


def test_card_apply_does_not_depend_on_the_session_hooks(tmp_path):
    from ws.bootstrap import card_gate_problems

    gates = _registered_gates()
    del gates["hooks"]["UserPromptSubmit"], gates["hooks"]["SessionStart"]
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(gates), encoding="utf-8")

    assert card_gate_problems(settings) == []


def test_copy_includes_the_session_hooks(env, _hooks_dir):
    _fake_hooks(env.repo)
    for script in (WATCH_SCRIPT, POINTER_SCRIPT, TIME_SCRIPT):
        (env.repo / "hooks" / script).write_bytes(f"print('{script}')\n".encode())

    _setup(env)

    for script in (WATCH_SCRIPT, POINTER_SCRIPT, TIME_SCRIPT):
        assert script in _copy_files(_hooks_dir)
    manifest = json.loads((_hooks_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest[WATCH_SCRIPT] == _sha(f"print('{WATCH_SCRIPT}')\n".encode())
    assert manifest[TIME_SCRIPT] == _sha(f"print('{TIME_SCRIPT}')\n".encode())
    assert _mode(_hooks_dir / POINTER_SCRIPT) == 0o444


def test_a_missing_time_hook_is_the_only_thing_printed(env):
    gates = _registered_gates()
    gates["hooks"]["UserPromptSubmit"] = [_hook_entry(WATCH_SCRIPT, None)]
    _write_settings(env.settings, gates)

    _, block = _needs_block(_setup(env))

    assert list(block) == ["hooks"]
    assert block["hooks"] == {
        "UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": _copy_command(TIME_SCRIPT), "timeout": 10}]}
        ]
    }
