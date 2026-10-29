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

import contextlib
import difflib
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

from ws import dictionary, gatecatalog, humans, userconfig
from ws.config import (
    claude_hooks_dir,
    claude_json_path,
    claude_settings_path,
    repo_root,
    ws_executable,
)

GITHOOKS_DIR = ".githooks"
HOOK_NAMES = ("pre-commit", "pre-merge-commit", "commit-msg", "pre-push")
CARD_ASK_RULE = "Bash(ws card apply:*)"
HOOKS_SOURCE = "hooks"
HOOKS_MANIFEST = "manifest.json"
HOOKS_COPY_GLOBS = ("*.py", "gate/*.py", "gate/*.json")
HOOKS_NOT_COPIED = ("ask_card_apply.py",)
GATE_SCRIPT = "approval_gate.py"
GATE_LIST_KEYS = (
    "push_without_asking",
    "push_remotes",
    "personal_github_owners",
    "environment_branches",
    "direct_push_repos",
)
GATE_MATCHER = "Bash|mcp__.*"
HOOK_TIMEOUT = 30
MIN_HOOK_TIMEOUT = 10
COPY_DIR_MODE = 0o555
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
GITHUB_SERVER_URL = "https://api.githubcopilot.com/mcp/"
GITHUB_HEADERS_ARGS = ("mcp-headers", "github")
ENV_PATTERN = re.compile(r"token|secret|key|pass|auth|cred|(?:^|_)pat(?:_|$)", re.IGNORECASE)
ENV_SKIP_PREFIXES = ("CLAUDE_CODE_", "WS_")
ENV_SKIP_NAMES = frozenset({"SSH_AUTH_SOCK"})
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
    *(f"mcp__github__{tool}" for tool in GITHUB_WRITE_TOOLS),
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
    def __init__(self, apply: bool, by_hand: bool | None = None):
        self.apply = apply
        self.result = SetupResult()
        self._by_hand = by_hand

    @property
    def by_hand(self) -> bool:
        if self._by_hand is None:
            self._by_hand = humans.by_hand()
        return self._by_hand

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
    by_hand: bool | None = None,
) -> SetupResult:
    """Wire the clone, fix what can be fixed and return what was done and what is left.

    The protected copy of the hooks is written only by hand (`by_hand`, by default the terminal
    test of `ws.humans`), after the user reads the diff and answers; run by an agent, setup only
    reports it."""
    if settings is None:
        settings = claude_settings_path()
    if hooks_dir is None:
        hooks_dir = claude_hooks_dir()
    setup = _Setup(apply=not check, by_hand=by_hand)
    hooks_path_ok = _set_hooks_path(setup, repo)
    _fix_hook_bits(setup, repo)
    if hooks_path_ok:
        _check_hooks_path(setup, repo)
    _link_skills(setup, repo, skills_target)
    _check_config(setup, config)
    _check_sandbox_tools(setup)
    _check_hook_python(setup)
    _install_dictionaries(setup)
    _sync_hooks_copy(setup, repo, hooks_dir)
    _check_claude_gates(setup, hooks_dir, settings, repo)
    _check_secret_variables(setup, settings)
    _check_github_server(setup, config)
    _check_mcp_catalog(setup, repo, settings)
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


