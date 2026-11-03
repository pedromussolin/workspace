"""`ws deploy-check`: the deploy plan and the Datadog checks (part D of the session automations
spec).

Step 0 stub: it only registers the command group. Part D replaces it with the subcommands.
"""

import argparse
import sys


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "deploy-check", help="Check a deploy in Datadog (not implemented yet)."
    )
    parser.set_defaults(handler=_not_implemented)


def _not_implemented(args: argparse.Namespace) -> int:
    print("ws deploy-check: not implemented yet", file=sys.stderr)
    return 2
