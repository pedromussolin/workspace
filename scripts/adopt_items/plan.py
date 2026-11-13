"""Pure planner of the items conversion: what moves, what becomes an item, what stays a document.

`Item.path` is the repo-relative final path (`projects/<project>/tasks/NN-x.md`): known for items
made from a file, predicted for new ones. Link paths written at plan time rely on that prediction,
so the executor must create new items in `plan.items` order and assert that the path `ws item new`
prints equals `Item.path`, refusing to continue otherwise.
"""

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ws.project import SLUG_PATTERN

from .maprows import (
    EPIC_ALIAS,
    PROJECT_DIR,
    Link,
    Row,
    check_rows,
    neutral_status,
)
from .relink import new_path

OLD_PROJECT = "operations-screens-migration"
NEW_PROJECT = "vm-migration"
_CLOSED = ("done", "cancelled")
_NN = re.compile(r"^(\d+)-")
_TS_IN_NAME = re.compile(r"ts-(\d+)")
_REAL_CARD = re.compile(r"TS-\d+")
_LINK_KINDS = ("blocks", "blocked_by", "relates")


class PlanError(Exception):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


@dataclass
class Item:
    project: str
    path: str | None
    slug: str | None
    origin: Literal["file", "new"]
    heading: str | None
    fields: dict
    row: Row
    scope: str | None
    done_when: str | None
    docs: list[str] = field(default_factory=list)
    link_rows: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Plan:
    rename: tuple[str, str] | None = None
    moves: list[tuple[str, str]] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    documents: dict[str, list[str]] = field(default_factory=dict)
    unattached: list[str] = field(default_factory=list)
    skipped: list[tuple[Row, str]] = field(default_factory=list)
    project_tomls: dict[str, dict] = field(default_factory=dict)
    pending_epics: list[tuple[Item, str]] = field(default_factory=list)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _number(name: str) -> int | None:
    m = _NN.match(name)
    return int(m.group(1)) if m else None


def _is_open_card(row: Row) -> bool:
    return neutral_status(row.status) not in _CLOSED


