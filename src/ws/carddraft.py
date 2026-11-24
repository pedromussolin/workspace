"""Draft files of `ws card`: TOML front matter between `+++` lines, then a Markdown body."""

import hashlib
import re
import tomllib
from datetime import date

from ws.tracker.vocab import DRAFT_LINK_KINDS, LABEL_KEYS
from ws.tracker.write import Draft, draft_problems, repeated_problem

OPS = ("create", "edit", "move", "comment", "worklog", "link")

REQUIRED = {
    "create": {"type", "priority"},
    "edit": {"key"},
    "move": {"key"},
    "comment": {"key"},
    "worklog": {"key", "time"},
    "link": {"key"},
}
OPTIONAL = {
    "create": {
        "epic",
        "parent",
        "assignee",
        "reporter",
        "sprint",
        "due",
        "item",
        "labels",
        "estimate",
    },
    "edit": {
        "title",
        "priority",
        "start",
        "due",
        "epic",
        "type",
        "assignee",
        "reporter",
        "parent",
        "sprint",
        "add_labels",
        "remove_labels",
        "estimate",
    },
    "move": {"to", "status"},
    "comment": set(),
    "worklog": {"day"},
    "link": set(DRAFT_LINK_KINDS),
}
DATE_KEYS = {"start", "due", "day"}
LIST_KEYS = set(DRAFT_LINK_KINDS) | set(LABEL_KEYS)

_DATE_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FENCE = "+++"


class DraftError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


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
    if op == "link" and any(line.strip() for line in body_lines):
        raise DraftError(["a link draft has no body"])
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
        if name in LIST_KEYS:
            parsed = _keys(front[name])
        elif name in DATE_KEYS:
            parsed = _date(front[name])
        else:
            parsed = _string(front[name])
        if parsed is None:
            kind = "a date (YYYY-MM-DD)" if name in DATE_KEYS else "a non-empty string"
            if name in LIST_KEYS:
                kind = "a list of labels" if name in LABEL_KEYS else "a list of card keys"
            problems.append(f"{name} must be {kind}")
        elif name in LIST_KEYS and (problem := repeated_problem(name, parsed)):
            problems.append(problem)
        else:
            values[name] = parsed
    if not problems:
        problems = draft_problems(op, values)
    if problems:
        raise DraftError(problems)
    return values


def _keys(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [_string(item) for item in value]
    return None if None in items else items


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
