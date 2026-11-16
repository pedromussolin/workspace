"""The neutral SQL guard: one read-only `select` or `with` statement, checked before any run.

It knows standard SQL quoting only: `'...'` literals and `"..."` identifiers, each escaped by
doubling. An engine whose own quoting goes further refuses the characters that open it through
`Rules.marks`, which are checked over the whole text. The guard narrows what reaches the database;
the read-only session of the adapter is still what keeps it from writing.
"""

import re

from ws.database.port import Refused, Rules

WORDS = (
    "insert",
    "update",
    "delete",
    "merge",
    "truncate",
    "drop",
    "alter",
    "create",
    "grant",
    "revoke",
    "call",
    "execute",
    "set",
    "reset",
    "lock",
    "begin",
    "commit",
    "rollback",
    "savepoint",
    "into",
)
PLACEHOLDERS = ("day", "day_from", "day_to")
PLACEHOLDER = re.compile(r"(?<!:):([A-Za-z_]\w*)")
QUOTED_PLACEHOLDER = re.compile(r"(?<!:):\Z")
COLONS = re.compile(r":{3,}")
BRACED_PLACEHOLDER = re.compile(r":\{")
QUOTED = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|['\"]")
WORD = re.compile(r"[A-Za-z_]\w*")
CALL = re.compile(r"\s*\(")
ATTRIBUTE = re.compile(r"\.\s*(?:[Uu]&)?\Z")
FIRST_WORDS = ("select", "with")
PLACEHOLDER_HINT = "use :day, :day_from or :day_to"
COLUMN_HINT = "quote a column named like a refused word"
NO_RULES = Rules()


def split(sql: str) -> list[tuple[str, str]]:
    """The text as `code`, `literal` and `identifier` pieces; each keeps its quotes, so joining
    the pieces gives the text back."""
    pieces = []
    start = 0
    for match in QUOTED.finditer(sql):
        text = match.group()
        if len(text) == 1:
            raise Refused("unclosed literal or quoted identifier")
        if match.start() > start:
            pieces.append(("code", sql[start : match.start()]))
        pieces.append(("literal" if text[0] == "'" else "identifier", text))
        start = match.end()
    if start < len(sql):
        pieces.append(("code", sql[start:]))
    return pieces


def guard(sql: str, rules: Rules = NO_RULES) -> tuple[str, tuple[str, ...]]:
    """The SQL without its last `;` and the placeholders it uses, or `Refused`."""
    for mark in rules.marks:
        if mark in sql:
            raise Refused(f'"{mark}" is not allowed')
    pieces = split(sql.strip())
    if any("--" in text or "/*" in text for kind, text in pieces if kind == "code"):
        raise Refused("comments are not allowed")
    if pieces and pieces[-1][0] == "code" and pieces[-1][1].endswith(";"):
        pieces[-1] = ("code", pieces[-1][1][:-1])
    if any(";" in text for kind, text in pieces if kind == "code"):
        raise Refused("only one statement is allowed")
    text = "".join(piece for _, piece in pieces).strip()
    if not text:
        raise Refused("the query is empty")
    first = WORD.match(text)
    if first is None or first.group().lower() not in FIRST_WORDS:
        raise Refused("the query must start with select or with")
    pieces = split(text)
    _check_parentheses(pieces)
    _check_words(pieces, rules)
    return text, _placeholders(pieces)


def _check_parentheses(pieces: list[tuple[str, str]]) -> None:
    """Balanced code keeps the query inside the one subquery an engine may wrap it in."""
    depth = 0
    for kind, text in pieces:
        if kind != "code":
            continue
        for char in text:
            depth += {"(": 1, ")": -1}.get(char, 0)
            if depth < 0:
                raise Refused("parentheses are not balanced")
    if depth:
        raise Refused("parentheses are not balanced")


def _check_words(pieces: list[tuple[str, str]], rules: Rules) -> None:
    """Words of the code, and a quoted identifier that may name a function: one called as
    `"name"(...)`, or one after a dot, since `(value)."name"` calls `name(value)`."""
    words = set(WORDS) | {word.lower() for word in rules.words}
    prefixes = tuple(prefix.lower() for prefix in rules.prefixes)
    for index, (kind, text) in enumerate(pieces):
        if kind == "code":
            for match in WORD.finditer(text):
                _check_name(match.group().lower(), words, prefixes, f"; {COLUMN_HINT}: ")
        elif kind == "identifier" and (_called(pieces, index) or _after_dot(pieces, index)):
            _check_name(text[1:-1].replace('""', '"').lower(), words, prefixes, None)


def _check_name(name: str, words: set[str], prefixes: tuple[str, ...], hint: str | None) -> None:
    advice = "" if hint is None else f'{hint}"{name}"'
    if name in words:
        raise Refused(f'"{name}" is not allowed outside a literal{advice}')
    for prefix in prefixes:
        if name.startswith(prefix):
            raise Refused(f"words starting with {prefix} are not allowed{advice}")


def _called(pieces: list[tuple[str, str]], index: int) -> bool:
    following = pieces[index + 1] if index + 1 < len(pieces) else None
    return following is not None and following[0] == "code" and bool(CALL.match(following[1]))


def _after_dot(pieces: list[tuple[str, str]], index: int) -> bool:
    before = pieces[index - 1] if index > 0 else None
    return before is not None and before[0] == "code" and bool(ATTRIBUTE.search(before[1]))


def _placeholders(pieces: list[tuple[str, str]]) -> tuple[str, ...]:
    used = set()
    for index, (kind, text) in enumerate(pieces):
        if kind != "code":
            continue
        if COLONS.search(text):
            raise Refused("three or more colons in a row are not allowed; use :: for a cast")
        if BRACED_PLACEHOLDER.search(text):
            raise Refused(f"placeholders with braces are not allowed; {PLACEHOLDER_HINT}")
        for match in PLACEHOLDER.finditer(text):
            name = match.group(1)
            if name not in PLACEHOLDERS:
                raise Refused(f"unknown placeholder :{name}; {PLACEHOLDER_HINT}")
            used.add(name)
        if index + 1 < len(pieces) and QUOTED_PLACEHOLDER.search(text):
            raise Refused(f"quoted placeholders are not allowed; {PLACEHOLDER_HINT}")
    return tuple(name for name in PLACEHOLDERS if name in used)
