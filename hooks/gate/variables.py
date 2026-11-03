"""Variables that a Bash command assigns itself, resolved before the rules judge it.

Agents write `A="git -C ~/repo"; $A diff; $A log`. The rules cannot read a program word that an
expansion builds, so each of those asked. `worlds(command)` returns the texts to judge instead:
copies of the command where the uses of a variable that the same text assigns a fixed literal
value are replaced by that value, as bash would expand them. `[command]` means nothing was
resolved. The caller judges every text and keeps the strictest decision.

The threat is a model that hides a write behind a variable, so a resolution must never show a
harmless program where bash would run a watched one. Whatever is uncertain stays as written, and
an expansion left in place is judged as before (it asks).

A candidate is a simple command made only of assignment words `NAME=value`, optionally after
`export`, with no redirection, at the top level of the text: not inside `(...)`, `$(...)`,
backticks, `{...}`, a function body or a compound command. Its value, after quote removal, has no
expansion; an unquoted leading `~/` (or a bare `~`) becomes the home, as bash does in assignments,
and any other `~` drops it. A prefix assignment (`X=1 cmd`) is not a candidate: bash does not keep
it. The name is an identifier, absent from the hook's environment (a variable the text does not
assign has the user's profile value) and not one bash treats specially (`IFS`, `PATH`, `HOME`,
`REPLY`, `BASH_*`, ...). The text assigns it exactly once (`NAME=`, `NAME+=`, `NAME[`, heredoc
bodies included); every other occurrence that bash could read as the name (a word of its own,
`{NAME}`, `NAME=`) is `$NAME`, `${NAME}` or a read-only `${NAME...}` form, never `${NAME=...}` or
`${NAME:=...}`, also after quote removal (`read A''B` names `AB`); and no use comes before the
assignment. Part of a longer word (`a.py` for `py`, `-A25` for `A`) is not the name.

Nothing is resolved in a text that mentions `IFS`, `PS4`, `PROMPT_COMMAND`, `BASH_*` or
`allexport`, or holds a control character other than tab and newline; runs `eval`, `source`,
`.`, `trap`, `declare`, `typeset`, `let`, `mapfile`, `alias`, `enable` or `set -a`; uses
arithmetic or subscripts (`((`, `$[`, `x[`, `${x:1}`), `[[`, `case`, `coproc`, `$'...'`,
`$"..."`, `${!x}`, `${x@P}` or `${ cmd; }`; shadows `export` with a function; or hands a builtin
that assigns a variable (`read`, `printf -v`, `unset`, `export`, `local`, `readonly`, `getopts`,
`wait`, `test -v`) a name built by an expansion or a glob, or a flag that hides the name
(`read -a`, `printf -vNAME`). These checks run again on each resolved text, because a resolved
program may turn out to be one of those builtins; any failure keeps the command as written.

A use is replaced only where bash gives the same words: never inside single quotes, heredoc
bodies, comments, backticks, another `${...}`, a heredoc delimiter or a here-string; inside double
quotes when the value has no `"`, `\\`, `$`, `!` or backtick; unquoted when the value holds only
`[A-Za-z0-9_./:@%+=,-]` and spaces, so splitting matches bash and nothing globs, expands a tilde or
a brace. Unquoted, a space needs a use that is a whole word (not glued, not a redirection target),
a piece with `=` must start with `-`, no piece may be a reserved word, the rest of the word holds
no `=`, and an empty value may not leave an assignment or a reserved word as the first word, nor
a word that starts with `#` (a comment) or `~`. Uses inside `$(...)` are replaced: a command
substitution inherits the variable.

An assignment that always runs (nothing joined by `&&` or `||` before it in its list, not in a
pipeline, not in the background) gives one text. Any other gives two, with the value and with the
empty string, because a skipped assignment expands to nothing and the next word becomes the
program: `false && A="git -C x"; $A curl ...` must still ask. Chains resolve in rounds (once `L`
is replaced, `B=$L/backup` is literal). At most `MAX_WORLDS` texts; past the cap the remaining
variables stay as written. The first text holds every value.
"""

import os
import re
import time
from dataclasses import dataclass, field
from itertools import product

from . import shell

