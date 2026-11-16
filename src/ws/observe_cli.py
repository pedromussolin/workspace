"""`ws observe`: the daily observation of a switched-off job, until it can go for good.

A plan per task lists the checks. `run` answers the database ones through `ws.database.scalar` and
records them; `request` prints the program the observability tool runs and `record` saves its
answer and the manual ones; `status` and `report` read the rows. Every document read, written or
sent is checked against its contract. Nothing here writes to the task tracker, a database or the
observability tool, and no output carries a query or a row.
"""

import argparse
import errno
import getpass
import json
import os
import re
import stat
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ws import bootstrap, contracts, database, humans, observability, observedef
from ws.config import claude_settings_path
from ws.database import guard
from ws.database.port import Busy, Database, Refused, Unreachable
from ws.database.port import Setup as DatabaseSetup
from ws.observability.port import Observability
from ws.observability.port import Setup as ObservabilitySetup
from ws.observedef import DEFAULT_DAYS, DEFAULT_TIMEZONE, Check, Invalid, Plan
from ws.observereport import render
from ws.observeresults import load_rows, make_row, number, put_row, results_path, utc_text
from ws.observestatus import (
    day_number,
    day_problem,
    day_window,
    due_day,
    plan_status,
    status_document,
    status_line,
)
from ws.tracker import port
from ws.tracker.port import TrackerError, TrackerSetup
from ws.userconfig import ConfigInvalid
from ws.workdays import extra_holidays

EXIT_OK = 0
EXIT_PROBLEM = 1
EXIT_SETUP = 2
EXIT_UNREACHABLE = 3
RANKED = (EXIT_SETUP, EXIT_UNREACHABLE, EXIT_PROBLEM)
PREFIX = "ws observe: "
MAX_RESULT_BYTES = 1024 * 1024
PRIVATE_FILE = 0o600
MAX_DAYS = 30
ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
WHOLE = re.compile(r"\d+", re.ASCII)
VALUE = re.compile(r"\d+(\.\d+)?", re.ASCII)
GATE_HINT = (
    "Run `ws setup` and add what it prints, so Claude Code asks you before every database query"
)
# The tool's own reason is dropped: it may echo the query.
TOOL_GAVE_NO_COUNT = "the observability tool gave no count; run ws observe fallback for it"


class Failure(Exception):
    """Problems that stop a command, with its exit code."""

    def __init__(self, problems: str | list[str], code: int = EXIT_PROBLEM):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        self.code = code
        super().__init__("; ".join(self.problems))


def _now() -> datetime:
    return datetime.now(UTC)


def _today(timezone: str | None = None) -> date:
    """Today in the plan's zone; without one, in the machine's zone."""
    moment = _now()
    return (moment.astimezone(ZoneInfo(timezone)) if timezone else moment.astimezone()).date()


def _ranked(codes: list[int]) -> int:
    return next((code for code in RANKED if code in codes), EXIT_OK)


def _problems_of(error: Exception) -> tuple[list[str], int]:
    if isinstance(error, Failure):
        return error.problems, error.code
    return [str(error)], EXIT_PROBLEM


def _fail(error: Exception) -> int:
    problems, code = _problems_of(error)
    for problem in problems:
        print(f"{PREFIX}{problem}", file=sys.stderr)
    return code


def _emit(report: dict, code: int) -> int:
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if code != EXIT_OK:
        for problem in report.get("problems", []):
            print(f"{PREFIX}{problem}", file=sys.stderr)
    return code


def _stopped(report: dict, error: Exception) -> tuple[dict, int]:
    problems, code = _problems_of(error)
    report["problems"].extend(problems)
    return report, code


def _valid(document: object, contract: str, what: str) -> object:
    problems = contracts.validate(document, contract)
    if problems:
        raise Invalid(f"{what}: {'; '.join(problems)}")
    return document


def _plan(path: Path) -> tuple[dict, Plan]:
    """The plan document, checked against its contract, and the parsed plan."""
    document, plan = observedef.load_plan(path)
    _valid(document, "observe-plan", str(path))
    if plan.task != path.stem:
        raise Invalid(f"{path}: task {plan.task} does not match the file name")
    return document, plan


def _rows(plan_path: Path) -> list[dict]:
    path = results_path(plan_path)
    found = load_rows(path)
    for index, row in enumerate(found, start=1):
        _valid(row, "observe-result", f"{path} row {index}")
    return found


