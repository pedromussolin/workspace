"""Shell parsing shared by the gates.

Two parsers live here, on purpose. The first (`strip_heredocs`, `simple_commands`,
`substitutions`, `locate_program`, `shell_script`) is the one `block_hook_bypass.py` always used,
moved here; its wrapper table and substitution search serve both gates. The second (`scan`) is the
approval gate's: it keeps what the first throws away, namely which words carry an unquoted
expansion, where each redirect points, and what feeds a command. It is heredoc-aware: the body of
a quoted heredoc (`<<'EOF'`, `<<"EOF"`, `<<\\EOF`) is data, unless the command that owns it is a
shell, `eval`, `source` or `.`, and then the body is scanned as commands; the body of an
unquoted heredoc is expanded by the shell, so its `$(...)` and backticks are scanned.
"""

import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import PurePath

OPERATOR_CHARS = ";()<>|&\n"
REDIRECT_CHARS = "<>"
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
RUNS_ITS_INPUT = SHELLS | {"eval", "source", "."}
MAX_DEPTH = 8
MAX_WALKS = 2000
WALK_SECONDS = 2.0

ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"[0-9]+[smhd]?")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
PYTHON = re.compile(r"python[0-9.]*")


def strip_heredocs(text: str) -> str:
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


def simple_commands(text: str) -> list[list[str]]:
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


def substitutions(text: str, quoting: bool = True) -> list[str]:
    """Contents of the outermost `$(...)` and backtick pairs that the shell would run.

    Nested ones are found by scanning each content again; listing them here too made every
    caller's recursion exponential in the nesting depth. Single-quoted text is literal, so a
    commit message in single quotes that cites a command in backticks is not a substitution. With
    `quoting` off, quotes mean nothing (the body of an unquoted heredoc is expanded whatever quotes
    it holds) outside the substitution; inside it, the shell parses quotes as usual.
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
        elif char == '"' and quoting:
            double = not double
        elif char == "'" and not double and quoting:
            single = True
        elif text.startswith("$(", index):
            try:
                end = _skip_group(text, index + 1, "(", ")")
                found.append(text[index + 2 : end - 1])
            except ValueError:
                end = len(text)
                found.append(text[index + 2 :])
            index = end
            continue
        elif char == "`":
            end = text.find("`", index + 1)
            found.append(text[index + 1 : end if end != -1 else len(text)])
            if end != -1:
                index = end
        index += 1
    return found


def locate_program(words: list[str]) -> int | None:
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


def shell_script(args: list[str]) -> str | None:
    for position, arg in enumerate(args):
        if not arg.startswith("-"):
            return None
        if not arg.startswith("--") and "c" in arg[1:]:
            return args[position + 1] if position + 1 < len(args) else None
    return None


@dataclass(frozen=True)
class Word:
    """One argument with its quotes removed.

    `bare`: it holds a `$`, a backtick or a brace expansion outside every quote. `expands`: the
    same, but a `$` or backtick inside double quotes counts too (single quotes never do).
    """

    text: str
    bare: bool = False
    expands: bool = False


def script_word(args: list[Word]) -> Word | None:
    """The `-c` script of a shell command as a word, so its expansion flags are known."""
    if shell_script([word.text for word in args]) is None:
        return None
    index = next(i for i, word in enumerate(args) if _is_c_flag(word.text))
    return args[index + 1]


def _is_c_flag(arg: str) -> bool:
    return arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]


@dataclass
class Command:
    words: list[Word] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    piped: bool = False
    reads: list[str] = field(default_factory=list)
    here_string: str | None = None
    inner: list[str] = field(default_factory=list)

    @property
    def reads_file(self) -> bool:
        return bool(self.reads)


@dataclass(frozen=True)
class Heredoc:
    body: str
    quoted: bool
    owner: str | None


@dataclass
class Scan:
    """What `scan` found. `overrun`: it gave up on a command too big or too nested to read."""

    commands: list[Command] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    overrun: bool = False
    walks: int = 0
    deadline: float = 0.0


HEREDOC_TAG = re.compile(r"""(-?)[ \t]*((?:'[^'\n]*'|"[^"\n]*"|\\.|[^\s;&|<>()'"\\])+)""")
TAG_QUOTING = re.compile(r"""'([^']*)'|"([^"]*)"|\\(.)""")
BRACE_EXPANSION = re.compile(r"\{[^{}]*?(?:,|\.\.)[^{}]*?\}")
OPERATORS = sorted(
    ["&>>", "<<<", "<<-", "&&", "||", ";;", "|&", "&>", "<<", ">>", ">|", ">&", "<&", "<>"]
    + list(";&|()<>"),
    key=len,
    reverse=True,
)
SEPARATORS = {";", ";;", "&", "&&", "||", "|", "|&", "(", ")"}
WORD_ENDS = set(" \t\r\n;&|()<>")