MAX_WORLDS = 8
MAX_ROUNDS = 8
MAX_TEXT = 200_000
MAX_GROWTH = 65_536
SECONDS = 1.0

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ASSIGNMENT_WORD = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=")
ASSIGNMENT_LIKE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\+?=")
ASSIGNED = re.compile(r"(?<![A-Za-z0-9_$])([A-Za-z_][A-Za-z0-9_]*)\+?=")
USED = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)")
VALUE_CHAR = re.compile(r"[A-Za-z0-9_./:@%+=,-]")
UNQUOTED = re.compile(r"[A-Za-z0-9_./:@%+=, -]*")
CLOSING_PAREN = re.compile(r"[ \t]*\)")
ANYWHERE = re.compile(r"IFS|PS[0-9]|PROMPT_COMMAND|BASH_|allexport|[\x00-\x08\x0b-\x1f\x7f]")
UNSAFE = re.compile(
    r"[A-Za-z0-9_]\[|\[\[|\(\(|\$\["
    r"|\$\{(?:[\s|!]|[^}]*[@\[]|#?(?:[A-Za-z0-9_]+|[*@#?$!-]):(?![-=?+]))"
    r"|function\s+export(?![A-Za-z0-9_])|(?<![A-Za-z0-9_])export\s*\(\s*\)"
)
NAME_BEFORE = frozenset(" \t\r\n;&|()<>{}!'\"\\`")
NAME_AFTER = frozenset(" \t\r\n;&|()<>}'\"\\`=[$+")
SPECIAL = frozenset(
    """BASH BASHOPTS BASHPID CDPATH CHILD_MAX COLUMNS COPROC DIRSTACK EMACS ENV EPOCHREALTIME
    EPOCHSECONDS EUID EXECIGNORE FCEDIT FIGNORE FUNCNAME FUNCNEST GLOBIGNORE GLOBSORT GROUPS HOME
    HOSTFILE HOSTNAME HOSTTYPE IFS IGNOREEOF INPUTRC INSIDE_EMACS LANG LINENO LINES MACHTYPE MAIL
    MAILCHECK MAILPATH MAPFILE OLDPWD OPTARG OPTERR OPTIND OSTYPE PATH PIPESTATUS POSIXLY_CORRECT
    PPID PROMPT_COMMAND PROMPT_DIRTRIM PS0 PS1 PS2 PS3 PS4 PWD RANDOM REPLY SECONDS SHELL
    SHELLOPTS SHLVL SRANDOM TIMEFORMAT TMOUT TMPDIR UID auto_resume histchars _""".split()
)
SPECIAL_PREFIX = re.compile(r"BASH|COMP_|READLINE_|LC_|HIST")
RESERVED = frozenset(
    "! [[ ]] { } case coproc do done elif else esac fi for function if in select then time "
    "until while".split()
)
OPENERS = {"if": "fi", "for": "done", "select": "done", "while": "done", "until": "done", "{": "}"}
CLOSERS = frozenset(OPENERS.values())
INSIDE_ONLY = frozenset({"then", "do", "else", "elif"})
REFUSED = frozenset({"case", "esac", "coproc", "[[", "]]"})
LEADS_COMMAND = frozenset({"if", "then", "else", "elif", "do", "while", "until", "!", "{", "time"})
SEPARATORS = frozenset({";", "&", "&&", "||", "|", "|&"})
JOINS = frozenset({"&&", "||", "|", "|&"})
WORD_ENDS = frozenset(" \t\r\n;&|()<>")
SPECIAL_PARAMETERS = frozenset("$?!#@*-0123456789")
REPARSERS = frozenset(
    "eval source . trap declare typeset let mapfile readarray alias enable compgen complete "
    "compopt fc bind".split()
)
DECLARES = frozenset({"local", "export", "readonly"})
NAME_TAKERS = frozenset({"read", "unset", "getopts", "wait"})
TESTS = frozenset({"test", "[", "[["})
GLOB_OR_SUBSCRIPT = frozenset("[*?")
EXPORT_FUNCTION = "BASH_FUNC_export%%"


class _GiveUp(Exception):
    """The text cannot be resolved with certainty; it is judged as written."""


