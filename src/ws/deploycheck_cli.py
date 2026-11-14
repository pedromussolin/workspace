"""`ws deploy-check`: the deploy plan and the Datadog checks (part D of the session automations
spec).

`plan` prints JSON, `script` the JavaScript for `execute_code`, `queries` the classic-tool fallback
as JSON. Nothing here reads Datadog, pulls a repo or writes a file.
"""

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from ws import deploycheck, userconfig

EXIT_ERROR = 1
EXIT_USAGE = 2


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "deploy-check",
        help="Plan and build the Datadog checks of a deploy (read-only).",
        description=(
            "Reads the deploy moment from the local argocd repo and builds the windows, the "
            "program for the Datadog MCP execute_code and the classic-tool fallback queries. "
            "The [deploy_check] table of config.toml names the services and the env tags."
        ),
    )
    commands = parser.add_subparsers(dest="deploy_check_command", required=True)

    plan = commands.add_parser("plan", help="The services in deploy order, deploys and windows.")
    _common(plan)
    plan.add_argument(
        "--only", nargs="+", metavar="KEY", help="Only these service keys (order kept)."
    )
    plan.set_defaults(handler=lambda args: _run(args, _plan))

    script = commands.add_parser("script", help="The JavaScript for execute_code, one service.")
    script.add_argument("key", help="Service key of [deploy_check.services].")
    _common(script)
    script.set_defaults(handler=lambda args: _run(args, _script))

    queries = commands.add_parser("queries", help="The classic-tool calls, as JSON, one service.")
    queries.add_argument("key", help="Service key of [deploy_check.services].")
    _common(queries)
    queries.set_defaults(handler=lambda args: _run(args, _queries))


def _moment(text: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not an ISO 8601 date and time") from None
    return parsed.astimezone(UTC)


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env", required=True, help="Environment: a key of deploy_check.env_tags.")
    parser.add_argument(
        "--at",
        type=_moment,
        metavar="ISO",
        help=(
            "Deploy moment, ISO 8601; without an offset it is local time of this machine "
            "(converted to UTC); default: the argocd commit."
        ),
    )


def _run(
    args: argparse.Namespace,
    build: Callable[[argparse.Namespace, deploycheck.DeployCheckSettings], str],
) -> int:
    try:
        settings = deploycheck.load_settings()
        output = build(args, settings)
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid) as error:
        print(f"ws deploy-check: {error}", file=sys.stderr)
        return EXIT_USAGE
    except deploycheck.DeployCheckError as error:
        print(f"ws deploy-check: {error}", file=sys.stderr)
        return EXIT_ERROR
    print(output)
    return 0


def _now() -> datetime:
    return datetime.now(UTC)


def _plan(args: argparse.Namespace, settings: deploycheck.DeployCheckSettings) -> str:
    result = deploycheck.plan(settings, args.env, at=args.at, only=args.only, now=_now())
    return json.dumps(result, ensure_ascii=False, indent=2)


def _script(args: argparse.Namespace, settings: deploycheck.DeployCheckSettings) -> str:
    script = deploycheck.build_script(settings, args.key, args.env, at=args.at, now=_now())
    return script.rstrip("\n")


def _queries(args: argparse.Namespace, settings: deploycheck.DeployCheckSettings) -> str:
    found = deploycheck.classic_queries(settings, args.key, args.env, at=args.at, now=_now())
    return json.dumps(found, ensure_ascii=False, indent=2)
