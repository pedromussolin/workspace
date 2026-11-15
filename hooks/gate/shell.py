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

import posixpath
import re
import shlex
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePath

OPERATOR_CHARS = ";()<>|&\n"
REDIRECT_CHARS = "<>"
SHELL_KEYWORDS = {"if", "then", "else", "elif", "while", "until", "do", "!", "{"}
DATA_HEADERS = {"for", "select", "case"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
RUNS_ITS_INPUT = SHELLS | {"eval", "source", "."}
MAX_DEPTH = 8
MAX_WALKS = 2000
WALK_SECONDS = 2.0

ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
PYTHON = re.compile(r"python[0-9.]*")


@dataclass(frozen=True)
class Wrapper:
    """How a program that runs another one reads its own arguments.

    `values`: flags followed by a value. `scripts`: flags whose value is a command line the
    wrapper hands to a shell or splits into a command. `operands`: its own words before the
    program (the `timeout` duration, the `flock` lock file). `joins`: the rest is joined and run by
    `sh -c` (`watch`). `runs_none`: no program follows, only a `scripts` value (`script`).
    """

    values: frozenset[str] = frozenset()
    scripts: frozenset[str] = frozenset()
    operands: int = 0
    joins: bool = False
    runs_none: bool = False


def _flags(text: str) -> frozenset[str]:
    return frozenset(text.split())


WRAPPERS = {
    "env": Wrapper(_flags("-u --unset -C --chdir"), _flags("-S --split-string")),
    "command": Wrapper(),
    "exec": Wrapper(_flags("-a")),
    "time": Wrapper(_flags("-f --format -o --output")),
    "nice": Wrapper(_flags("-n --adjustment")),
    "nohup": Wrapper(),
    "sudo": Wrapper(
        _flags(
            "-u --user -g --group -C --close-from -D --chdir -p --prompt -r --role -t --type "
            "-T --command-timeout -U --other-user -h --host"
        )
    ),
    "builtin": Wrapper(),
    "setsid": Wrapper(),
    "timeout": Wrapper(_flags("-s --signal -k --kill-after"), operands=1),
    "ionice": Wrapper(_flags("-c --class -n --classdata -p --pid -P --pgid -u --uid")),
    "flock": Wrapper(
        _flags("-w --wait --timeout -E --conflict-exit-code"), _flags("-c --command"), operands=1
    ),
    "watch": Wrapper(_flags("-n --interval -q --equexit"), joins=True),
    "stdbuf": Wrapper(_flags("-i --input -o --output -e --error")),
    "script": Wrapper(
        _flags(
            "-E --echo -I --log-in -O --log-out -B --log-io -T --log-timing -m --logging-format"
        ),
        _flags("-c --command"),
        runs_none=True,
    ),
}


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


def _wrapper_flags(
    words: list[str], index: int, wrapper: Wrapper, scripts: list[tuple[int, int, bool]]
) -> int:
    """Index past the flags of a wrapper that start at `index`; script values go to `scripts`."""
    while index < len(words):
        word = words[index]
        if word == "--":
            return index + 1
        if ASSIGNMENT.match(word):
            index += 1
            continue
        if not word.startswith("-"):
            return index
        index += 1
        if word.startswith("--"):
            name, equals, _ = word.partition("=")
            if equals:
                if name in wrapper.scripts:
                    scripts.append((index - 1, len(name) + 1, False))
            elif name in wrapper.values | wrapper.scripts and index < len(words):
                if name in wrapper.scripts:
                    scripts.append((index, 0, False))
                index += 1
            continue
        for offset in range(1, len(word)):
            flag = "-" + word[offset]
            if flag not in wrapper.values | wrapper.scripts:
                continue
            if offset + 1 < len(word):
                if flag in wrapper.scripts:
                    scripts.append((index - 1, offset + 1, False))
            elif index < len(words):
                if flag in wrapper.scripts:
                    scripts.append((index, 0, False))
                index += 1
            break
    return index


def _unwrap(words: list[str]) -> tuple[int | None, list[tuple[int, int, bool]]]:
    """The program's index and the command lines wrappers run on their own.

    Each command line is (word index, offset in that word, whether the words from there on are
    joined into one line, as `watch` does).
    """
    scripts: list[tuple[int, int, bool]] = []
    index = 0
    wrapped = False
    while index < len(words):
        word = words[index]
        if ASSIGNMENT.match(word) or word in SHELL_KEYWORDS:
            index += 1
            continue
        if word in DATA_HEADERS and not wrapped:
            # `for NAME in WORDS` and `case WORD in` are data, with no program; `for NAME do CMD`
            # runs CMD. Behind a wrapper the word is a program name like any other.
            if word != "case" and words[index + 2 : index + 3] == ["do"]:
                index += 2
                continue
            return None, scripts
        wrapper = WRAPPERS.get(PurePath(word).name)
        if wrapper is None:
            return index, scripts
        wrapped = True
        index = _wrapper_flags(words, index + 1, wrapper, scripts)
        index = min(index + wrapper.operands, len(words))
        if index < len(words) and words[index].partition("=")[0] in wrapper.scripts:
            index = _wrapper_flags(words, index, wrapper, scripts)
        if wrapper.runs_none:
            return None, scripts
        if wrapper.joins and index < len(words):
            scripts.append((index, 0, True))
    return None, scripts


def locate_program(words: list[str]) -> int | None:
    """Index of the program a simple command runs, after assignments, keywords and wrappers."""
    return _unwrap(words)[0]


def wrapper_scripts(words: list["Word"]) -> list["Word"]:
    """The command lines that wrappers such as `script -c`, `env -S` and `watch` run."""
    found = []
    for index, offset, joined in _unwrap([word.text for word in words])[1]:
        if joined:
            rest = words[index:]
            found.append(
                Word(
                    " ".join(word.text for word in rest),
                    any(word.bare for word in rest),
                    any(word.expands for word in rest),
                )
            )
        else:
            word = words[index]
            found.append(Word(word.text[offset:], word.bare, word.expands))
    return found


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
    index = next(i for i, word in enumerate(args) if is_c_flag(word.text))
    return args[index + 1]


def is_c_flag(arg: str) -> bool:
    return arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]