@dataclass
class _Word:
    start: int
    end: int
    redirect: str | None
    command: int


@dataclass
class _Use:
    start: int
    end: int
    name: str
    quoted: bool
    word: int = -1


@dataclass
class _Item:
    """A command at the top level: its words, and whether it is a simple one without redirection."""

    words: list[int] = field(default_factory=list)
    simple: bool = True
    redirect: bool = False


class _Layout:
    """One pass over the text, with bash's reading of quotes, heredocs and nesting.

    Collects the uses of `$NAME`/`${NAME}` where a replacement is possible, every word with the
    redirection it is the target of, the top-level commands with the operators between them, and
    the spans that are literal data (`quiet`: single-quoted text, quoted heredoc bodies). A heredoc
    body ends at the exact delimiter line, the longest reading, so no use inside it is replaced;
    as data it ends at the first line that starts with the delimiter, the shortest, so no command
    bash may run is hidden from the checks. Raises `_GiveUp` on anything it does not follow.
    """

    def __init__(self, text: str):
        self.text = text
        self.words: list[_Word] = []
        self.uses: list[_Use] = []
        self.quiet: list[tuple[int, int]] = []
        self.sequence: list[_Item | str] = []
        self.followers: dict[int, list[int]] = {}
        self.pending: list[tuple[str, bool, bool]] = []
        self.commands = 0
        self.program(0, 0)

    def _command(self) -> int:
        self.commands += 1
        self.followers[self.commands] = []
        return self.commands

    def _item(self, item: _Item | None) -> _Item:
        if item is None:
            item = _Item()
            self.sequence.append(item)
        return item

    def program(self, index: int, level: int) -> int:
        """Read commands from `index` to the `)` closing this level, or to the end at level 0."""
        text = self.text
        stack: list[str] = []
        command = self._command()
        leading = True
        redirect: str | None = None
        item: _Item | None = None
        while index < len(text):
            char = text[index]
            top = level == 0 and not stack
            if char in " \t\r":
                index += 1
            elif text.startswith("\\\n", index):
                index += 2
            elif char == "\n":
                if redirect:
                    raise _GiveUp
                if top and not _joined(self.sequence):
                    self.sequence.append("\n")
                    item = None
                command, leading = self._command(), True
                index = self._bodies(index + 1)
            elif char == "#":
                end = text.find("\n", index)
                index = len(text) if end == -1 else end
            elif char == ")" and level > 0 and not stack:
                if redirect:
                    raise _GiveUp
                return index
            elif char in "<>" and text[index + 1 : index + 2] == "(":
                index = self.program(index + 2, level + 1) + 1
                leading, redirect = False, None
            elif char in ";&|()<>":
                operator = next(op for op in shell.OPERATORS if text.startswith(op, index))
                if operator == ";;" or redirect:
                    raise _GiveUp
                if operator in SEPARATORS:
                    if top:
                        self.sequence.append(operator)
                        item = None
                    command, leading = self._command(), True
                    index += len(operator)
                elif operator == "(":
                    if top:
                        item = self._item(item)
                        item.simple = False
                    closing = CLOSING_PAREN.match(text, index + 1)
                    if not leading and closing:
                        index = closing.end()
                    elif leading:
                        stack.append(")")
                        index += 1
                    else:
                        raise _GiveUp
                    leading = True
                elif operator == ")":
                    if not stack or stack[-1] != ")":
                        raise _GiveUp
                    stack.pop()
                    leading = False
                    index += 1
                else:
                    if top:
                        item = self._item(item)
                        item.redirect = True
                    if operator in ("<<", "<<-"):
                        index = self._heredoc(index)
                    else:
                        redirect = operator
                        index += len(operator)
            else:
                start = index
                index, found = self._word(index, level)
                raw = text[start:index]
                if raw.isdigit() and text[index : index + 1] in ("<", ">"):
                    continue
                if top:
                    item = self._item(item)
                    item.words.append(len(self.words))
                if leading and raw in RESERVED:
                    if raw in REFUSED or (raw in INSIDE_ONLY and not stack):
                        raise _GiveUp
                    if item is not None and top:
                        item.simple = False
                    if raw in OPENERS:
                        stack.append(OPENERS[raw])
                    elif raw in CLOSERS:
                        if not stack or stack[-1] != raw:
                            raise _GiveUp
                        stack.pop()
                    leading = raw in LEADS_COMMAND
                else:
                    leading = False
                position = len(self.words)
                self.words.append(_Word(start, index, redirect, command))
                self.followers[command].append(position)
                for use in found:
                    use.word = position
                    self.uses.append(use)
                redirect = None
        if level > 0 or stack or redirect:
            raise _GiveUp
        return index

    def _heredoc(self, index: int) -> int:
        match = shell.HEREDOC_TAG.match(self.text, index + 2)
        if match is None:
            raise _GiveUp
        raw = match.group(2)
        tag = shell.TAG_QUOTING.sub(lambda m: m.group(1) or m.group(2) or m.group(3) or "", raw)
        self.pending.append((tag, tag != raw, bool(match.group(1))))
        return match.end()

    def _bodies(self, index: int) -> int:
        """Skip the bodies of the heredocs opened on the line that just ended."""
        text = self.text
        for tag, quoted, tabs in self.pending:
            start = position = index
            short = None
            after = len(text)
            while position < len(text):
                newline = text.find("\n", position)
                stop = len(text) if newline == -1 else newline
                line = text[position:stop]
                if short is None and line.strip().startswith(tag):
                    short = position
                if (line.lstrip("\t") if tabs else line) == tag:
                    after = len(text) if newline == -1 else newline + 1
                    break
                position = len(text) if newline == -1 else newline + 1
            if quoted:
                self.quiet.append((start, short if short is not None else after))
            index = after
        self.pending = []
        return index

    def _word(self, index: int, level: int) -> tuple[int, list[_Use]]:
        text = self.text
        found: list[_Use] = []
        while index < len(text) and text[index] not in WORD_ENDS:
            char = text[index]
            if char == "\\":
                index += 2
            elif char == "'":
                end = text.find("'", index + 1)
                if end == -1:
                    raise _GiveUp
                self.quiet.append((index + 1, end))
                index = end + 1
            elif char == '"':
                index = self._double(index, level, found)
            elif char == "`":
                index = self._backtick(index)
            elif char == "$":
                index = self._dollar(index, level, False, found)
            else:
                index += 1
        return index, found

    def _double(self, index: int, level: int, found: list[_Use]) -> int:
        text = self.text
        index += 1
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
            elif char == '"':
                return index + 1
            elif char == "`":
                index = self._backtick(index)
            elif char == "$":
                index = self._dollar(index, level, True, found)
            else:
                index += 1
        raise _GiveUp

    def _backtick(self, index: int) -> int:
        text = self.text
        end = index + 1
        while end < len(text):
            if text[end] == "\\":
                end += 2
            elif text[end] == "`":
                if "<<" in text[index:end]:
                    raise _GiveUp
                return end + 1
            else:
                end += 1
        raise _GiveUp

    def _dollar(self, index: int, level: int, quoted: bool, found: list[_Use]) -> int:
        text = self.text
        following = text[index + 1 : index + 2]
        if following == "(":
            if text.startswith("((", index + 1):
                raise _GiveUp
            return self.program(index + 2, level + 1) + 1
        if following == "{":
            try:
                end = shell._skip_group(text, index + 1, "{", "}")
            except ValueError:
                raise _GiveUp from None
            inner = text[index + 2 : end - 1]
            if IDENTIFIER.fullmatch(inner):
                found.append(_Use(index, end, inner, quoted))
            return end
        if following == "[":
            raise _GiveUp
        if following in ("'", '"'):
            if not quoted:
                raise _GiveUp
            return index + 1
        match = IDENTIFIER.match(text, index + 1)
        if match:
            found.append(_Use(index, match.end(), match.group(), quoted))
            return match.end()
        return index + (2 if following and following in SPECIAL_PARAMETERS else 1)

    def next_word(self, position: int) -> str | None:
        """The raw word after `position` in the same simple command, or None."""
        siblings = self.followers[self.words[position].command]
        place = siblings.index(position)
        if place + 1 < len(siblings):
            following = self.words[siblings[place + 1]]
            return self.text[following.start : following.end]
        return None


