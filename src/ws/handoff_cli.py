"""`ws handoff`: hands a chat over to a new one (part A of the session automations spec).

Step 0 stub: it only registers the command group. Part A replaces it with the subcommands.
"""

import argparse
import sys


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "handoff", help="Hand a chat over to a new one (not implemented yet)."
    )
    parser.set_defaults(handler=_not_implemented)


def _not_implemented(args: argparse.Namespace) -> int:
    print("ws handoff: not implemented yet", file=sys.stderr)
    return 2
