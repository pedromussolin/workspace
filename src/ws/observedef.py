"""The observation plan: a local TOML that maps one to one onto the `observe-plan` document."""

import hashlib
import json
import os
import re
import tomllib
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ws import userconfig
from ws.config import data_dir
from ws.privatefile import PRIVATE_FOLDER, private_folder
from ws.project import SLUG_PATTERN
from ws.tracker.vocab import REF

KINDS = ("observability", "database", "manual")
SIGNALS = ("traces", "logs", "metrics")
DEFAULT_DAYS = 5
DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_DATABASE = "replica"
CHECK_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
EXPECT = re.compile(r"(==|<=) ?(\d+)")
DATABASE_NAME = re.compile(r"[a-z0-9_-]+")
PRIVATE_FILE = 0o600
RESULTS_SUFFIX = ".results.jsonl"

NEEDS = {
    "observability": ("signal", "query", "expect"),
    "database": ("sql", "expect", "database"),
    "manual": ("question",),
}
KIND_FIELDS = ("signal", "query", "expect", "database", "sql", "question")


class Invalid(ValueError):
    pass


@dataclass(frozen=True)
class Check:
    id: str
    kind: str
    label: str | None = None
    expect: str | None = None
    signal: str | None = None
    query: str | None = None
    database: str | None = None
    sql: str | None = None
    question: str | None = None


@dataclass(frozen=True)
class Plan:
    task: str
    job: str
    switched_off: date
    days: int
    timezone: str
    checks: tuple[Check, ...]


def plan_document(table: dict) -> dict:
    document = dict(table)
    if isinstance(document.get("switched_off"), date):
        document["switched_off"] = document["switched_off"].isoformat()
    document.setdefault("days", DEFAULT_DAYS)
    document.setdefault("timezone", DEFAULT_TIMEZONE)
    checks = []
    for each in document.get("checks", []):
        if isinstance(each, dict) and each.get("kind") == "database":
            each = {**each, "database": each.get("database", DEFAULT_DATABASE)}
        checks.append(each)
    document["checks"] = checks
    return document


