"""Idempotent setup of a workspace clone: it fixes what it can by itself and reports the rest.

It fixes: the git hooks path, the executable bit of the four hooks, the skill links, the folders
and modes of the private config, the protected copy of the Claude Code hooks (read-only files
and a manifest of SHA-256 sums) and the common-word dictionaries (downloaded without root). It
reports, as "needs you": what only the user can settle (a missing `names.toml`, a skill link that
points elsewhere) and the Claude Code gates, because ws never writes `~/.claude/settings.json`: it
prints one JSON block that Claude applies after the user approves.

With `check` nothing is changed and the network is not used; the changes that setup would make are
listed instead.
"""

import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import textwrap
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePath

from ws import dictionary
from ws.config import claude_hooks_dir, claude_settings_path

GITHOOKS_DIR = ".githooks"
HOOK_NAMES = ("pre-commit", "pre-merge-commit", "commit-msg", "pre-push")
CARD_ASK_RULE = "Bash(ws card apply:*)"
HOOKS_SOURCE = "hooks"
HOOKS_MANIFEST = "manifest.json"
HOOKS_COPY_GLOBS = ("*.py", "gate/*.py", "gate/*.json")
HOOKS_NOT_COPIED = ("ask_card_apply.py",)
GATE_SCRIPT = "approval_gate.py"
GATE_MATCHER = "Bash|mcp__.*"
GATE_PROBE_TOOLS = ("Bash", "mcp__plugin_github_github__push_files")
HOOK_REGISTRATIONS = (
    (GATE_SCRIPT, GATE_MATCHER, GATE_PROBE_TOOLS),
    ("block_co_authored_by.py", "Bash", ("Bash",)),
    ("block_hook_bypass.py", "Bash", ("Bash",)),
)
DENY_RULE = "Read(~/.config/workspace/credentials)"
ATLASSIAN_SERVERS = ("claude_ai_Atlassian_MCP", "plugin_productivity_atlassian")
ATLASSIAN_WRITE_TOOLS = (
    "createJiraIssue",
    "editJiraIssue",
    "transitionJiraIssue",
    "addCommentToJiraIssue",
    "addOrEditJiraIssueComment",
    "addWorklogToJiraIssue",
    "createIssueLink",
    "executeWrite",
    "executeDestructive",
)
GITHUB_WRITE_TOOLS = (
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
)
GITKRAKEN_WRITE_TOOLS = (
    "git_push",
    "issues_add_comment",
    "issues_create",
    "pull_request_create",
    "pull_request_create_review",
)
ASK_RULES = (
    CARD_ASK_RULE,
    *(f"mcp__{server}__{tool}" for server in ATLASSIAN_SERVERS for tool in ATLASSIAN_WRITE_TOOLS),
    *(f"mcp__plugin_github_github__{tool}" for tool in GITHUB_WRITE_TOOLS),
    *(f"mcp__plugin_gitkraken_gitkraken__{tool}" for tool in GITKRAKEN_WRITE_TOOLS),
)
PACKAGES = " and ".join(source.package for source in dictionary.SOURCES)
SANDBOX_TOOLS = ("bwrap", "socat")


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
    hooks_dir: Path | None = None,
) -> SetupResult:
    """Wire the clone, fix what can be fixed and return what was done and what is left."""
    if settings is None:
        settings = claude_settings_path()
    if hooks_dir is None:
        hooks_dir = claude_hooks_dir()
    setup = _Setup(apply=not check)
    hooks_path_ok = _set_hooks_path(setup, repo)
    _fix_hook_bits(setup, repo)
    if hooks_path_ok:
        _check_hooks_path(setup, repo)
    _link_skills(setup, repo, skills_target)
    _check_config(setup, config)
    _check_sandbox_tools(setup)
    _install_dictionaries(setup)
    _sync_hooks_copy(setup, repo, hooks_dir)
    _check_claude_gates(setup, hooks_dir, settings)
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
    else:
        _check_gate_table(setup, settings_file)

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


