"""`ws card`: check, preview and apply the model's drafts to the user's Jira, behind an approval."""

import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ws import cardrules, userconfig
from ws.carddraft import Draft, DraftError, parse_draft
from ws.cardrules import Verdict
from ws.config import data_dir
from ws.jira import JiraClient, JiraError

REQUEST_TIMEOUT = 20
APPROVAL_WINDOW = timedelta(minutes=30)

_CODE = re.compile(r"^[0-9a-f]{12}$")
_PROJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SUBFOLDERS = ("drafts", "pending", "done")


class SetupNeeded(Exception):
    pass


@dataclass
class Loaded:
    path: Path
    draft: Draft | None
    sha256: str | None
    problems: list[str]


@dataclass
class Plan:
    loaded: list[Loaded]
    verdicts: list[Verdict]

    @property
    def ok(self) -> bool:
        return all(not verdict.problems for verdict in self.verdicts)


def _now() -> datetime:
    return datetime.now(UTC)


def _store(*parts: str) -> Path:
    return data_dir().joinpath("cards", *parts)


def _ensure_store() -> None:
    for name in ("", *_SUBFOLDERS):
        folder = _store(name) if name else _store()
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        folder.chmod(0o700)


def collect(argument: str, single: bool = False) -> list[Path]:
    path = Path(argument).expanduser().resolve()
    if path.is_file():
        return [path]
    if single:
        raise DraftError([f"{argument} is not a draft file"])
    if path.is_dir():
        found = sorted(item for item in path.iterdir() if item.is_file() and item.suffix == ".md")
        if found:
            return found
        raise DraftError([f"{argument} holds no .md drafts"])
    raise DraftError([f"{argument} does not exist"])


def load(path: Path) -> Loaded:
    try:
        raw = path.read_bytes()
    except OSError as error:
        return Loaded(path, None, None, [f"cannot read the draft: {error.strerror}"])
    try:
        draft = parse_draft(raw)
    except DraftError as error:
        return Loaded(path, None, hashlib.sha256(raw).hexdigest(), error.problems)
    return Loaded(path, draft, draft.sha256, [])


def _needed_keys(loaded: list[Loaded]) -> set[str]:
    needed = {"project"}
    for item in loaded:
        if item.draft is None:
            continue
        op, values = item.draft.op, item.draft.values
        if op == "create":
            needed |= {"board_id", "issue_type", "start_date_field", "sprint_field"}
        if op == "edit":
            if "priority" in values:
                needed.add("issue_type")
            if "start" in values:
                needed.add("start_date_field")
    return needed


def _session(needed: set[str]) -> tuple[userconfig.JiraConfig, JiraClient]:
    try:
        settings = userconfig.load_config().jira
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid) as error:
        raise SetupNeeded(str(error)) from None
    missing = [name for name in sorted(needed) if getattr(settings, name) is None]
    if missing:
        raise SetupNeeded(
            f"config.toml [jira] is missing {', '.join(missing)}; see the README section "
            '"Local config"'
        )
    if not _PROJECT.match(settings.project):
        raise SetupNeeded("config.toml [jira] project is not a valid project key")
    try:
        credential = userconfig.load_jira_token()
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid):
        raise SetupNeeded(
            "no Jira API key; run `ws config token jira` in your own terminal"
        ) from None
    return settings, JiraClient(settings.site, settings.email, credential, timeout=REQUEST_TIMEOUT)


def _run(command: str, action) -> int:
    try:
        return action()
    except SetupNeeded as error:
        print(f"ws card {command}: {error}", file=sys.stderr)
        return 2
    except JiraError as error:
        print(f"ws card {command}: {error}", file=sys.stderr)
        return 3
    except (KeyError, TypeError, AttributeError) as error:
        print(f"ws card {command}: unexpected answer from Jira ({error!r})", file=sys.stderr)
        return 3


def build_plan(client: JiraClient, settings, loaded: list[Loaded]) -> Plan:
    context = cardrules.Context.load(client, settings, _now())
    verdicts = [
        cardrules.check(context, item.draft) if item.draft else Verdict(problems=item.problems)
        for item in loaded
    ]
    return Plan(loaded, verdicts)


def approval_code(site: str, requests: list[dict]) -> str:
    material = {
        "site": site.rstrip("/"),
        "requests": [
            {"method": item["method"], "path": item["path"], "body": item["body"]}
            for item in requests
        ],
    }
    text = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def run_check(argument: str) -> int:
    try:
        [path] = collect(argument, single=True)
    except DraftError as error:
        _print_verdict(Verdict(problems=error.problems))
        return 1
    item = load(path)
    if item.draft is None:
        _print_verdict(Verdict(problems=item.problems))
        return 1

    def action() -> int:
        settings, client = _session(_needed_keys([item]))
        _ensure_store()
        verdict = build_plan(client, settings, [item]).verdicts[0]
        _print_verdict(verdict)
        return 1 if verdict.problems else 0

    return _run("check", action)


