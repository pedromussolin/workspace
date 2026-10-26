"""New-word check: capitalized words that the pushed state has not seen yet.

A real name that is not in `names.toml` yet looks like any other capitalized word, so the check
lists every capitalized word of the added lines and of the commit messages that is not already
known. The pending list is computed each time; nothing is stored.

The code of the ws CLI is not checked (see SKIPPED_PATHS); notes, docs and messages are.

A word is known (compared lowercased and without accents) when it appears in the text of the
pushed state, is listed in `.known-words` or is an analog in `names.toml`. A real name that is
already in `names.toml` is not reported: `ws check-secrets` blocks it.

Every function here reads or reports; the hooks and `ws names` decide what to do with the result.
Errors are never swallowed here, so callers can fail closed.
"""

import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from ws import secrets
from ws.names import NamesTable, fold, real_name_matches

KNOWN_WORDS_FILE = ".known-words"
KNOWN_WORDS_HEADER = """\
# Harmless capitalized words (tools, products, acronyms) that `ws names check` should not report
# as new. One word per line; lines starting with # are comments, so a reason goes above it.
#
# The check compares lowercase and without accents, so `Celery` also covers `CELERY` and `celery`.
# A word is also known when it already appears in the text of the pushed state (origin/main),
# and when it is an analog in names.toml, so only words that are new to the repo belong here.
#
# Only harmless words go in this file, and only after the user answered for each one: a real name
# goes to names.toml with `ws names add`, never here. The file is read from the commit being
# pushed (from the index when committing), so an entry counts once it is committed.
"""
MIN_LETTERS = 3
LETTER_RUNS = re.compile(rf"[^\W\d_]{{{MIN_LETTERS},}}")
SINGLE_WORD = re.compile(r"[^\W\d_]+")
SYMLINK_MODE = "120000"
# Where the places of a word are listed in a report; the rest is counted.
REPORT_PLACES = 3
DEFAULT_BASES = ("@{upstream}", "origin/main")
# The code of the ws CLI: English, written by us, and its tests use made-up names on purpose. It
# is left out of this check only; ws check-secrets still reads it for the names of the table.
SKIPPED_PATHS = ("src/", "tests/", "hooks/", ".githooks/")


@dataclass(frozen=True)
class Place:
    path: str
    line: int
    commit: str = ""

    def __str__(self) -> str:
        where = f"{self.commit[:10]}:" if self.commit else ""
        return f"{where}{self.path}:{self.line}"


@dataclass(frozen=True)
class NewWord:
    word: str
    places: tuple[Place, ...]


@dataclass(frozen=True)
class Known:
    """What makes a word not new, and the table used to leave real names to ws check-secrets."""

    table: NamesTable
    words: frozenset[str]

    def is_known(self, word: str) -> bool:
        return fold(word) in self.words or bool(real_name_matches(word, self.table))


def _parts(run: str) -> list[str]:
    """Split a run of letters at camelCase edges: `HTTPServer` gives `HTTP` and `Server`."""
    if run.islower() or run.isupper():
        return [run]
    parts = []
    start = 0
    for index in range(1, len(run)):
        if not run[index].isupper():
            continue
        previous = run[index - 1]
        acronym_ends = previous.isupper() and index + 1 < len(run) and run[index + 1].islower()
        if previous.islower() or acronym_ends:
            parts.append(run[start:index])
            start = index
    parts.append(run[start:])
    return parts


def words_of(text: str) -> Iterator[str]:
    """The words of three letters or more; digits, underscores and camelCase edges split them."""
    if not text.isascii():
        text = unicodedata.normalize("NFC", text)
    for run in LETTER_RUNS.findall(text):
        for part in _parts(run):
            if len(part) >= MIN_LETTERS:
                yield part


def capitalized_words(text: str) -> Iterator[str]:
    return (word for word in words_of(text) if word[0].isupper())