# `-R` and `-t` are no-ops that CPython still accepts.
PYTHON_FLAGS = frozenset("bBdEhiIOPqRsStuvVx?")
PYTHON_VALUE_FLAGS = frozenset("WXcm")
PYTHON_LONG_FLAGS = frozenset("--help --version --help-all --help-env --help-xoptions".split())
PYTHON_STDIN_SCRIPT = re.compile(r"/dev/stdin|/dev/fd/\d+|/proc/(?:self|thread-self)/fd/\d+")
# Modules that read stdin as code (a REPL, debugger commands) or run code from it, and modules
# that run another module or script named in their own arguments.
STDIN_CODE_MODULES = frozenset({"code", "asyncio", "pdb", "cProfile", "profile", "trace", "timeit"})
RUNNER_MODULES = frozenset({"pdb", "cProfile", "profile", "trace", "runpy", "doctest"})
STDIN_CODE_CALLS = re.compile(
    r"\b(?:interact|InteractiveConsole|InteractiveInterpreter|breakpoint|set_trace)\b"
)
STDIN_FD = re.compile(r"(?:^|/)fd/\d+$")
PATH_LITERAL = r"""\s*\(\s*(?:\w+\s*=\s*)?[rbuRBU]{0,2}(['"])([^'"\\]*)\1"""
RUN_PATH_CALL = re.compile(r"\brun_path" + PATH_LITERAL)
OPEN_CALL = re.compile(r"\bopen" + PATH_LITERAL)
# `exec`, `eval` and `compile` as bare calls (not `re.compile`), with a read of stdin to feed them.
RUNS_TEXT = re.compile(r"(?<![.\w'\"])(?:exec|eval|compile)\s*\(")
READS_STDIN = re.compile(r"\bstdin\b")
MAX_RUNNER_WORDS = 8
MAX_RUNNER_DEPTH = 2
UV_RUN_VALUES = frozenset(
    "--extra --no-extra --group --no-group --only-group --no-editable-package --env-file -w --with "
    "--with-editable --with-requirements --package --python-platform --index --default-index -i "
    "--index-url --extra-index-url -f --find-links --index-strategy --keyring-provider -P "
    "--upgrade-package --upgrade-group --resolution --prerelease --prerelease-package "
    "--fork-strategy --exclude-newer --exclude-newer-package --no-sources-package "
    "--reinstall-package --link-mode -C --config-setting --config-settings-package "
    "--no-build-isolation-package --no-build-package --no-binary-package --cache-dir "
    "--refresh-package -p --python --color --allow-insecure-host --directory --project "
    "--config-file --python-preference --python-downloads --python-fetch".split()
)


