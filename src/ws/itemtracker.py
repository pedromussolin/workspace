"""Items against the tracker: drift, pending creates and links, orphans, and the drafts for them.

The item file is the contract: where an item and its card differ, the draft written here moves the
card to the item. Nothing in this module writes to the tracker; `ws card apply` does."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ws import itemrecord
from ws.card import drafts_folder
from ws.itemfile import Item, ItemError
from ws.items import (
    Project,
    check_offline,
    link_ref,
    load_project,
    project_slugs,
    rel,
)
from ws.taskmodel import Status
from ws.tracker.port import Card, CardQuery, People, Tracker
from ws.tracker.vocab import LINK_KINDS, required_sections

DEFAULT_PRIORITY = "Medium"
_CLOSED = (Status.DONE, Status.CANCELLED)
_INVERSE = {"blocks": "blocked_by", "blocked_by": "blocks", "relates": "relates"}
_FIELDS = ("type", "epic", "assignee", "reporter")
_CAPABILITY = {"type": "change_type", "reporter": "set_reporter"}


@dataclass
class Report:
    problems: list[dict] = field(default_factory=list)
    drift: list[dict] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)
    orphans: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "problems": self.problems,
            "drift": self.drift,
            "pending": self.pending,
            "orphans": self.orphans,
        }


class _Reader:
    """Cards read once each, and the declared links of items as refs."""

    def __init__(self, projects: list[Project], root: Path, tracker: Tracker):
        self.root = root
        self.tracker = tracker
        self._cards: dict[str, Card | None] = {}
        self.owner = {
            item.card: (project, item)
            for project in projects
            for item in project.items
            if item.tracked and item.card
        }

    def card(self, ref: str) -> Card | None:
        if ref not in self._cards:
            self._cards[ref] = self.tracker.card(ref)
        return self._cards[ref]

    def declared(self, project: Project, item: Item, kind: str) -> list[str | None]:
        """The refs an item lists under `kind`; None for a target whose item has no card yet."""
        out: list[str | None] = []
        for target in item.links[kind]:
            try:
                out.append(link_ref(self.root, project, target))
            except ItemError:
                continue
        return out


def _person_value(people: People, account: str | None) -> str | None:
    if account is None:
        return None
    return people.dev_id(account) or account


def _drift(path: str, item: Item, card: Card, tracker: Tracker, people: People) -> list[dict]:
    """A closed card keeps its type (spec decision 9), so its type is never drift."""
    found = []
    for name in _FIELDS:
        if name not in item.front or (name == "type" and card.status in _CLOSED):
            continue
        wanted = item.front[name]
        if name in ("assignee", "reporter"):
            have = getattr(card, name)
            if people.account(wanted) == have:
                continue
            accounts = {"item": people.account(wanted), "tracker": have}
            names = {
                side: tracker.display_name(account) if account else None
                for side, account in accounts.items()
            }
            entry = {"item": wanted, "tracker": _person_value(people, have), "names": names}
        else:
            have = card.type if name == "type" else card.parent
            if wanted == have:
                continue
            entry = {"item": wanted, "tracker": have}
        found.append({"path": path, "card": card.ref, "field": name, **entry})
    return found


def _canonical(kind: str, ref: str, other: str) -> tuple:
    if kind == "relates":
        return ("relates", *sorted((ref, other)))
    return ("blocks", ref, other) if kind == "blocks" else ("blocks", other, ref)


def _link_state(
    reader: _Reader, project: Project, item: Item, path: str, card: Card, seen: set
) -> tuple[list[dict], list[dict]]:
    problems: list[dict] = []
    pending: list[dict] = []
    have = {(link.kind, link.ref) for link in card.links}
    for kind in LINK_KINDS:
        for target in item.links[kind]:
            try:
                ref = link_ref(reader.root, project, target)
            except ItemError:
                continue
            if ref is None:
                pending.append(
                    {
                        "path": path,
                        "card": card.ref,
                        "op": "link",
                        "kind": kind,
                        "to": target,
                        "waits": True,
                    }
                )
            elif reader.card(ref) is None:
                problems.append(
                    {
                        "path": path,
                        "problem": f"{kind}: {ref} was not found in the tracker's project",
                    }
                )
            elif (kind, ref) not in have:
                key = _canonical(kind, card.ref, ref)
                if key not in seen:
                    seen.add(key)
                    pending.append(
                        {
                            "path": path,
                            "card": card.ref,
                            "op": "link",
                            "kind": kind,
                            "to": ref,
                            "waits": False,
                        }
                    )
    return problems, pending


def _undeclared(reader: _Reader, project: Project, item: Item, path: str, card: Card) -> list[dict]:
    drift = []
    for kind in LINK_KINDS:
        listed = {ref for ref in reader.declared(project, item, kind) if ref}
        extra = []
        for link in card.links:
            if link.kind != kind or link.ref in listed:
                continue
            other = reader.owner.get(link.ref)
            if other and card.ref in {
                ref for ref in reader.declared(*other, _INVERSE[kind]) if ref
            }:
                continue
            extra.append(link.ref)
        if extra:
            drift.append(
                {
                    "path": path,
                    "card": card.ref,
                    "field": kind,
                    "item": list(item.links[kind]),
                    "tracker": [link.ref for link in card.links if link.kind == kind],
                    "undeclared": extra,
                }
            )
    return drift


def compare(projects: list[Project], root: Path, tracker: Tracker, people: People) -> Report:
    report = Report(problems=check_offline(projects, root, people))
    bad = {p["path"] for p in report.problems}
    chosen = {project.slug for project in projects}
    everyone = projects + [
        load_project(root, slug) for slug in project_slugs(root) if slug not in chosen
    ]
    reader = _Reader(everyone, root, tracker)
    seen: set = set()
    for project in projects:
        for item in project.items:
            path = rel(root, item.path)
            if not item.tracked or path in bad:
                continue
            if not item.card:
                entry = {"path": path, "card": None, "op": "create"}
                if "epic" not in item.front:
                    entry["needs"] = "epic"
                report.pending.append(entry)
                continue
            card = reader.card(item.card)
            if card is None:
                report.problems.append(
                    {
                        "path": path,
                        "problem": f"card {item.card} was not found in the tracker's project",
                    }
                )
                continue
            if card.level != 0:
                report.problems.append(
                    {"path": path, "problem": f"{item.card} is not a card (level {card.level})"}
                )
                continue
            report.drift += _drift(path, item, card, tracker, people)
            problems, pending = _link_state(reader, project, item, path, card, seen)
            report.problems += problems
            report.pending += pending
            report.drift += _undeclared(reader, project, item, path, card)
    held = {item.card for project in everyone for item in project.items if item.card}
    listed: set[str] = set()
    for project in projects:
        if not project.epics:
            continue
        for card in tracker.cards(CardQuery(project.epics)):
            if card.ref not in held and card.ref not in listed:
                listed.add(card.ref)
                report.orphans.append(
                    {"card": card.ref, "title": card.title, "type": card.type, "epic": card.parent}
                )
    return report


def _selected(only: set[str] | None, path: str, ref: str | None) -> bool:
    return only is None or path in only or (ref is not None and ref in only)


def _toml(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _draft(op: str, values: dict, body: str = "") -> str:
    lines = [f'op = "{op}"', *(f"{key} = {_toml(value)}" for key, value in values.items())]
    return "+++\n" + "\n".join(lines) + "\n+++\n" + body


def _link_text(kind: str, ref: str, other: str) -> str:
    return f"{ref} {kind.replace('_', ' ')} {other}"


def _check_only(only: set[str] | None, projects: list[Project], root: Path) -> None:
    if only is None:
        return
    known = set()
    for project in projects:
        for item in project.items:
            known.add(rel(root, item.path))
            if item.card:
                known.add(item.card)
    unknown = sorted(only - known)
    if unknown:
        raise ItemError(f"--only names no item or card: {', '.join(unknown)}")


def _new_folder(name: str) -> Path:
    for number in range(1, 100):
        try:
            return drafts_folder(name if number == 1 else f"{name}-{number}")
        except FileExistsError:
            continue
    raise ItemError(f"cannot find a free drafts folder named {name}")


def write_drafts(
    report: Report,
    projects: list[Project],
    root: Path,
    tracker: Tracker,
    only: set[str] | None,
    now: datetime,
) -> dict:
    if report.problems:
        raise ItemError(
            f"ws item check --tracker reports {len(report.problems)} problem(s): fix them first"
        )
    _check_only(only, projects, root)
    by_hand: list[str] = []
    waiting: list[dict] = []
    files: list[tuple[str, str]] = []
    need_text: list[str] = []
    items = {
        rel(root, item.path): (project, item) for project in projects for item in project.items
    }

    edits: dict[str, dict] = {}
    for entry in report.drift:
        if entry["field"] in LINK_KINDS or not _selected(only, entry["path"], entry["card"]):
            continue
        capability = _CAPABILITY.get(entry["field"])
        if capability and capability not in tracker.capabilities:
            by_hand.append(f"change the {entry['field']} of {entry['card']} by hand in the tracker")
            continue
        edits.setdefault(entry["card"], {"key": entry["card"]})[entry["field"]] = entry["item"]
    files += [(f"edit-{ref}.md", _draft("edit", values)) for ref, values in edits.items()]

    for entry in report.drift:
        if entry["field"] in LINK_KINDS and _selected(only, entry["path"], entry["card"]):
            for target in entry["undeclared"]:
                text = _link_text(entry["field"], entry["card"], target)
                by_hand.append(
                    f"remove the link {text} by hand, or ws item pull {entry['path']} "
                    f"--fields {entry['field']}"
                )

    links: dict[str, dict] = {}
    for entry in report.pending:
        if entry["op"] != "link" or not _selected(only, entry["path"], entry["card"]):
            continue
        if entry["waits"]:
            waiting.append(entry)
        elif "link_types" not in tracker.capabilities:
            text = _link_text(entry["kind"], entry["card"], entry["to"])
            by_hand.append(f"create the link {text} by hand in the tracker")
        else:
            values = links.setdefault(entry["card"], {"key": entry["card"]})
            values.setdefault(entry["kind"], []).append(entry["to"])
    files += [(f"link-{ref}.md", _draft("link", values)) for ref, values in links.items()]

    creates = []
    for entry in report.pending:
        if entry["op"] != "create" or not _selected(only, entry["path"], None):
            continue
        project, item = items[entry["path"]]
        if "epic" not in item.front:
            by_hand.append(
                f"item {entry['path']} has no epic: set it in the item, then run ws item "
                "drafts again"
            )
            continue
        if pending := itemrecord.recorded(entry["path"]):
            raise ItemError(
                f"item {entry['path']} has an uncertain create ({pending}): check the tracker, "
                f"then run ws item set-card {entry['path']} <ref> (or --none)"
            )
        creates.append((entry["path"], project, item))

    if not (files or creates):
        return {"folder": None, "count": 0, "need_text": [], "waiting": waiting, "by_hand": by_hand}
    folder = _new_folder(f"items-{now:%Y%m%d-%H%M%S}")
    for name, text in files:
        (folder / name).write_text(text, encoding="utf-8")
    for path, project, item in creates:
        kind = item.front["type"]
        values = {"type": kind, "epic": item.front["epic"], "priority": DEFAULT_PRIORITY}
        values |= {key: item.front[key] for key in ("assignee", "reporter") if key in item.front}
        values["item"] = path
        body = "# \n\n" + "".join(f"## {section}\n\n" for section in required_sections(kind))
        target = folder / f"create-{project.slug}-{item.path.stem}.md"
        target.write_text(_draft("create", values, body.rstrip("\n") + "\n"), encoding="utf-8")
        need_text.append(str(target))
    return {
        "folder": str(folder),
        "count": len(files) + len(creates),
        "need_text": need_text,
        "waiting": waiting,
        "by_hand": by_hand,
    }