def _check_hook_python(setup: _Setup) -> None:
    """The Claude Code hooks run with the system `python3`, not uv's, and the gate reads TOML."""
    probe = "import sys, tomllib; print(*sys.version_info[:2])"
    try:
        result = subprocess.run(
            ["python3", "-I", "-c", probe], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as error:
        setup.need(f"python3 for the Claude Code hooks: could not run it ({error})")
        return
    if result.returncode != 0:
        setup.need(
            "python3 for the Claude Code hooks is older than 3.11 (no tomllib); the approval "
            "gate would ask before every command. Install python3.11 or newer as python3"
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


def _mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


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


@contextlib.contextmanager
def _writable(folder: Path):
    """Let the owner write in a folder of the copy (they are 0555) and put its mode back."""
    mode = stat.S_IMODE(folder.stat().st_mode)
    folder.chmod(mode | 0o200)
    try:
        yield
    finally:
        folder.chmod(mode)


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _ensure_dir(path: Path, root: Path) -> None:
    if path.exists():
        return
    _ensure_dir(path.parent, root)
    with _writable(path.parent) if _inside(path.parent, root) else contextlib.nullcontext():
        path.mkdir(mode=0o755)
    path.chmod(COPY_DIR_MODE if _inside(path, root) else 0o755)


def _write_read_only(target: Path, data: bytes, root: Path) -> None:
    """Unlink and write, so a read-only file or a link is never written through."""
    _ensure_dir(target.parent, root)
    with _writable(target.parent):
        target.unlink(missing_ok=True)
        target.write_bytes(data)
        target.chmod(0o444)


def _write_manifest(hooks_dir: Path, expected: dict[str, str]) -> None:
    text = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    _write_read_only(hooks_dir / HOOKS_MANIFEST, text.encode("utf-8"), hooks_dir)


def _write_copy(hooks_dir: Path, contents: dict[str, bytes], expected: dict[str, str]) -> None:
    for rel, data in contents.items():
        _write_read_only(hooks_dir / rel, data, hooks_dir)
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


def _copy_folders(expected: dict[str, str]) -> set[str]:
    """The folders of the copy, as paths relative to it, that hold an expected file."""
    folders = {""}
    for rel in expected:
        folders.update(parent.as_posix() for parent in PurePath(rel).parents)
    return {"" if folder == "." else folder for folder in folders}


def _extras(hooks_dir: Path, expected: dict[str, str]) -> list[str]:
    """Files, links and folders of the copy that are not in the manifest, `__pycache__` included:
    Python imports a stale `.pyc` or a folder that shadows a module before it reads the real one."""
    folders = _copy_folders(expected)
    extras = set()
    for folder, dirnames, filenames in os.walk(hooks_dir):
        base = Path(folder)
        for name in list(dirnames):
            rel = (base / name).relative_to(hooks_dir).as_posix()
            if (base / name).is_symlink() or rel not in folders:
                extras.add(rel)
                dirnames.remove(name)
        for name in filenames:
            rel = (base / name).relative_to(hooks_dir).as_posix()
            if rel not in expected and rel != HOOKS_MANIFEST:
                extras.add(rel)
    return sorted(extras)


def _remove_extra(hooks_dir: Path, rel: str) -> None:
    target = hooks_dir / rel
    with _writable(target.parent):
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)


_UNSAFE = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u2028\u2029]")


def _visible(line: str) -> str:
    """Escape what could move the cursor or hide a diff line on the user's terminal."""
    return _UNSAFE.sub(lambda match: f"\\x{ord(match.group()):02x}", line)


def _lines(text: str) -> list[str]:
    return text.removesuffix("\n").split("\n") if text else []


def _diff_lines(rel: str, old: bytes, new: bytes) -> list[str]:
    """What the user reads before the copy changes; `.json` files as pretty JSON."""

    def text(data: bytes) -> str:
        decoded = data.decode("utf-8", errors="replace")
        if rel.endswith(".json"):
            try:
                return json.dumps(json.loads(decoded), indent=2, ensure_ascii=False) + "\n"
            except ValueError:
                pass
        return decoded

    diff = difflib.unified_diff(
        _lines(text(old)),
        _lines(text(new)),
        fromfile=f"copia/{rel}",
        tofile=f"repo/{rel}",
        lineterm="",
    )
    return [_visible(line) for line in diff]