@dataclass(frozen=True)
class PythonProgram:
    """What a `python` command line runs: `kind` is code (`-c`), module (`-m`), script, stdin or
    unknown (an option the table does not know). `word` holds the code, module or script path;
    `args` are the program's own arguments. `procsub`: the script is a process substitution.
    `inspect`: `-i`, so stdin is read as code after the program ends."""

    kind: str
    word: Word | None = None
    args: tuple[Word, ...] = ()
    procsub: bool = False
    inspect: bool = False


def python_source(text: str) -> str:
    """Code as Python reads its names: NFKC-normalized (`𝐰𝐬` is `ws`), without backslash-newlines.

    The shell deletes a backslash-newline in an unquoted heredoc and Python deletes it inside a
    string, so `from w\\` + newline + `s.cli` reaches Python as `ws.cli`.
    """
    return unicodedata.normalize("NFKC", text.replace("\\\n", ""))


def lexical_path(text: str) -> str:
    """An absolute path with `//`, `.` and `..` resolved as text; a relative one as given."""
    if not text.startswith("/"):
        return text
    return posixpath.normpath(re.sub("/+", "/", text))


def stdin_path(text: str) -> bool:
    """A path that may be the standard input: under `/dev` or `/proc`, `…/stdin` or `…fd/N`."""
    return (
        lexical_path(text).startswith(("/dev/", "/proc/"))
        or posixpath.basename(text) == "stdin"
        or bool(STDIN_FD.search(text))
    )


def code_reads_stdin(code: str) -> bool:
    """`-c` code that runs what comes in stdin: a REPL or debugger, `runpy.run_path('/dev/stdin')`,
    or `exec`/`eval`/`compile` with `sys.stdin` or `open('/dev/stdin')`."""
    if STDIN_CODE_CALLS.search(code):
        return True
    if any(stdin_path(found.group(2)) for found in RUN_PATH_CALL.finditer(code)):
        return True
    if not RUNS_TEXT.search(code):
        return False
    return bool(READS_STDIN.search(code)) or any(
        stdin_path(found.group(2)) for found in OPEN_CALL.finditer(code)
    )


def _python_target(rest: list[Word], inspect: bool) -> PythonProgram:
    if not rest:
        return PythonProgram("stdin", inspect=inspect)
    first = rest[0]
    procsub = first.text.startswith("<(")
    if first.text == "-" or procsub or PYTHON_STDIN_SCRIPT.fullmatch(lexical_path(first.text)):
        return PythonProgram("stdin", None, tuple(rest[1:]), procsub, inspect)
    return PythonProgram("script", first, tuple(rest[1:]), inspect=inspect)


def parse_python(args: list[Word]) -> PythonProgram:
    """Python's own argv: options (combined, with attached or separate values), then the program."""
    index = 0
    inspect = False
    while index < len(args):
        word = args[index]
        text = word.text
        if text == "--":
            return _python_target(args[index + 1 :], inspect)
        if text == "-" or not text.startswith("-"):
            return _python_target(args[index:], inspect)
        index += 1
        if text.startswith("--"):
            if text in PYTHON_LONG_FLAGS:
                continue
            if text == "--check-hash-based-pycs" and index < len(args):
                index += 1
                continue
            return PythonProgram("unknown")
        for position, char in enumerate(text[1:], 1):
            if char in PYTHON_FLAGS:
                inspect = inspect or char == "i"
                continue
            if char not in PYTHON_VALUE_FLAGS:
                return PythonProgram("unknown")
            attached = text[position + 1 :]
            if attached:
                value = Word(attached, word.bare, word.expands)
            elif index < len(args):
                value = args[index]
                index += 1
            else:
                return PythonProgram("unknown")
            if char == "c":
                return PythonProgram("code", value, tuple(args[index:]), inspect=inspect)
            if char == "m":
                return PythonProgram("module", value, tuple(args[index:]), inspect=inspect)
            break
    return PythonProgram("stdin", inspect=inspect)


