"""`ws handoff`: hands a chat over to a new one (part A of the session automations spec)."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from ws import config, handoff, userconfig


def _day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD") from None


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("handoff", help="Hand a chat over to a new one.")
    commands = parser.add_subparsers(dest="handoff_command", required=True)

    collected = commands.add_parser(
        "collect",
        help="JSON of the repos, worktrees, open PRs and handoff files (read-only, no fetch).",
    )
    collected.add_argument(
        "--all", action="store_true", help="list the clean repos too (default: count them)"
    )
    collected.add_argument("--no-prs", action="store_true", help="do not ask gh for open PRs")
    collected.set_defaults(handler=_cmd_collect)

    new = commands.add_parser(
        "new", help="Create the private HANDOFF file of a project from the template."
    )
    new.add_argument("slug", help="a folder under projects/, or standalone")
    new.add_argument("--topic", required=True, help="lowercase words joined by hyphens")
    new.add_argument("--date", type=_day, help="YYYY-MM-DD (default: today)")
    new.set_defaults(handler=_cmd_new)

    refresh = commands.add_parser(
        "refresh", help="Re-render the state block of a handoff file; --diff only shows changes."
    )
    refresh.add_argument("file", type=Path)
    refresh.add_argument("--diff", action="store_true", help="write nothing, print what changed")
    refresh.set_defaults(handler=_cmd_refresh)

    verdict = commands.add_parser(
        "check", help="JSON verdict on a handoff file; exit 0 when ok, 1 otherwise."
    )
    verdict.add_argument("file", type=Path)
    verdict.set_defaults(handler=_cmd_check)


def _collect(args: argparse.Namespace, name: str, include_clean: bool = False) -> dict | int:
    """The collected state, or the exit code to return (2: the config cannot be used)."""
    try:
        cfg = userconfig.load_standup()
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid) as error:
        print(f"ws handoff {name}: {error}", file=sys.stderr)
        return 2
    try:
        return handoff.collect(
            cfg,
            config.repo_root(),
            include_clean=include_clean,
            prs=not getattr(args, "no_prs", False),
        )
    except OSError as error:
        print(f"ws handoff {name}: {error}", file=sys.stderr)
        return 1


def _cmd_collect(args: argparse.Namespace) -> int:
    result = _collect(args, "collect", include_clean=args.all)
    if isinstance(result, int):
        return result
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


def _cmd_new(args: argparse.Namespace) -> int:
    collected = _collect(args, "new")
    if isinstance(collected, int):
        return collected
    try:
        path = handoff.new_handoff(
            args.slug,
            args.topic,
            args.date or date.today(),
            collected,
            root=config.repo_root(),
            data_dir=config.data_dir(),
        )
    except (handoff.HandoffError, OSError) as error:
        print(f"ws handoff new: {error}", file=sys.stderr)
        return 1
    summary = {
        "path": str(path),
        "repos": len(collected["repos"]),
        "prs": len(collected["prs"]),
        "warnings": collected["warnings"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_refresh(args: argparse.Namespace) -> int:
    collected = _collect(args, "refresh")
    if isinstance(collected, int):
        return collected
    try:
        diff = handoff.refresh(args.file, collected, diff_only=args.diff)
    except (handoff.HandoffError, OSError) as error:
        print(f"ws handoff refresh: {error}", file=sys.stderr)
        return 1
    print(diff or "no changes")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        verdict = handoff.check(
            args.file, data_dir=config.data_dir(), extra_globs=handoff.configured_globs()
        )
    except handoff.HandoffError as error:
        print(f"ws handoff check: {error}", file=sys.stderr)
        return 1
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict["ok"] else 1
