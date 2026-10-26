"""Idempotent setup of a workspace clone: git hooks path, skill links, private config and gates."""

import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path

from ws.config import claude_settings_path

GITHOOKS_DIR = ".githooks"
HOOK_SCRIPTS = ("hooks/block_co_authored_by.py", "hooks/block_hook_bypass.py")
DENY_RULE = "Read(~/.config/workspace/credentials)"


def run_setup(
    repo: Path, config: Path, skills_target: Path, settings: Path | None = None
) -> list[str]:
    """Wire the clone and return the problems found; an empty list means ok."""
    if settings is None:
        settings = claude_settings_path()
    hooks_problems = _set_hooks_path(repo)
    if not hooks_problems:
        hooks_problems = _check_git_hooks(repo)
    return [
        *hooks_problems,
        *_link_skills(repo, skills_target),
        *_check_config(config),
        *_check_claude_gates(repo, settings),
    ]


def _set_hooks_path(repo: Path) -> list[str]:
    command = ["git", "-C", str(repo), "config", "core.hooksPath", GITHOOKS_DIR]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except OSError as error:
        return [f"git hooks path: could not run git: {error}"]
    if result.returncode != 0:
        return [f"git hooks path: {result.stderr.strip()}"]
    return []


def _check_git_hooks(repo: Path) -> list[str]:
    """Check what git will really use: the effective hooks path and the executable bits."""
    problems = []
    command = ["git", "-C", str(repo), "config", "--get", "--type=path", "core.hooksPath"]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except OSError as error:
        return [f"git hooks path: could not run git: {error}"]
    configured = result.stdout.strip()
    hooks = repo / GITHOOKS_DIR
    if result.returncode != 0 or not configured:
        problems.append(f"git hooks path: core.hooksPath is not set in {repo}")
    elif (repo / configured).resolve() != hooks.resolve():
        problems.append(
            f"git hooks path: core.hooksPath resolves to {(repo / configured).resolve()}, "
            f"not {hooks.resolve()}; something overrides the setting made here "
            "(see: git config --show-origin --get-all core.hooksPath)"
        )
    if hooks.is_dir():
        for hook in sorted(path for path in hooks.iterdir() if path.is_file()):
            if not os.access(hook, os.X_OK):
                problems.append(f"{hook} is not executable, so git skips it; run: chmod +x {hook}")
    return problems


def _link_skills(repo: Path, skills_target: Path) -> list[str]:
    skills_target.mkdir(parents=True, exist_ok=True)
    source = repo / "skills"
    if not source.is_dir():
        return []
    problems = []
    for skill in sorted(path for path in source.iterdir() if path.is_dir()):
        link = skills_target / skill.name
        if not (link.is_symlink() or link.exists()):
            link.symlink_to(skill.resolve(), target_is_directory=True)
        elif not (link.is_symlink() and link.resolve() == skill.resolve()):
            problems.append(f"skill {skill.name}: {link} exists and is not a link to this repo")
    return problems


def _mode_problem(path: Path, expected: int) -> list[str]:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode == expected:
        return []
    return [f"{path} has mode {mode:04o}; run: chmod {expected:o} {path}"]


def _check_config(config: Path) -> list[str]:
    config.mkdir(mode=0o700, parents=True, exist_ok=True)
    problems = _mode_problem(config, 0o700)

    names = config / "names.toml"
    if names.is_file():
        problems += _mode_problem(names, 0o600)
    else:
        problems.append(f"{names} is missing; the secrets hook fails closed without it")

    credentials = config / "credentials"
    if credentials.exists():
        problems += _mode_problem(credentials, 0o600)

    private = config / "private"
    if not private.exists():
        private.mkdir(mode=0o700)
        private.chmod(0o700)
    elif private.is_dir():
        problems += _mode_problem(private, 0o700)
    else:
        problems.append(f"{private} exists and is not a folder")
    return problems


def _hook_entry(repo: Path, script: str) -> dict:
    command = f'python3 -I "{repo.absolute() / script}"'
    return {"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}


def _hook_gate(repo: Path, scripts: tuple[str, ...] = HOOK_SCRIPTS) -> dict:
    return {"hooks": {"PreToolUse": [_hook_entry(repo, script) for script in scripts]}}


def _deny_gate() -> dict:
    return {"permissions": {"deny": [DENY_RULE]}}


def _problem_with_json(message: str, snippet: dict) -> str:
    return f"{message}\n{textwrap.indent(json.dumps(snippet, indent=2), '  ')}"


def _check_claude_gates(repo: Path, settings_path: Path) -> list[str]:
    try:
        raw = settings_path.read_bytes()
    except FileNotFoundError:
        both = {**_hook_gate(repo), **_deny_gate()}
        return [
            _problem_with_json(f"Claude settings {settings_path} not found; create it with:", both)
        ]
    except OSError as error:
        return [f"Claude settings {settings_path} could not be read: {error}"]
    try:
        settings = json.loads(raw)
    except ValueError:
        settings = None
    if not isinstance(settings, dict):
        return [f"Claude settings {settings_path} is not a valid JSON object; fix it first"]

    problems = []
    for script in HOOK_SCRIPTS:
        if not _has_hook_gate(settings, script):
            message = f"Claude Code gate missing in {settings_path}: add this PreToolUse hook"
            problems.append(_problem_with_json(message, _hook_gate(repo, (script,))))
    if not _has_deny_rule(settings):
        message = f"Claude Code gate missing in {settings_path}: add this deny rule"
        problems.append(_problem_with_json(message, _deny_gate()))
    return problems


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _has_hook_gate(settings: dict, script: str) -> bool:
    entries = _as_list(_as_dict(settings.get("hooks")).get("PreToolUse"))
    for entry in entries:
        for hook in _as_list(_as_dict(entry).get("hooks")):
            command = _as_dict(hook).get("command")
            if isinstance(command, str) and script in command:
                return True
    return False


def _has_deny_rule(settings: dict) -> bool:
    return DENY_RULE in _as_list(_as_dict(settings.get("permissions")).get("deny"))
