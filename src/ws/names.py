"""Names table: real partner names, their fictitious analogs and the company domains to block.

The table lives outside the repo (`names.toml` in the config dir). Matching is accent-insensitive
by turning each letter of a term into a character class, so the regex runs on the original text
and a replacement keeps the offsets.
"""

import json
import re
import tomllib
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from itertools import chain
from pathlib import Path

from ws.config import config_dir

COMBINING_MARKS = r"[\u0300-\u036f]*"
# A name ends where a letter does not continue it. An underscore, a digit and a lowercase to
# uppercase step (camelCase) count as edges, so identifiers such as `acme_theme`, `AcmeTheme`,
# `ACME_API_URL` and `acme2` are found, while `Acmeville` is not. Both edges sit outside the
# case-insensitive group of a term, so they stay case-sensitive.
LEFT_EDGE = r"(?:(?<![^\W\d_])|(?<=[a-z])(?=[A-Z]))"
RIGHT_EDGE = r"(?:(?![^\W\d_])|(?<=[a-z])(?=[A-Z]))"


@dataclass(frozen=True)
class Name:
    real: str
    analog: str
    aliases: tuple[str, ...] = ()
    case_sensitive: bool = False


@dataclass(frozen=True)
class NamesTable:
    names: tuple[Name, ...]
    blocked_domains: tuple[str, ...]


class NamesTableMissing(Exception):
    """The names table does not exist, so there is nothing to check text against."""

    def __init__(self, path: Path):
        super().__init__(f"names table not found at {path}")
        self.path = path


def _parse_name(entry: object, position: int) -> Name:
    if not isinstance(entry, dict):
        raise ValueError(f"names entry {position} is not a table")
    aliases = entry.get("aliases", [])
    case_sensitive = entry.get("case_sensitive", False)
    texts = [entry.get("real"), entry.get("analog"), *aliases] if isinstance(aliases, list) else []
    if not texts or not all(isinstance(text, str) and text.strip() for text in texts):
        raise ValueError(f"names entry {position} needs a non-empty real, analog and aliases")
    if not isinstance(case_sensitive, bool):
        raise ValueError(f"names entry {position}: case_sensitive must be true or false")
    return Name(entry["real"], entry["analog"], tuple(aliases), case_sensitive)


def _parse_domains(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(d, str) and d.strip() for d in value):
        raise ValueError("blocked_domains must be a list of non-empty strings")
    return tuple(value)


def load_names(path: Path | None = None) -> NamesTable:
    if path is None:
        path = config_dir() / "names.toml"
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (FileNotFoundError, NotADirectoryError) as error:
        raise NamesTableMissing(path) from error
    names = tuple(_parse_name(entry, i) for i, entry in enumerate(data.get("names", []), start=1))
    return NamesTable(names, _parse_domains(data.get("blocked_domains", [])))


def fold(text: str) -> str:
    """Lowercase and without accents: the form in which two spellings of a word are compared."""
    text = text.casefold()
    if text.isascii():
        return text
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _toml_string(value: str) -> str:
    # A JSON string is a valid TOML basic string: same escapes, and UTF-8 text stays as is.
    return json.dumps(value, ensure_ascii=False)