def program_name(word: str) -> str:
    """The program a word names: its last path component (`/usr/bin/git` is `git`)."""
    return PurePath(word).name or word


def _owner(prefix: str) -> str | None:
    words = prefix.split()
    index = locate_program(words)
    return None if index is None else program_name(words[index].strip("'\""))


def _heredoc_body(text: str, start: int, tag: str) -> tuple[str, int] | None:
    """The body that begins at `start` and where the line after its delimiter begins."""
    position = start
    while position <= len(text):
        end = text.find("\n", position)
        line = text[position : len(text) if end == -1 else end]
        if line.strip() == tag:
            return text[start:position], len(text) if end == -1 else end + 1
        if end == -1:
            return None
        position = end + 1
    return None


def split_heredocs(text: str) -> tuple[str, list[Heredoc]]:
    """The text without the bodies of its heredocs, and the heredocs found.

    A quote state machine keeps `<<` inside quotes literal, yet live inside a `$(...)` that sits
    in double quotes (the usual `git commit -m "$(cat <<'EOF' ...)"`). A heredoc with no
    delimiter line is left in place, so its lines are read as commands.
    """
    kept: list[str] = []
    found: list[Heredoc] = []
    pending: list[tuple[str, bool, str | None]] = []
    stack = ["top"]
    segment = 0
    index, size = 0, len(text)
    while index < size:
        char, context = text[index], stack[-1]
        if context == "sq":
            if char == "'":
                stack.pop()
        elif char == "\\":
            kept.append(text[index : index + 2])
            index += 2
            continue
        elif context == "dq":
            if char == '"':
                stack.pop()
            elif text.startswith("$(", index):
                stack.append("sub")
                kept.append("$(")
                index += 2
                segment = index
                continue
            elif char == "`":
                stack.append("bt")
        elif char == "'":
            stack.append("sq")
        elif char == '"':
            stack.append("dq")
        elif char == "`":
            if context == "bt":
                stack.pop()
            else:
                stack.append("bt")
            segment = index + 1
        elif text.startswith("$(", index):
            stack.append("sub")
            kept.append("$(")
            index += 2
            segment = index
            continue
        elif char in "()":
            if char == "(":
                stack.append("grp")
            elif context in ("sub", "grp"):
                stack.pop()
            segment = index + 1
        elif char in ";&|":
            segment = index + 1
        elif char == "#" and (index == 0 or text[index - 1] in " \t\n;&|()"):
            end = text.find("\n", index)
            end = size if end == -1 else end
            kept.append(text[index:end])
            index = end
            continue
        elif char == "\n":
            kept.append(char)
            index += 1
            for tag, quoted, owner in pending:
                body = _heredoc_body(text, index, tag)
                if body is not None:
                    found.append(Heredoc(body[0], quoted, owner))
                    index = body[1]
            pending = []
            segment = index
            continue
        elif text.startswith("<<", index) and text[index : index + 3] != "<<<":
            match = HEREDOC_TAG.match(text, index + 2) if text[index - 1 : index] != "<" else None
            if match:
                raw = match.group(2)
                tag = TAG_QUOTING.sub(lambda m: m.group(1) or m.group(2) or m.group(3) or "", raw)
                pending.append((tag, tag != raw, _owner(text[segment:index])))
                kept.append(text[index : match.end()])
                index = match.end()
                continue
        kept.append(char)
        index += 1
    return "".join(kept), found