def uv_modules(args: list[Word]) -> list[PythonProgram]:
    """The modules `uv run -m` may run.

    In uv, `-m/--module` is a flag: the module is the first positional word after the options,
    so `-m -q ws.cli` and `-qm ws.cli` run `ws.cli`. A `-m` after that word belongs to the program.
    The text after `m` in a short group (`-mws`) and the word after any `-m` are candidates too,
    as older readings: an option whose value the table does not know would hide the module.
    """
    texts = [word.text for word in args]
    if "run" not in texts:
        return []
    start = texts.index("run") + 1
    found = _uv_first_module(args, start)
    for index in range(start, len(texts) - 1):
        text = texts[index]
        if text == "--module" or (
            text.startswith("-") and not text.startswith("--") and text.endswith("m")
        ):
            candidate = PythonProgram("module", args[index + 1], tuple(args[index + 2 :]))
            if candidate not in found:
                found.append(candidate)
    return found


def _uv_first_module(args: list[Word], index: int) -> list[PythonProgram]:
    """The module `uv run -m` runs as uv reads its options (from `index`), and `-mws`."""
    module = False
    found: list[PythonProgram] = []
    while index < len(args):
        word = args[index]
        text = word.text
        index += 1
        if text == "--":
            if module and index < len(args):
                found.append(PythonProgram("module", args[index], tuple(args[index + 1 :])))
            break
        if text.startswith("--"):
            name, equals, value = text.partition("=")
            if name == "--module":
                module = True
                if equals:
                    attached = Word(value, word.bare, word.expands)
                    found.append(PythonProgram("module", attached, tuple(args[index:])))
            elif name in UV_RUN_VALUES and not equals:
                index += 1
            continue
        if text.startswith("-") and len(text) > 1:
            for position, char in enumerate(text[1:], 1):
                if char == "m":
                    module = True
                    if attached_text := text[position + 1 :]:
                        attached = Word(attached_text, word.bare, word.expands)
                        found.append(PythonProgram("module", attached, tuple(args[index:])))
                    continue
                if "-" + char in UV_RUN_VALUES:
                    if position + 1 == len(text):
                        index += 1
                    break
            continue
        if module:
            found.append(PythonProgram("module", word, tuple(args[index:])))
        break
    return found


def _runner_codes(program: PythonProgram) -> list[str]:
    """Code a runner module takes in its arguments: `timeit` statements, `pdb -c` commands."""
    module = program.word.text if program.kind == "module" and program.word else ""
    args = list(program.args)
    if module == "timeit":
        return ["\n".join(word.text for word in args)]
    if module != "pdb":
        return []
    found = []
    for index, word in enumerate(args):
        text = word.text
        if text in ("-c", "--command") and index + 1 < len(args):
            found.append(args[index + 1].text)
        elif text.startswith("--command="):
            found.append(text.partition("=")[2])
        elif text.startswith("-c") and len(text) > 2:
            found.append(text[2:])
    return found


def _runner_candidates(program: PythonProgram) -> list[PythonProgram]:
    """What a runner module (`-m cProfile`, `-m pdb`, `-m runpy`...) may run from its arguments.

    Their options differ (`trace -c` counts, `pdb -c` takes a command), so every positional word
    among the first ones is taken as the module or the script, with the words after it as its
    arguments.
    """
    if program.kind != "module" or program.word is None or program.word.text not in RUNNER_MODULES:
        return []
    args = list(program.args)
    found = []
    for index, word in enumerate(args):
        if word.text != "-" and word.text.startswith("-"):
            continue
        found.append(PythonProgram("module", word, tuple(args[index + 1 :])))
        found.append(_python_target(args[index:], False))
        if len(found) >= 2 * MAX_RUNNER_WORDS:
            break
    return found


