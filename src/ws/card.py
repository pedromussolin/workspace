"""`ws card`: check, preview and apply the model's drafts to the user's tracker, behind an approval.

The tracker is reached only through the `Writer` port: it plans the drafts (`card-plan`), guards
and sends its own calls; this module shows the plan, keeps the approval and reports the result.
"""

import hashlib
import json
import os  # noqa: F401  (tests patch card.os)
import re
import shlex
import shutil
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from ws import approval, bootstrap, humans, itemrecord, userconfig
from ws.carddraft import DraftError, parse_draft
from ws.config import claude_settings_path, data_dir, repo_root
from ws.identity import dev_id
from ws.itemfile import ItemError
from ws.tracker import port, write
from ws.tracker.errors import TrackerError, TrackerSetup
from ws.tracker.port import Writer
from ws.tracker.write import Draft

APPROVAL_WINDOW = approval.APPROVAL_WINDOW

_CODE = approval.CODE
_SUBFOLDERS = ("drafts", "pending", "done", "uncertain")
_OPERATIONS = {
    "create": "Criar card",
    "edit": "Editar card",
    "move": "Mover card",
    "comment": "Comentar no card",
    "worklog": "Lançar horas no card",
    "link": "Vincular cards",
}


SetupNeeded = TrackerSetup


@dataclass
class Loaded:
    """A draft as read. With no `draft`, `problems` are why it did not parse; with one, they are
    what the `card-write` contract refuses in it (shown only if the tracker accepts the draft)."""

    path: Path
    draft: Draft | None
    sha256: str | None
    problems: list[str]

    @property
    def entry(self) -> dict:
        """What the writer plans: where the draft is, its `card-write` document, its problems."""
        return {
            "source": {"path": str(self.path), "sha256": self.sha256},
            "write": write.to_document(self.draft) if self.draft else None,
            "problems": self.problems,
        }


@dataclass(frozen=True)
class Preview:
    status: int
    text: str
    code: str | None


