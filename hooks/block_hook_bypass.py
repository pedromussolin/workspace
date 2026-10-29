"""Claude Code PreToolUse gate: blocks Bash commands that bypass or disable the git hooks.

Blocked: `--no-verify` on any git command, `git commit -n` (also inside a flag group such as
`-nm`), a `core.hooksPath` override (`git -c core.hooksPath=...`, `GIT_CONFIG_*` variables) and
a `core.hooksPath` change (`git config`), except the exact `git config core.hooksPath .githooks`
that `ws setup` runs. It applies in every repo: company repos have their own hooks, and the AI
must not skip them either.

The command is split into simple commands (on `;`, `&&`, `||`, `|`, `&`, parentheses and
newlines) and each one is checked as a token sequence, so `grep -- --no-verify` or
`echo "git commit --no-verify"` pass. Command substitutions, `bash -c` and `eval` are scanned
too, and so are a heredoc body or a here-string that a shell, `eval`, `source` or `.` runs. Any
other body is data (a commit message in `git commit -F- <<'EOF'`), unless it is unquoted: then
its `$(...)` is scanned. A command that cannot be parsed is blocked only if its text mentions
`--no-verify` or `hooksPath`.

Exit 2 blocks the tool call and sends stderr back to Claude. Any internal error also exits 2,
because Claude Code treats other non-zero codes as non-blocking and the gate would fail open; so
does running out of time (`DEADLINE_SECONDS`), since a hook that times out lets the call run.
"""

import importlib.util
import json
import os
import re
import shlex
import signal
import sys
from pathlib import Path, PurePath


