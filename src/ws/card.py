"""`ws card`: check, preview and apply the model's drafts to the user's Jira, behind an approval."""

import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ws import bootstrap, cardrules, humans, userconfig
from ws.carddraft import Draft, DraftError, parse_draft
from ws.cardrules import Verdict
from ws.config import claude_settings_path, data_dir
from ws.jira import JiraClient, JiraError, SiteRefused
from ws.tracker import UnknownTracker, require_kind

REQUEST_TIMEOUT = 20
APPROVAL_WINDOW = timedelta(minutes=30)

_CODE = re.compile(r"[0-9a-f]{12}")
_PROJECT = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_SUBFOLDERS = ("drafts", "pending", "done", "uncertain")
_OPERATIONS = {
    "create": "Criar card",
    "edit": "Editar card",
    "move": "Mover card",
    "comment": "Comentar no card",
    "worklog": "Lançar horas no card",
}


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

    @property
    def requests(self) -> list[dict]:
        return [request for verdict in self.verdicts for request in verdict.requests]

    @property
    def befores(self) -> list[dict]:
        return [verdict.before for verdict in self.verdicts]

    @property
    def today(self) -> str | None:
        return self.verdicts[0].resolved.get("today") if self.verdicts else None

    @property
    def blocks(self) -> list[list[str]]:
        """One block of PT-BR lines per draft: a header naming the operation and the card, then the
        preview lines and the warnings. The printed preview and the pending record both use it."""
        total = len(self.loaded)
        blocks = []
        for number, (item, verdict) in enumerate(zip(self.loaded, self.verdicts, strict=True), 1):
            label = _OPERATIONS.get(item.draft.op, item.draft.op) if item.draft else "?"
            key = verdict.resolved.get("card", {}).get("key")
            header = f"[{number}/{total}] {label}{f' {key}' if key else ''} ({item.path.name})"
            blocks.append(
                [
                    header,
                    *[f"  {line}" for line in verdict.preview],
                    *[f"  Aviso: {warning}" for warning in verdict.warnings],
                ]
            )
        return blocks

    @property
    def summary(self) -> list[str]:
        return [line for block in self.blocks for line in block]


def _now() -> datetime:
    return datetime.now(UTC)


def _session_id() -> int:
    """The session of the shell that runs this command. Claude Code runs each Bash call in its own
    session, so a preview and an approval in one command line share it and are refused."""
    return os.getsid(0)


def _store(*parts: str) -> Path:
    return data_dir().joinpath("cards", *parts)


def _ensure_store() -> None:
    for name in ("", *_SUBFOLDERS):
        folder = _store(name) if name else _store()
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        folder.chmod(0o700)


def _drafts_root() -> Path:
    return _store("drafts").resolve()


def drafts_folder(name: str) -> Path:
    """A new private folder under `cards/drafts/`; `FileExistsError` if the name is taken."""
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError(f"{name!r} is not a folder name")
    _ensure_store()
    folder = _store("drafts", name)
    folder.mkdir(mode=0o700)
    return folder


def collect(argument: str, single: bool = False) -> list[Path]:
    """Drafts are real files under `cards/drafts/`: nothing else is read, moved or sent."""
    root = _drafts_root()
    path = Path(argument).expanduser()
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise DraftError([f"{argument} is not a real file or folder inside {root}"])
    path = path.resolve()
    if path.is_file():
        return [path]
    if single:
        raise DraftError([f"{argument} is not a draft file"])
    if path.is_dir():
        found = []
        for item in sorted(path.iterdir()):
            if item.suffix != ".md":
                continue
            if item.is_symlink() or not item.resolve().is_relative_to(root):
                raise DraftError([f"{item.name} is a symlink or leaves {root}"])
            if item.is_file():
                found.append(item.resolve())
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
            needed |= {"board_id", "types", "sprint_field"}
        if op == "edit":
            if "priority" in values or "type" in values:
                needed.add("types")
            if "start" in values:
                needed.add("start_date_field")
        if op == "link":
            needed.add("links")
    return needed


