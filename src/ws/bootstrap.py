"""Idempotent setup of a workspace clone: it fixes what it can by itself and reports the rest.

It fixes: the git hooks path, the executable bit of the four hooks, the skill links, the folders
and modes of the private config, and the common-word dictionaries (downloaded without root). It
reports, as "needs you": what only the user can settle (a missing `names.toml`, a skill link that
points elsewhere) and the Claude Code gates, because ws never writes `~/.claude/settings.json`: it
prints one JSON block that Claude applies after the user approves.

With `check` nothing is changed and the network is not used; the changes that setup would make are
listed instead.
"""

import json
import os
import stat
import subprocess
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ws import dictionary
from ws.config import claude_settings_path

GITHOOKS_DIR = ".githooks"
HOOK_NAMES = ("pre-commit", "pre-merge-commit", "commit-msg", "pre-push")
HOOK_SCRIPTS = ("hooks/block_co_authored_by.py", "hooks/block_hook_bypass.py")
DENY_RULE = "Read(~/.config/workspace/credentials)"
PACKAGES = " and ".join(source.package for source in dictionary.SOURCES)


@dataclass
class SetupResult:
    """`fixed`: the changes made (with `check`, those setup would make); `needs`: what is left."""

    fixed: list[str] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)


class _Setup:
    def __init__(self, apply: bool):
        self.apply = apply
        self.result = SetupResult()

    def fix(self, message: str, action: Callable[[], None], failure: str) -> bool:
        """Make a change and record it; with `check`, only record it. False when it failed."""
        if self.apply:
            try:
                action()
            except OSError as error:
                self.result.needs.append(f"{failure}: {error}")
                return False
        self.result.fixed.append(message)
        return True

    def need(self, message: str) -> None:
        self.result.needs.append(message)


def run_setup(
    repo: Path,
    config: Path,
    skills_target: Path,
    settings: Path | None = None,
    *,
    check: bool = False,
) -> SetupResult:
    """Wire the clone, fix what can be fixed and return what was done and what is left."""
    if settings is None:
        settings = claude_settings_path()
    setup = _Setup(apply=not check)
    hooks_path_ok = _set_hooks_path(setup, repo)
    _fix_hook_bits(setup, repo)
    if hooks_path_ok:
        _check_hooks_path(setup, repo)
    _link_skills(setup, repo, skills_target)
    _check_config(setup, config)
    _install_dictionaries(setup)
    _check_claude_gates(setup, repo, settings)
    return setup.result


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _set_git_hooks_path(repo: Path) -> None:
    result = _git(repo, "config", "core.hooksPath", GITHOOKS_DIR)
    if result.returncode != 0:
        raise OSError(result.stderr.strip())


def _set_hooks_path(setup: _Setup, repo: Path) -> bool:
    """Point the clone at `.githooks`; True when it does now, so the effective path can be read."""
    try:
        probe = _git(repo, "rev-parse", "--git-dir")
        if probe.returncode != 0:
            setup.need(f"git hooks path: {probe.stderr.strip()}")
            return False
        current = _git(repo, "config", "--local", "--get", "core.hooksPath").stdout.strip()
        if current == GITHOOKS_DIR:
            return True
        done = setup.fix(
            f"git hooks path: set core.hooksPath to {GITHOOKS_DIR} in {repo}",
            lambda: _set_git_hooks_path(repo),
            "git hooks path",
        )
        return (
            done and setup.apply
        )  # with check nothing was set, so the effective path says nothing
    except OSError as error:
        setup.need(f"git hooks path: could not run git: {error}")
        return False


def _fix_hook_bits(setup: _Setup, repo: Path) -> None:
    """Git skips a hook that is not executable, so the four known hooks get `chmod +x`."""
    for name in HOOK_NAMES:
        hook = repo / GITHOOKS_DIR / name
        if hook.is_file() and not os.access(hook, os.X_OK):
            mode = stat.S_IMODE(hook.stat().st_mode)
            setup.fix(
                f"hook {hook}: chmod +x",
                lambda hook=hook, mode=mode: hook.chmod(mode | 0o111),
                f"hook {hook} is not executable, so git skips it, and chmod +x failed",
            )


def _check_hooks_path(setup: _Setup, repo: Path) -> None:
    """Check what git will really use: the effective hooks path, which something may override."""
    command = ["config", "--get", "--type=path", "core.hooksPath"]
    try:
        result = _git(repo, *command)
    except OSError as error:
        setup.need(f"git hooks path: could not run git: {error}")
        return
    configured = result.stdout.strip()
    hooks = repo / GITHOOKS_DIR
    if result.returncode != 0 or not configured:
        setup.need(f"git hooks path: core.hooksPath is not set in {repo}")
    elif (repo / configured).resolve() != hooks.resolve():
        setup.need(
            f"git hooks path: core.hooksPath resolves to {(repo / configured).resolve()}, "
            f"not {hooks.resolve()}; something overrides the setting made here "
            "(see: git config --show-origin --get-all core.hooksPath)"
        )