def _load_shell():
    """`gate/shell.py` next to this file, loaded by path and never through `sys.path`.

    A module planted next to the hooks (`re.py`, `dataclasses.py`) must not shadow the standard
    library.
    """
    path = Path(__file__).resolve().parent / "gate" / "shell.py"
    spec = importlib.util.spec_from_file_location("workspace_gate_shell", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"no parser at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    shell = _load_shell()
except Exception as error:
    print(f"Hook-bypass gate could not load its parser ({error}); blocking.", file=sys.stderr)
    sys.exit(2)

HOOKS_PATH_KEY = "core.hookspath"
ALLOWED_CONFIG_ARGS = ["core.hookspath", ".githooks"]
NO_VERIFY = "--no-verify"
CONFIG_READ_FLAGS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l"}
SHORT_OPTIONS_WITH_VALUE = "mFCctuS"
GIT_OPTIONS_WITH_VALUE = {"-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix"}

DEADLINE_SECONDS = 5.0

UNPARSEABLE_BYPASS = re.compile(r"--no-verify|hookspath", re.IGNORECASE)


def _is_hooks_path_key(text: str) -> bool:
    return text.lower().partition("=")[0] == HOOKS_PATH_KEY


def _split_git(args: list[str]) -> tuple[list[str], str, list[str]]:
    """Return the `-c` settings, the subcommand and its arguments of a `git ...` command."""
    overrides: list[str] = []
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        index += 1
        if option in ("-c", "--config-env") and index < len(args):
            overrides.append(args[index])
            index += 1
        elif option.startswith("--config-env="):
            overrides.append(option.partition("=")[2])
        elif option in GIT_OPTIONS_WITH_VALUE:
            index += 1
    if index >= len(args):
        return overrides, "", []
    return overrides, args[index], args[index + 1 :]


def _short_group_has_n(word: str) -> bool:
    for letter in word[1:]:
        if letter == "n":
            return True
        if letter in SHORT_OPTIONS_WITH_VALUE:
            return False
    return False


def _skips_verification(subcommand: str, args: list[str]) -> bool:
    for word in args:
        if word == "--":
            return False
        if word.startswith("--no-v") and NO_VERIFY.startswith(word):
            return True
        if (
            subcommand == "commit"
            and re.fullmatch(r"-[A-Za-z]+", word)
            and _short_group_has_n(word)
        ):
            return True
    return False


def _changes_hooks_path(args: list[str]) -> bool:
    if not any(_is_hooks_path_key(word) for word in args):
        return False
    if [args[0].lower(), *args[1:]] == ALLOWED_CONFIG_ARGS:
        return False
    return not (CONFIG_READ_FLAGS & set(args) or args[0] in ("get", "list"))


def _check_alias(setting: str) -> str | None:
    """Why a `-c alias.NAME=VALUE` bypasses the hooks: its value is read as a git command line."""
    key, _, value = setting.partition("=")
    if not key.lower().startswith("alias."):
        return None
    if value.startswith("!"):
        reason = _scan(value[1:])
    else:
        try:
            reason = _check_git(shlex.split(value))
        except ValueError:
            reason = "an alias that cannot be parsed" if UNPARSEABLE_BYPASS.search(value) else None
    return f"{reason}, inside a -c alias" if reason else None


def _check_git(args: list[str]) -> str | None:
    overrides, subcommand, rest = _split_git(args)
    if any(_is_hooks_path_key(setting) for setting in overrides):
        return "a core.hooksPath override with -c"
    for setting in overrides:
        if reason := _check_alias(setting):
            return reason
    if subcommand == "config" and _changes_hooks_path(rest):
        return "a change of core.hooksPath"
    if _skips_verification(subcommand, rest):
        return "skipping the hooks with --no-verify (or -n on git commit)"
    return None


def _check_simple(words: list[str]) -> str | None:
    for script in shell.wrapper_scripts([shell.Word(word) for word in words]):
        if reason := _scan(script.text):
            return reason
    index = shell.locate_program(words)
    if index is None:
        return None
    for word in words[:index]:
        if word.startswith("GIT_CONFIG") and "hookspath" in word.lower():
            return "a core.hooksPath override through GIT_CONFIG_* variables"
    name = PurePath(words[index]).name
    args = words[index + 1 :]
    if name == "git":
        return _check_git(args)
    if name in shell.SHELLS:
        script = shell.shell_script(args)
        return _scan(script) if script is not None else None
    if name == "eval":
        return _scan(" ".join(args))
    return None


def _check_heredoc(heredoc: "shell.Heredoc") -> str | None:
    """A body is data, unless a shell runs it or it is unquoted and so expands `$(...)`."""
    if heredoc.owner in shell.RUNS_ITS_INPUT:
        return _scan(heredoc.body)
    if heredoc.quoted:
        return None
    for inner in shell.substitutions(heredoc.body, quoting=False):
        if reason := _scan(inner):
            return reason
    return None


def _check_here_strings(text: str) -> str | None:
    """A here-string (`<<<`) is data, unless a shell, `eval`, `source` or `.` runs it."""
    if "<<<" not in text:
        return None
    try:
        commands = shell.parse_commands(text)
    except ValueError:
        if UNPARSEABLE_BYPASS.search(text):
            return "text that mentions --no-verify or hooksPath and cannot be parsed"
        return None
    for command in commands:
        runs_it = any(name in shell.RUNS_ITS_INPUT for name, _ in shell.invocations(command))
        if runs_it and command.here_string is not None and (reason := _scan(command.here_string)):
            return reason
    return None


def _scan(text: str) -> str | None:
    """Return why the command bypasses the git hooks, or None."""
    text, heredocs = shell.split_heredocs(text)
    for heredoc in heredocs:
        if reason := _check_heredoc(heredoc):
            return reason
    try:
        commands = shell.simple_commands(text)
    except ValueError:
        if UNPARSEABLE_BYPASS.search(text):
            return "text that mentions --no-verify or hooksPath and cannot be parsed"
        return None
    for reason in (_check_simple(words) for words in commands):
        if reason:
            return reason
    if reason := _check_here_strings(text):
        return reason
    for inner in shell.substitutions(text):
        if reason := _scan(inner):
            return reason
    return None


def _late(signum, frame) -> None:
    os.write(2, b"Hook-bypass gate could not check the command in time; blocking.\n")
    os._exit(2)


def main() -> int:
    if hasattr(signal, "setitimer"):
        signal.signal(signal.SIGALRM, _late)
        signal.setitimer(signal.ITIMER_REAL, DEADLINE_SECONDS)
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        if not isinstance(command, str):
            raise TypeError("tool_input.command is not a string")
        reason = _scan(command)
    except Exception as error:
        print(f"Hook-bypass gate could not check the command ({error}); blocking.", file=sys.stderr)
        return 2
    if hasattr(signal, "setitimer"):
        signal.setitimer(signal.ITIMER_REAL, 0)
    if reason:
        print(
            f"Blocked: {reason}. The git hooks are a safety net and are never skipped or "
            "reconfigured by the AI, in any repo. Fix what the hook reports instead; if it is a "
            "false positive, ask the user.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