def _check_sandbox_tools(setup: _Setup) -> None:
    """The evals run Claude inside bubblewrap and socat; ws itself does not need them."""
    missing = [tool for tool in SANDBOX_TOOLS if shutil.which(tool) is None]
    if missing:
        setup.need(
            f"sandbox tools missing ({', '.join(missing)}); run "
            "sudo apt-get install -y bubblewrap socat (only to run the evals)"
        )


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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hook_sources(repo: Path) -> dict[str, Path]:
    """The hook files to copy, by path relative to `hooks/`; the repo's other files stay out."""
    root = repo / HOOKS_SOURCE
    found: dict[str, Path] = {}
    for pattern in HOOKS_COPY_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and path.name not in HOOKS_NOT_COPIED:
                found[path.relative_to(root).as_posix()] = path
    return found


def _ensure_dir(path: Path) -> None:
    if path.exists():
        return
    _ensure_dir(path.parent)
    path.mkdir(mode=0o755)
    path.chmod(0o755)


def _write_read_only(target: Path, data: bytes) -> None:
    """Unlink and write, so a read-only file or a link is never written through."""
    _ensure_dir(target.parent)
    target.unlink(missing_ok=True)
    target.write_bytes(data)
    target.chmod(0o444)


def _write_manifest(hooks_dir: Path, expected: dict[str, str]) -> None:
    text = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    _write_read_only(hooks_dir / HOOKS_MANIFEST, text.encode("utf-8"))


def _write_copy(hooks_dir: Path, contents: dict[str, bytes], expected: dict[str, str]) -> None:
    for rel, data in contents.items():
        _write_read_only(hooks_dir / rel, data)
    _write_manifest(hooks_dir, expected)