def _session(needed: set[str]) -> tuple[userconfig.JiraConfig, JiraClient]:
    try:
        config = userconfig.load_config()
        require_kind(config.tracker_kind)
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid, UnknownTracker) as error:
        raise SetupNeeded(str(error)) from None
    settings = config.jira
    missing = [name for name in sorted(needed) if not getattr(settings, name)]
    if missing:
        tables = {"types": "[jira.types]", "links": "[jira.links]"}
        raise SetupNeeded(
            f"config.toml [jira] is missing "
            f"{', '.join(tables.get(name, name) for name in missing)}; "
            'see the README section "Local config"'
        )
    if not _PROJECT.fullmatch(settings.project):
        raise SetupNeeded("config.toml [jira] project is not a valid project key")
    try:
        credential = userconfig.load_jira_token()
    except userconfig.ConfigMissing:
        raise SetupNeeded(
            "no Jira API key; run `ws config token jira` in your own terminal"
        ) from None
    except userconfig.ConfigInvalid as error:
        raise SetupNeeded(str(error)) from None
    try:
        client = JiraClient(settings.site, settings.email, credential, timeout=REQUEST_TIMEOUT)
    except SiteRefused as error:
        raise SetupNeeded(str(error)) from None
    return settings, client


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
    except OSError as error:
        print(f"ws card {command}: file error: {error}", file=sys.stderr)
        return 1


def build_plan(client: JiraClient, settings, loaded: list[Loaded]) -> Plan:
    context = cardrules.Context.load(client, settings, _now())
    verdicts = [
        cardrules.check(context, item.draft) if item.draft else Verdict(problems=item.problems)
        for item in loaded
    ]
    return Plan(loaded, verdicts)


