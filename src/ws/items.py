"""The items of a planning project: loading, offline checks, creation and the README table."""

import posixpath
import re
import tomllib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ws.identity import DEV_ID
from ws.itemfile import (
    LINK_PATH,
    Item,
    ItemError,
    is_doc,
    link_path,
    read_item,
    schema_problems,
    write_text,
)
from ws.project import SLUG_PATTERN
from ws.tracker.vocab import (
    CARD_TYPES,
    LINK_KINDS,
    REF,
    STATUS_LABELS,
    TYPE_LABELS,
    required_sections,
)

TABLE_START = "<!-- ws:items -->"
TABLE_END = "<!-- /ws:items -->"
TABLE_HEADER = "| # | Tarefa | Card | Tipo | Responsável | Status |"
TABLE_RULE = "|---|---|---|---|---|---|"
_PROJECT_KEYS = ("epics", "initiative", "prefixes")
_NUMBER = re.compile(r"\d+")
_PREFIX = re.compile(r"[^\[\]\s](?:[^\[\]\r\n]*[^\[\]\s])?")
_TITLE_NUMBER = re.compile(r"^\d+\s+—\s+")
_WORD = re.compile(r"[a-z0-9]+")
_NAME_WORDS = 6


class ProjectMissing(Exception):
    pass


class PeopleDirectory(Protocol):
    def problem(self, dev_id: str) -> str | None: ...


@dataclass
class Project:
    slug: str
    folder: Path
    epics: tuple[str, ...]
    initiative: str | None
    prefixes: dict[str, str]
    items: list[Item]
    problems: list[dict] = field(default_factory=list)


def rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def project_slugs(root: Path) -> list[str]:
    folder = root.resolve() / "projects"
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir() if (p / "project.toml").is_file())


def _project_toml(root: Path, path: Path) -> tuple[tuple[str, ...], str | None, dict, list[dict]]:
    where = rel(root, path)
    problems: list[dict] = []

    def bad(text: str) -> None:
        problems.append({"path": where, "problem": text})

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        bad(f"project.toml is not valid TOML: {error}")
        return (), None, {}, problems
    for key in data:
        if key not in _PROJECT_KEYS:
            bad(f"unknown key '{key}'")
    epics = data.get("epics")
    if not isinstance(epics, list) or not all(
        isinstance(e, str) and REF.fullmatch(e) for e in epics
    ):
        bad("epics must be a list of card refs")
        epics = []
    initiative = data.get("initiative")
    if initiative is not None and not (isinstance(initiative, str) and REF.fullmatch(initiative)):
        bad("initiative must be a card ref")
        initiative = None
    prefixes: dict[str, str] = {}
    raw = data.get("prefixes", {})
    if not isinstance(raw, dict):
        bad("prefixes must be a table of epic to prefix")
        raw = {}
    for key, value in raw.items():
        if key not in epics:
            bad(f"prefixes: {key!r} is not in epics")
        elif not isinstance(value, str) or not _PREFIX.fullmatch(value):
            bad(
                f"prefixes: the prefix of {key} must be one line of text without brackets "
                "nor spaces at the ends"
            )
        else:
            prefixes[key] = value
    return tuple(epics), initiative, prefixes, problems


def load_project(root: Path, slug: str) -> Project:
    folder = root.resolve() / "projects" / slug
    toml = folder / "project.toml"
    if not SLUG_PATTERN.fullmatch(slug) or not toml.is_file():
        raise ProjectMissing(f"project {slug!r} has no projects/{slug}/project.toml")
    epics, initiative, prefixes, problems = _project_toml(root, toml)
    items = []
    for path in sorted((folder / "tasks").glob("*.md")):
        try:
            item = read_item(path)
        except ItemError as error:
            problems.append({"path": rel(root, path), "problem": str(error)})
            continue
        if item is not None:
            items.append(item)
    return Project(slug, folder, epics, initiative, prefixes, items, problems)


def link_ref(root: Path, project: Project, target: str) -> str | None:
    if REF.fullmatch(target):
        return target
    path = link_path(root, project.slug, target)
    if not path.parents[1].is_dir():
        raise ItemError(f"{target!r}: its project folder does not exist")
    if not path.is_file():
        raise ItemError(f"{target!r} does not exist")
    item = read_item(path)
    if item is None:
        raise ItemError(f"{target!r} is not an item (no front matter)")
    if not item.tracked:
        raise ItemError(f"{target!r} has tracker = false")
    return item.card


def _link_problems(root: Path, project: Project, item: Item) -> list[str]:
    out = []
    seen: dict[str, str] = {}
    own = item.path.resolve()
    for kind in LINK_KINDS:
        for target in item.links[kind]:
            if not isinstance(target, str) or not (
                REF.fullmatch(target) or LINK_PATH.fullmatch(target)
            ):
                continue
            try:
                link_ref(root, project, target)
            except ItemError as error:
                out.append(f"{kind}: {error}")
                continue
            if REF.fullmatch(target):
                key, itself = target, target == item.card
            else:
                resolved = link_path(root, project.slug, target)
                key, itself = str(resolved), resolved == own
            if itself:
                out.append(f"{kind}: {target!r} is the item itself")
            elif key in seen and seen[key] != kind:
                out.append(f"{target!r} is in more than one link list ({seen[key]}, {kind})")
            seen.setdefault(key, kind)
    return out