def _read_manifest(hooks_dir: Path) -> dict[str, str]:
    try:
        data = json.loads((hooks_dir / HOOKS_MANIFEST).read_bytes())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def _copy_file_sha(path: Path) -> str | None:
    """The SHA-256 of a regular file; None for a link, a folder or an unreadable file."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return _sha256(path.read_bytes())
    except OSError:
        return None


def _extra_files(hooks_dir: Path, expected: dict[str, str]) -> list[str]:
    extras = set()
    for folder, dirnames, filenames in os.walk(hooks_dir):
        base = Path(folder)
        links = [name for name in dirnames if (base / name).is_symlink()]
        dirnames[:] = [name for name in dirnames if name not in links and name != "__pycache__"]
        for name in [*filenames, *links]:
            rel = (base / name).relative_to(hooks_dir).as_posix()
            if rel not in expected and rel != HOOKS_MANIFEST:
                extras.add(rel)
    return sorted(extras)


def _sync_hooks_copy(setup: _Setup, repo: Path, hooks_dir: Path) -> None:
    """Keep `hooks_dir` a read-only copy of the repo hooks, with a manifest of SHA-256 sums."""
    sources = _hook_sources(repo)
    if not sources:
        return
    contents = {rel: path.read_bytes() for rel, path in sources.items()}
    expected = {rel: _sha256(data) for rel, data in contents.items()}
    failure = f"hooks copy: could not write in {hooks_dir}"
    if hooks_dir.is_symlink() or (hooks_dir.exists() and not hooks_dir.is_dir()):
        setup.need(f"hooks copy: {hooks_dir} exists and is not a folder")
        return
    if not hooks_dir.exists():
        setup.fix(
            f"hooks copy: create {hooks_dir} with {len(expected)} files and the manifest",
            lambda: _write_copy(hooks_dir, contents, expected),
            failure,
        )
        return
    manifest = _read_manifest(hooks_dir)
    for rel, data in contents.items():
        target = hooks_dir / rel
        if not (target.is_symlink() or target.exists()):
            message = f"hooks copy {rel}: missing; copy it to {target}"
        elif (actual := _copy_file_sha(target)) != expected[rel]:
            edited = actual is None or (rel in manifest and actual != manifest[rel])
            reason = "edited after the copy (differs from the manifest)" if edited else "stale"
            message = f"hooks copy {rel}: {reason}; restore it from the repo"
        elif stat.S_IMODE(target.stat().st_mode) != 0o444:
            setup.fix(
                f"hooks copy {rel}: chmod 444",
                lambda target=target: target.chmod(0o444),
                f"{target} is not read-only and chmod 444 failed",
            )
            continue
        else:
            continue
        setup.fix(
            message,
            lambda target=target, data=data: _write_read_only(target, data),
            f"{failure} ({rel})",
        )
    for rel in _extra_files(hooks_dir, expected):
        setup.fix(
            f"hooks copy {rel}: not in the repo; remove it",
            lambda rel=rel: (hooks_dir / rel).unlink(missing_ok=True),
            f"could not remove {hooks_dir / rel}",
        )
    if manifest != expected or _copy_file_sha(hooks_dir / HOOKS_MANIFEST) is None:
        setup.fix(
            f"hooks copy: write the manifest {hooks_dir / HOOKS_MANIFEST}",
            lambda: _write_manifest(hooks_dir, expected),
            f"{failure} (manifest)",
        )


def _hook_command(hooks_dir: Path, script: str) -> str:
    return f'python3 -I "{hooks_dir.absolute() / script}"'


def _hook_entry(hooks_dir: Path, script: str, matcher: str) -> dict:
    return {
        "matcher": matcher,
        "hooks": [{"type": "command", "command": _hook_command(hooks_dir, script)}],
    }


def _hook_gate(hooks_dir: Path, scripts: tuple[str, ...] | None = None) -> dict:
    entries = [
        _hook_entry(hooks_dir, script, matcher)
        for script, matcher, _ in HOOK_REGISTRATIONS
        if scripts is None or script in scripts
    ]
    return {"hooks": {"PreToolUse": entries}}


def _permission_gate(deny: bool = True, ask: tuple[str, ...] = ASK_RULES) -> dict:
    permissions: dict = {}
    if deny:
        permissions["deny"] = [DENY_RULE]
    if ask:
        permissions["ask"] = list(ask)
    return {"permissions": permissions} if permissions else {}


def _gates_needed(message: str, snippet: dict) -> str:
    return f"{message}\n{textwrap.indent(json.dumps(snippet, indent=2), '  ')}"


def _check_claude_gates(setup: _Setup, hooks_dir: Path, settings_path: Path) -> None:
    """ws never writes the Claude settings: it asks for one block with everything missing."""
    approval = "ws never writes that file; Claude applies this block after you approve:"
    try:
        raw = settings_path.read_bytes()
    except FileNotFoundError:
        both = {**_hook_gate(hooks_dir), **_permission_gate()}
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

    missing_scripts = []
    for script, _, tools in HOOK_REGISTRATIONS:
        registered, notes = _registration_state(settings, hooks_dir, script, tools)
        if not registered:
            missing_scripts.append(script)
        for note in notes:
            setup.need(f"stale hook registration in {settings_path}: {note}")
    block: dict = _hook_gate(hooks_dir, tuple(missing_scripts)) if missing_scripts else {}
    block.update(
        _permission_gate(deny=not _has_deny_rule(settings), ask=_missing_ask_rules(settings))
    )
    if block:
        message = f"Claude Code gates missing in {settings_path}. {approval}"
        setup.need(_gates_needed(message, block))


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _hook_commands(settings: dict):
    """Every `PreToolUse` command hook as (matcher, command)."""
    for entry in _as_list(_as_dict(settings.get("hooks")).get("PreToolUse")):
        entry = _as_dict(entry)
        for hook in _as_list(entry.get("hooks")):
            hook = _as_dict(hook)
            if hook.get("type") == "command":
                yield entry.get("matcher"), hook.get("command")


def _registration_state(
    settings: dict, hooks_dir: Path, script: str, tools: tuple[str, ...]
) -> tuple[bool, list[str]]:
    """Whether `script` runs from the copy for every tool in `tools`, and what is stale.

    A substring match would accept `echo <script>`; a registration that still points at the
    repo's `hooks/` would run a file the agent can edit.
    """
    wanted = str(hooks_dir.absolute() / script)
    replacement = _hook_command(hooks_dir, script)
    registered = False
    notes = []
    for matcher, command in _hook_commands(settings):
        path = _python_script(command)
        if path is None:
            continue
        name = PurePath(path).name
        if name in HOOKS_NOT_COPIED and script == GATE_SCRIPT:
            notes.append(f"{path} is replaced by {replacement}; remove the old entry")
        elif name != script:
            continue
        elif _expand(path) != wanted:
            notes.append(f"{path} is replaced by {replacement}; remove the old entry")
        elif not _matcher_covers_all(matcher, tools):
            notes.append(f"{path} has the matcher {matcher!r}, which does not cover {tools}")
        else:
            registered = True
    return registered, notes


def _expand(path: str) -> str:
    return os.path.normpath(os.path.expanduser(os.path.expandvars(path)))


def _matcher_covers_all(matcher: object, tools: tuple[str, ...]) -> bool:
    if matcher is None or matcher in ("", "*"):
        return True
    if not isinstance(matcher, str):
        return False
    try:
        return all(re.fullmatch(matcher, tool) is not None for tool in tools)
    except re.error:
        return False


def _python_script(command: object) -> str | None:
    """The script a `python3 [-I] SCRIPT` command runs; None for any other command."""
    if not isinstance(command, str):
        return None
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    if len(words) < 2 or not re.fullmatch(r"python[0-9.]*", PurePath(words[0]).name):
        return None
    return words[-1]


def _check_gate_table(setup: _Setup, settings_file: Path) -> None:
    """The optional `[gate]` table of config.toml: a wrong type is reported, nothing is written."""
    try:
        data = tomllib.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        setup.need(f"{settings_file} could not be read as TOML: {error}")
        return
    if "gate" not in data:
        return
    gate = data["gate"]
    if not isinstance(gate, dict):
        setup.need(f"{settings_file}: [gate] must be a table")
        return
    for key in ("push_without_asking", "personal_github_owners"):
        value = gate.get(key)
        if value is not None and not (
            isinstance(value, list) and all(isinstance(item, str) for item in value)
        ):
            setup.need(f"{settings_file}: [gate] {key} must be a list of strings")


def _has_deny_rule(settings: dict) -> bool:
    return DENY_RULE in _as_list(_as_dict(settings.get("permissions")).get("deny"))


def _missing_ask_rules(settings: dict) -> tuple[str, ...]:
    present = _as_list(_as_dict(settings.get("permissions")).get("ask"))
    return tuple(rule for rule in ASK_RULES if rule not in present)


def card_gate_problems(settings_path: Path) -> list[str]:
    """What `ws card apply --approve` needs in the Claude settings and does not find (read-only)."""
    try:
        settings = json.loads(settings_path.read_bytes())
    except FileNotFoundError:
        return [f"Claude settings {settings_path} not found"]
    except (OSError, ValueError) as error:
        return [f"Claude settings {settings_path} is not a valid, readable JSON file ({error})"]
    if not isinstance(settings, dict):
        return [f"Claude settings {settings_path} is not a valid JSON object"]
    problems = []
    if CARD_ASK_RULE not in _as_list(_as_dict(settings.get("permissions")).get("ask")):
        problems.append(f"permissions.ask lacks {CARD_ASK_RULE}")
    hooks_dir = claude_hooks_dir()
    registered, _ = _registration_state(settings, hooks_dir, GATE_SCRIPT, ("Bash",))
    if not registered:
        problems.append(
            f"the PreToolUse hook {GATE_SCRIPT} is not registered from {hooks_dir} "
            "with a matcher that covers Bash"
        )
    return problems