def approval_code(site: str, requests: list[dict], befores: list[dict], summary: list[str]) -> str:
    """Covers what is sent, the state of the card the preview showed as "before" and the text the
    person reads when approving, so the text cannot differ from what is sent."""
    material = {
        "site": site.rstrip("/"),
        "requests": [
            {"method": item["method"], "path": item["path"], "body": item["body"]}
            for item in requests
        ],
        "before": befores,
        "summary": summary,
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
        "requests": verdict.requests,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _epic_entry(issue: dict, level: int, parent: str | None) -> dict:
    fields = issue.get("fields") or {}
    title = fields.get("summary") or ""
    prefix = re.match(r"^\[[^\]]+\]", title)
    return {
        "key": issue["key"],
        "title": title,
        "prefix": prefix.group(0) if prefix else None,
        "status": (fields.get("status") or {}).get("name"),
        "level": level,
        "parent": parent,
    }


def _owned_levels(types: dict[str, str]) -> dict[str, int]:
    levels = {"epic": 1, "initiative": 2}
    return {types[name]: level for name, level in levels.items() if types.get(name)}


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
            epics.setdefault(parent["key"], _epic_entry(parent, 1, None))
        levels = _owned_levels(settings.types)
        if levels:
            wanted = ", ".join(levels)
            owned = (
                f"issuetype in ({wanted}) AND (assignee = currentUser() "
                "OR reporter = currentUser()) AND statusCategory != Done "
                f'AND project = "{settings.project}"'
            )
            fields = ["summary", "status", "issuetype", "parent"]
            found = client.search(owned, fields)
            initiatives = []
            for issue in found:
                issue_fields = issue.get("fields") or {}
                level = levels.get((issue_fields.get("issuetype") or {}).get("id"))
                if level is None:
                    continue
                parent = (issue_fields.get("parent") or {}).get("key")
                entry = _epic_entry(issue, level, parent)
                epics[issue["key"]] = {**epics.get(issue["key"], {}), **entry}
                if level == 2:
                    initiatives.append(issue["key"])
            if initiatives:
                children = f"parent in ({', '.join(initiatives)}) AND statusCategory != Done"
                for issue in client.search(children, fields):
                    parent = ((issue.get("fields") or {}).get("parent") or {}).get("key")
                    epics.setdefault(issue["key"], _epic_entry(issue, 1, parent))
        print(json.dumps({"epics": list(epics.values())}, ensure_ascii=False, indent=2))
        return 0

    return _run("epics", action)


def run_preview(argument: str) -> int:
    try:
        loaded = [load(path) for path in collect(argument)]
    except DraftError as error:
        print(f"ws card preview: {'; '.join(error.problems)}", file=sys.stderr)
        return 1
    return _run("preview", lambda: _preview(argument, loaded))


def run_apply(argument: str, approve: str | None) -> int:
    if approve is None:
        print("ws card apply: --approve CODE is required; see `ws card preview`", file=sys.stderr)
        return 1
    if not _CODE.fullmatch(approve):
        print("ws card apply: the approval code is 12 lowercase hex characters", file=sys.stderr)
        return 1
    try:
        loaded = [load(path) for path in collect(argument)]
    except DraftError as error:
        print(f"ws card apply: {'; '.join(error.problems)}", file=sys.stderr)
        return 1
    return _run("apply", lambda: _approve(approve, loaded))


def _print_problems(plan: Plan) -> None:
    print("Nada foi enviado. Problemas encontrados:")
    for item, verdict in zip(plan.loaded, plan.verdicts, strict=True):
        for problem in verdict.problems:
            print(f"  {item.path.name}: {problem}")


def _preview(argument: str, loaded: list[Loaded]) -> int:
    settings, client = _session(_needed_keys(loaded))
    _ensure_store()
    plan = build_plan(client, settings, loaded)
    if not plan.ok:
        _print_problems(plan)
        return 1
    code = approval_code(settings.site, plan.requests, plan.befores, plan.summary)
    try:
        _purge_expired()
        _write_pending(code, settings.site, plan)
    except OSError as error:
        print(
            f"ws card preview: could not save the pending record: {error.strerror or error}",
            file=sys.stderr,
        )
        return 1
    print(f"Prévia de {len(loaded)} mudança(s); nada foi enviado ao Jira.")
    for block, verdict in zip(plan.blocks, plan.verdicts, strict=True):
        print()
        print("\n".join(block))
        for request in verdict.requests:
            print(f"  Requisição: {request['method']} {request['path']}")
            body = json.dumps(request["body"], ensure_ascii=False, indent=2)
            print("\n".join(f"    {line}" for line in body.splitlines()))
    print(f"\nCódigo de aprovação: {code}")
    print(f"Para aplicar: ws card apply {shlex.quote(argument)} --approve {code}")
    return 0


def _pending_path(code: str) -> Path:
    return _store("pending", f"{code}.json")


def _write_pending(code: str, site: str, plan: Plan) -> None:
    record = {
        "code": code,
        "created_at": _now().isoformat(),
        "site": site.rstrip("/"),
        "today": plan.today,
        "sid": _session_id(),
        "drafts": [{"path": str(item.path), "sha256": item.sha256} for item in plan.loaded],
        "requests": plan.requests,
        "before": plan.befores,
        "summary": plan.summary,
    }
    path = _pending_path(code)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False)
        path.chmod(0o600)
    except OSError:
        path.unlink(missing_ok=True)
        raise


def _read_pending(code: str) -> tuple[dict | None, str | None]:
    """(record, None) usable; (None, None) absent; (None, reason) present but refused."""
    path = _pending_path(code)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, None
    except OSError as error:
        return None, f"cannot read the pending record: {error.strerror}"
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        return None, (
            f"the pending record {code} is not a private file of yours (owner, mode 600); "
            "delete it and run ws card preview again"
        )
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        created = datetime.fromisoformat(record["created_at"])
        if created.tzinfo is None:
            raise ValueError("no time zone")
    except (OSError, ValueError, KeyError, TypeError):
        return None, f"the pending record {code} is unreadable; run ws card preview again"
    if created > _now():
        return None, f"the pending record {code} is in the future; run ws card preview again"
    record["_created"] = created
    return record, None


