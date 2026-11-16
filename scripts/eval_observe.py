"""The `ws observe` of the observe evals: fixed answers that stay inside the real contracts.

The real `run` queries the production replica, and the day it picks depends on the clock, so the
shim answers `status`, `run`, `request`, `fallback` and `record` from here when the scaffold wrote
~/.eval-observe (the name of a variant below). Every JSON is checked against its contract in
src/ws/data/contracts before it is printed, and the program of `request` and the calls of
`fallback` come from the real adapter. `record --result` checks the saved answer like the real
command: contract, task, provider, day and each check's hash. Made-up data only: task TS-5,
project demo, host db.invalid. The file sits in scripts/, not evals/: the eval sandbox hides
evals/ from the run.
"""

import argparse
import json
import shlex
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ws import contracts
from ws.observability.datadog_adapter import Datadog
from ws.observestatus import status_line

PREFIX = "ws observe: "
TASK = "TS-5"
PROJECT = "demo"
JOB = "job de exemplo que copia a fila"
TODAY = "2026-11-12"
DAY = "2026-11-11"
DAY_NUMBER = 3
WINDOW = ["2026-11-11T03:00:00Z", "2026-11-12T03:00:00Z"]
PROVIDER = "datadog"
TOOL = "execute_code"
NO_COUNT = "the observability tool gave no count; run ws observe fallback for it"

DATABASE = {"fila-pendente": 0}
OBSERVABILITY = {
    "chamadas-rota": {
        "signal": "metrics",
        "query": (
            "sum:trace.http.request.hits{service:demo-api,resource_name:post_/exemplo}.as_count()"
        ),
        "hash": "ac1a935c81bf",
    },
    "logs-job": {"signal": "logs", "query": "service:demo-job status:info", "hash": "0cbe962dcc6c"},
}
MANUAL = {"conciliacao-ok": "A conciliação de ontem fechou sem diferença?"}
VARIANTS = {
    "database": ("fila-pendente",),
    "full": ("fila-pendente", "chamadas-rota", "logs-job", "conciliacao-ok"),
}


