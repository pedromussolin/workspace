"""Entry point of the ws command. Each subcommand sets a handler that returns the exit code."""

import argparse

from ws import bootstrap
from ws.config import claude_skills_dir, config_dir, repo_root


def _add_setup(subparsers) -> None:
    parser = subparsers.add_parser(
        "setup",
        help="Wire this clone: git hooks path, skill links, private config and Claude Code gates.",
    )
    parser.set_defaults(handler=_cmd_setup)


def _cmd_setup(args: argparse.Namespace) -> int:
    problems = bootstrap.run_setup(repo_root(), config_dir(), claude_skills_dir())
    if not problems:
        print("ok")
        return 0
    for problem in problems:
        print(problem)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ws", description="Personal workspace tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_setup(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)