def _skip_group(text: str, start: int, opener: str, closer: str) -> int:
    """Index just past the group whose opener is at `start`; quotes inside do not count."""
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "'":
            end = text.find("'", index + 1)
            if end == -1:
                raise ValueError("unterminated quote")
            index = end + 1
            continue
        if char == '"':
            index = _skip_double(text, index)
            continue
        if char == "`":
            index = _skip_backtick(text, index)
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise ValueError(f"unterminated {opener}")


def _skip_backtick(text: str, start: int) -> int:
    index = start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
        elif text[index] == "`":
            return index + 1
        else:
            index += 1
    raise ValueError("unterminated backtick")


def _skip_double(text: str, start: int) -> int:
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
        elif char == '"':
            return index + 1
        elif text.startswith("$(", index):
            index = _skip_group(text, index + 1, "(", ")")
        elif text.startswith("${", index):
            index = _skip_group(text, index + 1, "{", "}")
        elif char == "`":
            index = _skip_backtick(text, index)
        else:
            index += 1
    raise ValueError("unterminated quote")


def _read_double(text: str, start: int) -> tuple[str, bool, int]:
    """Value, whether it expands something, and the index past a double-quoted string."""
    end = _skip_double(text, start)
    value: list[str] = []
    expands = False
    index = start + 1
    while index < end - 1:
        char = text[index]
        if char == "\\":
            following = text[index + 1]
            if following == "\n":
                pass
            elif following in '$`"\\':
                value.append(following)
            else:
                value.append(char + following)
            index += 2
        elif text.startswith("$(", index) or text.startswith("${", index):
            opener = text[index + 1]
            stop = _skip_group(text, index + 1, opener, ")" if opener == "(" else "}")
            value.append(text[index:stop])
            expands = True
            index = stop
        elif char == "`":
            stop = _skip_backtick(text, index)
            value.append(text[index:stop])
            expands = True
            index = stop
        else:
            expands = expands or (char == "$" and text[index + 1] not in ' \t\n"')
            value.append(char)
            index += 1
    return "".join(value), expands, end


def _read_word(text: str, start: int) -> tuple[Word, int]:
    index = start
    value: list[str] = []
    bare: list[str] = []
    bare_expansion = expands = False
    while index < len(text) and text[index] not in WORD_ENDS:
        char = text[index]
        if char == "\\":
            if text[index + 1 : index + 2] != "\n":
                value.append(text[index + 1 : index + 2] or "\\")
                bare.append("\0")
            index += 2
        elif char == "'":
            end = text.find("'", index + 1)
            if end == -1:
                raise ValueError("unterminated quote")
            value.append(text[index + 1 : end])
            bare.append("\0")
            index = end + 1
        elif char == '"':
            inside, inside_expands, index = _read_double(text, index)
            value.append(inside)
            bare.append("\0")
            expands = expands or inside_expands
        elif char == "`":
            end = _skip_backtick(text, index)
            value.append(text[index:end])
            bare.append("$")
            bare_expansion = expands = True
            index = end
        elif char == "$":
            bare_expansion = expands = True
            end = index + 1
            following = text[end : end + 1]
            if following in ("(", "{"):
                end = _skip_group(text, end, following, ")" if following == "(" else "}")
            value.append(text[index:end])
            bare.append("$")
            index = end
        else:
            value.append(char)
            bare.append(char)
            index += 1
    brace = bool(BRACE_EXPANSION.search("".join(bare)))
    return Word("".join(value), bare_expansion or brace, expands or brace), index