def parse_known_words(text: str) -> frozenset[str]:
    words = set()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = unicodedata.normalize("NFC", raw.strip())
        if not line or line.startswith("#"):
            continue
        if not SINGLE_WORD.fullmatch(line):
            raise ValueError(f"{KNOWN_WORDS_FILE} line {number}: expected one word, letters only")
        words.add(fold(line))
    return frozenset(words)


def read_known_words(repo: Path, tree: str = "") -> frozenset[str]:
    """`.known-words` as staged (no tree) or as committed at a revision."""
    if tree:
        secrets._git(repo, "rev-parse", "--verify", f"{tree}^{{commit}}")
    (data,) = secrets._read_objects(repo, [f"{tree}:{KNOWN_WORDS_FILE}"])
    return frozenset() if data is None else parse_known_words(data.decode("utf-8"))


def add_known_words(repo: Path, words: Iterable[str]) -> tuple[list[str], list[str]]:
    """Append words to the work-tree `.known-words`; returns (added, already listed)."""
    path = repo / KNOWN_WORDS_FILE
    text = path.read_text(encoding="utf-8") if path.is_file() else KNOWN_WORDS_HEADER
    listed = set(parse_known_words(text))
    added: list[str] = []
    skipped: list[str] = []
    for word in words:
        word = unicodedata.normalize("NFC", word.strip())
        if not SINGLE_WORD.fullmatch(word):
            raise ValueError(f"{word!r} is not a single word of letters")
        if fold(word) in listed:
            skipped.append(word)
        else:
            listed.add(fold(word))
            added.append(word)
    if added:
        separator = "" if text.endswith("\n") else "\n"
        path.write_text(text + separator + "".join(f"{word}\n" for word in added), "utf-8")
    return added, skipped


def _analog_words(table: NamesTable) -> frozenset[str]:
    return frozenset(fold(word) for name in table.names for word in words_of(name.analog))


def _blob_ids(repo: Path, rev: str) -> list[str]:
    out = secrets._git(repo, "ls-tree", "-r", "-z", "--full-tree", rev)
    ids = []
    for record in out.split(b"\0"):
        if record:
            meta, _, _path = record.partition(b"\t")
            mode, kind, oid = meta.decode().split(" ")
            if kind == "blob" and mode != SYMLINK_MODE:
                ids.append(oid)
    return ids


def vocabulary(repo: Path, rev: str) -> frozenset[str]:
    """Every word (folded) of the tracked text files at a revision; binary files are skipped."""
    words: set[str] = set()
    for data in secrets._read_objects(repo, _blob_ids(repo, rev)):
        if data is None:
            raise RuntimeError(f"an object of {rev} is missing")
        text = secrets._decode(data)
        if text is not None:
            words.update(fold(word) for word in set(words_of(text)))
    return frozenset(words)


def make_known(repo: Path, table: NamesTable, against: str | None, listed: frozenset[str]) -> Known:
    """`against` is the revision whose text is the vocabulary; None means nothing is pushed."""
    pushed = frozenset() if against is None else vocabulary(repo, against)
    return Known(table, pushed | listed | _analog_words(table))


def resolve_base(repo: Path) -> str | None:
    """What the current branch would be pushed over: its upstream, else origin/main, else None."""
    for candidate in DEFAULT_BASES:
        try:
            secrets._git(repo, "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}")
        except RuntimeError:
            continue
        return candidate
    return None


def _text_hits(
    path: str, text: str, only_lines: set[int] | None, known: Known, commit: str = ""
) -> Iterator[tuple[str, Place]]:
    # Only "\n" ends a line, as in git, so the numbers match the diff.
    for number, line in enumerate(text.split("\n"), start=1):
        if only_lines is None or number in only_lines:
            for word in capitalized_words(line):
                if not known.is_known(word):
                    yield word, Place(path, number, commit)


