"""The neutral side of a card write: documents, approval digest, pending record, apply loop.

Nothing here knows a tracker; an adapter supplies the plan and the `Writer` that sends it.
"""

import hashlib
import json
from collections.abc import Callable, Iterator
from datetime import date

from ws import approval, contracts
from ws.carddraft import Draft
from ws.tracker.port import TrackerError

VERSION = 1
SCHEMAS = ("card-write", "card-plan", "card-result")
OPS = ("create", "edit", "move", "comment", "worklog", "link")

REQUIRED = {
    "create": {"type", "priority", "title"},
    "edit": {"key"},
    "move": {"key"},
    "comment": {"key", "body"},
    "worklog": {"key", "time"},
    "link": {"key"},
}
OPTIONAL = {
    "create": {"body", "epic", "parent", "assignee", "reporter", "sprint", "due", "item"},
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
        "body",
    },
    "move": {"to", "status"},
    "comment": set(),
    "worklog": {"day", "body"},
    "link": {"blocks", "blocked_by", "relates"},
}
HEADER = {"$schema", "version", "op"}
DATES = {"start", "due", "day"}


def to_document(draft: Draft) -> dict:
    document: dict = {"$schema": "card-write", "version": VERSION, "op": draft.op}
    for name, value in draft.values.items():
        document[name] = value.isoformat() if isinstance(value, date) else value
    if draft.title is not None:
        document["title"] = draft.title
    if draft.body.strip():
        document["body"] = draft.body
    return document


def from_document(document: dict) -> Draft:
    values = {}
    for name, value in document.items():
        if name in HEADER or name == "body" or (name == "title" and document["op"] == "create"):
            continue
        values[name] = date.fromisoformat(value) if name in DATES else value
    canonical = json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return Draft(
        document["op"],
        values,
        document.get("title") if document["op"] == "create" else None,
        document.get("body", ""),
        hashlib.sha256(canonical.encode()).hexdigest(),
    )


def check_document(document: dict) -> list[str]:
    name = document.get("$schema")
    if name not in SCHEMAS:
        return [f"$schema: unknown contract {name!r}"]
    if document.get("version") != VERSION:
        return [f"version: unknown version {document.get('version')!r}"]
    problems = contracts.validate(document, name)
    op = document.get("op")
    if name == "card-write" and op in OPS and not problems:
        problems += _op_problems(document, op)
    return problems


def _op_problems(document: dict, op: str) -> list[str]:
    allowed = REQUIRED[op] | OPTIONAL[op] | HEADER
    problems = [f"$.{key}: not a key of op {op}" for key in document if key not in allowed]
    problems += [
        f"$: missing required key {key} for op {op}" for key in sorted(REQUIRED[op] - set(document))
    ]
    for name in sorted(DATES & set(document)):
        if not _is_date(document[name]):
            problems.append(f"$.{name}: expected a date YYYY-MM-DD")
    if "sprint" in document and "sprint" in OPTIONAL[op]:
        problems += _sprint_problems(document["sprint"], op)
    if op == "move" and "to" in document and "status" in document:
        problems.append("a move needs exactly one of to or status, not both")
    if op == "move" and "to" not in document and "status" not in document:
        problems.append("missing key 'to' for op move")
    if op == "link" and not any(document.get(kind) for kind in OPTIONAL["link"]):
        problems.append("$: a link needs blocks, blocked_by or relates")
    return problems


def _sprint_problems(sprint: str, op: str) -> list[str]:
    """`sprint` is "active", "next", "backlog" or a sprint's name; the tracker resolves it."""
    if not sprint.strip():
        return ["$.sprint: expected a non-empty string"]
    if op == "create" and sprint == "backlog":
        return ["$.sprint: a create without `sprint` already goes to the backlog"]
    return []


def _is_date(value: object) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def calls(plan: dict) -> list[dict]:
    return [
        {"method": call["method"], "path": call["path"], "body": call["body"]}
        for step in plan["steps"]
        for call in step["native"]
    ]


def digest_material(plan: dict) -> dict:
    return {
        "site": plan["target"].rstrip("/"),
        "requests": calls(plan),
        "before": [step["before"] for step in plan["steps"]],
        "summary": plan["summary"],
    }


def plan_code(plan: dict) -> str:
    return approval.digest(digest_material(plan))


def pending_record(plan: dict, *, created_at: str, sid: int) -> dict:
    material = digest_material(plan)
    return {
        "code": plan_code(plan),
        "created_at": created_at,
        "site": material["site"],
        "today": plan["today"],
        "sid": sid,
        "drafts": [step["draft"] for step in plan["steps"]],
        "requests": material["requests"],
        "before": material["before"],
        "summary": material["summary"],
    }


def apply_steps(writer, plan: dict, send: Callable[[dict], object]) -> Iterator[dict]:
    for step in plan["steps"]:
        sent: list[dict] = []
        first = None
        try:
            for call in step["native"]:
                reply = send(call)
                if not sent:
                    first = reply
                sent.append(call)
        except TrackerError as error:
            uncertain = bool(getattr(error, "uncertain", False))
            yield _result(step, "uncertain" if uncertain else "failed", sent, str(error))
            return
        except Exception as error:
            yield _result(step, "uncertain", sent, f"{type(error).__name__}: {error}")
            return
        try:
            created = writer.created_key(first) if step["op"] == "create" else None
            key = created or step["card"]
            url = writer.card_url(key) if key else None
        except Exception as error:
            yield _result(step, "uncertain", sent, f"{type(error).__name__}: {error}")
            return
        yield _result(step, "applied", sent, None, created=created, url=url)


def _result(
    step: dict,
    status: str,
    sent: list[dict],
    error: str | None,
    *,
    created: str | None = None,
    url: str | None = None,
) -> dict:
    return {
        "draft": step["draft"],
        "status": status,
        "sent": sent,
        "created": created,
        "url": url,
        "error": error,
    }