def _print_verdict(verdict: Verdict) -> None:
    payload = {
        "ok": not verdict.problems,
        "problems": verdict.problems,
        "warnings": verdict.warnings,
        "resolved": verdict.resolved,
        "requests": [verdict.request] if verdict.request else [],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_epics() -> int:
    def action() -> int:
        settings, client = _session({"project"})
        jql = (
            f'assignee = currentUser() AND project = "{settings.project}" '
            "AND statusCategory != Done"
        )
        epics: dict[str, dict] = {}
        for issue in client.search(jql, ["parent"]):
            parent = (issue.get("fields") or {}).get("parent") or {}
            fields = parent.get("fields") or {}
            status = fields.get("status") or {}
            done = (status.get("statusCategory") or {}).get("key") == "done"
            if (fields.get("issuetype") or {}).get("hierarchyLevel") != 1 or done:
                continue
            title = fields.get("summary") or ""
            prefix = re.match(r"^\[[^\]]+\]", title)
            epics.setdefault(
                parent["key"],
                {
                    "key": parent["key"],
                    "title": title,
                    "prefix": prefix.group(0) if prefix else None,
                    "status": status.get("name"),
                },
            )
        print(json.dumps({"epics": list(epics.values())}, ensure_ascii=False, indent=2))
        return 0

    return _run("epics", action)


def run_apply(argument: str, dry_run: bool, approve: str | None) -> int:
    if dry_run == (approve is not None):
        print("ws card apply: use exactly one of --dry-run or --approve CODE", file=sys.stderr)
        return 1
    if approve is not None and not _CODE.match(approve):
        print("ws card apply: the approval code is 12 lowercase hex characters", file=sys.stderr)
        return 1
    try:
        loaded = [load(path) for path in collect(argument)]
    except DraftError as error:
        print(f"ws card apply: {'; '.join(error.problems)}", file=sys.stderr)
        return 1
    if dry_run:
        return _run("apply", lambda: _dry_run(argument, loaded))
    return _run("apply", lambda: _approve(approve, loaded))


def _print_problems(plan: Plan) -> None:
    print("Nada foi enviado. Problemas encontrados:")
    for item, verdict in zip(plan.loaded, plan.verdicts, strict=True):
        for problem in verdict.problems:
            print(f"  {item.path.name}: {problem}")


def _dry_run(argument: str, loaded: list[Loaded]) -> int:
    settings, client = _session(_needed_keys(loaded))
    _ensure_store()
    plan = build_plan(client, settings, loaded)
    if not plan.ok:
        _print_problems(plan)
        return 1
    requests = [verdict.request for verdict in plan.verdicts]
    code = approval_code(settings.site, requests)
    _purge_expired()
    _write_pending(code, settings.site, loaded, requests)
    print(f"Prévia de {len(loaded)} mudança(s); nada foi enviado ao Jira.")
    for number, (item, verdict) in enumerate(zip(loaded, plan.verdicts, strict=True), start=1):
        print(f"\n[{number}/{len(loaded)}] {item.path.name}")
        for line in verdict.preview:
            print(f"  {line}")
        for warning in verdict.warnings:
            print(f"  Aviso: {warning}")
        request = verdict.request
        print(f"  Requisição: {request['method']} {request['path']}")
        body = json.dumps(request["body"], ensure_ascii=False, indent=2)
        print("\n".join(f"    {line}" for line in body.splitlines()))
    print(f"\nCódigo de aprovação: {code}")
    print(f"Para aplicar: ws card apply {argument} --approve {code}")
    return 0


def _pending_path(code: str) -> Path:
    return _store("pending", f"{code}.json")


def _write_pending(code: str, site: str, loaded: list[Loaded], requests: list[dict]) -> None:
    record = {
        "code": code,
        "created_at": _now().isoformat(),
        "site": site.rstrip("/"),
        "drafts": [{"path": str(item.path), "sha256": item.sha256} for item in loaded],
        "requests": requests,
    }
    descriptor = os.open(_pending_path(code), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
    _pending_path(code).chmod(0o600)


def _read_pending(code: str) -> dict | None:
    try:
        record = json.loads(_pending_path(code).read_text(encoding="utf-8"))
        created = datetime.fromisoformat(record["created_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    record["_created"] = created
    return record


def _purge_expired() -> None:
    for path in _store("pending").glob("*.json"):
        record = _read_pending(path.stem)
        if record is None or _now() - record["_created"] > APPROVAL_WINDOW:
            path.unlink(missing_ok=True)


def _approve(code: str, loaded: list[Loaded]) -> int:
    _ensure_store()
    record = _read_pending(code)
    if record is None:
        print(
            f"ws card apply: no pending preview for code {code}; run --dry-run first",
            file=sys.stderr,
        )
        return 1
    if _now() - record["_created"] > APPROVAL_WINDOW:
        _pending_path(code).unlink(missing_ok=True)
        print(
            "ws card apply: the preview expired (30 minutes); run --dry-run again", file=sys.stderr
        )
        return 1
    current = [{"path": str(item.path), "sha256": item.sha256} for item in loaded]
    if record.get("drafts") != current:
        print(
            "ws card apply: the drafts changed since the preview; run --dry-run again",
            file=sys.stderr,
        )
        return 1
    settings, client = _session(_needed_keys(loaded))
    plan = build_plan(client, settings, loaded)
    if not plan.ok:
        _print_problems(plan)
        return 1
    requests = [verdict.request for verdict in plan.verdicts]
    if approval_code(settings.site, requests) != code or record.get("site") != settings.site.rstrip(
        "/"
    ):
        print(
            "ws card apply: the requests now differ from the preview (Jira changed); "
            "run --dry-run again",
            file=sys.stderr,
        )
        return 1
    if (refused := guard(settings.project, requests)) is not None:
        print(f"ws card apply: request outside the allowed shapes: {refused}", file=sys.stderr)
        return 1
    try:
        _pending_path(code).unlink()
    except FileNotFoundError:
        print(f"ws card apply: the preview {code} was already used", file=sys.stderr)
        return 1
    return _send_all(settings, client, plan)


def guard(project: str, requests: list[dict]) -> str | None:
    """The last line of defence: only the five request shapes, only on cards of the project."""
    key = rf"{re.escape(project)}-[1-9]\d*"
    allowed = {
        ("POST", re.compile(r"/rest/api/3/issue")),
        ("PUT", re.compile(rf"/rest/api/3/issue/{key}")),
        ("POST", re.compile(rf"/rest/api/3/issue/{key}/(transitions|comment|worklog)")),
    }
    for request in requests:
        if not any(
            request["method"] == method and pattern.fullmatch(request["path"])
            for method, pattern in allowed
        ):
            return f"{request['method']} {request['path']}"
    return None


def _send(client: JiraClient, request: dict):
    if request["method"] == "PUT":
        return client.put(request["path"], request["body"])
    return client.post(request["path"], request["body"])


def _jql_for(project: str, title: str) -> str:
    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')

    phrase = f'"{escape(title)}"'
    return f'project = "{project}" AND summary ~ "{escape(phrase)}" ORDER BY created DESC'


def _send_all(settings, client: JiraClient, plan: Plan) -> int:
    site = settings.site.rstrip("/")
    for index, (item, verdict) in enumerate(zip(plan.loaded, plan.verdicts, strict=True)):
        request = verdict.request
        try:
            answer = _send(client, request)
        except JiraError as error:
            _report_failure(settings, plan, index, error)
            return 3
        key = (answer or {}).get("key") if request["path"] == "/rest/api/3/issue" else None
        key = key or verdict.resolved.get("card", {}).get("key")
        verb = "Criado" if request["path"] == "/rest/api/3/issue" else "Aplicado"
        link = f" {site}/browse/{key}" if key else ""
        print(f"{verb}: {item.path.name}{link}")
        _move_to_done(item.path)
    return 0


def _report_failure(settings, plan: Plan, index: int, error: JiraError) -> None:
    item, verdict = plan.loaded[index], plan.verdicts[index]
    if error.uncertain:
        print(f"{item.path.name}: resultado incerto: confira no Jira ({error})")
        if verdict.request["path"] == "/rest/api/3/issue":
            title = verdict.request["body"]["fields"]["summary"]
            print(f"Para procurar o card, use esta JQL: {_jql_for(settings.project, title)}")
    else:
        print(f"{item.path.name}: o Jira recusou: {error}")
    print(
        "Nada mais foi enviado, e a aprovação foi consumida; refaça a prévia para tentar de novo."
    )
    pending = [other.path.name for other in plan.loaded[index + 1 :]]
    if pending:
        print(f"Não enviados: {', '.join(pending)}")


def _move_to_done(path: Path) -> None:
    target = _store("done", path.name)
    number = 1
    while target.exists():
        target = _store("done", f"{path.stem}-{number}{path.suffix}")
        number += 1
    shutil.move(path, target)