def _file_hits(
    name: str, data: bytes, only_lines: set[int] | None, known: Known, commit: str = ""
) -> Iterator[tuple[str, Place]]:
    if name.startswith(SKIPPED_PATHS):
        return
    text = secrets._decode(data)
    if text is None:
        return
    if data.startswith(tuple(bom for bom, _ in secrets.WIDE_BOMS)):
        # Git counts lines by the 0x0A byte, which is not always a line break in these encodings.
        only_lines = None
    yield from _text_hits(name, text, only_lines, known, commit)


def group(hits: Iterable[tuple[str, Place]]) -> list[NewWord]:
    """One entry per word (by its folded form), in order of appearance, with its places."""
    grouped: dict[str, tuple[str, dict[Place, None]]] = {}
    for word, place in hits:
        _, places = grouped.setdefault(fold(word), (word, {}))
        places[place] = None
    return [NewWord(word, tuple(places)) for word, places in grouped.values()]


def check_staged(repo: Path, table: NamesTable, against: str | None) -> list[NewWord]:
    """New words of the staged added lines; `.known-words` is the staged one."""
    known = make_known(repo, table, against, read_known_words(repo))
    entries = secrets._index_entries(repo)
    hits = []
    for name, data, only_lines in secrets._sources(repo, "staged", None, entries):
        hits.extend(_file_hits(name, data, only_lines, known))
    return group(hits)


def check_message(repo: Path, text: str, table: NamesTable, against: str | None) -> list[NewWord]:
    """New words of a commit message file, without the lines git drops."""
    known = make_known(repo, table, against, read_known_words(repo))
    text = secrets._without_comments(text)
    return group(_text_hits(secrets.MESSAGE_PATH, text, None, known))


def check_range(
    repo: Path, revs: list[str], table: NamesTable, against: str | None, tip: str = "HEAD"
) -> list[NewWord]:
    """New words of the added lines and the message of each commit in a rev-list expression.

    A merge adds no lines of its own: the commits it brings are in the range themselves.
    `.known-words` is the one committed at `tip`, so a word answered in the pushed commits counts.
    """
    if not revs:
        raise ValueError("a revision range is needed")
    known = make_known(repo, table, against, read_known_words(repo, tip))
    hits: list[tuple[str, Place]] = []
    for commit in secrets._range_commits(repo, revs):
        hits.extend(_text_hits(secrets.MESSAGE_PATH, commit.message, None, known, commit.sha))
        if commit.is_merge:
            continue
        diff = secrets._git(repo, "show", "--format=", *secrets.DIFF_FLAGS, commit.sha)
        additions = secrets.parse_additions(diff.decode("utf-8", errors="replace"))
        contents = secrets._read_objects(repo, [f"{commit.sha}:{name}" for name in additions])
        for (name, only_lines), data in zip(additions.items(), contents, strict=True):
            if data is None:
                raise RuntimeError(f"{name} is missing in commit {commit.sha}")
            hits.extend(_file_hits(name, data, only_lines, known, commit.sha))
    return group(hits)


def default_scope(repo: Path) -> tuple[list[str], str | None]:
    """The unpushed commits and the revision whose text is the vocabulary."""
    base = resolve_base(repo)
    return ([f"{base}..HEAD"] if base else ["HEAD"]), base


def format_places(item: NewWord, limit: int = REPORT_PLACES) -> str:
    shown = ", ".join(str(place) for place in item.places[:limit])
    more = len(item.places) - limit
    return f"{shown} (+{more} more)" if more > 0 else shown


def format_report(words: list[NewWord], blocking: bool) -> list[str]:
    lines = [f"{len(words)} new word(s), not in the pushed state, .known-words or names.toml:"]
    lines.extend(f"  {item.word}: {format_places(item)}" for item in words)
    lines.append(
        "Ask the user about each word: a real name goes in with `ws names add REAL --analog "
        "ANALOG`, a harmless one with `ws names known WORD...` (`ws names review` asks in the "
        "terminal)."
    )
    lines.append(
        "The push is blocked until each word is answered."
        if blocking
        else "The commit goes through; the push is blocked until each word is answered."
    )
    return lines
