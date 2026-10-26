"""Claude Code PreToolUse gate: blocks Bash commands that bypass or disable the git hooks.

Blocked: `--no-verify` on any git command, `git commit -n` (also inside a flag group such as
`-nm`), a `core.hooksPath` override (`git -c core.hooksPath=...`, `GIT_CONFIG_*` variables) and
a `core.hooksPath` change (`git config`), except the exact `git config core.hooksPath .githooks`
that `ws setup` runs. It applies in every repo: company repos have their own hooks, and the AI
must not skip them either.

The command is split into simple commands (on `;`, `&&`, `||`, `|`, `&`, parentheses and
newlines) and each one is checked as a token sequence, so `grep -- --no-verify` or
`echo "git commit --no-verify"` pass. Command substitutions, `bash -c` and `eval` are scanned
too. A command that cannot be parsed is blocked only if its text mentions `--no-verify` or
`hooksPath`.

Exit 2 blocks the tool call and sends stderr back to Claude. Any internal error also exits 2,
because Claude Code treats other non-zero codes as non-blocking and the gate would fail open.
"""

import json
import re
import shlex
import sys
from pathlib import PurePath

HOOKS_PATH_KEY = "core.hookspath"
ALLOWED_CONFIG_ARGS = ["core.hookspath", ".githooks"]
NO_VERIFY = "--no-verify"
CONFIG_READ_FLAGS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l"}
OPERATOR_CHARS = ";()<>|&\n"
REDIRECT_CHARS = "<>"
SHORT_OPTIONS_WITH_VALUE = "mFCctuS"
GIT_OPTIONS_WITH_VALUE = {"-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix"}
WRAPPERS = {
    "env",
    "command",
    "exec",
    "time",
    "nice",
    "nohup",
    "sudo",
    "builtin",
    "setsid",
    "timeout",
}
SHELL_KEYWORDS = {"if", "then", "else", "elif", "while", "until", "do", "!", "{"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}

ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"[0-9]+[smhd]?")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
UNPARSEABLE_BYPASS = re.compile(r"--no-verify|hookspath", re.IGNORECASE)


def _strip_heredocs(text: str) -> str:
    """Drop heredoc bodies (and their delimiter lines): they are data, not commands."""
    lines = text.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        for _, tag in HEREDOC.findall(line):
            end = next((i for i in range(index, len(lines)) if lines[i].strip() == tag), None)
            if end is not None:
                index = end + 1
    return "\n".join(kept)


def _simple_commands(text: str) -> list[list[str]]:
    lexer = shlex.shlex(text.replace("\\\n", " "), posix=True, punctuation_chars=OPERATOR_CHARS)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    commands: list[list[str]] = []
    current: list[str] = []
    for token in lexer:
        if not set(token) <= set(OPERATOR_CHARS):
            current.append(token)
        elif not set(token) & set(REDIRECT_CHARS):
            if current:
                commands.append(current)
            current = []
    if current:
        commands.append(current)
    return commands


def _substitutions(text: str) -> list[str]:
    """Contents of every `$(...)` and backtick pair that the shell would run, nested ones too.

    Single-quoted text is literal, so a commit message in single quotes that cites a command in
    backticks is not a substitution.
    """
    found = []
    single = double = False
    index = 0
    while index < len(text):
        char = text[index]
        if single:
            single = char != "'"
        elif char == "\\":
            index += 1
        elif char == '"':
            double = not double
        elif char == "'" and not double:
            single = True
        elif text.startswith("$(", index):
            depth, end = 1, index + 2
            while end < len(text) and depth:
                depth += (text[end] == "(") - (text[end] == ")")
                end += 1
            found.append(text[index + 2 : end - 1 if depth == 0 else end])
        elif char == "`":
            end = text.find("`", index + 1)
            found.append(text[index + 1 : end if end != -1 else len(text)])
            if end != -1:
                index = end
        index += 1
    return found


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


def _check_git(args: list[str]) -> str | None:
    overrides, subcommand, rest = _split_git(args)
    if any(_is_hooks_path_key(setting) for setting in overrides):
        return "a core.hooksPath override with -c"
    if subcommand == "config" and _changes_hooks_path(rest):
        return "a change of core.hooksPath"
    if _skips_verification(subcommand, rest):
        return "skipping the hooks with --no-verify (or -n on git commit)"
    return None


def _locate_program(words: list[str]) -> int | None:
    """Index of the program a simple command runs, after assignments, keywords and wrappers."""
    index = 0
    while index < len(words):
        word = words[index]
        if ASSIGNMENT.match(word) or word in SHELL_KEYWORDS:
            index += 1
        elif PurePath(word).name in WRAPPERS:
            index += 1
            while index < len(words) and (
                words[index].startswith("-")
                or ASSIGNMENT.match(words[index])
                or DURATION.fullmatch(words[index])
            ):
                index += 1
        else:
            return index
    return None


def _shell_script(args: list[str]) -> str | None:
    for position, arg in enumerate(args):
        if not arg.startswith("-"):
            return None
        if not arg.startswith("--") and "c" in arg[1:]:
            return args[position + 1] if position + 1 < len(args) else None
    return None


def _check_simple(words: list[str]) -> str | None:
    index = _locate_program(words)
    if index is None:
        return None
    for word in words[:index]:
        if word.startswith("GIT_CONFIG") and "hookspath" in word.lower():
            return "a core.hooksPath override through GIT_CONFIG_* variables"
    name = PurePath(words[index]).name
    args = words[index + 1 :]
    if name == "git":
        return _check_git(args)
    if name in SHELLS:
        script = _shell_script(args)
        return _scan(script) if script is not None else None
    if name == "eval":
        return _scan(" ".join(args))
    return None


def _scan(text: str) -> str | None:
    """Return why the command bypasses the git hooks, or None."""
    text = _strip_heredocs(text)
    try:
        commands = _simple_commands(text)
    except ValueError:
        if UNPARSEABLE_BYPASS.search(text):
            return "text that mentions --no-verify or hooksPath and cannot be parsed"
        return None
    for reason in (_check_simple(words) for words in commands):
        if reason:
            return reason
    for inner in _substitutions(text):
        if reason := _scan(inner):
            return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        if not isinstance(command, str):
            raise TypeError("tool_input.command is not a string")
        reason = _scan(command)
    except Exception as error:
        print(f"Hook-bypass gate could not check the command ({error}); blocking.", file=sys.stderr)
        return 2
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
