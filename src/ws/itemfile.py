"""The item file: a Markdown file under `projects/<slug>/tasks/` with a TOML front matter."""

import os
import posixpath
import re
import stat
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ws.identity import DEV_ID
from ws.taskmodel import Status
from ws.tracker.vocab import CARD_TYPES, LINK_KINDS, REF
from ws.userconfig import toml_string

CONTRACT_KEYS = (
    "card",
    "type",
    "epic",
    "assignee",
    "reporter",
    "blocks",
    "blocked_by",
    "relates",
    "docs",
    "tracker",
    "status",
)
CACHE_KEYS = ("status", "priority", "due", "sprint", "synced")
ITEM_PATH = re.compile(r"projects/[a-z0-9]+(?:-[a-z0-9]+)*/tasks/[A-Za-z0-9._-]+\.md")
LINK_PATH = re.compile(r"(?:\.\./[a-z0-9]+(?:-[a-z0-9]+)*/)?tasks/[A-Za-z0-9._-]+\.md")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_KEY_LINE = re.compile(r"\s*([A-Za-z0-9_-]+)\s*=")
_FENCE = "+++"
_CACHE_TEXT = ("status", "priority", "sprint")
_CACHE_DATES = ("due", "synced")


class ItemError(Exception):
    pass


@dataclass(frozen=True)
class Item:
    path: Path
    front: dict
    heading: str

    @property
    def card(self) -> str | None:
        card = self.front.get("card")
        return card if isinstance(card, str) else None

    @property
    def tracked(self) -> bool:
        return self.front.get("tracker") is not False

    @property
    def links(self) -> dict[str, list[str]]:
        out = {}
        for kind in LINK_KINDS:
            value = self.front.get(kind)
            out[kind] = list(value) if isinstance(value, list) else []
        return out

    @property
    def cache(self) -> dict:
        table = self.front.get("tracker")
        return dict(table) if isinstance(table, dict) else {}


def _split(text: str) -> tuple[list[str], int] | None:
    """The lines and the index of the closing fence; None when there is no front matter."""
    lines = text.removeprefix("﻿").splitlines(keepends=True)
    if not lines or lines[0].strip() != _FENCE:
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FENCE:
            return lines, i
    raise ItemError("front matter is not closed by a +++ line")


def _parse(lines: list[str], end: int) -> dict:
    try:
        return tomllib.loads("".join(lines[1:end]))
    except tomllib.TOMLDecodeError as error:
        raise ItemError(f"front matter is not valid TOML: {error}") from None


def read_item(path: Path) -> Item | None:
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise ItemError(f"{path.name} is not valid UTF-8") from None
    split = _split(text)
    if split is None:
        return None
    lines, end = split
    front = _parse(lines, end)
    heading = ""
    for line in lines[end + 1 :]:
        if line.startswith("# "):
            heading = line[2:].strip()
            break
    return Item(path, front, heading)


def _is_link(value: object) -> bool:
    return isinstance(value, str) and bool(REF.fullmatch(value) or LINK_PATH.fullmatch(value))


def is_doc(doc: object) -> bool:
    """A non-empty relative path from `tasks/` that stays inside the project folder."""
    if not isinstance(doc, str) or not doc or doc.startswith("/") or "\\" in doc or "\0" in doc:
        return False
    resolved = posixpath.normpath(posixpath.join("tasks", doc))
    return resolved != "." and resolved != ".." and not resolved.startswith("../")


def _person_problem(key: str, value: object) -> str | None:
    if value == "me":
        return f"{key} must be a dev id, not me: the repo is shared; ws people me prints yours"
    if not isinstance(value, str) or not DEV_ID.fullmatch(value):
        return f"{key} must be a dev id (dev- and 10 hex digits)"
    return None


def _cache_problems(table: dict) -> list[str]:
    out = []
    for key, value in table.items():
        if key not in CACHE_KEYS:
            out.append(f"unknown key '{key}' in [tracker]")
        elif key in _CACHE_TEXT and not isinstance(value, str):
            out.append(f"[tracker] {key} must be text")
        elif key in _CACHE_DATES and (not isinstance(value, date) or isinstance(value, datetime)):
            out.append(f"[tracker] {key} must be a date")
    return out


def schema_problems(item: Item) -> list[str]:
    front = item.front
    out = [f"unknown key '{key}'" for key in front if key not in CONTRACT_KEYS]
    tracker = front.get("tracker")
    untracked = tracker is False
    if isinstance(tracker, dict):
        out += _cache_problems(tracker)
    elif not untracked and "tracker" in front:
        out.append("tracker is either false or the [tracker] table")
    if untracked:
        if "status" not in front:
            out.append("tracker = false needs a status")
        elif not isinstance(front["status"], str) or front["status"] not in {
            s.value for s in Status
        }:
            out.append("status must be one of " + ", ".join(s.value for s in Status))
        if "card" in front:
            out.append("tracker = false has no card")
    elif "status" in front:
        out.append("status needs tracker = false")
    has_card = "card" in front
    required = [] if untracked else ["type", "assignee", "reporter"]
    if has_card and not untracked:
        required.append("epic")
    out += [f"missing key '{key}'" for key in required if key not in front]
    if has_card and not untracked and not REF.fullmatch(str(front["card"])):
        out.append("card must be a card ref")
    if "epic" in front and not (isinstance(front["epic"], str) and REF.fullmatch(front["epic"])):
        out.append("epic must be a card ref")
    if "type" in front and front["type"] not in CARD_TYPES:
        out.append("type must be one of " + ", ".join(CARD_TYPES))
    for key in ("assignee", "reporter"):
        if key in front and (problem := _person_problem(key, front[key])):
            out.append(problem)
    for kind in LINK_KINDS:
        if kind not in front:
            continue
        value = front[kind]
        if not isinstance(value, list):
            out.append(f"{kind} must be a list")
            continue
        out += [
            f"{kind}: {entry!r} is neither a card ref nor tasks/<file>.md "
            "nor ../<project>/tasks/<file>.md"
            for entry in value
            if not _is_link(entry)
        ]
    if "docs" in front:
        docs = front["docs"]
        if not isinstance(docs, list):
            out.append("docs must be a list")
        else:
            out += [
                f"docs: {doc!r} must be a path relative to tasks/"
                for doc in docs
                if not is_doc(doc)
            ]
    return out


