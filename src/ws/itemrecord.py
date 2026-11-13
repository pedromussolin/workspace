"""Items whose card was created but not written back, or whose create result is uncertain.

The record is `cards/uncertain/items.tsv` under the data dir, one line per item:
`<rel>\\t<ref or ?>\\t<YYYY-MM-DD>`. `ws card` refuses a second create for a recorded item until
`ws item set-card` writes the ref (or `--none`) and clears the line."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ws.config import data_dir
from ws.itemfile import ItemError, item_path, read_item, set_keys, write_text

UNKNOWN = "?"


def _file() -> Path:
    return data_dir() / "cards" / "uncertain" / "items.tsv"


def _lines() -> list[list[str]]:
    try:
        text = _file().read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return [line.split("\t") for line in text.splitlines() if line.count("\t") >= 1]


def _store(rows: list[list[str]]) -> None:
    target = _file()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=target.parent, prefix=".items.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.writelines("\t".join(row) + "\n" for row in rows)
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def record(rel: str, ref: str | None) -> None:
    rows = [row for row in _lines() if row[0] != rel]
    rows.append([rel, ref or UNKNOWN, datetime.now(UTC).date().isoformat()])
    _store(rows)


def recorded(rel: str) -> str | None:
    for row in _lines():
        if row[0] == rel:
            return row[1]
    return None


def clear(rel: str) -> None:
    rows = _lines()
    kept = [row for row in rows if row[0] != rel]
    if len(kept) != len(rows):
        _store(kept)


def write_back(root: Path, rel: str, ref: str) -> None:
    path = item_path(root, rel)
    try:
        item = read_item(path)
    except FileNotFoundError:
        raise ItemError(f"{rel} no longer exists") from None
    if item is None:
        raise ItemError(f"{rel} has no front matter")
    if item.front.get("card") == ref:
        return
    if "card" in item.front:
        raise ItemError(f"{rel} already has card {item.front['card']!r}")
    text = path.read_bytes().decode("utf-8")
    write_text(path, set_keys(text, {"card": ref}))


def _person(value: str | None, own_dev_id: str) -> str:
    return own_dev_id if value in (None, "me") else value


def create_problems(root: Path, values: dict, own_dev_id: str) -> list[str]:
    rel = values["item"]
    try:
        item = read_item(item_path(root, rel))
    except (ItemError, OSError):
        item = None
    if item is None:
        return [f"item {rel} is not an item"]
    problems = []
    if item.card:
        problems.append(
            f"item {rel} already has card {item.card}: a second create would duplicate it"
        )
    if not item.tracked:
        problems.append(f"item {rel} has tracker = false")
    for field in ("type", "epic"):
        if item.front.get(field) != values.get(field):
            problems.append(f"{field} differs from the item {rel} ({item.front.get(field)})")
    for field in ("assignee", "reporter"):
        if field not in item.front:
            continue
        mine = _person(values.get(field), own_dev_id)
        if item.front[field] != mine:
            problems.append(f"{field} differs from the item {rel} ({item.front[field]})")
    pending = recorded(rel)
    if pending:
        problems.append(
            f"item {rel} has an uncertain create ({pending}): check the tracker, then run "
            f"ws item set-card {rel} <ref> (or --none)"
        )
    return problems
