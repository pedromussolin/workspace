"""Common-word dictionaries of the new-word check: the Debian `wamerican` and `wbrazilian` lists.

A capitalized word at the start of a sentence is probably an ordinary word, so the check lets the
dictionaries clear it there (see `ws.newwords`). The files are looked up in the ws data dir first,
then in `/usr/share/dict/`.

Every function reads; the callers decide what a missing dictionary means.
"""

from dataclasses import dataclass
from pathlib import Path

from ws import config
from ws.names import fold

DATA_SUBDIR = "dict"


@dataclass(frozen=True)
class Source:
    package: str
    filename: str


SOURCES = (Source("wamerican", "american-english"), Source("wbrazilian", "brazilian"))


def data_path() -> Path:
    return config.data_dir() / DATA_SUBDIR


def find(source: Source) -> Path | None:
    """The file of a dictionary: the data dir wins over the system one."""
    for folder in (data_path(), config.system_dict_dir()):
        path = folder / source.filename
        if path.is_file():
            return path
    return None


def missing() -> list[Source]:
    return [source for source in SOURCES if find(source) is None]


def load() -> frozenset[str]:
    """The folded entries of the dictionaries found; empty when there is none.

    Only entries that start with a lowercase letter and hold letters alone count: a capitalized
    entry is a proper noun (a first name) and an apostrophe or hyphen never matches a word.
    """
    words: set[str] = set()
    for source in SOURCES:
        path = find(source)
        if path is None:
            continue
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                entry = line.strip()
                if entry[:1].islower() and entry.isalpha():
                    words.add(fold(entry))
    return frozenset(words)
