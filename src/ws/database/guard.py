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
    "replace",
)
PLACEHOLDERS = ("day", "day_from", "day_to")
PLACEHOLDER = re.compile(r"(?<!:):([A-Za-z_]\w*)")
QUOTED_PLACEHOLDER = re.compile(r"(?<!:):\Z")
QUOTED = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|['\"]")
WORD = re.compile(r"[A-Za-z_]\w*")
CALL = re.compile(r"\s*\(")
FIRST_WORDS = ("select", "with")
PLACEHOLDER_HINT = "use :day, :day_from or :day_to"
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
    _check_words(pieces, rules)
    return text, _placeholders(pieces)


def _check_words(pieces: list[tuple[str, str]], rules: Rules) -> None:
    """Words of the code, and a quoted identifier called as a function (`"name"(...)`)."""
    words = set(WORDS) | {word.lower() for word in rules.words}
    prefixes = tuple(prefix.lower() for prefix in rules.prefixes)
    for index, (kind, text) in enumerate(pieces):
        if kind == "code":
            names = [match.group() for match in WORD.finditer(text)]
        elif kind == "identifier" and _called(pieces, index):
            names = [text[1:-1].replace('""', '"')]
        else:
            continue
        for name in names:
            lowered = name.lower()
            if lowered in words:
                raise Refused(f'"{lowered}" is not allowed outside a literal')
            for prefix in prefixes:
                if lowered.startswith(prefix):
                    raise Refused(f"words starting with {prefix} are not allowed")


def _called(pieces: list[tuple[str, str]], index: int) -> bool:
    following = pieces[index + 1] if index + 1 < len(pieces) else None
    return following is not None and following[0] == "code" and bool(CALL.match(following[1]))


def _placeholders(pieces: list[tuple[str, str]]) -> tuple[str, ...]:
    used = set()
    for index, (kind, text) in enumerate(pieces):
        if kind != "code":
            continue
        for match in PLACEHOLDER.finditer(text):
            name = match.group(1)
            if name not in PLACEHOLDERS:
                raise Refused(f"unknown placeholder :{name}; {PLACEHOLDER_HINT}")
            used.add(name)
        if index + 1 < len(pieces) and QUOTED_PLACEHOLDER.search(text):
            raise Refused(f"quoted placeholders are not allowed; {PLACEHOLDER_HINT}")
    return tuple(name for name in PLACEHOLDERS if name in used)