def _format(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        raise ItemError("a datetime is not an item value")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return toml_string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format(v) for v in value) + "]"
    raise ItemError(f"cannot write {type(value).__name__} to the front matter")


def _eol(line: str) -> str:
    return "\r\n" if line.endswith("\r\n") else "\n"


def _entries(lines: list[str], end: int) -> dict[str, tuple[int, int]]:
    """Top-level `key =` entries before the first table header, as [start, stop) line ranges."""
    found: dict[str, tuple[int, int]] = {}
    i = 1
    while i < end:
        stripped = lines[i].strip()
        if stripped.startswith("["):
            break
        match = _KEY_LINE.match(lines[i])
        if not match or stripped.startswith("#"):
            i += 1
            continue
        stop = i + 1
        while stop <= end:
            try:
                tomllib.loads("".join(lines[i:stop]))
                break
            except tomllib.TOMLDecodeError:
                stop += 1
        found[match.group(1)] = (i, min(stop, end))
        i = stop
    return found


def _checked(old: str, new: str, changes: dict) -> str:
    before = _split(old)
    after = _split(new)
    if before is None or after is None:
        raise ItemError("the item has no front matter")
    expected = {**_parse(*before), **changes}
    if _parse(*after) != expected:
        raise ItemError("the rewrite would change more than the asked keys")
    return new


def _parsed_value(key: str, rendered: str) -> object:
    return tomllib.loads(f"{key} = {rendered}")[key]


def set_keys(text: str, values: dict[str, object]) -> str:
    split = _split(text)
    if split is None:
        raise ItemError("the item has no front matter")
    lines, end = split
    _parse(lines, end)
    rendered = {key: _format(value) for key, value in values.items()}
    entries = _entries(lines, end)
    out = list(lines)
    for key, (start, stop) in sorted(
        ((k, entries[k]) for k in rendered if k in entries), key=lambda kv: -kv[1][0]
    ):
        out[start:stop] = [f"{key} = {rendered[key]}{_eol(lines[stop - 1])}"]
    new_lines = [
        f"{key} = {rendered[key]}{_eol(lines[0])}" for key in rendered if key not in entries
    ]
    out[1:1] = new_lines
    changes = {key: _parsed_value(key, rendered[key]) for key in rendered}
    return _checked(text, "".join(out), changes)


def set_cache(text: str, table: dict) -> str:
    split = _split(text)
    if split is None:
        raise ItemError("the item has no front matter")
    lines, end = split
    _parse(lines, end)
    unknown = [key for key in table if key not in CACHE_KEYS]
    if unknown:
        raise ItemError(f"unknown key '{unknown[0]}' in [tracker]")
    eol = _eol(lines[0])
    body = [f"{key} = {_format(table[key])}{eol}" for key in CACHE_KEYS if key in table]
    header = next((i for i in range(1, end) if lines[i].strip() == "[tracker]"), None)
    out = list(lines)
    if header is None:
        spacer = [] if end == 1 or not lines[end - 1].strip() else [eol]
        out[end:end] = [*spacer, f"[tracker]{eol}", *body]
    else:
        stop = next((i for i in range(header + 1, end) if lines[i].lstrip().startswith("[")), end)
        while stop - 1 > header and not lines[stop - 1].strip():
            stop -= 1
        out[header + 1 : stop] = body
    ordered = {key: table[key] for key in CACHE_KEYS if key in table}
    return _checked(text, "".join(out), {"tracker": ordered})


def _inside_projects(root: Path, lexical: Path) -> Path:
    projects = root.resolve() / "projects"
    if lexical.resolve() != lexical or not lexical.is_relative_to(projects):
        raise ItemError(f"{lexical} is outside projects/ or goes through a symlink")
    return lexical


def item_path(root: Path, rel: str) -> Path:
    if not ITEM_PATH.fullmatch(rel):
        raise ItemError(f"{rel!r} is not projects/<project>/tasks/<file>.md")
    return _inside_projects(root, root.resolve() / rel)


def link_path(root: Path, slug: str, target: str) -> Path:
    if not _SLUG.fullmatch(slug):
        raise ItemError(f"{slug!r} is not a project name")
    if not LINK_PATH.fullmatch(target):
        raise ItemError(f"{target!r} is neither tasks/<file>.md nor ../<project>/tasks/<file>.md")
    lexical = Path(os.path.normpath(root.resolve() / "projects" / slug / target))
    return _inside_projects(root, lexical)


def write_text(path: Path, text: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(text.encode("utf-8"))
        os.chmod(temp, mode)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
