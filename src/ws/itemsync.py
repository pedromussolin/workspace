"""`ws item pull` and `ws item sync`: bring tracker values into an item, never the other way."""

from datetime import date
from pathlib import Path

from ws.itemfile import Item, ItemError, item_path, read_item, set_cache, set_keys, write_text
from ws.items import Project, ProjectMissing, link_ref, load_project, rel
from ws.tracker.port import Card, People, Tracker, TrackerError
from ws.tracker.vocab import LINK_KINDS

PULL_FIELDS = ("type", "epic", "assignee", "reporter", "blocks", "blocked_by", "relates")


def _person(account: str | None, role: str, people: People) -> str:
    if not account:
        raise ItemError(f"the tracker has no {role}")
    found = people.dev_id(account)
    if found is None:
        raise ItemError(f"the tracker's {role} {account} has no dev id: run ws people add <e-mail>")
    return found


def _links(root: Path, rel_path: str, item: Item, kind: str, card: Card) -> list[str]:
    """The item's list moved to the card's links of `kind`, keeping what the card cannot show.

    An entry whose item has no card yet waits, so it stays; an entry the card already has stays as
    the item spells it (a path is not rewritten to its ref); the card's other refs are added,
    sorted; the item's entries the card lacks are dropped."""
    entries = item.front.get(kind, [])
    if not isinstance(entries, list):
        raise ItemError(f"{rel_path}: {kind} must be a list; fix the item first")
    try:
        project = load_project(root, rel_path.split("/")[1])
    except ProjectMissing as error:
        raise ItemError(str(error)) from None
    tracker = {link.ref for link in card.links if link.kind == kind}
    kept: list[str] = []
    covered: set[str] = set()
    for entry in entries:
        if not isinstance(entry, str):
            raise ItemError(f"{rel_path}: {kind}: {entry!r} is not a link; fix the item first")
        try:
            ref = link_ref(root, project, entry)
        except ItemError as error:
            raise ItemError(f"{rel_path}: {kind}: {error}; fix the item first") from None
        if ref is None or ref in tracker:
            kept.append(entry)
        if ref is not None:
            covered.add(ref)
    return kept + sorted(tracker - covered)


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
    raise ItemError(f"{field!r} cannot be pulled")


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
    values = {
        name: _links(root, rel_path, item, name, card)
        if name in LINK_KINDS
        else _value(name, card, people)
        for name in dict.fromkeys(fields)
    }
    changed = {
        name: {"item": item.front.get(name), "tracker": value}
        for name, value in values.items()
        if item.front.get(name, [] if name in LINK_KINDS else None) != value
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
        problems.extend(project.problems)
        for item in project.items:
            if not item.tracked or not item.card:
                continue
            name = rel(root, item.path)
            try:
                card = tracker.card(item.card)
            except TrackerError as error:
                problems.append({"path": name, "problem": f"tracker error: {error}"})
                continue
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
                try:
                    write_text(item.path, new)
                except OSError as error:
                    problems.append({"path": name, "problem": f"cannot write: {error}"})
                    continue
                updated.append(name)
    return {"updated": updated, "problems": problems}