def _current_bytes(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            return b""
        return path.read_bytes()
    except OSError:
        return b""


def _confirm_copy(hooks_dir: Path, changes: list[tuple[str, str, bytes]]) -> bool:
    print(f"Cópia protegida dos hooks em {hooks_dir}: {len(changes)} arquivo(s) mudam.")
    for rel, reason, data in changes:
        print(f"\n== {rel} ({reason})")
        diff = _diff_lines(rel, _current_bytes(hooks_dir / rel), data)
        print("\n".join(diff) if diff else "(sem diferença de conteúdo)")
    try:
        answer = input("\nAtualizar a cópia protegida dos hooks? [s/N] ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in ("s", "sim")


def _content_approved(
    setup: _Setup, hooks_dir: Path, changes: list[tuple[str, str, bytes]]
) -> bool:
    """Whether the copy may take the repo's content: only by hand, after the diff and an `s`.
    Anything the repo holds could have been edited by an agent, so an agent never writes it."""
    if not changes or not setup.apply:
        return True
    if not setup.by_hand:
        listed = ", ".join(f"{rel} ({reason})" for rel, reason, _ in changes)
        setup.need(f"hooks copy: {listed}; run ws setup in your own terminal to review and apply")
        return False
    if _confirm_copy(hooks_dir, changes):
        return True
    setup.need("hooks copy: not updated, the change was not approved")
    return False


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
        changes = [(rel, "novo", data) for rel, data in contents.items()]
        if _content_approved(setup, hooks_dir, changes):
            setup.fix(
                f"hooks copy: create {hooks_dir} with {len(expected)} files and the manifest",
                lambda: _write_copy(hooks_dir, contents, expected),
                failure,
            )
        return
    manifest = _read_manifest(hooks_dir)
    changes = []
    messages: dict[str, str] = {}
    for rel, data in contents.items():
        target = hooks_dir / rel
        if not (target.is_symlink() or target.exists()):
            messages[rel] = f"hooks copy {rel}: missing; copy it to {target}"
            changes.append((rel, "ausente na cópia", data))
        elif (actual := _copy_file_sha(target)) != expected[rel]:
            edited = actual is None or (rel in manifest and actual != manifest[rel])
            reason = "edited after the copy (differs from the manifest)" if edited else "stale"
            messages[rel] = f"hooks copy {rel}: {reason}; restore it from the repo"
            changes.append((rel, "editado depois da cópia" if edited else "desatualizado", data))
    approved = _content_approved(setup, hooks_dir, changes)
    for rel, data in contents.items():
        target = hooks_dir / rel
        if rel in messages:
            if approved:
                setup.fix(
                    messages[rel],
                    lambda target=target, data=data: _write_read_only(target, data, hooks_dir),
                    f"{failure} ({rel})",
                )
        elif stat.S_IMODE(target.stat().st_mode) != 0o444:
            setup.fix(
                f"hooks copy {rel}: chmod 444",
                lambda target=target: target.chmod(0o444),
                f"{target} is not read-only and chmod 444 failed",
            )
    for rel in _extras(hooks_dir, expected):
        setup.fix(
            f"hooks copy {rel}: not in the repo; remove it",
            lambda rel=rel: _remove_extra(hooks_dir, rel),
            f"could not remove {hooks_dir / rel}",
        )
    for folder in sorted(_copy_folders(expected)):
        path = hooks_dir / folder
        if path.is_dir() and not path.is_symlink() and (mode := _mode_of(path)) != COPY_DIR_MODE:
            setup.fix(
                f"hooks copy folder {folder or '.'}: chmod {COPY_DIR_MODE:o} (from {mode:04o})",
                lambda path=path: path.chmod(COPY_DIR_MODE),
                f"{path} is writable and chmod {COPY_DIR_MODE:o} failed",
            )
    if approved and (manifest != expected or _copy_file_sha(hooks_dir / HOOKS_MANIFEST) is None):
        setup.fix(
            f"hooks copy: write the manifest {hooks_dir / HOOKS_MANIFEST}",
            lambda: _write_manifest(hooks_dir, expected),
            f"{failure} (manifest)",
        )


def _hook_command(hooks_dir: Path, script: str) -> str:
    return f'python3 -I -B "{hooks_dir.absolute() / script}"'


def _hook_entry(hooks_dir: Path, script: str, matcher: str) -> dict:
    hook = {"type": "command", "command": _hook_command(hooks_dir, script), "timeout": HOOK_TIMEOUT}
    return {"matcher": matcher, "hooks": [hook]}


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


def _check_claude_gates(setup: _Setup, hooks_dir: Path, settings_path: Path, repo: Path) -> None:
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

    for path in _hooks_disabled(settings_path, settings, repo):
        setup.need(
            f"disableAllHooks is true in {path}, which switches every gate off. ws never writes "
            "that file: set it to false or remove it"
        )
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


def _hooks_disabled(settings_path: Path, settings: dict, repo: Path) -> list[str]:
    """The settings files that switch every hook off: `settings.json` and its sibling
    `settings.local.json`, and the project-level pair in the `.claude` folder of the repo."""
    project = repo / ".claude"
    found = []
    for path in (
        settings_path,
        settings_path.with_name("settings.local.json"),
        project / "settings.json",
        project / "settings.local.json",
    ):
        try:
            data = settings if path == settings_path else json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue
        if _as_dict(data).get("disableAllHooks") is True:
            found.append(str(path))
    return found


def _blanked_variables(settings_path: Path) -> set[str]:
    """The names the Claude settings already blank in `env`; any read problem means none."""
    try:
        settings = json.loads(settings_path.read_bytes())
    except (OSError, ValueError):
        return set()
    env = _as_dict(_as_dict(settings).get("env"))
    return {name for name, value in env.items() if value == ""}


def _check_secret_variables(setup: _Setup, settings_path: Path) -> None:
    """Any command Claude runs reads the session environment: secrets there must be blanked."""
    blanked = _blanked_variables(settings_path)
    names = sorted(
        name
        for name, value in os.environ.items()
        if value
        and ENV_PATTERN.search(name)
        and not name.upper().startswith(ENV_SKIP_PREFIXES)
        and name not in ENV_SKIP_NAMES
        and name not in blanked
    )
    if not names:
        return
    snippet = {"env": {name: "" for name in names}}
    message = (
        f"secret variables in the environment: {', '.join(names)}. Every command Claude Code "
        f"runs can read them. This blanks them in Claude Code sessions only (terminals and "
        f"VS Code keep them); add it to {settings_path}, which ws never writes:"
    )
    setup.need(_gates_needed(message, snippet))


def _github_server_problem(claude_json: Path) -> str | None:
    """None when the user-scope `github` server is the expected one, else what is wrong."""
    try:
        data = json.loads(claude_json.read_bytes())
    except FileNotFoundError:
        return "missing"
    except (OSError, ValueError) as error:
        return f"unreadable ({error})"
    server = _as_dict(_as_dict(data).get("mcpServers")).get("github")
    if server is None:
        return "missing"
    server = _as_dict(server)
    if server.get("type") != "http" or server.get("url") != GITHUB_SERVER_URL:
        return "different: it must be type http with the GitHub MCP url"
    try:
        words = shlex.split(str(server.get("headersHelper")))
    except ValueError:
        words = []
    if (
        len(words) != 3
        or PurePath(words[0]).name != "ws"
        or tuple(words[1:]) != GITHUB_HEADERS_ARGS
    ):
        return "different: headersHelper must run `ws mcp-headers github`"
    return None


def _check_github_server(setup: _Setup, config: Path) -> None:
    """The GitHub MCP server reads its token from `credentials` through `ws mcp-headers`."""
    claude_json = claude_json_path()
    problem = _github_server_problem(claude_json)
    try:
        userconfig.load_token("github", config)
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid) as error:
        why = "none is stored" if isinstance(error, userconfig.ConfigMissing) else error
        setup.need(
            f"no usable GitHub token ({why}); the GitHub MCP server needs one. Run in a terminal, "
            "outside Claude: ws config token github"
        )
        return
    if problem is None:
        return
    executable = ws_executable()
    if executable is None:
        setup.need("GitHub MCP server: the ws executable was not found, so no command can be built")
        return
    spec = {
        "type": "http",
        "url": GITHUB_SERVER_URL,
        "headersHelper": f"{shlex.quote(str(executable))} {' '.join(GITHUB_HEADERS_ARGS)}",
    }
    command = f"claude mcp add-json github {shlex.quote(json.dumps(spec))} --scope user"
    if problem.startswith("different"):
        command = f"claude mcp remove github --scope user && {command}"
    setup.need(
        f"GitHub MCP server in {claude_json} is {problem}. ws never writes that file; "
        f"run in a terminal:\n  {command}"
    )


def _check_mcp_catalog(setup: _Setup, repo: Path, settings: Path) -> None:
    """An MCP server the catalog does not know asks before every call, reads included."""
    try:
        catalog = gatecatalog.load_catalog(repo / HOOKS_SOURCE / "gate" / "catalog.json")
    except gatecatalog.CatalogError:
        return
    missing = gatecatalog.unknown_servers(catalog, settings)
    if missing:
        setup.need(
            f"MCP servers the approval gate does not know: {', '.join(missing)}. Every call of "
            "theirs asks, reads included, until their tools are classified: "
            "run `ws gate catalog`."
        )


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _hook_commands(settings: dict):
    """Every `PreToolUse` command hook as (matcher, hook)."""
    for entry in _as_list(_as_dict(settings.get("hooks")).get("PreToolUse")):
        entry = _as_dict(entry)
        for hook in _as_list(entry.get("hooks")):
            hook = _as_dict(hook)
            if hook.get("type") == "command":
                yield entry.get("matcher"), hook


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
    for matcher, hook in _hook_commands(settings):
        command = hook.get("command")
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
        elif not _isolated(command):
            notes.append(
                f"{command!r} does not run exactly python3 -I {path}; it is replaced by "
                f"{replacement}; remove the old entry"
            )
        elif not _matcher_covers_all(matcher, tools):
            notes.append(f"{path} has the matcher {matcher!r}, which does not cover {tools}")
        elif not _timeout_ok(hook.get("timeout")):
            notes.append(
                f"{path} has timeout {hook.get('timeout')!r}, under {MIN_HOOK_TIMEOUT} seconds, "
                f"so the hook can be cut short and then does not run; use {HOOK_TIMEOUT}"
            )
        else:
            registered = True
    return registered, notes


def _timeout_ok(value: object) -> bool:
    """No timeout means Claude's own default, which is long; a short one cuts the gate off."""
    if value is None:
        return True
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and (value >= MIN_HOOK_TIMEOUT)
    )