@dataclass(frozen=True)
class _Candidate:
    name: str
    value: str
    start: int
    always: bool


@dataclass(frozen=True)
class _State:
    text: str
    tried: frozenset[str] = frozenset()
    resolved: frozenset[str] = frozenset()


def _joined(sequence: list) -> bool:
    """Whether the last top-level entry joins the next command (`&&`, `||`, `|`): a newline then
    continues the same list."""
    return bool(sequence) and isinstance(sequence[-1], str) and sequence[-1] in JOINS


def _always(sequence: list, position: int) -> bool:
    """Whether the top-level command at `position` runs in the current shell whatever happens."""
    if _joined(sequence[:position]):
        return False
    following = sequence[position + 1 : position + 2]
    if following and isinstance(following[0], str) and following[0] in ("|", "|&"):
        return False
    for entry in sequence[position + 1 :]:
        if isinstance(entry, str) and entry in (";", "\n"):
            return True
        if isinstance(entry, str) and entry == "&":
            return False
    return True


def _home(text: str) -> str | None:
    """The home a leading `~` stands for, or None when the text may change `HOME`."""
    home = os.environ.get("HOME", "")
    if not home.startswith("/") or not UNQUOTED.fullmatch(home) or " " in home:
        return None
    for match in re.finditer(r"(?<![A-Za-z0-9_])HOME(?![A-Za-z0-9_])", text):
        if not text[: match.start()].endswith(("$", "${")):
            return None
    return home


