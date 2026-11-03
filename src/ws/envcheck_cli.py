"""`ws env`: the env var names a repo reads against the Parameter Store (part C of the session
automations spec).

Step 0 stub: it only registers the command group. Part C replaces it with `ws env check`.
"""

import argparse
import sys


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "env", help="Check the env var names a repo reads (not implemented yet)."
    )
    parser.set_defaults(handler=_not_implemented)


def _not_implemented(args: argparse.Namespace) -> int:
    print("ws env: not implemented yet", file=sys.stderr)
    return 2