def add_name(path: Path, real: str, analog: str, case_sensitive: bool = False) -> None:
    """Append an entry to the names table, leaving the rest of the file and its mode untouched.

    Raises NamesTableMissing when the file does not exist (it is never created here, so a partial
    table cannot replace the fail-closed behavior of the check) and ValueError when the real name
    is empty, already in the table (as a name or alias) or the analog of an entry.
    """
    real = real.strip()
    analog = analog.strip()
    if not real or not analog:
        raise ValueError("a real name and an analog are both needed")
    table = load_names(path)
    if fold(real) == fold(analog):
        raise ValueError("the analog must differ from the real name")
    for name in table.names:
        if fold(real) in {fold(term) for term in (name.real, *name.aliases)}:
            raise ValueError("that name is already in the table")
        if fold(real) == fold(name.analog):
            raise ValueError("that name is the analog of an existing entry")
    entry = f"\n[[names]]\nreal = {_toml_string(real)}\nanalog = {_toml_string(analog)}\n"
    if case_sensitive:
        entry += "case_sensitive = true\n"
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        entry = "\n" + entry
    tomllib.loads(text + entry)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def _accent_variants() -> dict[str, str]:
    variants: dict[str, str] = {}
    for code in chain(range(0xC0, 0x250), range(0x1E00, 0x1F00)):
        char = chr(code)
        decomposed = unicodedata.normalize("NFD", char)
        base = decomposed[0]
        if len(decomposed) > 1 and base.isascii() and base.isalpha():
            variants[base] = variants.get(base, "") + char
    return variants


ACCENT_VARIANTS = _accent_variants()


def _char_pattern(char: str) -> str:
    if char.isspace():
        return r"\s+"
    base = unicodedata.normalize("NFD", char)[0]
    if base.isascii() and base.isalpha():
        return f"[{base}{ACCENT_VARIANTS.get(base, '')}]{COMBINING_MARKS}"
    return re.escape(char)


def _spelled(term: str) -> str:
    return "".join(_char_pattern(char) for char in unicodedata.normalize("NFC", term))


def _term_pattern(term: str, case_sensitive: bool) -> str:
    if not case_sensitive:
        return f"(?i:{_spelled(term)})"
    # A case-sensitive term still matches its all-caps form: a heading, a constant or an env var.
    upper = unicodedata.normalize("NFC", term.upper())
    if upper == unicodedata.normalize("NFC", term):
        return _spelled(term)
    return f"(?:{_spelled(term)}|{_spelled(upper)})"


@lru_cache(maxsize=4)
def _name_matcher(table: NamesTable) -> tuple[re.Pattern[str], dict[str, str]] | None:
    terms = [(term, name) for name in table.names for term in (name.real, *name.aliases)]
    if not terms:
        return None
    terms.sort(key=lambda item: len(item[0]), reverse=True)
    groups = [
        f"(?P<t{i}>{_term_pattern(term, name.case_sensitive)})"
        for i, (term, name) in enumerate(terms)
    ]
    analogs = {f"t{i}": name.analog for i, (_, name) in enumerate(terms)}
    return re.compile(rf"{LEFT_EDGE}(?:{'|'.join(groups)}){RIGHT_EDGE}"), analogs


def real_name_matches(text: str, table: NamesTable) -> list[tuple[int, str]]:
    """Offset and matched text of each real name, in order, so callers can map them to lines."""
    matcher = _name_matcher(table)
    if matcher is None:
        return []
    return [(match.start(), match.group()) for match in matcher[0].finditer(text)]


def find_real_names(text: str, table: NamesTable) -> list[str]:
    return [matched for _, matched in real_name_matches(text, table)]


def blocked_domain_matches(text: str, table: NamesTable) -> list[tuple[int, str]]:
    """Offset and matched text of each blocked domain, in order."""
    if not table.blocked_domains:
        return []
    domains = sorted(table.blocked_domains, key=len, reverse=True)
    regex = re.compile("|".join(re.escape(domain) for domain in domains), re.IGNORECASE)
    return [(match.start(), match.group()) for match in regex.finditer(text)]


def find_blocked_domains(text: str, table: NamesTable) -> list[str]:
    return [matched for _, matched in blocked_domain_matches(text, table)]


def _match_case(matched: str, analog: str) -> str:
    if matched.islower():
        return analog.lower()
    if matched.isupper():
        return analog.upper()
    return analog


def mask_text(text: str, table: NamesTable) -> str:
    matcher = _name_matcher(table)
    if matcher is None:
        return text
    regex, analogs = matcher
    return regex.sub(lambda match: _match_case(match.group(), analogs[match.lastgroup]), text)