def _hashes(plan: Plan) -> dict[str, str]:
    return {check.id: observedef.check_hash(check) for check in plan.checks}


def _holidays() -> frozenset[date]:
    try:
        return extra_holidays()
    except ConfigInvalid as error:
        raise Failure(str(error), EXIT_SETUP) from None


def _day(text: str | None, what: str = "--day") -> date | None:
    if text is None:
        return None
    if isinstance(text, str) and ISO_DAY.fullmatch(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
    raise Invalid(f"{what}: {text!r} must be a date YYYY-MM-DD")


def _closed_day(plan: Plan, day: date | None, today: date, extra: frozenset[date]) -> date:
    chosen = day or due_day(today, extra)
    problem = day_problem(chosen, plan.switched_off, today, extra)
    if problem:
        raise Invalid(problem)
    return chosen


def _check(plan: Plan, check_id: str) -> Check:
    for check in plan.checks:
        if check.id == check_id:
            return check
    known = ", ".join(check.id for check in plan.checks)
    raise Invalid(f"unknown check {check_id}; the plan has {known}")


def _where(project: str, task: str) -> str:
    """` --project SLUG` when the task has plans in more than one project."""
    found = [name for name, path in observedef.all_plans(None) if path.stem == task]
    return f" --project {project}" if len(found) > 1 else ""


def _open_observability() -> Observability:
    try:
        return observability.open_observability()
    except (ObservabilitySetup, ConfigInvalid) as error:
        raise Failure(str(error), EXIT_SETUP) from None


def database_request(check: Check, bounds: dict[str, str], timeout: int) -> dict:
    return {
        "version": 1,
        "database": check.database,
        "sql": check.sql,
        "bounds": dict(bounds),
        "timeout_seconds": timeout,
    }


def database_result(check: Check, value: Decimal, started: datetime, finished: datetime) -> dict:
    return {
        "version": 1,
        "database": check.database,
        "value": number(value),
        "started": utc_text(started),
        "finished": utc_text(finished),
    }


def observability_request(
    plan: Plan,
    day: date,
    windows: tuple[datetime, datetime],
    hashes: dict[str, str],
    only: tuple[str, ...] = (),
) -> dict:
    """The counts of the plan's observability checks; with `only`, of those checks alone."""
    start, end = (utc_text(moment) for moment in windows)
    counts = [
        {
            "check": check.id,
            "signal": check.signal,
            "query": check.query,
            "from": start,
            "to": end,
            "hash": hashes[check.id],
        }
        for check in plan.checks
        if check.kind == "observability" and (not only or check.id in only)
    ]
    return {"version": 1, "task": plan.task, "day": day.isoformat(), "counts": counts}


def _bounds(day: date, window: tuple[datetime, datetime]) -> dict[str, str]:
    return {"day": day.isoformat(), "day_from": utc_text(window[0]), "day_to": utc_text(window[1])}


def _recorded(row: dict) -> dict:
    return {"check": row["check"], "value": row["value"], "verdict": row["verdict"]}


def _prepare(queries: list[Check]) -> dict[str, tuple[Database, tuple[str, ...]]]:
    """Before any query: the approval gate, each database opened once and every SQL guarded."""
    if not humans.by_hand():
        problems = bootstrap.observe_gate_problems(claude_settings_path())
        if problems:
            raise Failure(f"{'; '.join(problems)}. {GATE_HINT}", EXIT_SETUP)
    opened: dict[str, Database] = {}
    prepared: dict[str, tuple[Database, tuple[str, ...]]] = {}
    refused = []
    for check in queries:
        if check.database not in opened:
            try:
                opened[check.database] = database.open_database(check.database)
            except DatabaseSetup as error:
                raise Failure(f"{check.id}: {error}", EXIT_SETUP) from None
        db = opened[check.database]
        try:
            _, used = guard.guard(check.sql, db.rules)
        except Refused as error:
            refused.append(f"{check.id}: {error}")
            continue
        prepared[check.id] = (db, used)
    if refused:
        raise Failure(refused)
    return prepared


def _query(
    check: Check, db: Database, day: date, window: tuple[datetime, datetime], path: Path
) -> dict:
    request = database_request(check, _bounds(day, window), db.timeout)
    _valid(request, "database-request", check.id)
    started = _now()
    value = database.scalar(db, check.sql, request["bounds"])
    finished = _now()
    _valid(database_result(check, value, started, finished), "database-result", check.id)
    row = make_row(
        check, day, value, started=started, finished=finished, window=window, times="run"
    )
    _valid(row, "observe-result", check.id)
    put_row(results_path(path), row)
    return row


def run_day(project: str, path: Path, day: date | None, only: list[str]) -> tuple[dict, int]:
    report: dict = {
        "task": path.stem,
        "day": None,
        "day_number": None,
        "window": None,
        "recorded": [],
        "observability": None,
        "ask": [],
        "problems": [],
        "warnings": [],
    }
    try:
        _, plan = _plan(path)
        extra = _holidays()
        for check_id in only:
            _check(plan, check_id)
        today = _today(plan.timezone)
        chosen = _closed_day(plan, day, today, extra)
    except (Failure, Invalid) as error:
        return _stopped(report, error)
    window = day_window(chosen, plan.switched_off, plan.timezone, extra)
    report["day"] = chosen.isoformat()
    report["day_number"] = day_number(chosen, plan.switched_off, extra)
    report["window"] = [utc_text(moment) for moment in window]
    selected = [check for check in plan.checks if not only or check.id in only]
    probes = [check for check in selected if check.kind == "observability"]
    queries = [check for check in selected if check.kind == "database"]
    try:
        tool = _open_observability() if probes else None
        prepared = _prepare(queries) if queries else {}
        where = _where(project, plan.task)
    except (Failure, Invalid) as error:
        return _stopped(report, error)

    codes = []
    due = due_day(today, extra)
    for check in queries:
        db, used = prepared[check.id]
        try:
            row = _query(check, db, chosen, window, path)
        except DatabaseSetup as error:
            report["problems"].append(f"{check.id}: {error}")
            codes.append(EXIT_SETUP)
            break
        except Unreachable as error:
            report["problems"].append(f"{check.id}: {error}")
            codes.append(EXIT_UNREACHABLE)
            continue
        except (Refused, Busy, ValueError) as error:
            report["problems"].append(f"{check.id}: {error}")
            codes.append(EXIT_PROBLEM)
            continue
        report["recorded"].append(_recorded(row))
        if not used and chosen < due:
            report["warnings"].append(
                f"{check.id} reads the current state; its value for {chosen} is as of now"
            )

    if tool is not None:
        subset = "".join(f" --check {check.id}" for check in probes) if only else ""
        report["observability"] = {
            "tool": tool.tool,
            "checks": [check.id for check in probes],
            "next": f"ws observe request {plan.task}{where} --day {chosen}{subset}",
            "result_path": str(path.parent / f"{plan.task}.{chosen}.result.json"),
        }
    manual = [check for check in selected if check.kind == "manual"]
    if manual:
        try:
            hashes = _hashes(plan)
            current = {
                row["check"]
                for row in _rows(path)
                if row["day"] == chosen.isoformat() and row["hash"] == hashes.get(row["check"])
            }
        except Invalid as error:
            report["problems"].append(str(error))
            codes.append(EXIT_PROBLEM)
            current = set()
        for check in manual:
            if check.id in current:
                continue
            command = f"ws observe record {plan.task}{where} --check {check.id} --day {chosen}"
            report["ask"].append(
                {
                    "check": check.id,
                    "question": check.question,
                    "yes": f"{command} --yes",
                    "no": f"{command} --no",
                }
            )
    return report, _ranked(codes)


def _moment(text: str, what: str) -> datetime:
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        moment = None
    if moment is None or moment.tzinfo is None:
        raise Invalid(f"{what} must be an ISO date-time with an offset")
    return moment


def _record_report(task: str) -> dict:
    return {"task": task, "day": None, "recorded": [], "problems": [], "warnings": []}


def record_result(project: str, path: Path, document: dict) -> tuple[dict, int]:
    """The observability tool's answer: each count of a current check becomes a row."""
    report = _record_report(path.stem)
    try:
        _valid(document, "observability-result", "the result")
        _, plan = _plan(path)
        extra = _holidays()
        if document["task"] != plan.task:
            raise Invalid(f"the result is for {document['task']}, not {plan.task}")
        chosen = _closed_day(plan, _day(document["day"], "day"), _today(plan.timezone), extra)
    except (Failure, Invalid) as error:
        return _stopped(report, error)
    report["day"] = chosen.isoformat()
    window = day_window(chosen, plan.switched_off, plan.timezone, extra)
    hashes = _hashes(plan)
    checks = {check.id: check for check in plan.checks}
    codes = []
    for count in document["counts"]:
        check = checks.get(count["check"])
        try:
            if check is None or check.kind != "observability":
                raise Invalid(
                    f"{_named(count['check'])} is not an observability check of {plan.task}"
                )
            if count["hash"] != hashes[check.id]:
                raise Invalid(f"{check.id} changed since the request; run ws observe request again")
            started = _moment(count["started"], f"{check.id}: started")
            finished = _moment(count["finished"], f"{check.id}: finished")
            value = Decimal(str(count["value"]))
            if not value.is_finite() or value < 0:
                raise Invalid(f"{check.id}: the count must be a finite number, zero or more")
            row = make_row(
                check,
                chosen,
                value,
                started=started,
                finished=finished,
                window=window,
                times="tool",
            )
            _valid(row, "observe-result", check.id)
            put_row(results_path(path), row)
        except Invalid as error:
            report["problems"].append(str(error))
            codes.append(EXIT_PROBLEM)
            continue
        report["recorded"].append(_recorded(row))
    for failed in document["failed"]:
        report["warnings"].append(f"{_named(failed['check'])}: {TOOL_GAVE_NO_COUNT}")
    return report, _ranked(codes)


def _named(check_id: str) -> str:
    """A check id from the tool's answer, shown only when it looks like one: the answer is not
    ours, and its text may echo a query."""
    return check_id if observedef.CHECK_ID.fullmatch(check_id) else "a check with an unknown id"


def _login() -> str:
    try:
        return getpass.getuser()
    except (OSError, KeyError):
        raise Invalid("the login name is unknown; pass --by NAME") from None


def record_one(
    project: str,
    path: Path,
    check_id: str,
    day: date | None,
    value: Decimal | bool,
    hash_: str | None,
    by: str | None,
) -> tuple[dict, int]:
    """One value typed by a person: a fallback count or a manual answer."""
    report = _record_report(path.stem)
    try:
        _, plan = _plan(path)
        extra = _holidays()
        check = _check(plan, check_id)
        if check.kind == "database":
            raise Invalid("database checks are recorded by ws observe run")
        if check.kind == "observability":
            if isinstance(value, bool):
                raise Invalid(f"{check.id} is an observability check; record it with --value N")
            if hash_ is None:
                raise Invalid("--hash is required with --value; ws observe fallback prints it")
            if hash_ != observedef.check_hash(check):
                raise Invalid(f"{check.id} changed since the request; run ws observe request again")
        elif not isinstance(value, bool) or hash_ is not None:
            raise Invalid(f"{check.id} is a manual check; record it with --yes or --no")
        if by is not None and (not by.strip() or not by.isprintable()):
            raise Invalid("--by must be a name on one line")
        who = by or _login()
        chosen = _closed_day(plan, day, _today(plan.timezone), extra)
        moment = _now()
        window = day_window(chosen, plan.switched_off, plan.timezone, extra)
        row = make_row(
            check,
            chosen,
            value,
            started=moment,
            finished=moment,
            window=window,
            times="record",
            by=who,
        )
        _valid(row, "observe-result", check.id)
        put_row(results_path(path), row)
    except (Failure, Invalid) as error:
        return _stopped(report, error)
    report["day"] = chosen.isoformat()
    report["recorded"].append(_recorded(row))
    return report, EXIT_OK


def check_plan(project: str, path: Path) -> tuple[dict, int]:
    """The contract, the plan rules and the guard on every SQL; modes back to 700 and 600."""
    report: dict = {
        "task": path.stem,
        "project": project,
        "path": str(path),
        "checks": [],
        "problems": [],
        "warnings": observedef.tighten(path),
    }
    try:
        _, plan = _plan(path)
        _rows(path)
    except Invalid as error:
        return _stopped(report, error)
    report["checks"] = [check.id for check in plan.checks]
    rules = {}
    for check in plan.checks:
        if check.kind != "database":
            continue
        if check.database not in rules:
            try:
                rules[check.database] = database.open_database(check.database).rules
            except DatabaseSetup as error:
                rules[check.database] = guard.NO_RULES
                report["warnings"].append(
                    f"database {check.database}: {error}; "
                    "its checks were guarded by the neutral rules only"
                )
        try:
            guard.guard(check.sql, rules[check.database])
        except Refused as error:
            report["problems"].append(f"{check.id}: {error}")
    return report, EXIT_PROBLEM if report["problems"] else EXIT_OK


def status_report(project: str | None) -> tuple[dict, int]:
    """Each plan counts its days from today in its own zone; `today` is the machine's."""
    extra = _holidays()
    entries, problems = [], []
    for name, path in observedef.all_plans(project):
        try:
            document, plan = _plan(path)
            found = _rows(path)
        except Invalid as error:
            problems.append(str(error))
            continue
        today = _today(plan.timezone)
        entries.append(plan_status(document, name, _hashes(plan), found, today, extra))
    report = status_document(entries, _today(), problems)
    report["problems"].extend(contracts.validate(report, "observe-status"))
    return report, EXIT_PROBLEM if report["problems"] else EXIT_OK


def _observability_document(
    path: Path, day: date | None, only: list[str]
) -> tuple[Observability, Plan, dict]:
    _, plan = _plan(path)
    extra = _holidays()
    chosen = _closed_day(plan, day, _today(plan.timezone), extra)
    if not any(check.kind == "observability" for check in plan.checks):
        raise Invalid(f"{plan.task} has no observability check")
    for check_id in only:
        if _check(plan, check_id).kind != "observability":
            raise Invalid(f"{check_id} is not an observability check of {plan.task}")
    tool = _open_observability()
    window = day_window(chosen, plan.switched_off, plan.timezone, extra)
    document = observability_request(plan, chosen, window, _hashes(plan), tuple(only))
    _valid(document, "observability-request", "the request")
    return tool, plan, document


def _title(task: str) -> str | None:
    try:
        card = port.open_tracker().card(task)
    except (TrackerSetup, TrackerError, OSError) as error:
        print(f"{PREFIX}warning: no title from the task tracker: {error}", file=sys.stderr)
        return None
    if card is None:
        print(f"{PREFIX}warning: {task} was not found in the task tracker", file=sys.stderr)
        return None
    return card.title


def _read_result(file: Path, folder: Path) -> dict:
    """The tool's JSON answer, read without following a symbolic link. Once it parses, a file
    under the plan's folder is set to 600 like the plan: it holds company queries. A file
    elsewhere keeps its mode, so a mistyped path never changes another file."""
    try:
        descriptor = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise Invalid(f"{file}: a symbolic link; pass the file itself") from None
        raise Invalid(f"{file}: cannot be read: {error.strerror}") from None
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise Invalid(f"{file}: not a regular file")
    with os.fdopen(descriptor, "rb") as stream:
        data = stream.read(MAX_RESULT_BYTES + 1)
        if len(data) > MAX_RESULT_BYTES:
            raise Invalid(f"{file}: larger than 1 MiB")
        try:
            document = json.loads(data.decode("utf-8"), parse_constant=_no_constant)
        except ValueError:
            raise Invalid(f"{file}: not JSON") from None
        if not isinstance(document, dict):
            raise Invalid(f"{file}: not a JSON object")
        if file.resolve().is_relative_to(folder.resolve()):
            os.fchmod(descriptor, PRIVATE_FILE)
    return document


def _no_constant(name: str) -> None:
    raise ValueError(f"{name} is not a number")


def _cmd_new(args: argparse.Namespace) -> int:
    try:
        task = observedef.valid_task(args.task)
        project = observedef.valid_project(args.project)
        if not args.job.strip() or not args.job.isprintable():
            raise Invalid("--job must be a non-empty text on one line")
        switched_off = _day(args.switched_off, "--switched-off")
        if not WHOLE.fullmatch(args.days) or not 1 <= int(args.days) <= MAX_DAYS:
            raise Invalid(f"--days must be a whole number from 1 to {MAX_DAYS}")
        try:
            ZoneInfo(args.timezone)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise Invalid(f"--timezone: {args.timezone!r} is not a known time zone") from None
        text = observedef.new_plan_text(task, args.job, switched_off, int(args.days), args.timezone)
        path = observedef.write_new(project, task, text)
    except Invalid as error:
        return _fail(error)
    print(json.dumps({"task": task, "project": project, "path": str(path)}, ensure_ascii=False))
    return EXIT_OK


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        project, path = observedef.find_plan(args.task, args.project)
    except Invalid as error:
        return _fail(error)
    return _emit(*check_plan(project, path))


def _cmd_show(args: argparse.Namespace) -> int:
    try:
        _, path = observedef.find_plan(args.task, args.project)
        document, plan = _plan(path)
    except Invalid as error:
        return _fail(error)
    if args.json:
        print(json.dumps(document, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(
        f"{plan.task}: {plan.job}; switched off {plan.switched_off}; "
        f"{plan.days} business days; {plan.timezone}"
    )
    for check in plan.checks:
        print(f"- {check.id} ({check.kind})" + (f": {check.label}" if check.label else ""))
    return EXIT_OK


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        day = _day(args.day)
        project, path = observedef.find_plan(args.task, args.project)
    except Invalid as error:
        return _fail(error)
    return _emit(*run_day(project, path, day, args.checks))


def _cmd_request(args: argparse.Namespace) -> int:
    try:
        _, path = observedef.find_plan(args.task, args.project)
        tool, _, document = _observability_document(path, _day(args.day), args.checks)
    except (Failure, Invalid) as error:
        return _fail(error)
    text = tool.request(document)
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return EXIT_OK


def _cmd_fallback(args: argparse.Namespace) -> int:
    try:
        project, path = observedef.find_plan(args.task, args.project)
        tool, plan, document = _observability_document(path, _day(args.day), args.checks)
        where = _where(project, plan.task)
    except (Failure, Invalid) as error:
        return _fail(error)
    day = document["day"]
    record = [
        {
            "check": count["check"],
            "hash": count["hash"],
            "command": (
                f"ws observe record {plan.task}{where} --check {count['check']} --day {day} "
                f"--hash {count['hash']} --value <N>"
            ),
        }
        for count in document["counts"]
    ]
    report = {"task": plan.task, "day": day, "calls": tool.fallback(document), "record": record}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return EXIT_OK


def _cmd_record(args: argparse.Namespace) -> int:
    typed = (args.check, args.day, args.value, args.hash, args.by)
    try:
        if args.result is not None and (
            any(item is not None for item in typed) or args.yes or args.no
        ):
            raise Invalid("--result takes no --check, --day, --value, --hash, --yes, --no or --by")
        if args.result is None and args.check is None:
            raise Invalid("pass --result FILE or --check ID")
        project, path = observedef.find_plan(args.task, args.project)
        if args.result is not None:
            document = _read_result(Path(args.result), path.parent)
            return _emit(*record_result(project, path, document))
        if [args.value is not None, args.yes, args.no].count(True) != 1:
            raise Invalid("pass exactly one of --value N, --yes or --no")
        if args.value is not None and not VALUE.fullmatch(args.value):
            raise Invalid(f"--value: {args.value!r} must be a number such as 0 or 12.5")
        value = Decimal(args.value) if args.value is not None else bool(args.yes)
        day = _day(args.day)
    except Invalid as error:
        return _fail(error)
    return _emit(*record_one(project, path, args.check, day, value, args.hash, args.by))


def _cmd_status(args: argparse.Namespace) -> int:
    try:
        report, code = status_report(args.project)
    except (Failure, Invalid) as error:
        return _fail(error)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for entry in report["plans"]:
            print(status_line(entry))
        if not report["plans"] and not report["problems"]:
            print("nenhuma observação")
    for problem in report["problems"]:
        print(f"{PREFIX}{problem}", file=sys.stderr)
    return code


def _cmd_report(args: argparse.Namespace) -> int:
    try:
        project, path = observedef.find_plan(args.task, args.project)
        document, plan = _plan(path)
        found = _rows(path)
        extra = _holidays()
    except (Failure, Invalid) as error:
        return _fail(error)
    hashes = _hashes(plan)
    entry = plan_status(document, project, hashes, found, _today(plan.timezone), extra)
    sys.stdout.write(render(document, hashes, found, entry, _title(plan.task), extra))
    return EXIT_OK


def _task(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("task", metavar="TASK", help="the task in the task tracker, as TS-123")
    parser.add_argument(
        "--project", metavar="SLUG", help="the planning project; needed when two hold the task"
    )


def _day_flag(parser: argparse.ArgumentParser, what: str) -> None:
    parser.add_argument(
        "--day",
        metavar="DATE",
        help=f"{what} (YYYY-MM-DD); default: the latest closed business day",
    )


def _only_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--check",
        dest="checks",
        action="append",
        default=[],
        metavar="ID",
        help="only this observability check",
    )


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "observe",
        help="Observe a switched-off job for N business days (read-only).",
        description=(
            "Keeps one observation plan per task: database counts, observability tool counts and "
            "manual confirmations, one value per business day, until the job can go for good. "
            "Never writes to the task tracker, a database or the observability tool."
        ),
    )
    commands = parser.add_subparsers(dest="observe_command", required=True)

    new = commands.add_parser(
        "new",
        help="Create the observation plan of a task.",
        description="Writes the plan header and commented examples; the checks are added by hand.",
    )
    new.add_argument("task", metavar="TASK", help="the task in the task tracker, as TS-123")
    new.add_argument("--project", required=True, metavar="SLUG", help="the planning project")
    new.add_argument("--job", required=True, metavar="TEXT", help="what was switched off")
    new.add_argument(
        "--switched-off",
        required=True,
        metavar="DATE",
        help="the day it was switched off (YYYY-MM-DD); day 1 is the next business day",
    )
    new.add_argument(
        "--days", default=str(DEFAULT_DAYS), metavar="N", help="business days to observe"
    )
    new.add_argument("--timezone", default=DEFAULT_TIMEZONE, metavar="TZ", help="the day's zone")
    new.set_defaults(handler=_cmd_new)

    check = commands.add_parser(
        "check",
        help="Validate a plan and guard its database queries.",
        description="Checks the plan contract, the rules of each check and the guard on every "
        "database query; sets the folder back to 700 and the files to 600.",
    )
    _task(check)
    check.set_defaults(handler=_cmd_check)

    show = commands.add_parser("show", help="Print a plan.", description="Prints a plan.")
    _task(show)
    show.add_argument("--json", action="store_true", help="the whole plan document")
    show.set_defaults(handler=_cmd_show)

    run = commands.add_parser(
        "run",
        help="Run and record the database checks of a day.",
        description="Runs the database checks of a closed business day, one read-only query at a "
        "time, and records them; lists the observability tool request and the questions left.",
    )
    _task(run)
    _day_flag(run, "the day to observe")
    run.add_argument(
        "--check", dest="checks", action="append", default=[], metavar="ID", help="only this check"
    )
    run.set_defaults(handler=_cmd_run)

    request = commands.add_parser(
        "request",
        help="Print the program the observability tool runs.",
        description="Prints, verbatim, the text the observability tool runs to count the day.",
    )
    _task(request)
    _day_flag(request, "the day to count")
    _only_flag(request)
    request.set_defaults(handler=_cmd_request)

    fallback = commands.add_parser(
        "fallback",
        help="Print the classic observability tool calls, as JSON.",
        description="Prints the classic observability tool calls that give the same counts.",
    )
    _task(fallback)
    _day_flag(fallback, "the day to count")
    _only_flag(fallback)
    fallback.set_defaults(handler=_cmd_fallback)

    record = commands.add_parser(
        "record",
        help="Record the observability tool's answer, a count or a manual answer.",
        description="Records the observability tool's answer (--result), or one value typed by a "
        "person (--check). Database checks are recorded by run.",
    )
    _task(record)
    record.add_argument("--result", metavar="FILE", help="the observability tool's JSON answer")
    record.add_argument("--check", metavar="ID", help="the check to record by hand")
    _day_flag(record, "the day of the value")
    record.add_argument("--value", metavar="N", help="the count of an observability check")
    record.add_argument("--hash", metavar="H", help="the check's hash from fallback")
    record.add_argument("--yes", action="store_true", help="the manual check passes")
    record.add_argument("--no", action="store_true", help="the manual check fails")
    record.add_argument("--by", metavar="NAME", help="who answered; default: the login name")
    record.set_defaults(handler=_cmd_record)

    status = commands.add_parser(
        "status",
        help="Where each observation stands.",
        description="One line per plan: day k of N, pending checks, streak and state.",
    )
    status.add_argument("--project", metavar="SLUG", help="only this planning project")
    status.add_argument("--json", action="store_true", help="the status document")
    status.set_defaults(handler=_cmd_status)

    report = commands.add_parser(
        "report",
        help="Print the observation as change record evidence.",
        description="Prints the days, values, times and hashes as Markdown; the title comes from "
        "the task tracker when it answers.",
    )
    _task(report)
    report.set_defaults(handler=_cmd_report)