def runner_word_positions(program: PythonProgram) -> int:
    """How many of a runner module's own arguments `_runner_candidates` judges as programs."""
    count = 0
    for position, word in enumerate(program.args):
        if word.text == "-" or not word.text.startswith("-"):
            count += 1
            if count >= MAX_RUNNER_WORDS:
                return position + 1
    return len(program.args)


def expand_python(program: PythonProgram, depth: int = 0) -> list[PythonProgram]:
    """The program and, for a runner module, what it may run in turn."""
    found = [program]
    if depth < MAX_RUNNER_DEPTH:
        for inner in _runner_candidates(program):
            found += expand_python(inner, depth + 1)
    return found


def python_programs(name: str, args: list[Word]) -> list[PythonProgram]:
    """Every Python program a `python` or `uv` invocation may run."""
    if PYTHON.fullmatch(name):
        return expand_python(parse_python(args))
    if name == "uv":
        return [each for module in uv_modules(args) for each in expand_python(module)]
    return []


def python_codes(program: PythonProgram) -> list[str]:
    """The Python code written in the command line for this program."""
    if program.kind == "code" and program.word is not None:
        return [python_source(program.word.text)]
    return [python_source(code) for code in _runner_codes(program)]


def reads_stdin_code(program: PythonProgram, inspect: bool = False) -> bool:
    """Whether the program runs what comes in stdin as code; `inspect`: `PYTHONINSPECT` is set."""
    if program.kind == "stdin" or program.inspect or inspect:
        return True
    if program.kind == "module" and program.word is not None:
        return program.word.text in STDIN_CODE_MODULES
    if program.kind == "code" and program.word is not None:
        return code_reads_stdin(python_source(program.word.text))
    return False


def inspect_variable(commands: list["Command"]) -> bool:
    """`PYTHONINSPECT` is set by one of the commands (`PYTHONINSPECT=1 python3`, `export`)."""
    return any(
        word.text.startswith("PYTHONINSPECT=") for command in commands for word in command.words
    )


@dataclass
class Command:
    words: list[Word] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    piped: bool = False
    reads: list[str] = field(default_factory=list)
    here_string: str | None = None
    here_string_expands: bool = False
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
    """What `scan` found. `overrun`: it gave up on a command too big or too nested to read.
    `depth`: set by the caller, how many command lines inside Python led to this one."""

    commands: list[Command] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    opaque_python: list[str] = field(default_factory=list)
    overrun: bool = False
    walks: int = 0
    deadline: float = 0.0
    depth: int = 0


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
                current.here_string_expands = word.expands
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
        for script in wrapper_scripts(command.words):
            _walk(script.text, result, depth + 1)
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
            for program in python_programs(name, args):
                result.scripts += python_codes(program)
                inspect = inspect_variable(result.commands)
                if command.here_string is not None and reads_stdin_code(program, inspect):
                    result.scripts.append(python_source(command.here_string))
    for inner in substitutions(kept):
        _walk(inner, result, depth + 1)
    for heredoc in heredocs:
        if heredoc.owner in RUNS_ITS_INPUT:
            _walk(heredoc.body, result, depth + 1)
        elif heredoc.owner and (PYTHON.fullmatch(heredoc.owner) or heredoc.owner in ("uv", "uvx")):
            result.scripts.append(python_source(heredoc.body))
            if not heredoc.quoted and ("$" in heredoc.body or "`" in heredoc.body):
                result.opaque_python.append(heredoc.body)
        if not heredoc.quoted and heredoc.owner not in RUNS_ITS_INPUT:
            for inner in substitutions(heredoc.body, quoting=False):
                _walk(inner, result, depth + 1)


def scan(text: str, seconds: float = WALK_SECONDS) -> Scan:
    """Every simple command in `text`, at any depth: `bash -c`, `eval`, `$(...)`, heredocs.

    The work is bounded (`MAX_WALKS` texts, `seconds`): past it the scan stops with `overrun`,
    because a hook that runs out of time lets the call through.
    """
    result = Scan(deadline=time.monotonic() + seconds)
    _walk(text, result, 0)
    return result