@dataclass
class Plan:
    """The drafts and the `card-plan` document the writer made of them."""

    loaded: list[Loaded]
    document: dict

    @property
    def steps(self) -> list[dict]:
        return self.document["steps"]

    @property
    def ok(self) -> bool:
        return all(not step["problems"] for step in self.steps)

    @property
    def today(self) -> str | None:
        return self.document["today"]

    @property
    def blocks(self) -> list[list[str]]:
        """One block of PT-BR lines per draft: a header naming the operation and the card, then the
        preview lines and the warnings. The printed preview and the pending record both use it."""
        total = len(self.loaded)
        blocks = []
        for number, (item, step) in enumerate(zip(self.loaded, self.steps, strict=True), 1):
            label = _OPERATIONS.get(item.draft.op, item.draft.op) if item.draft else "?"
            key = step["card"]
            header = f"[{number}/{total}] {label}{f' {key}' if key else ''} ({item.path.name})"
            blocks.append(
                [
                    header,
                    *[f"  {line}" for line in step["preview"]],
                    *[f"  Aviso: {warning}" for warning in step["warnings"]],
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
    return approval.session_id()


def _store(*parts: str) -> Path:
    return data_dir().joinpath("cards", *parts)


def _ensure_store() -> None:
    for name in ("", *_SUBFOLDERS):
        approval.ensure_store(_store(name) if name else _store())


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


_DRAFT_NAME = re.compile(r"[A-Za-z0-9._-]+\.(md|json)")
_DRAFT_SUFFIXES = (".md", ".json")


def _draft_path(name: str) -> Path:
    if not _DRAFT_NAME.fullmatch(name) or name.startswith("."):
        raise ValueError(f"{name!r} is not a draft file name")
    return _drafts_root() / name


def write_draft(name: str, text: str) -> Path:
    """Write `cards/drafts/<name>` (replacing it), private, through a temp file and a rename.

    The temp file is always new (`O_EXCL`, a stale one is removed first) and never followed if it
    is a symlink, and it reaches the disk before the rename.
    """
    path = _draft_path(name)
    _ensure_store()
    if path.is_symlink() or path.is_dir():
        raise DraftError([f"{name} is a symlink or a folder, not a draft file"])
    temporary = path.with_name(f".{name}.tmp")
    temporary.unlink(missing_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return path


def remove_draft(name: str) -> bool:
    """Delete the draft `cards/drafts/<name>` when it is a file; True when one was removed."""
    path = _draft_path(name)
    if path.is_symlink() or not path.is_file():
        return False
    path.unlink()
    return True


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
            if item.suffix not in _DRAFT_SUFFIXES:
                continue
            if item.is_symlink() or not item.resolve().is_relative_to(root):
                raise DraftError([f"{item.name} is a symlink or leaves {root}"])
            if item.is_file():
                found.append(item.resolve())
        if found:
            return found
        raise DraftError([f"{argument} holds no .md or .json drafts"])
    raise DraftError([f"{argument} does not exist"])


def load(path: Path) -> Loaded:
    try:
        raw = path.read_bytes()
    except OSError as error:
        return Loaded(path, None, None, [f"cannot read the draft: {error.strerror}"])
    if path.suffix == ".json":
        return _load_json(path, raw)
    try:
        draft = parse_draft(raw)
    except DraftError as error:
        return Loaded(path, None, hashlib.sha256(raw).hexdigest(), error.problems)
    return Loaded(path, draft, draft.sha256, write.check_document(write.to_document(draft)))


def _load_json(path: Path, raw: bytes) -> Loaded:
    """A `.json` draft is a `card-write` document; the pending record keeps the file's sha256."""
    digest = hashlib.sha256(raw).hexdigest()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return Loaded(path, None, digest, ["draft is not valid JSON"])
    if not isinstance(document, dict):
        return Loaded(path, None, digest, ["draft must be a JSON object"])
    if document.get("$schema") != "card-write":
        return Loaded(path, None, digest, ["$schema: a draft must be a card-write document"])
    problems = write.check_document(document)
    if problems:
        return Loaded(path, None, digest, problems)
    return Loaded(path, replace(write.from_document(document), sha256=digest), digest, [])


def _card_plan_problems(path: Path) -> list[str] | None:
    """The schema problems of a `card-plan` JSON document; None when the file is not one."""
    if path.suffix != ".json":
        return None
    try:
        document = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(document, dict) or document.get("$schema") != "card-plan":
        return None
    return write.check_document(document)


def show(path: str) -> dict:
    """The `card-write` document of a draft under `cards/drafts/`; `DraftError` when the draft
    does not parse or the contract refuses it."""
    [found] = collect(str(path), single=True)
    item = load(found)
    if item.draft is None or item.problems:
        raise DraftError(item.problems)
    return write.to_document(item.draft)


def _open_writer(loaded: list[Loaded]) -> Writer:
    return port.open_writer([item.entry for item in loaded])


def _run(command: str, action) -> int:
    try:
        return action()
    except SetupNeeded as error:
        print(f"ws card {command}: {error}", file=sys.stderr)
        return 2
    except TrackerError as error:
        print(f"ws card {command}: {error}", file=sys.stderr)
        return 3
    except (KeyError, TypeError, AttributeError) as error:
        print(f"ws card {command}: unexpected answer from the tracker ({error!r})", file=sys.stderr)
        return 3
    except OSError as error:
        print(f"ws card {command}: file error: {error}", file=sys.stderr)
        return 1


def _plan(writer: Writer, loaded: list[Loaded]) -> Plan:
    """The writer's plan of the drafts, with the core's checks on top and the `summary` the
    person approves. The tracker's verdict comes first; a draft it accepts still fails on what
    `load` found in it (parse problems, or what the `card-write` contract refuses), and on the
    item a create names."""
    document = writer.plan([item.entry for item in loaded])
    for item, step in zip(loaded, document["steps"], strict=True):
        if item.problems and not step["problems"]:
            step["problems"] = list(item.problems)
            step["native"] = []
    _item_problems(loaded, document["steps"])
    plan = Plan(loaded, document)
    document["summary"] = plan.summary
    return plan


def _own_dev_id() -> str:
    email = userconfig.load_config().identity_email
    return dev_id(email) if email else ""


def _item_problems(loaded: list[Loaded], steps: list[dict]) -> None:
    """A create naming an item must match it and be the only create for it: the card key goes
    back into the item, and a second create would make a duplicate."""
    creators: dict[str, list[int]] = {}
    for index, item in enumerate(loaded):
        values = item.draft.values if item.draft and item.draft.op == "create" else {}
        if "item" in values:
            creators.setdefault(values["item"], []).append(index)
    own_dev_id = _own_dev_id() if creators else ""
    for rel, indexes in creators.items():
        for index in indexes:
            values = loaded[index].draft.values
            problems = itemrecord.create_problems(repo_root(), values, own_dev_id)
            if len(indexes) > 1:
                problems.append(f"two drafts create a card for item {rel}")
            if problems:
                steps[index]["problems"].extend(problems)
                steps[index]["native"] = []


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
    return approval.digest(material)


def run_check(argument: str) -> int:
    try:
        [path] = collect(argument, single=True)
    except DraftError as error:
        _print_check(error.problems)
        return 1
    plan_problems = _card_plan_problems(path)
    if plan_problems is not None:
        _print_check(plan_problems)
        return 1 if plan_problems else 0
    item = load(path)
    if item.draft is None:
        _print_check(item.problems)
        return 1

    def action() -> int:
        writer = _open_writer([item])
        _ensure_store()
        [step] = _plan(writer, [item]).steps
        resolved = getattr(writer, "resolved", None) or [{}]
        _print_check(step["problems"], step["warnings"], resolved[0], step["native"])
        return 1 if step["problems"] else 0

    return _run("check", action)


def _print_check(
    problems: list[str],
    warnings: list[str] | None = None,
    resolved: dict | None = None,
    requests: list[dict] | None = None,
) -> None:
    payload = {
        "ok": not problems,
        "problems": problems,
        "warnings": warnings or [],
        "resolved": resolved or {},
        "requests": requests or [],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_epics() -> int:
    def action() -> int:
        found = port.open_writer([]).epics()
        print(json.dumps({"epics": found}, ensure_ascii=False, indent=2))
        return 0

    return _run("epics", action)


def preview(argument: str) -> Preview:
    return _previewed(argument)[0]


def preview_plan(argument: str) -> dict:
    """The preview as a `card-plan` document, with `summary`, and with `code` when the pending
    record was saved (the same record and code as `preview`); empty when no plan could be made,
    the reason on stderr."""
    return _previewed(argument)[1]


def preview_json(argument: str) -> tuple[dict, int]:
    """The `card-plan` document (empty when no plan could be made) and the exit status of one
    preview: the same pending record, code and status as `preview`."""
    result, plan = _previewed(argument)
    return plan, result.status


def _previewed(argument: str) -> tuple[Preview, dict]:
    try:
        loaded = [load(path) for path in collect(argument)]
    except DraftError as error:
        print(f"ws card preview: {'; '.join(error.problems)}", file=sys.stderr)
        return Preview(1, "", None), {}
    results: list[tuple[Preview, dict]] = []

    def action() -> int:
        results.append(_preview(argument, loaded))
        return results[0][0].status

    status = _run("preview", action)
    return results[0] if results else (Preview(status, "", None), {})


def run_preview(argument: str) -> int:
    result = preview(argument)
    sys.stdout.write(result.text)
    return result.status


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


def _problem_lines(plan: Plan) -> list[str]:
    lines = ["Nada foi enviado. Problemas encontrados:"]
    for item, step in zip(plan.loaded, plan.steps, strict=True):
        lines.extend(f"  {item.path.name}: {problem}" for problem in step["problems"])
    return lines


def _print_problems(plan: Plan) -> None:
    print("\n".join(_problem_lines(plan)))


def _preview(argument: str, loaded: list[Loaded]) -> tuple[Preview, dict]:
    writer = _open_writer(loaded)
    _ensure_store()
    plan = _plan(writer, loaded)
    if not plan.ok:
        return Preview(1, "\n".join(_problem_lines(plan)) + "\n", None), plan.document
    code = write.plan_code(plan.document)
    try:
        _purge_expired()
        _write_pending(plan)
    except OSError as error:
        print(
            f"ws card preview: could not save the pending record: {error.strerror or error}",
            file=sys.stderr,
        )
        return Preview(1, "", None), plan.document
    plan.document["code"] = code
    lines = [f"Prévia de {len(loaded)} mudança(s); nada foi enviado ao {writer.name}."]
    for block, step in zip(plan.blocks, plan.steps, strict=True):
        lines.append("")
        lines.extend(block)
        for call in step["native"]:
            lines.append(f"  Requisição: {call['method']} {call['path']}")
            body = json.dumps(call["body"], ensure_ascii=False, indent=2)
            lines.extend(f"    {line}" for line in body.splitlines())
    lines.append(f"\nCódigo de aprovação: {code}")
    lines.append(f"Para aplicar: ws card apply {shlex.quote(argument)} --approve {code}")
    return Preview(0, "\n".join(lines) + "\n", code), plan.document


def _pending_path(code: str) -> Path:
    return _store("pending", f"{code}.json")


def _write_pending(plan: Plan) -> None:
    record = write.pending_record(plan.document, created_at=_now().isoformat(), sid=_session_id())
    approval.write_pending(_store("pending"), record["code"], record)


def _read_pending(code: str) -> tuple[dict | None, str | None]:
    return approval.read_pending(_store("pending"), code, now=_now(), preview="ws card preview")


def _purge_expired() -> None:
    approval.purge_expired(_store("pending"), now=_now(), preview="ws card preview")


def _interactive() -> bool:
    return humans.by_hand()


def _confirm(summary: list[str], tracker: str) -> bool:
    print("\n".join(summary))
    try:
        answer = input(f"Gravar no {tracker}? [s/N] ")
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
    writer = _open_writer(loaded)
    plan = _plan(writer, loaded)
    if not plan.ok:
        _print_problems(plan)
        return 1
    if write.plan_code(plan.document) != code or record.get("site") != writer.target:
        print(f"ws card apply: {_why_it_differs(record, plan, writer)}", file=sys.stderr)
        return 1
    if (refused := writer.guard(write.calls(plan.document))) is not None:
        print(f"ws card apply: request outside the allowed shapes: {refused}", file=sys.stderr)
        return 1
    if by_hand and not _confirm(plan.summary, writer.name):
        print("Nada foi enviado.")
        return 1
    try:
        _pending_path(code).unlink()
    except FileNotFoundError:
        print(f"ws card apply: the preview {code} was already used", file=sys.stderr)
        return 1
    return _send_all(writer, plan)


def _why_it_differs(record: dict, plan: Plan, writer: Writer) -> str:
    if record.get("today") != plan.today:
        return "a data de hoje mudou desde a prévia; rode o ws card preview de novo"
    if record.get("site") == writer.target and record.get("requests") == write.calls(plan.document):
        return f"o card mudou no {writer.name} desde a prévia; rode o ws card preview de novo"
    return (
        f"the site or the requests now differ from the preview ({writer.name} changed); "
        "run ws card preview again"
    )


def _send(writer: Writer, call: dict):
    """The one function every write leaves by: `apply` gets it, so a test can watch each send."""
    return writer.send(call)


def _send_all(writer: Writer, plan: Plan) -> int:
    applied: list[str] = []
    applied_paths: list[Path] = []
    write_back_failed = False
    results = iter(writer.apply(plan.document, lambda call: _send(writer, call)))
    for index, item in enumerate(plan.loaded):
        result = next(results, None)
        if result is None or result.get("draft") != item.entry["source"]:
            _report_unreported(writer, plan, index, applied)
            _drop_records_for(applied_paths)
            return 3
        if result["status"] != "applied":
            _report_failure(writer, plan, index, result, applied)
            _drop_records_for([*applied_paths, item.path])
            return 3
        applied_paths.append(item.path)
        applied.append(item.path.name)
        created = _report_applied(plan, index, result)
        if not _write_back_item(item, created, writer.name):
            write_back_failed = True
        try:
            _move_to_done(item.path)
        except OSError as error:
            print(f"Aplicado, mas não consegui mover {item.path.name} para done/: {error}")
    _drop_records_for(applied_paths)
    return 1 if write_back_failed else 0


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


def _report_applied(plan: Plan, index: int, result: dict) -> str | None:
    """Prints the line of the applied draft; returns the key of the card it created, if any."""
    item, step = plan.loaded[index], plan.steps[index]
    if step["op"] == "link":
        for line in step["preview"]:
            if not line.endswith(": já existe"):
                print(f"Vinculado: {line}")
        return None
    creating = step["op"] == "create"
    key = result["created"] or step["card"]
    link = f" {result['url']}" if result["url"] else ""
    print(f"{'Criado' if creating else 'Aplicado'}: {item.path.name}{link}")
    if creating and key:
        _log_created(item.path.name, key, plan.today)
    return key if creating else None


def _write_back_item(item: Loaded, key: str | None, tracker: str) -> bool:
    """The card is already created: a write-back that fails is reported and recorded, and the
    rest of the batch goes on. True when there was nothing to write or it was written."""
    rel = item.draft.values.get("item") if item.draft else None
    if not rel:
        return True
    if not key:
        print(
            f"O {tracker} não devolveu a chave do card; o item {rel} ficou registrado como incerto"
        )
        _record_item(rel, None)
        return False
    try:
        itemrecord.write_back(repo_root(), rel, key)
    except (ItemError, OSError) as error:
        print(
            f"Card {key} criado, mas o item {rel} não foi atualizado ({error}); "
            f"rode ws item set-card {rel} {key}"
        )
        _record_item(rel, key)
        return False
    print(f'Item atualizado: {rel} (card = "{key}")')
    return True


def _record_item(rel: str, ref: str | None) -> None:
    try:
        itemrecord.record(rel, ref)
    except OSError as error:
        print(f"Não consegui registrar o item {rel} ({error}); confira antes de criar de novo")


def _log_created(name: str, key: str, today: str | None) -> None:
    """`today` is the day in the user's tracker time zone, the one the rules used. The card is
    already created, so a log that cannot be written never stops the rest of the batch."""
    try:
        with _store("created.tsv").open("a", encoding="utf-8") as log:
            log.write(f"{name}\t{key}\t{today}\n")
    except OSError as error:
        print(f"{name} {key} (não registrado em created.tsv: {error})")


def _report_failure(
    writer: Writer, plan: Plan, index: int, result: dict, applied: list[str]
) -> None:
    """`result` is the `card-result` step of the draft that failed; its `sent` holds the calls of
    this draft that already succeeded."""
    item, step = plan.loaded[index], plan.steps[index]
    sent = len(result["sent"])
    kept = _keep_aside(item.path, writer.name)
    if applied:
        print(f"Já aplicados: {', '.join(applied)}")
    if sent and step["op"] == "link":
        created = [line for line in step["preview"] if not line.endswith(": já existe")][:sent]
        print(f"{item.path.name}: {sent} vínculo(s) já criado(s); o restante não foi enviado")
        print(*[f"  Vinculado: {line}" for line in created], sep="\n")
    elif sent:
        print(f"{item.path.name}: a transição foi aplicada, mas a data de início não")
    if result["status"] == "uncertain":
        print(f"{item.path.name}: resultado incerto: confira no {writer.name} ({result['error']})")
        if step["op"] == "create":
            print(f"Para procurar o card, {writer.find_hint(step['title'])}")
            rel = item.draft.values.get("item") if item.draft else None
            if rel:
                _record_item(rel, None)
                print(f"O item {rel} ficou registrado como incerto; veja ws item set-card")
    else:
        print(f"{item.path.name}: o {writer.name} recusou: {result['error']}")
    print(
        "Nada mais foi enviado, e a aprovação foi consumida; refaça a prévia para tentar de novo."
    )
    print(kept)
    pending = [other.path.name for other in plan.loaded[index + 1 :]]
    if pending:
        print(f"Não enviados: {', '.join(pending)}")


def _report_unreported(writer: Writer, plan: Plan, index: int, applied: list[str]) -> None:
    """The writer stopped reporting, or reported another draft, at draft `index`: nothing more is
    asked of it, and that draft and the rest stay in `drafts/` as not sent."""
    item = plan.loaded[index]
    print(
        f"ws card apply: {writer.name} did not return the result of {item.path.name}",
        file=sys.stderr,
    )
    if applied:
        print(f"Já aplicados: {', '.join(applied)}")
    print(
        "Nada mais foi enviado, e a aprovação foi consumida; refaça a prévia para tentar de novo."
    )
    print(f"Não enviados: {', '.join(other.path.name for other in plan.loaded[index:])}")


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


def _keep_aside(path: Path, tracker: str) -> str:
    """A draft whose write failed or is uncertain leaves `drafts/`, so it is never sent again
    by a later preview of the folder; the user decides after checking the tracker."""
    try:
        target = _move_inside_drafts(path, "uncertain")
    except OSError as error:
        return f"Não consegui tirar {path.name} de drafts/ ({error}); confira antes de repetir."
    return f"O rascunho {path.name} foi para {target}; confira no {tracker} antes de repetir."