class Problem(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def _plan_dir() -> Path:
    return Path.home() / ".local/share/workspace/projects" / PROJECT / "observations"


def _emit(report: dict, contract: str) -> int:
    broken = contracts.validate(report, contract)
    report["problems"].extend(broken)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    for problem in report["problems"]:
        print(f"{PREFIX}{problem}", file=sys.stderr)
    return 1 if report["problems"] else 0


def _plan(args: argparse.Namespace, checks: tuple[str, ...]) -> None:
    if args.task != TASK:
        raise Problem(
            f"no observation plan for {args.task}; run ws observe new {args.task} --project <slug>"
        )
    if args.project not in (None, PROJECT):
        raise Problem(f"no observation plan for {args.task} in {args.project}")
    day = getattr(args, "day", None)
    if day not in (None, DAY):
        raise Problem(f"--day {day}: this eval's fixture holds only {DAY}")
    for check in getattr(args, "checks", None) or []:
        if check not in checks:
            raise Problem(f"unknown check {check}; the plan has {', '.join(checks)}")


def _probes(args: argparse.Namespace, checks: tuple[str, ...]) -> list[str]:
    probes = [check for check in checks if check in OBSERVABILITY]
    if not probes:
        raise Problem(f"{TASK} has no observability check")
    for check in args.checks:
        if check not in OBSERVABILITY:
            raise Problem(f"{check} is not an observability check of {TASK}")
    return [check for check in probes if not args.checks or check in args.checks]


def _request_document(probes: list[str]) -> dict:
    counts = [
        {
            "check": check,
            "signal": OBSERVABILITY[check]["signal"],
            "query": OBSERVABILITY[check]["query"],
            "from": WINDOW[0],
            "to": WINDOW[1],
            "hash": OBSERVABILITY[check]["hash"],
        }
        for check in probes
    ]
    document = {"version": 1, "task": TASK, "day": DAY, "counts": counts}
    broken = contracts.validate(document, "observability-request")
    if broken:
        raise Problem("; ".join(broken))
    return document


def status(args: argparse.Namespace, checks: tuple[str, ...]) -> int:
    if args.project not in (None, PROJECT):
        plans = []
    else:
        plans = [
            {
                "task": TASK,
                "project": PROJECT,
                "job": JOB,
                "days": 5,
                "due_day": DAY,
                "first_day": "2026-11-09",
                "day": DAY_NUMBER,
                "pending": list(checks),
                "missing_days": [],
                "stale": [],
                "attention_days": [],
                "streak": 2,
                "state": "observing",
            }
        ]
    report = {"version": 1, "today": TODAY, "plans": plans, "problems": []}
    if args.json:
        return _emit(report, "observe-status")
    for entry in plans:
        print(status_line(entry))
    if not plans:
        print("nenhuma observação")
    return 0


def run(args: argparse.Namespace, checks: tuple[str, ...]) -> int:
    report = {
        "version": 1,
        "task": TASK,
        "day": DAY,
        "day_number": DAY_NUMBER,
        "window": WINDOW,
        "recorded": [],
        "observability": None,
        "ask": [],
        "problems": [],
        "warnings": [],
    }
    selected = [check for check in checks if not args.checks or check in args.checks]
    for check in selected:
        if check in DATABASE:
            report["recorded"].append({"check": check, "value": DATABASE[check], "verdict": "pass"})
    probes = [check for check in selected if check in OBSERVABILITY]
    if probes:
        subset = "".join(f" --check {check}" for check in probes) if args.checks else ""
        result_path = str(_plan_dir() / f"{TASK}.{DAY}.result.json")
        report["observability"] = {
            "tool": TOOL,
            "checks": probes,
            "next": f"ws observe request {TASK} --day {DAY}{subset}",
            "record": f"ws observe record {TASK} --result {shlex.quote(result_path)}",
            "fallback": f"ws observe fallback {TASK} --day {DAY}{subset}",
            "result_path": result_path,
        }
    for check in selected:
        if check in MANUAL:
            command = f"ws observe record {TASK} --check {check} --day {DAY}"
            report["ask"].append(
                {
                    "check": check,
                    "question": MANUAL[check],
                    "yes": f"{command} --yes",
                    "no": f"{command} --no",
                }
            )
    return _emit(report, "observe-run")


def request(args: argparse.Namespace, checks: tuple[str, ...]) -> int:
    text = Datadog().request(_request_document(_probes(args, checks)))
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


def fallback(args: argparse.Namespace, checks: tuple[str, ...]) -> int:
    document = _request_document(_probes(args, checks))
    record = [
        {
            "check": count["check"],
            "hash": count["hash"],
            "command": f"ws observe record {TASK} --check {count['check']} --day {DAY} "
            f"--hash {count['hash']} --value <N>",
        }
        for count in document["counts"]
    ]
    report = {
        "version": 1,
        "task": TASK,
        "day": DAY,
        "calls": Datadog().fallback(document),
        "record": record,
        "problems": [],
    }
    return _emit(report, "observe-fallback")


def _verdict(value: Decimal) -> str:
    return "pass" if value == 0 else "fail"


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _moment(text: str, what: str) -> None:
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        moment = None
    if moment is None or moment.tzinfo is None:
        raise Problem(f"{what} must be an ISO date-time with an offset")


def _record_result(path: Path, checks: tuple[str, ...], report: dict) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise Problem(f"{path}: cannot be read: {error.strerror}") from None
    except ValueError:
        raise Problem(f"{path}: not JSON") from None
    broken = contracts.validate(document, "observability-result")
    if broken:
        raise Problem("the result: " + "; ".join(broken))
    if document["task"] != TASK:
        raise Problem(f"the result is for {document['task']}, not {TASK}")
    if document["provider"] != PROVIDER:
        raise Problem(
            "the result comes from another provider than the configured observability tool "
            f"({PROVIDER})"
        )
    if document["day"] != DAY:
        raise Problem(f"day {document['day']}: this eval's fixture holds only {DAY}")
    report["day"] = DAY
    for count in document["counts"]:
        check = count["check"]
        if check not in checks or check not in OBSERVABILITY:
            report["problems"].append(f"{check} is not an observability check of {TASK}")
            continue
        if count["hash"] != OBSERVABILITY[check]["hash"]:
            report["problems"].append(
                f"{check} changed since the request; run ws observe request again"
            )
            continue
        try:
            _moment(count["started"], f"{check}: started")
            _moment(count["finished"], f"{check}: finished")
        except Problem as error:
            report["problems"].append(str(error))
            continue
        value = Decimal(str(count["value"]))
        if not value.is_finite() or value < 0:
            report["problems"].append(f"{check}: the count must be a finite number, zero or more")
            continue
        report["recorded"].append(
            {"check": check, "value": _number(value), "verdict": _verdict(value)}
        )
    for failed in document["failed"]:
        report["warnings"].append(f"{failed['check']}: {NO_COUNT}")


def _record_one(args: argparse.Namespace, checks: tuple[str, ...], report: dict) -> None:
    check = args.check
    if check not in checks:
        raise Problem(f"unknown check {check}; the plan has {', '.join(checks)}")
    if check in DATABASE:
        raise Problem("database checks are recorded by ws observe run")
    if [args.value is not None, args.yes, args.no].count(True) != 1:
        raise Problem("pass exactly one of --value N, --yes or --no")
    if check in OBSERVABILITY:
        if args.value is None:
            raise Problem(f"{check} is an observability check; record it with --value N")
        if args.hash is None:
            raise Problem("--hash is required with --value; ws observe fallback prints it")
        if args.hash != OBSERVABILITY[check]["hash"]:
            raise Problem(f"{check} changed since the request; run ws observe request again")
        try:
            value = Decimal(args.value)
        except InvalidOperation:
            raise Problem(f"--value: {args.value!r} must be a number such as 0 or 12.5") from None
        if not value.is_finite() or value < 0:
            raise Problem(f"--value: {args.value!r} must be a number such as 0 or 12.5")
        recorded = {"check": check, "value": _number(value), "verdict": _verdict(value)}
    else:
        if args.value is not None or args.hash is not None:
            raise Problem(f"{check} is a manual check; record it with --yes or --no")
        recorded = {"check": check, "value": args.yes, "verdict": "pass" if args.yes else "fail"}
    report["day"] = DAY
    report["recorded"].append(recorded)


def record(args: argparse.Namespace, checks: tuple[str, ...]) -> int:
    report = {
        "version": 1,
        "task": TASK,
        "day": None,
        "recorded": [],
        "problems": [],
        "warnings": [],
    }
    typed = (args.check, args.day, args.value, args.hash, args.by)
    if args.result is not None:
        if any(item is not None for item in typed) or args.yes or args.no:
            raise Problem("--result takes no --check, --day, --value, --hash, --yes, --no or --by")
        _record_result(Path(args.result), checks, report)
    elif args.check is None:
        raise Problem("pass --result FILE or --check ID")
    else:
        _record_one(args, checks, report)
    return _emit(report, "observe-record")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ws observe")
    commands = parser.add_subparsers(dest="command", required=True)

    def task(name: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name)
        sub.add_argument("task")
        sub.add_argument("--project")
        return sub

    for name in ("run", "request", "fallback"):
        sub = task(name)
        sub.add_argument("--day")
        sub.add_argument("--check", dest="checks", action="append", default=[])
    sub = task("record")
    for flag in ("--result", "--check", "--day", "--value", "--hash", "--by"):
        sub.add_argument(flag)
    sub.add_argument("--yes", action="store_true")
    sub.add_argument("--no", action="store_true")
    sub = commands.add_parser("status")
    sub.add_argument("--project")
    sub.add_argument("--json", action="store_true")
    return parser


HANDLERS = {
    "status": status,
    "run": run,
    "request": request,
    "fallback": fallback,
    "record": record,
}


def main(argv: list[str], variant: str) -> int:
    checks = VARIANTS.get(variant)
    if checks is None:
        print(f"{PREFIX}unknown eval variant {variant!r}", file=sys.stderr)
        return 2
    if not argv or argv[0] not in HANDLERS:
        name = argv[0] if argv else "(none)"
        print(f"{PREFIX}{name}: not part of this eval's fixture", file=sys.stderr)
        return 2
    args = _parser().parse_args(argv)
    try:
        if args.command != "status":
            _plan(args, checks)
        return HANDLERS[args.command](args, checks)
    except Problem as error:
        print(f"{PREFIX}{error}", file=sys.stderr)
        return error.code