class _Planner:
    def __init__(self, rows, repo, people, overrides):
        self.rows, self.repo, self.people, self.overrides = rows, repo, people, overrides
        self.problems: list[str] = []
        self.plan = Plan()
        old, new = repo / "projects" / OLD_PROJECT, repo / "projects" / NEW_PROJECT
        if old.is_dir():
            if new.exists():
                self.problems.append(
                    f"both projects/{OLD_PROJECT} and projects/{NEW_PROJECT} exist"
                )
            self.plan.rename = (f"projects/{OLD_PROJECT}", f"projects/{NEW_PROJECT}")
        self.source_of: dict[int, str] = {}
        self.consumed: dict[str, set[str]] = {}

    def final(self, project: str) -> str:
        name = PROJECT_DIR.get(project, project)
        return NEW_PROJECT if self.plan.rename and name == OLD_PROJECT else name

    def physical(self, project: str) -> Path:
        name = self.final(project)
        if self.plan.rename and name == NEW_PROJECT:
            name = OLD_PROJECT
        return self.repo / "projects" / name

    def rel(self, project: str, name: str) -> str:
        return f"projects/{self.final(project)}/tasks/{name}"

    def after_rename(self, path: str) -> str:
        moved = dict([self.plan.rename]) if self.plan.rename else {}
        return new_path(path, moved)

    def where(self, row: Row) -> str:
        return f"{row.source}:{row.line}"

    def run(self) -> Plan:
        self.problems += check_rows(self.rows, self.people)
        self.classify()
        self.attach_documents()
        self.slugs_and_numbers()
        self.resolve_links()
        if self.problems:
            raise PlanError(self.problems)
        return self.plan

    def toml(self, project: str) -> dict:
        return self.plan.project_tomls.setdefault(self.final(project), {"epics": []})

    def classify(self):
        by_file: dict[tuple[str, str], list[Row]] = {}
        for r in self.rows:
            if r.project == "epico":
                continue
            toml = self.toml(r.project)
            if r.type_ == "initiative":
                if _REAL_CARD.fullmatch(r.card):
                    toml["initiative"] = r.card
                continue
            if r.type_ == "epic":
                if _REAL_CARD.fullmatch(r.card) and r.card not in toml["epics"]:
                    toml["epics"].append(r.card)
                continue
            if r.file and r.status.strip().lower() == "documento de apoio":
                self.document_row(r)
                continue
            if r.file:
                origin = r.origin_project or r.project
                by_file.setdefault((self.final(origin), r.file), []).append(r)
            else:
                self.rowless(r)
        for (origin, file), group in by_file.items():
            self.file_group(origin, file, group)
        self.plan.items.sort(key=lambda i: (i.row.source, i.row.line))

    def document_row(self, r: Row):
        self.register_doc(r.origin_project or r.project, r.project, r.file)

    def register_doc(self, origin: str, dest: str, file: str):
        name = file.removeprefix("tasks/")
        if not (self.physical(origin) / "tasks" / name).is_file():
            self.problems.append(f"file projects/{self.final(origin)}/{file} does not exist")
            return
        self.consumed.setdefault(self.final(origin), set()).add(name)
        self.plan.documents.setdefault(self.final(dest), []).append(name)
        if self.final(origin) != self.final(dest):
            self.add_move(origin, dest, name)

    def add_move(self, origin: str, dest: str, name: str):
        src = self.after_rename(self.rel(origin, name))
        dst = self.rel(dest, name)
        target = self.physical(dest) / "tasks" / name
        if (src, dst) in self.plan.moves:
            return
        if target.exists() or any(d == dst for _, d in self.plan.moves):
            self.problems.append(f"cannot move {src}: {dst} already exists")
        else:
            self.plan.moves.append((src, dst))

    def rowless(self, r: Row):
        if r.action == "sem-card":
            return
        if r.status.strip().lower() == "documento de apoio":
            self.plan.skipped.append((r, "support document without a file"))
        elif _REAL_CARD.fullmatch(r.card) and not _is_open_card(r):
            self.plan.skipped.append((r, "closed card, no file"))
        else:
            self.add_item(r, "new", None)

    def file_group(self, origin: str, file: str, group: list[Row]):
        name = file.removeprefix("tasks/")
        if not (self.physical(origin) / "tasks" / name).is_file():
            self.problems.append(
                f"{self.where(group[0])} file projects/{origin}/{file} does not exist"
            )
            return
        if len(group) == 1:
            r = group[0]
            self.consumed.setdefault(origin, set()).add(name)
            self.source_of[id(r)] = origin
            if origin != self.final(r.project):
                self.add_move(origin, r.project, name)
            self.add_item(r, "file", self.rel(r.project, name))
            return
        dest = group[0].project
        self.register_doc(origin, dest, file)
        for r in group:
            if r.action == "sem-card":
                self.plan.skipped.append((r, "sem-card row of a file that became a document"))
                continue
            item = self.add_item(r, "new", None)
            item.docs.append(name)
            self.source_of[id(r)] = origin

    def add_item(self, r: Row, origin: str, path: str | None) -> Item:
        if r.action == "sem-card":
            fields: dict = {"tracker": False, "status": neutral_status(r.status) or r.status}
        else:
            fields = {}
            if _REAL_CARD.fullmatch(r.card):
                fields["card"] = r.card
            fields["type"] = r.type_
            epic = EPIC_ALIAS.get(r.epic, r.epic) if r.epic else None
            if epic and not epic.startswith("novo-"):
                fields["epic"] = epic
                toml = self.toml(r.project)
                if epic not in toml["epics"]:
                    toml["epics"].append(epic)
            for role, name in (("assignee", r.assignee), ("reporter", r.reporter)):
                if name in self.people:
                    fields[role] = self.people[name]
        item = Item(
            project=self.final(r.project),
            path=path,
            slug=None,
            origin=origin,
            heading=r.heading if origin == "new" else None,
            fields=fields,
            row=r,
            scope=r.scope or None,
            done_when=r.done_when or None,
        )
        if r.epic and fields.get("tracker", True) is not False:
            placeholder = EPIC_ALIAS.get(r.epic, r.epic)
            if placeholder.startswith("novo-"):
                self.plan.pending_epics.append((item, placeholder))
        self.plan.items.append(item)
        return item

    def attach_documents(self):
        row_folders = {self.final(r.project) for r in self.rows if r.project != "epico"}
        sources = {self.source_of.get(id(i.row), i.project) for i in self.plan.items}
        for folder in sorted(row_folders | sources):
            self.attach_in(folder, folder in row_folders)

    def attach_in(self, folder: str, report: bool):
        tasks = self.physical(folder) / "tasks"
        if not tasks.is_dir():
            return
        mine = [i for i in self.plan.items if self.source_of.get(id(i.row), i.project) == folder]
        by_card = {i.fields["card"]: i for i in mine if "card" in i.fields}
        by_number: dict[int, list[Item]] = {}
        for i in mine:
            file = i.row.file
            if file and (n := _number(file.removeprefix("tasks/"))) is not None:
                by_number.setdefault(n, []).append(i)
        taken = self.consumed.get(folder, set())
        for doc in sorted(p.name for p in tasks.iterdir() if p.is_file() and p.name[0] != "."):
            if doc in taken:
                continue
            item = self.owner(folder, doc, by_card, by_number, mine)
            if item is None:
                if report:
                    self.plan.unattached.append(f"{folder}/{doc}")
                    self.plan.documents.setdefault(folder, []).append(doc)
                continue
            item.docs.append(doc)
            self.plan.documents.setdefault(item.project, []).append(doc)
            if item.project != folder:
                self.add_move(folder, item.project, doc)
        for docs in self.plan.documents.values():
            docs.sort()
        for i in mine:
            i.docs.sort()

    def owner(self, folder, doc, by_card, by_number, mine) -> Item | None:
        if m := _TS_IN_NAME.search(doc.lower()):
            if item := by_card.get(f"TS-{m.group(1)}"):
                return item
        n = _number(doc)
        if n is not None and len(by_number.get(n, [])) == 1:
            return by_number[n][0]
        for project, file, card in self.overrides:
            if file == doc and self.final(project) == folder and card in by_card:
                return by_card[card]
        return None

    def slugs_and_numbers(self):
        used: dict[str, set[str]] = {}
        highest: dict[str, int] = {}
        for i in self.plan.items:
            tasks = self.physical(i.project) / "tasks"
            if i.project not in highest:
                nums = [_number(p.name) for p in tasks.glob("*") if tasks.is_dir()]
                highest[i.project] = max([n for n in nums if n is not None], default=0)
        for _, dst in self.plan.moves:
            project, name = dst.split("/")[1], dst.rsplit("/", 1)[1]
            if (n := _number(name)) is not None:
                highest[project] = max(highest.get(project, 0), n)
        for i in self.plan.items:
            if i.origin != "new":
                continue
            i.slug = self.slug_for(i, used.setdefault(i.project, set()))
            highest[i.project] += 1
            i.path = f"projects/{i.project}/tasks/{highest[i.project]:02d}-{i.slug}.md"

    def slug_for(self, item: Item, used: set[str]) -> str:
        r = item.row
        if r.file:
            stem = _NN.sub("", r.file.removeprefix("tasks/").removesuffix(".md"))
            base = _slugify(stem)
            if _REAL_CARD.fullmatch(r.card):
                base = f"{r.card.lower()}-{base}"
        elif _REAL_CARD.fullmatch(r.card):
            base = r.card.lower()
        else:
            base = "new-" + _slugify(r.card.removeprefix("novo-"))
        slug, n = base, 1
        while slug in used:
            n += 1
            slug = f"{base}-{n}"
        used.add(slug)
        if not SLUG_PATTERN.fullmatch(slug):
            self.problems.append(f"{self.where(r)} slug '{slug}' is not valid")
        return slug

    def target_path(self, target: Item, from_project: str) -> str:
        path = target.path.removeprefix(f"projects/{target.project}/")
        if target.project == from_project:
            return path
        return posixpath.join("..", target.project, path)

    def resolve_links(self):
        by_card = {i.row.card: i for i in self.plan.items}
        for i in self.plan.items:
            if i.fields.get("tracker") is False:
                continue
            for link in i.row.links:
                self.resolve_one(i, link, by_card)

    def resolve_one(self, item: Item, link: Link, by_card: dict[str, Item]):
        ref = link.ref
        if not ref.startswith("novo-"):
            item.fields.setdefault(link.kind, []).append(ref)
            return
        item.link_rows.append((link.kind, ref))
        target = by_card.get(ref)
        if target is None or target.fields.get("tracker") is False:
            why = "a skipped or unknown row" if target is None else "a tracker = false item"
            self.problems.append(f"{self.where(item.row)} link to '{ref}', {why}")
            return
        item.fields.setdefault(link.kind, []).append(self.target_path(target, item.project))