def _purge_expired() -> None:
    for path in _store("pending").glob("*.json"):
        record, _ = _read_pending(path.stem)
        if record is None or _now() - record["_created"] > APPROVAL_WINDOW:
            path.unlink(missing_ok=True)


def _interactive() -> bool:
    return humans.by_hand()


def _confirm(summary: list[str]) -> bool:
    print("\n".join(summary))
    try:
        answer = input("Gravar no Jira? [s/N] ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in ("s", "sim")


def _record_matches_code(record: dict, code: str) -> bool:
    try:
        return code == approval_code(
            record["site"], record["requests"], record["before"], record["summary"]
        )
    except (KeyError, TypeError, AttributeError):
        return False


def _approve(code: str, loaded: list[Loaded]) -> int:
    by_hand = _interactive()
    if not by_hand and (problems := bootstrap.card_gate_problems(claude_settings_path())):
        raise SetupNeeded(
            f"{'; '.join(problems)}. Run `ws setup` and add what it prints, so Claude Code asks "
            "you before every approval"
        )
    _ensure_store()
    record, refusal = _read_pending(code)
    if refusal:
        print(f"ws card apply: {refusal}", file=sys.stderr)
        return 1
    if record is None:
        print(
            f"ws card apply: no pending preview for code {code}; run ws card preview first",
            file=sys.stderr,
        )
        return 1
    if _now() - record["_created"] > APPROVAL_WINDOW:
        _pending_path(code).unlink(missing_ok=True)
        print(
            "ws card apply: the preview expired (30 minutes); run ws card preview again",
            file=sys.stderr,
        )
        return 1
    if not _record_matches_code(record, code):
        print(
            "ws card apply: o registro pendente foi alterado; rode o ws card preview de novo",
            file=sys.stderr,
        )
        return 1
    if not by_hand and (record.get("sid") is None or record.get("sid") == _session_id()):
        print(
            "ws card apply: a prévia e a aprovação precisam ser passos separados "
            "(rode `ws card apply` em outro comando, depois de mostrar a prévia)",
            file=sys.stderr,
        )
        return 1
    current = [{"path": str(item.path), "sha256": item.sha256} for item in loaded]
    if record.get("drafts") != current:
        print(
            "ws card apply: the drafts changed since the preview; run ws card preview again",
            file=sys.stderr,
        )
        return 1
    settings, client = _session(_needed_keys(loaded))
    plan = build_plan(client, settings, loaded)
    if not plan.ok:
        _print_problems(plan)
        return 1
    site = settings.site.rstrip("/")
    if approval_code(site, plan.requests, plan.befores, plan.summary) != code or (
        record.get("site") != site
    ):
        print(f"ws card apply: {_why_it_differs(record, plan, site)}", file=sys.stderr)
        return 1
    if (refused := guard(settings.project, plan.requests)) is not None:
        print(f"ws card apply: request outside the allowed shapes: {refused}", file=sys.stderr)
        return 1
    if by_hand and not _confirm(plan.summary):
        print("Nada foi enviado.")
        return 1
    try:
        _pending_path(code).unlink()
    except FileNotFoundError:
        print(f"ws card apply: the preview {code} was already used", file=sys.stderr)
        return 1
    return _send_all(settings, client, plan)


def _why_it_differs(record: dict, plan: Plan, site: str) -> str:
    if record.get("today") != plan.today:
        return "a data de hoje mudou desde a prévia; rode o ws card preview de novo"
    if record.get("site") == site and record.get("requests") == plan.requests:
        return "o card mudou no Jira desde a prévia; rode o ws card preview de novo"
    return (
        "the site or the requests now differ from the preview (Jira changed); "
        "run ws card preview again"
    )


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
    applied: list[str] = []
    applied_paths: list[Path] = []
    for index, (item, verdict) in enumerate(zip(plan.loaded, plan.verdicts, strict=True)):
        answer = None
        for sent, request in enumerate(verdict.requests):
            try:
                reply = _send(client, request)
            except JiraError as error:
                _report_failure(settings, plan, index, error, applied, sent)
                _drop_records_for([*applied_paths, item.path])
                return 3
            except Exception as error:
                unknown = JiraError(f"{type(error).__name__}: {error}", uncertain=True)
                _report_failure(settings, plan, index, unknown, applied, sent)
                _drop_records_for([*applied_paths, item.path])
                return 3
            if sent == 0:
                answer = reply
        applied_paths.append(item.path)
        applied.append(item.path.name)
        _report_applied(site, item, verdict, answer)
        try:
            _move_to_done(item.path)
        except OSError as error:
            print(f"Aplicado, mas não consegui mover {item.path.name} para done/: {error}")
    _drop_records_for(applied_paths)
    return 0


def _drop_records_for(paths: list[Path]) -> None:
    """A preview that mentions a draft already applied could only fail or repeat the write."""
    wanted = {str(path) for path in paths}
    if not wanted:
        return
    for record in _store("pending").glob("*.json"):
        try:
            drafts = json.loads(record.read_text(encoding="utf-8")).get("drafts", [])
            mentioned = {item.get("path") for item in drafts}
        except (OSError, ValueError, AttributeError, TypeError):
            continue
        if mentioned & wanted:
            record.unlink(missing_ok=True)


def _report_applied(site: str, item: Loaded, verdict: Verdict, answer) -> None:
    creating = verdict.request["path"] == "/rest/api/3/issue"
    key = answer.get("key") if creating and isinstance(answer, dict) else None
    key = key or verdict.resolved.get("card", {}).get("key")
    link = f" {site}/browse/{key}" if key else ""
    print(f"{'Criado' if creating else 'Aplicado'}: {item.path.name}{link}")


def _report_failure(
    settings, plan: Plan, index: int, error: JiraError, applied: list[str], sent: int = 0
) -> None:
    """`sent` counts the requests of this draft that already succeeded."""
    item, verdict = plan.loaded[index], plan.verdicts[index]
    kept = _keep_aside(item.path)
    if applied:
        print(f"Já aplicados: {', '.join(applied)}")
    if sent:
        print(f"{item.path.name}: a transição foi aplicada, mas a data de início não")
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
    print(kept)
    pending = [other.path.name for other in plan.loaded[index + 1 :]]
    if pending:
        print(f"Não enviados: {', '.join(pending)}")


def _unique(folder: str, name: str) -> Path:
    target = _store(folder, name)
    stem, suffix = target.stem, target.suffix
    number = 1
    while target.exists():
        target = _store(folder, f"{stem}-{number}{suffix}")
        number += 1
    return target


def _move_inside_drafts(path: Path, folder: str) -> Path:
    root = _drafts_root()
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise OSError(f"{path} is not inside {root}; left where it is")
    target = _unique(folder, path.name)
    shutil.move(path, target)
    return target


def _move_to_done(path: Path) -> None:
    _move_inside_drafts(path, "done")


def _keep_aside(path: Path) -> str:
    """A draft whose write failed or is uncertain leaves `drafts/`, so it is never sent again
    by a later preview of the folder; the user decides after checking Jira."""
    try:
        target = _move_inside_drafts(path, "uncertain")
    except OSError as error:
        return f"Não consegui tirar {path.name} de drafts/ ({error}); confira antes de repetir."
    return f"O rascunho {path.name} foi para {target}; confira no Jira antes de repetir."