def parse_commands(text: str) -> list[Command]:
    """Simple commands of `text` with quoting kept as flags; raises ValueError on bad quoting."""
    commands: list[Command] = []
    current = Command()
    redirect: str | None = None
    index, size = 0, len(text)

    def finish(next_piped: bool = False) -> None:
        nonlocal current, redirect
        if current.words or current.writes or current.here_string is not None:
            commands.append(current)
        current = Command(piped=next_piped)
        redirect = None

    while index < size:
        char = text[index]
        if char in " \t\r":
            index += 1
        elif text.startswith("\\\n", index):
            index += 2
        elif char == "\n":
            finish()
            index += 1
        elif char == "#":
            end = text.find("\n", index)
            index = size if end == -1 else end
        elif char in "<>" and text[index + 1 : index + 2] == "(":
            end = _skip_group(text, index + 1, "(", ")")
            current.inner.append(text[index + 2 : end - 1])
            current.words.append(Word(text[index:end], True, True))
            index = end
        elif char in ";&|()<>":
            operator = next(op for op in OPERATORS if text.startswith(op, index))
            index += len(operator)
            if operator in SEPARATORS:
                finish(operator in ("|", "|&"))
            else:
                redirect = operator
        else:
            word, end = _read_word(text, index)
            digits = text[index:end] == word.text and word.text.isdigit()
            index = end
            if digits and text[index : index + 1] in ("<", ">"):
                continue
            if redirect is None:
                current.words.append(word)
            elif redirect == "<<<":
                current.here_string = word.text
            elif ">" in redirect:
                if not (redirect.endswith("&") and (word.text.isdigit() or word.text == "-")):
                    current.writes.append(word.text)
            elif redirect in ("<", "<&"):
                current.reads.append(word.text)
            redirect = None
    finish()
    return commands


def invocations(command: Command) -> list[tuple[str, list[Word]]]:
    """(program name, its arguments) the command may run.

    One entry normally. Behind `uv` every later word is a candidate program, since `uv run`
    takes options with values and the program comes after them.
    """
    texts = [word.text for word in command.words]
    index = locate_program(texts)
    if index is None:
        return []
    rest = command.words[index + 1 :]
    name = program_name(texts[index])
    found = [(name, rest)]
    if name in ("uv", "uvx"):
        found += [(program_name(word.text), rest[k + 1 :]) for k, word in enumerate(rest)]
    return found


def _walk(text: str, result: Scan, depth: int) -> None:
    result.walks += 1
    if result.overrun or result.walks > MAX_WALKS or time.monotonic() > result.deadline:
        result.overrun = True
        result.unparsed.append(text)
        return
    if depth > MAX_DEPTH:
        result.unparsed.append(text)
        return
    kept, heredocs = split_heredocs(text)
    try:
        commands = parse_commands(kept)
    except ValueError:
        result.unparsed.append(kept)
        commands = []
    for command in commands:
        result.commands.append(command)
        for inner in command.inner:
            _walk(inner, result, depth + 1)
        for name, args in invocations(command):
            texts = [word.text for word in args]
            if name in SHELLS:
                script = shell_script(texts)
                if script is None and not any(not t.startswith("-") for t in texts):
                    script = command.here_string
                if script is not None:
                    _walk(script, result, depth + 1)
            elif name == "eval":
                _walk(" ".join(texts), result, depth + 1)
            elif PYTHON.fullmatch(name):
                code = shell_script(texts)
                if code is not None:
                    result.scripts.append(code)
    for inner in substitutions(kept):
        _walk(inner, result, depth + 1)
    for heredoc in heredocs:
        if heredoc.owner in RUNS_ITS_INPUT:
            _walk(heredoc.body, result, depth + 1)
        elif heredoc.owner and PYTHON.fullmatch(heredoc.owner):
            result.scripts.append(heredoc.body)
        if not heredoc.quoted and heredoc.owner not in RUNS_ITS_INPUT:
            for inner in substitutions(heredoc.body, quoting=False):
                _walk(inner, result, depth + 1)


def scan(text: str) -> Scan:
    """Every simple command in `text`, at any depth: `bash -c`, `eval`, `$(...)`, heredocs.

    The work is bounded (`MAX_WALKS` texts, `WALK_SECONDS`): past it the scan stops with
    `overrun`, because a hook that runs out of time lets the call through.
    """
    result = Scan(deadline=time.monotonic() + WALK_SECONDS)
    _walk(text, result, 0)
    return result
