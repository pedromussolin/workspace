"""Reads the board map (TSV files kept outside the repo) into rows and checks them."""

import csv
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ws.identity import DEV_ID, dev_id

TYPE_NEUTRAL = {
    "Tarefa": "task",
    "Bug": "bug",
    "HotFix": "hotfix",
    "Melhoria": "improvement",
    "Nova função": "feature",
    "Epic": "epic",
    "Iniciativa": "initiative",
}
SUPPORT_FILES = ("docs.tsv", "adopt-pending.tsv")
PROJECT_DIR = {"whitelabel": "whitelabel-restructure"}
EPIC_ALIAS = {"VM TELAS": "novo-E1"}

_STATUS_PREFIXES = (
    ("conclu", "done"),
    ("cancel", "cancelled"),
    ("absorvid", "cancelled"),
    ("em andamento", "in_progress"),
    ("a fazer", "todo"),
    ("decisões pendentes", "todo"),
    ("aguardando", "todo"),
    ("em parte substituída", "todo"),
    ("adiada", "todo"),
)
_LEGACY_KIND = re.compile(r"\b(blocked by|blocks|relates)\b", re.IGNORECASE)
_LEGACY_KINDS = {"blocked by": "blocked_by", "blocks": "blocks", "relates": "relates"}
_CANONICAL_KINDS = {"blocks", "blocked_by", "relates"}
_CANONICAL = re.compile(r"(blocks|blocked_by|relates):")
_TS_REF = re.compile(r"TS-\d+")
_FILE = re.compile(r"(?P<file>\S+?)(?: \((?P<origin>[^)]+)\))?")
_PREFIX = re.compile(r"^\[[^\]]*\]\s*")


@dataclass(frozen=True)
class Link:
    kind: str
    ref: str


@dataclass(frozen=True)
class Row:
    source: str
    line: int
    project: str
    file: str | None
    origin_project: str | None
    card: str
    action: str
    type_: str | None
    epic: str | None
    assignee: str | None
    reporter: str | None
    links: tuple[Link, ...]
    status: str
    scope: str
    heading: str
    done_when: str
    title: str = ""


def parse_links(text: str) -> tuple[Link, ...]:
    text = text.strip()
    if text in ("", "-"):
        return ()
    if _CANONICAL.match(text):
        links = []
        for part in text.split(";"):
            kind, _, ref = part.partition(":")
            if kind.strip() in _CANONICAL_KINDS and ref.strip():
                links.append(Link(kind.strip(), ref.strip()))
        return tuple(links)
    links = []
    matches = list(_LEGACY_KIND.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        kind = _LEGACY_KINDS[m.group(1).lower()]
        links += [Link(kind, ref) for ref in _TS_REF.findall(text[m.end() : end])]
    return tuple(links)


def neutral_status(text: str) -> str | None:
    lowered = text.strip().lower()
    for prefix, status in _STATUS_PREFIXES:
        if lowered.startswith(prefix):
            return status
    return None


def _cell(value: str | None) -> str | None:
    value = (value or "").strip()
    return None if value in ("", "-") else value


def _row(stem: str, number: int, cells: dict[str, str | None]) -> Row:
    file = origin = None
    raw_file = _cell(cells.get("file"))
    if raw_file and raw_file.startswith("tasks/") and (m := _FILE.fullmatch(raw_file)):
        file, origin = m["file"], m["origin"]
    card = (cells.get("card") or "").strip()
    if card == "novo":
        card = f"novo-{stem}-{number}"
    epic = _cell(cells.get("epic"))
    type_ = _cell(cells.get("type"))
    return Row(
        source=f"{stem}.tsv",
        line=number,
        project=(cells.get("project") or "").strip(),
        file=file,
        origin_project=origin,
        card=card,
        action=(cells.get("action") or "").strip(),
        type_=TYPE_NEUTRAL.get(type_, type_) if type_ else None,
        epic=EPIC_ALIAS.get(epic, epic) if epic else None,
        assignee=_cell(cells.get("assignee")),
        reporter=_cell(cells.get("reporter")),
        links=parse_links(cells.get("links") or ""),
        status=(cells.get("status") or "").strip(),
        scope=_cell(cells.get("scope")) or "",
        heading=_PREFIX.sub("", (cells.get("title") or "").strip()),
        done_when=_cell(cells.get("done_when")) or "",
        title=(cells.get("title") or "").strip(),
    )


def load_rows(map_dir: Path) -> list[Row]:
    rows = []
    for path in sorted(map_dir.glob("*.tsv")):
        if path.name in SUPPORT_FILES:
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
            for record in reader:
                if not any((v or "").strip() for v in record.values() if isinstance(v, str)):
                    continue
                rows.append(_row(path.stem, reader.line_num, record))
    return rows


def load_people(path: Path) -> dict[str, str]:
    people, bad = {}, []
    for name, value in tomllib.loads(path.read_text(encoding="utf-8")).items():
        value = str(value).strip()
        if "@" in value:
            people[name] = dev_id(value)
        elif DEV_ID.fullmatch(value):
            people[name] = value
        else:
            bad.append(name)
    if bad:
        raise ValueError(f"people file: neither an e-mail nor a dev id: {', '.join(bad)}")
    return people


def _is_item_row(row: Row) -> bool:
    return row.project != "epico" and row.type_ not in ("epic", "initiative")


def check_rows(rows: list[Row], people: dict[str, str]) -> list[str]:
    cards = {r.card for r in rows}
    problems = []
    for r in rows:
        where = f"{r.source}:{r.line}"
        if r.action == "perguntar":
            problems.append(f"{where} action 'perguntar' is still open: edit the map")
        if not _is_item_row(r):
            continue
        tracked = r.action != "sem-card"
        if r.type_ is not None and r.type_ not in TYPE_NEUTRAL.values():
            problems.append(f"{where} unknown type '{r.type_}'")
        if tracked and r.type_ is None:
            problems.append(f"{where} tracked row without a type")
        for role, name in (("assignee", r.assignee), ("reporter", r.reporter)):
            if name is None and tracked:
                problems.append(f"{where} tracked row without a {role}")
            elif name is not None and name not in people:
                problems.append(f"{where} {role} '{name}' is not in the people file")
        if not tracked and r.file and neutral_status(r.status) is None:
            problems.append(f"{where} unknown status text '{r.status}' on a card-less row")
        if r.epic and r.epic.startswith("novo-") and r.card.upper().startswith("TS-"):
            problems.append(f"{where} card {r.card} points to the epic {r.epic}, not created yet")
        for link in r.links:
            if link.ref.startswith("novo-") and link.ref not in cards:
                problems.append(f"{where} link to '{link.ref}', which no row has")
    return problems