def text_of(value: object, where: str, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Invalid(f"{where}: {key}: must be a non-empty text")
    return value


def parse_check(raw: object, index: int, where: str, seen: set[str]) -> Check:
    prefix = f"checks[{index}]"
    if not isinstance(raw, dict):
        raise Invalid(f"{where}: {prefix}: must be a table")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise Invalid(f"{where}: {prefix}.kind: must be one of {', '.join(KINDS)}")
    check_id = text_of(raw.get("id"), where, f"{prefix}.id")
    if not CHECK_ID.fullmatch(check_id):
        raise Invalid(f"{where}: {prefix}.id: must match {CHECK_ID.pattern}")
    if check_id in seen:
        raise Invalid(f"{where}: {prefix}.id: duplicate {check_id}")
    seen.add(check_id)
    known = {field.name for field in fields(Check)}
    for name in raw:
        if name not in known:
            raise Invalid(f"{where}: {prefix}.{name}: unknown key")
    for name in KIND_FIELDS:
        if name in raw and name not in NEEDS[kind]:
            raise Invalid(f"{where}: {prefix}.{name}: not allowed for {kind}")
    for name in NEEDS[kind]:
        if name not in raw:
            raise Invalid(f"{where}: {prefix}.{name}: required for {kind}")
        text_of(raw[name], where, f"{prefix}.{name}")
    if "label" in raw:
        text_of(raw["label"], where, f"{prefix}.label")
    if "expect" in raw and not EXPECT.fullmatch(raw["expect"]):
        raise Invalid(f"{where}: {prefix}.expect: must look like '== 0' or '<= 3'")
    if kind == "observability" and raw["signal"] not in SIGNALS:
        raise Invalid(f"{where}: {prefix}.signal: must be one of {', '.join(SIGNALS)}")
    if kind == "database" and not DATABASE_NAME.fullmatch(raw["database"]):
        raise Invalid(f"{where}: {prefix}.database: must match {DATABASE_NAME.pattern}")
    return Check(**raw)


PLAN_KEYS = ("version", "task", "job", "switched_off", "days", "timezone", "checks")


def parse_plan(document: dict, where: str) -> Plan:
    for name in document:
        if name not in PLAN_KEYS:
            raise Invalid(f"{where}: {name}: unknown key")
    if document.get("version") != 1 or isinstance(document.get("version"), bool):
        raise Invalid(f"{where}: version: must be 1")
    task = text_of(document.get("task"), where, "task")
    if not REF.fullmatch(task):
        raise Invalid(f"{where}: task: must look like TS-123")
    job = text_of(document.get("job"), where, "job")
    try:
        switched_off = date.fromisoformat(str(document.get("switched_off")))
    except ValueError:
        raise Invalid(f"{where}: switched_off: must be an ISO date") from None
    days = document.get("days", DEFAULT_DAYS)
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 30:
        raise Invalid(f"{where}: days: must be a whole number from 1 to 30")
    zone = document.get("timezone", DEFAULT_TIMEZONE)
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError, TypeError, OSError):
        raise Invalid(f"{where}: timezone: unknown time zone") from None
    raw_checks = document.get("checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        raise Invalid(f"{where}: checks: at least one check is required")
    seen: set[str] = set()
    checks = tuple(parse_check(raw, i, where, seen) for i, raw in enumerate(raw_checks))
    return Plan(task, job, switched_off, days, zone, checks)


def load_plan(path: Path) -> tuple[dict, Plan]:
    try:
        table = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise Invalid(f"{path}: not valid TOML: {error}") from None
    except OSError as error:
        raise Invalid(f"{path}: cannot be read: {error.strerror}") from None
    document = plan_document(table)
    return document, parse_plan(document, str(path))


def check_hash(check: Check) -> str:
    payload = {
        field.name: getattr(check, field.name)
        for field in fields(check)
        if field.name not in ("id", "label") and getattr(check, field.name) is not None
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def meets(value: Decimal, expect: str) -> bool:
    found = EXPECT.fullmatch(expect)
    if not found:
        raise Invalid(f"expect: {expect!r} must look like '== 0' or '<= 3'")
    limit = Decimal(found.group(2))
    return value == limit if found.group(1) == "==" else value <= limit


def projects_root() -> Path:
    return data_dir() / "projects"


def valid_project(project: str) -> str:
    if not isinstance(project, str) or not SLUG_PATTERN.fullmatch(project):
        raise Invalid(f"project: {project!r} must be a slug (a-z, 0-9 and '-')")
    return project


def valid_task(task: str) -> str:
    if not isinstance(task, str) or not REF.fullmatch(task):
        raise Invalid(f"task: {task!r} must look like TS-123")
    return task


def plan_path(project: str, task: str) -> Path:
    valid_project(project)
    valid_task(task)
    return projects_root() / project / "observations" / f"{task}.toml"


def all_plans(project: str | None) -> list[tuple[str, Path]]:
    root = projects_root()
    if project is not None:
        valid_project(project)
        folders = [root / project]
    else:
        folders = sorted(root.iterdir()) if root.is_dir() else []
    found = []
    for folder in folders:
        plans = folder / "observations"
        if plans.is_dir():
            found.extend((folder.name, path) for path in sorted(plans.glob("*.toml")))
    return found


def find_plan(task: str, project: str | None) -> tuple[str, Path]:
    valid_task(task)
    matches = [(name, path) for name, path in all_plans(project) if path.stem == task]
    if not matches:
        raise Invalid(f"no observation plan for {task}; run ws observe new {task} --project <slug>")
    if len(matches) > 1:
        names = ", ".join(name for name, _ in matches)
        raise Invalid(f"{task} has plans in {names}; pass --project")
    return matches[0]


EXAMPLES = """\

# One block per check; copy, uncomment and edit. The id is 1 to 40 of a-z, 0-9 and "-".
#
# [[checks]]
# id = "errors"
# kind = "observability"
# label = "Errors of the job"
# signal = "logs"          # traces, logs or metrics (a count)
# query = "<query in the observability tool's language>"
# expect = "== 0"          # "== N" or "<= N"
#
# [[checks]]
# id = "rows"
# kind = "database"
# database = "replica"
# sql = "<one read-only statement that returns one number>"
# expect = "<= 0"
#
# [[checks]]
# id = "looks-fine"
# kind = "manual"
# question = "<what the person confirms by looking>"
"""


def new_plan_text(task: str, job: str, switched_off: date, days: int, timezone: str) -> str:
    head = (
        "version = 1\n"
        f"task = {userconfig.toml_string(task)}\n"
        f"job = {userconfig.toml_string(job)}\n"
        f"switched_off = {switched_off.isoformat()}\n"
        f"days = {days}\n"
        f"timezone = {userconfig.toml_string(timezone)}\n"
    )
    return head + EXAMPLES


def write_new(project: str, task: str, text: str) -> Path:
    path = plan_path(project, task)
    private_folder(path.parent)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_FILE)
    except FileExistsError:
        raise Invalid(f"{path} exists; edit it or delete it first") from None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        path.chmod(PRIVATE_FILE)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def tighten(path: Path) -> list[str]:
    changes = []
    results = path.with_name(f"{path.stem}{RESULTS_SUFFIX}")
    targets = [(path.parent, PRIVATE_FOLDER), (path, PRIVATE_FILE), (results, PRIVATE_FILE)]
    for target, wanted in targets:
        if not target.exists():
            continue
        current = target.stat().st_mode & 0o777
        if current != wanted:
            target.chmod(wanted)
            changes.append(f"{target}: mode {current:o} set to {wanted:o}")
    return changes