def _literal(raw: str, home: str | None) -> str | None:
    """The value of an assignment word after quote removal, or None if it expands anything."""
    parts: list[str] = []
    index = 0
    if raw == "~" or raw.startswith("~/"):
        if home is None:
            return None
        parts.append(home)
        index = 1
    while index < len(raw):
        char = raw[index]
        if char == "'":
            end = raw.find("'", index + 1)
            if end == -1:
                return None
            parts.append(raw[index + 1 : end])
            index = end + 1
        elif char == '"':
            end = raw.find('"', index + 1)
            if end == -1 or set(raw[index + 1 : end]) & set("$`\\"):
                return None
            parts.append(raw[index + 1 : end])
            index = end + 1
        elif VALUE_CHAR.fullmatch(char):
            parts.append(char)
            index += 1
        else:
            return None
    value = "".join(parts)
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    return value


def _candidates(layout: _Layout, home: str | None) -> list[_Candidate]:
    text = layout.text
    found = []
    for position, entry in enumerate(layout.sequence):
        if not isinstance(entry, _Item) or not entry.simple or entry.redirect or not entry.words:
            continue
        raws = [text[layout.words[i].start : layout.words[i].end] for i in entry.words]
        starts = [layout.words[i].start for i in entry.words]
        if raws[0] == "export":
            if EXPORT_FUNCTION in os.environ:
                continue
            raws, starts = raws[1:], starts[1:]
        if not raws or not all(ASSIGNMENT_WORD.match(raw) for raw in raws):
            continue
        always = _always(layout.sequence, position)
        for raw, start in zip(raws, starts, strict=True):
            name = raw.partition("=")[0]
            value = _literal(raw[len(name) + 1 :], home)
            if value is not None:
                found.append(_Candidate(name, value, start, always))
    return found


def _kind(text: str, start: int, end: int) -> str:
    """How bash may read the identifier at `text[start:end]`.

    `use`: `$NAME`, `${NAME}` or `${NAME...}`; `ambiguous`: such a form after another `$` or a
    backslash; `name`: a word of its own, `NAME=`, `NAME[`, `{NAME}` or next to a quote, where a
    builtin or an assignment may take it as a name; `part`: inside a longer word (`a.py`).
    """
    before = text[max(0, start - 3) : start]
    opener = next((o for o in ("${#", "${!", "${", "$") if before.endswith(o)), None)
    if opener is not None:
        dollar = start - len(opener)
        return "ambiguous" if text[dollar - 1 : dollar] in ("$", "\\") and dollar else "use"
    previous = text[start - 1 : start]
    following = text[end : end + 1]
    if (not previous or previous in NAME_BEFORE) and (not following or following in NAME_AFTER):
        return "name"
    return "part"


