"""Draft files of `ws card`: TOML front matter between `+++` lines, then a Markdown body."""

import hashlib
import re
import tomllib
from dataclasses import dataclass
from datetime import date

OPS = ("create", "edit", "move", "comment", "worklog")

REQUIRED = {
    "create": {"epic", "priority", "due"},
    "edit": {"key"},
    "move": {"key", "to"},
    "comment": {"key"},
    "worklog": {"key", "time"},
}
OPTIONAL = {
    "create": {"start"},
    "edit": {"title", "priority", "start", "due", "epic"},
    "move": set(),
    "comment": set(),
    "worklog": {"day"},
}
DATE_KEYS = {"start", "due", "day"}

_DATE_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FENCE = "+++"


class DraftError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Draft:
    op: str
    values: dict
    title: str | None
    body: str
    sha256: str


def parse_draft(raw: bytes) -> Draft:
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise DraftError(["draft is not valid UTF-8"]) from None
    lines = text.removeprefix("﻿").splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise DraftError([f"draft must start with a {_FENCE} front matter line"])
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == _FENCE)
    except StopIteration:
        raise DraftError([f"front matter is not closed by a {_FENCE} line"]) from None
    try:
        front = tomllib.loads("\n".join(lines[1:end]))
    except tomllib.TOMLDecodeError as error:
        raise DraftError([f"front matter is not valid TOML: {error}"]) from None
    body_lines = lines[end + 1 :]
    op = front.get("op")
    if op not in OPS:
        raise DraftError([f"op must be one of {', '.join(OPS)}"])
    values = _values(op, front)
    title = None
    if op == "create":
        title, body_lines = _split_title(body_lines)
    return Draft(op, values, title, "\n".join(body_lines), digest)


def _values(op: str, front: dict) -> dict:
    problems = []
    allowed = REQUIRED[op] | OPTIONAL[op] | {"op"}
    for name in sorted(set(front) - allowed):
        problems.append(f"unknown key {name!r} for op {op}")
    for name in sorted(REQUIRED[op] - set(front)):
        problems.append(f"missing key {name!r} for op {op}")
    values = {}
    for name in sorted(set(front) & (allowed - {"op"})):
        parsed = _date(front[name]) if name in DATE_KEYS else _string(front[name])
        if parsed is None:
            kind = "a date (YYYY-MM-DD)" if name in DATE_KEYS else "a non-empty string"
            problems.append(f"{name} must be {kind}")
        else:
            values[name] = parsed
    if problems:
        raise DraftError(problems)
    return values


def _string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _date(value: object) -> date | None:
    if type(value) is date:
        return value
    if isinstance(value, str) and _DATE_TEXT.match(value.strip()):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _split_title(lines: list[str]) -> tuple[str, list[str]]:
    """The first non-blank line is `# title`. The title line becomes blank, so the line numbers
    the converter reports still count from the first line after the front matter."""
    for index, line in enumerate(lines):
        if line.strip():
            if not line.startswith("# ") or not line[2:].strip():
                raise DraftError(["the body must start with a '# title' line (create)"])
            return line[2:].strip(), [""] * (index + 1) + lines[index + 1 :]
    raise DraftError(["the body must start with a '# title' line (create)"])
