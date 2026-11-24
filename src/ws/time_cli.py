"""`ws time`: the command group; the handlers import lazily. JSON on stdout, exit 0 ok, 1 a rule
(a refused mark, an empty or unusable argument), 2 setup, 3 the tracker."""

import argparse
import json
import sys

from ws import userconfig

REF_HELP = "Card ref, like TS-123."
AT_HELP = "Today at this local time (HH:MM) instead of now; never in the future."


def _print(document: dict) -> None:
    print(json.dumps(document, ensure_ascii=False, indent=2))


def _start(args: argparse.Namespace) -> int:
    from ws import timelog

    try:
        _print(timelog.start(args.ref, args.at))
    except timelog.TimeRefused as error:
        print(f"ws time start: {error}", file=sys.stderr)
        return error.code
    except OSError as error:
        print(f"ws time start: file error: {error}", file=sys.stderr)
        return 1
    return 0


def _stop(args: argparse.Namespace) -> int:
    from ws import timelog

    try:
        _print(timelog.stop(args.ref, args.at))
    except timelog.TimeRefused as error:
        print(f"ws time stop: {error}", file=sys.stderr)
        return error.code
    except OSError as error:
        print(f"ws time stop: file error: {error}", file=sys.stderr)
        return 1
    return 0


def _status(args: argparse.Namespace) -> int:
    from ws import timelog

    try:
        _print(timelog.status(userconfig.load_time().idle_minutes))
    except (userconfig.ConfigInvalid, userconfig.ConfigMissing) as error:
        print(f"ws time status: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"ws time status: file error: {error}", file=sys.stderr)
        return 1
    return 0


def _report(args: argparse.Namespace) -> int:
    from ws import timereport

    return timereport.run(
        card=args.card,
        from_=args.from_,
        to=args.to,
        week=args.week,
        drafts=args.drafts,
        unplanned=args.unplanned,
    )


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "time", help="Mark the time spent on cards and report the hours worked from evidence."
    )
    commands = parser.add_subparsers(dest="time_command", required=True)

    start = commands.add_parser(
        "start",
        help="Open an interval for a card; several cards may be open. Marking a card already "
        "open changes nothing.",
    )
    start.add_argument("ref", metavar="REF", help=REF_HELP)
    start.add_argument("--at", metavar="HH:MM", help=AT_HELP)
    start.set_defaults(handler=_start)

    stop = commands.add_parser(
        "stop",
        help="Close the open interval of a card, or of every card without a ref. A stop before "
        "the start is refused.",
    )
    stop.add_argument("ref", nargs="?", metavar="REF", help=REF_HELP)
    stop.add_argument("--at", metavar="HH:MM", help=AT_HELP)
    stop.set_defaults(handler=_stop)

    status = commands.add_parser(
        "status", help="Print the open intervals and today's minutes per card (JSON)."
    )
    status.set_defaults(handler=_status)

    report = commands.add_parser(
        "report",
        help="Print the hours per day and card from marks, session activity and commits (JSON), "
        "less what the tracker already holds; never writes to the tracker.",
    )
    report.add_argument("--card", metavar="REF", help="The days this card was worked on.")
    report.add_argument("--from", dest="from_", metavar="DATE", help="First day, YYYY-MM-DD.")
    report.add_argument("--to", metavar="DATE", help="Last day, YYYY-MM-DD.")
    report.add_argument("--week", metavar="YYYY-Www", help="An ISO week, like 2026-W48.")
    report.add_argument(
        "--drafts",
        metavar="DIR",
        help="With --card: write a worklog draft per day with time to log into DIR, a folder "
        "under cards/drafts (new, or holding other drafts; a name already taken refuses).",
    )
    report.add_argument(
        "--unplanned",
        action="store_true",
        help="With --card: the card had no plan, so --drafts also writes an estimate draft equal "
        "to its real time.",
    )
    report.set_defaults(handler=_report)