def _occurrences_fit(name: str, text: str) -> bool:
    """Exactly one assignment of `name`; every other occurrence a use or a read-only form."""
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])")
    for each in (text, text.replace("\\\n", "")):
        assignments = 0
        for match in pattern.finditer(each):
            kind = _kind(each, match.start(), match.end())
            after = each[match.end() : match.end() + 2]
            braced = each[match.start() - 1] != "$"
            if kind == "ambiguous":
                return False
            if kind == "use" and braced and after.startswith(("=", ":=")):
                return False
            if kind == "name":
                if not after.startswith(("=", "+=", "[")):
                    return False
                assignments += 1
        if assignments != 1:
            return False
    return True


def _name_fits(name: str, text: str, start: int) -> bool:
    if name in os.environ or name in SPECIAL or SPECIAL_PREFIX.match(name):
        return False
    if re.search(rf"\$\{{?[#!]?{name}(?![A-Za-z0-9_])", text[:start]):
        return False
    return _occurrences_fit(name, text)


def _fits(layout: _Layout, use: _Use, value: str) -> bool:
    """Whether bash gives the same words for this use and for `value` written in its place."""
    if use.quoted:
        return not set(value) & set('"\\$`!')
    if not UNQUOTED.fullmatch(value):
        return False
    text = layout.text
    word = layout.words[use.word]
    before, after = text[word.start : use.start], text[use.end : word.end]
    pieces = value.split()
    if any(piece in RESERVED for piece in pieces):
        return False
    if any("=" in piece and not piece.startswith("-") for piece in pieces):
        return False
    if "=" in after or "~" in before or set(before + after) & set("{}"):
        return False
    if not before and not value and after[:1] in ("#", "~"):
        # The word would start with `#` (a comment hiding the rest of the line) or `~`.
        return False
    if word.redirect is not None and ("<<" in word.redirect or not value.strip() or " " in value):
        return False
    whole = not before and not after
    glued_redirect = text[word.end : word.end + 1] in ("<", ">")
    if " " in value and (not whole or glued_redirect):
        return False
    if value and glued_redirect and not after:
        return False
    if whole and not value.strip():
        following = layout.next_word(use.word)
        if following is not None and (ASSIGNMENT_LIKE.match(following) or following in RESERVED):
            return False
    return True


def _round(state: _State, room: int) -> tuple[list[_State], int]:
    """One round of resolution of one text: the texts it becomes and the room left."""
    text = state.text
    layout = _Layout(text)
    home = _home(text)
    plans = []
    tried = set(state.tried)
    copies = 1
    for candidate in _candidates(layout, home):
        name, value = candidate.name, candidate.value
        if name in tried:
            continue
        tried.add(name)
        if not _name_fits(name, text, candidate.start):
            continue
        uses = [use for use in layout.uses if use.name == name]
        options = [[(u.start, u.end, value) for u in uses if _fits(layout, u, value)]]
        if not candidate.always:
            options.append([(u.start, u.end, "") for u in uses if _fits(layout, u, "")])
        if not any(options):
            continue
        if not candidate.always:
            if copies > room:
                continue
            room -= copies
            copies *= 2
        plans.append((name, options))
    if not plans:
        return [_State(text, frozenset(tried), state.resolved)], room
    resolved = state.resolved | {name for name, _ in plans}
    children = []
    for combination in product(*(options for _, options in plans)):
        new = text
        replacements = sorted((r for chosen in combination for r in chosen), reverse=True)
        for start, end, value in replacements:
            new = new[:start] + value + new[end:]
        children.append(_State(new, frozenset(tried), resolved))
    return children, room


def _resolve(command: str, deadline: float) -> list[_State]:
    states = [_State(command)]
    for _ in range(MAX_ROUNDS):
        room = MAX_WORLDS - len(states)
        following: list[_State] = []
        for state in states:
            if time.monotonic() > deadline:
                raise _GiveUp
            children, room = _round(state, room)
            following += children
        if any(len(state.text) > len(command) + MAX_GROWTH for state in following):
            raise _GiveUp
        if [state.text for state in following] == [state.text for state in states]:
            return following
        states = following
    return states