def _item_problems(root: Path, project: Project, item: Item, people: PeopleDirectory) -> list[str]:
    out = schema_problems(item)
    epic = item.front.get("epic")
    if isinstance(epic, str) and REF.fullmatch(epic) and epic not in project.epics:
        out.append(f"epic {epic} is not in project.toml")
    for key in ("assignee", "reporter"):
        value = item.front.get(key)
        if isinstance(value, str) and DEV_ID.fullmatch(value) and (found := people.problem(value)):
            out.append(f"{key}: {found}")
    docs = item.front.get("docs")
    if isinstance(docs, list):
        for doc in docs:
            if is_doc(doc) and not (project.folder / posixpath.normpath(f"tasks/{doc}")).is_file():
                out.append(f"docs: {doc!r} does not exist in the project")
    return out + _link_problems(root, project, item)


def check_offline(projects: list[Project], root: Path, people: PeopleDirectory) -> list[dict]:
    found = [dict(p) for project in projects for p in project.problems]
    cards: dict[str, list[Item]] = {}
    for project in projects:
        for item in project.items:
            if item.tracked and item.card:
                cards.setdefault(item.card, []).append(item)
    for project in projects:
        for item in project.items:
            where = rel(root, item.path)
            texts = _item_problems(root, project, item, people)
            for other in cards.get(item.card or "", []):
                if other.path != item.path:
                    texts.append(f"{item.card} is also the card of {rel(root, other.path)}")
            found += [{"path": where, "problem": text} for text in texts]
    return found


def pending_offline(projects: list[Project], root: Path) -> list[dict]:
    """The creates that wait for an epic, in the shape of `ws item check --tracker`'s pending."""
    return [
        {"path": rel(root, item.path), "card": None, "op": "create", "needs": "epic"}
        for project in projects
        for item in project.items
        if item.tracked and not item.card and "epic" not in item.front
    ]


def _fold(heading: str) -> str:
    plain = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode()
    return "-".join(_WORD.findall(plain.lower())[:_NAME_WORDS])


def new_item(
    root: Path,
    slug: str,
    *,
    type_: str,
    epic: str | None = None,
    assignee: str,
    reporter: str,
    heading: str,
    name: str | None = None,
) -> Path:
    folder = root.resolve() / "projects" / slug
    if not SLUG_PATTERN.fullmatch(slug) or not folder.is_dir():
        raise ProjectMissing(f"project {slug!r} has no folder projects/{slug}")
    if type_ not in CARD_TYPES:
        raise ItemError(f"type must be one of {', '.join(CARD_TYPES)}")
    if epic is not None and not REF.fullmatch(epic):
        raise ItemError(f"epic {epic!r} is not a card ref")
    for label, person in (("assignee", assignee), ("reporter", reporter)):
        if not DEV_ID.fullmatch(person):
            raise ItemError(f"{label} {person!r} must be a dev id (ws people me prints yours)")
    heading = heading.strip()
    if not heading or "\n" in heading:
        raise ItemError("heading must be one non-empty line")
    name = name if name is not None else _fold(heading)
    if not SLUG_PATTERN.fullmatch(name):
        raise ItemError(f"name {name!r} must be lowercase letters and digits joined by hyphens")
    template = root.resolve() / "templates" / "item" / f"{type_}.md"
    if not template.is_file():
        raise ItemError(f"missing template templates/item/{type_}.md")
    sections = template.read_text(encoding="utf-8")
    if tuple(re.findall(r"^## (.+)$", sections, re.M)) != required_sections(type_):
        raise ItemError(f"templates/item/{type_}.md does not hold the required sections")
    tasks = folder / "tasks"
    tasks.mkdir(exist_ok=True)
    numbers = [int(m.group()) for p in tasks.iterdir() if (m := _NUMBER.match(p.name))]
    number = f"{max(numbers, default=0) + 1:02d}"
    path = tasks / f"{number}-{name}.md"
    keys = [("type", type_)]
    if epic is not None:
        keys.append(("epic", epic))
    keys += [("assignee", assignee), ("reporter", reporter)]
    front = "".join(f'{key} = "{value}"\n' for key, value in keys)
    write_text(path, f"+++\n{front}+++\n# {number} — {heading}\n\n{sections}")
    return path


def _escape(text: str) -> str:
    return text.replace("|", "\\|")


def _status(item: Item) -> str:
    raw = item.cache.get("status") if item.tracked else item.front.get("status")
    return STATUS_LABELS.get(raw, "—") if isinstance(raw, str) else "—"


def _row(item: Item) -> str:
    number = _NUMBER.match(item.path.name)
    title = _TITLE_NUMBER.sub("", item.heading, count=1) or item.path.stem
    kind = item.front.get("type")
    person = item.front.get("assignee")
    cells = [
        number.group() if number else "—",
        f"[{_escape(title)}](tasks/{item.path.name})",
        item.card or "—",
        TYPE_LABELS.get(kind, "—") if isinstance(kind, str) else "—",
        _escape(person) if isinstance(person, str) else "—",
        _status(item),
    ]
    return "| " + " | ".join(cells) + " |"


def table_block(project: Project) -> str:
    rows = [_row(item) for item in project.items]
    return "\n".join([TABLE_START, TABLE_HEADER, TABLE_RULE, *rows, TABLE_END])


def write_table(project: Project) -> bool:
    readme = project.folder / "README.md"
    try:
        text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ItemError(f"cannot read {readme.name}: {error}") from None
    start = text.find(TABLE_START)
    end = text.find(TABLE_END, start + len(TABLE_START)) if start >= 0 else -1
    if start < 0 or end < 0:
        raise ItemError(
            f"projects/{project.slug}/README.md needs {TABLE_START} then {TABLE_END}; "
            "ws item table never adds them"
        )
    new = text[:start] + table_block(project) + text[end + len(TABLE_END) :]
    if new == text:
        return False
    write_text(readme, new)
    return True