def _isolated(command: object) -> bool:
    """Exactly `python3 -I SCRIPT`, with `-B` allowed (`-I -B`, `-IB`): no other word, such as
    `-c`, can stop the script from running."""
    try:
        words = shlex.split(command) if isinstance(command, str) else []
    except ValueError:
        return False
    flags = words[1:-1]
    return (
        len(words) >= 3
        and all(flag in ("-I", "-B", "-IB", "-BI") for flag in flags)
        and any("I" in flag for flag in flags)
    )


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
    for key in GATE_LIST_KEYS:
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
    problems = [
        f"disableAllHooks is true in {path}, which switches every hook off"
        for path in _hooks_disabled(settings_path, settings, repo_root())
    ]
    if CARD_ASK_RULE not in _as_list(_as_dict(settings.get("permissions")).get("ask")):
        problems.append(f"permissions.ask lacks {CARD_ASK_RULE}")
    hooks_dir = claude_hooks_dir()
    registered, notes = _registration_state(settings, hooks_dir, GATE_SCRIPT, ("Bash",))
    if not registered:
        problems.append(
            f"the PreToolUse hook {GATE_SCRIPT} is not registered from {hooks_dir} "
            "with a matcher that covers Bash, as exactly python3 -I and a timeout of at least "
            f"{MIN_HOOK_TIMEOUT} seconds"
        )
    for script, _, tools in HOOK_REGISTRATIONS[1:]:
        _, notes = _registration_state(settings, hooks_dir, script, tools)
        problems += [note for note in notes if "timeout" in note]
    return problems