def build_plan(
    rows: list[Row], repo: Path, people: dict[str, str], docs_overrides: list[tuple[str, str, str]]
) -> Plan:
    return _Planner(rows, repo, people, docs_overrides).run()


def render_plan(plan: Plan) -> str:
    lines = []
    if plan.rename:
        lines.append(f"rename {plan.rename[0]} -> {plan.rename[1]}")
    lines += [f"move {old} -> {new}" for old, new in plan.moves]
    for i in plan.items:
        where = i.path
        card = i.fields.get("card", "-")
        kind = "item" if i.fields.get("tracker") is not False else "item (tracker = false)"
        lines.append(f"{kind} {i.project}/{where} card={card} source={i.row.source}:{i.row.line}")
    for item, placeholder in plan.pending_epics:
        lines.append(f"pending epic {item.path} -> {placeholder}")
    for project, names in sorted(plan.documents.items()):
        lines += [f"document {project}/{name}" for name in names]
    lines += [f"unattached document {name}" for name in plan.unattached]
    for r, reason in plan.skipped:
        lines.append(f"skip {r.source}:{r.line} {r.card}: {reason}")
    docs = sum(len(v) for v in plan.documents.values())
    lines.append(
        f"total: {1 if plan.rename else 0} rename, {len(plan.moves)} moves, "
        f"{len(plan.items)} items, {docs} documents, {len(plan.unattached)} unattached, "
        f"{len(plan.skipped)} skipped, {len(plan.pending_epics)} pending epics"
    )
    return "\n".join(lines) + "\n"