def _link(link: Path, skill: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(skill.resolve(), target_is_directory=True)


def _link_skills(setup: _Setup, repo: Path, skills_target: Path) -> None:
    source = repo / "skills"
    if not source.is_dir():
        return
    for skill in sorted(path for path in source.iterdir() if path.is_dir()):
        link = skills_target / skill.name
        if not (link.is_symlink() or link.exists()):
            setup.fix(
                f"skill {skill.name}: link {link}",
                lambda link=link, skill=skill: _link(link, skill),
                f"skill {skill.name}: could not link {link}",
            )
        elif not (link.is_symlink() and link.resolve() == skill.resolve()):
            setup.need(f"skill {skill.name}: {link} exists and is not a link to this repo")


def _make_private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def _fix_mode(setup: _Setup, path: Path, expected: int, label: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != expected:
        setup.fix(
            f"{label} {path}: chmod {expected:o} (from {mode:04o})",
            lambda: path.chmod(expected),
            f"{path} has mode {mode:04o} and chmod {expected:o} failed",
        )


def _check_config(setup: _Setup, config: Path) -> None:
    if config.exists():
        _fix_mode(setup, config, 0o700, "config folder")
    else:
        setup.fix(
            f"config folder {config}: create with mode 700",
            lambda: _make_private_dir(config),
            f"could not create {config}",
        )

    names = config / "names.toml"
    if names.is_file():
        _fix_mode(setup, names, 0o600, "names table")
    else:
        setup.need(f"{names} is missing; the secrets hook fails closed without it")

    settings_file = config / "config.toml"
    if not settings_file.is_file():
        setup.need(f'{settings_file} is missing; see "Local config" in README.md')

    credentials = config / "credentials"
    if credentials.exists():
        _fix_mode(setup, credentials, 0o600, "credentials")

    private = config / "private"
    if not private.exists():
        setup.fix(
            f"private folder {private}: create with mode 700",
            lambda: _make_private_dir(private),
            f"could not create {private}",
        )
    elif private.is_dir():
        _fix_mode(setup, private, 0o700, "private folder")
    else:
        setup.need(f"{private} exists and is not a folder")


def _install_dictionaries(setup: _Setup) -> None:
    """The common-word dictionaries, downloaded without root when neither place has them."""
    if not dictionary.missing():
        return
    target = dictionary.data_path()
    if not setup.apply:
        setup.result.fixed.append(f"dictionaries: download {PACKAGES} into {target}")
        return
    try:
        dictionary.install()
    except dictionary.InstallError as error:
        setup.need(
            f"dictionaries not installed ({error}); the new-word check is stricter without them; "
            f"run: {dictionary.MANUAL_COMMAND}"
        )
        return
    setup.result.fixed.append(f"dictionaries: download {PACKAGES} into {target}")


def _hook_entry(repo: Path, script: str) -> dict:
    command = f'python3 -I "{repo.absolute() / script}"'
    return {"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}


def _hook_gate(repo: Path, scripts: tuple[str, ...] = HOOK_SCRIPTS) -> dict:
    return {"hooks": {"PreToolUse": [_hook_entry(repo, script) for script in scripts]}}


def _deny_gate() -> dict:
    return {"permissions": {"deny": [DENY_RULE]}}


def _gates_needed(message: str, snippet: dict) -> str:
    return f"{message}\n{textwrap.indent(json.dumps(snippet, indent=2), '  ')}"


def _check_claude_gates(setup: _Setup, repo: Path, settings_path: Path) -> None:
    """ws never writes the Claude settings: it asks for one block with everything missing."""
    approval = "ws never writes that file; Claude applies this block after you approve:"
    try:
        raw = settings_path.read_bytes()
    except FileNotFoundError:
        both = {**_hook_gate(repo), **_deny_gate()}
        message = f"Claude settings {settings_path} not found. {approval}"
        setup.need(_gates_needed(message, both))
        return
    except OSError as error:
        setup.need(f"Claude settings {settings_path} could not be read: {error}")
        return
    try:
        settings = json.loads(raw)
    except ValueError:
        settings = None
    if not isinstance(settings, dict):
        setup.need(f"Claude settings {settings_path} is not a valid JSON object; fix it first")
        return

    missing_scripts = tuple(s for s in HOOK_SCRIPTS if not _has_hook_gate(settings, s))
    block: dict = _hook_gate(repo, missing_scripts) if missing_scripts else {}
    if not _has_deny_rule(settings):
        block.update(_deny_gate())
    if block:
        message = f"Claude Code gates missing in {settings_path}. {approval}"
        setup.need(_gates_needed(message, block))


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