def _hides_a_name(words: list[shell.Word]) -> bool:
    """A word that could name any variable: built by an expansion, a glob or a subscript."""
    return any(word.expands or set(word.text) & GLOB_OR_SUBSCRIPT for word in words)


def _printf_target(args: list[shell.Word]) -> bool:
    """Whether `printf` may assign a variable whose name the text does not show as a word."""
    if args and args[0].expands:
        return True
    for position, word in enumerate(args):
        if not word.text.startswith("-") or word.text == "--":
            return False
        if word.text.startswith("-v"):
            if word.text != "-v" or position + 1 >= len(args):
                return True
            target = args[position + 1]
            if target.expands or not IDENTIFIER.fullmatch(target.text):
                return True
    return False


def _changes_variables(command: shell.Command) -> bool:
    """Whether a command may assign a variable in a way the text does not show."""
    texts = [word.text for word in command.words]
    index = shell.locate_program(texts)
    if index is None:
        return False
    name = shell.program_name(texts[index])
    args = command.words[index + 1 :]
    flags = [word.text for word in args if word.text.startswith("-")]
    if name in REPARSERS:
        return True
    if name == "set":
        for word in args:
            if word.text == "--":
                break
            if word.expands or re.match(r"[-+][A-Za-z]*a", word.text):
                return True
        return False
    if name in DECLARES:
        return any(
            word.text.startswith("-")
            or not IDENTIFIER.fullmatch(word.text.partition("=")[0])
            or (word.expands and "=" not in word.text)
            for word in args
        )
    if name in NAME_TAKERS:
        hidden = {"read": "a", "wait": "p"}.get(name)
        return _hides_a_name(args) or bool(hidden and any(hidden in flag for flag in flags))
    if name == "printf":
        return _printf_target(args)
    if name in TESTS:
        return any(word.text in ("-v", "-R") for word in args) or (
            any(word.expands for word in args) and any("[" in word.text for word in args)
        )
    return False


def _bare_words(name: str, scan: shell.Scan) -> int:
    """How many parsed words, after quote removal, hold `name` where it may be read as a name."""
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])")
    count = 0
    for command in scan.commands:
        for word in command.words:
            for match in pattern.finditer(word.text):
                if _kind(word.text, match.start(), match.end()) in ("name", "ambiguous"):
                    count += 1
    return count


def _blank(text: str, spans: list[tuple[int, int]]) -> str:
    characters = list(text)
    for start, end in spans:
        for index in range(start, min(end, len(text))):
            if characters[index] != "\n":
                characters[index] = " "
    return "".join(characters)


def _check(text: str, deadline: float, names: frozenset[str] = frozenset()) -> None:
    """Raise `_GiveUp` when the text may assign a variable in a way the resolution cannot see."""
    if ANYWHERE.search(text):
        raise _GiveUp
    layout = _Layout(text)
    if UNSAFE.search(_blank(text, layout.quiet)):
        raise _GiveUp
    left = deadline - time.monotonic()
    if left <= 0:
        raise _GiveUp
    scan = shell.scan(text, left)
    if scan.overrun or scan.unparsed:
        raise _GiveUp
    if any(_changes_variables(command) for command in scan.commands):
        raise _GiveUp
    for name in names:
        if _bare_words(name, scan) != 1 or not _occurrences_fit(name, text):
            raise _GiveUp


def _worth_trying(command: str) -> bool:
    if len(command) > MAX_TEXT:
        return False
    assigned = set(ASSIGNED.findall(command))
    return any(name in assigned for name in USED.findall(command))


def worlds(command: str) -> list[str]:
    """The texts to judge instead of `command`, the one with every value first."""
    if not _worth_trying(command):
        return [command]
    deadline = time.monotonic() + SECONDS
    try:
        _check(command, deadline)
        states = _resolve(command, deadline)
        if all(state.text == command for state in states):
            return [command]
        texts: list[str] = []
        for state in states:
            _check(state.text, deadline, state.resolved)
            if state.text not in texts:
                texts.append(state.text)
        return texts
    except (_GiveUp, RecursionError):
        return [command]
