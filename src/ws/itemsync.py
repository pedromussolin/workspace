"""`ws item pull` and `ws item sync`: bring tracker values into an item, never the other way."""

from datetime import date
from pathlib import Path

from ws.itemfile import ItemError, item_path, read_item, set_cache, set_keys, write_text
from ws.items import Project, rel
from ws.tracker.port import Card, People, Tracker

PULL_FIELDS = ("type", "epic", "assignee", "reporter", "blocks", "blocked_by", "relates")


def _person(account: str | None, role: str, people: People) -> str:
    if not account:
        raise ItemError(f"the tracker has no {role}")
    found = people.dev_id(account)
    if found is None:
        raise ItemError(f"the tracker's {role} {account} has no dev id: run ws people add <e-mail>")
    return found


def _value(field: str, card: Card, people: People) -> object:
    if field == "type":
        if card.type is None:
            raise ItemError(f"card {card.ref} has a type with no mapping in config.toml")
        return card.type
    if field == "epic":
        if card.parent is None:
            raise ItemError(f"card {card.ref} has no epic")
        return card.parent
    if field in ("assignee", "reporter"):
        return _person(getattr(card, field), field, people)
    return sorted({link.ref for link in card.links if link.kind == field})


def pull(root: Path, rel_path: str, fields: list[str], tracker: Tracker, people: People) -> dict:
    for name in fields:
        if name not in PULL_FIELDS:
            raise ItemError(f"{name!r} cannot be pulled: choose from {', '.join(PULL_FIELDS)}")
    if not fields:
        raise ItemError("name the fields to pull")
    path = item_path(root, rel_path)
    try:
        item = read_item(path)
    except FileNotFoundError:
        raise ItemError(f"{rel_path} does not exist") from None
    if item is None:
        raise ItemError(f"{rel_path} has no front matter")
    if not item.tracked:
        raise ItemError(f"{rel_path} has tracker = false")
    if not item.card:
        raise ItemError(f"{rel_path} has no card")
    card = tracker.card(item.card)
    if card is None:
        raise ItemError(f"card {item.card} is not in the tracker")
    values = {name: _value(name, card, people) for name in dict.fromkeys(fields)}
    changed = {
        name: {"item": item.front.get(name), "tracker": value}
        for name, value in values.items()
        if item.front.get(name) != value
    }
    if changed:
        text = path.read_bytes().decode("utf-8")
        write_text(path, set_keys(text, {name: values[name] for name in changed}))
    return {"path": rel_path, "changed": changed}


def _cache(card: Card, today: date) -> dict:
    table: dict = {"status": card.status.value}
    if card.priority is not None:
        table["priority"] = card.priority
    if card.due is not None:
        table["due"] = card.due
    table["sprint"] = card.sprint or ""
    table["synced"] = today
    return table


def sync(projects: list[Project], root: Path, tracker: Tracker, today: date) -> dict:
    updated: list[str] = []
    problems: list[dict] = []
    for project in projects:
        for item in project.items:
            if not item.tracked or not item.card:
                continue
            name = rel(root, item.path)
            card = tracker.card(item.card)
            if card is None:
                problems.append(
                    {"path": name, "problem": f"card {item.card} is not in the tracker"}
                )
                continue
            text = item.path.read_bytes().decode("utf-8")
            try:
                new = set_cache(text, _cache(card, today))
            except ItemError as error:
                problems.append({"path": name, "problem": str(error)})
                continue
            if new != text:
                write_text(item.path, new)
                updated.append(name)
    return {"updated": updated, "problems": problems}
