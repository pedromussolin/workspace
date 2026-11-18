"""`ws release`: the command group; the handlers live in `ws.release` and import lazily."""

import argparse


def _project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", metavar="SLUG", help="planning project (workspace slug)")


def _repos(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo", dest="repos", action="extend", nargs="+", default=[], metavar="NAME"
    )


def _envs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env",
        dest="envs",
        action="extend",
        nargs="+",
        default=[],
        metavar="NAME",
        help="environments (production, or those of [release.environments]); default: the "
        "default ones",
    )


def _branches(args: argparse.Namespace) -> int:
    from ws.release import branches

    return branches.run_branches(args)


def _new(args: argparse.Namespace) -> int:
    from ws.release import build

    return build.run_new(args)


def _preview_publish(args: argparse.Namespace) -> int:
    from ws.release import publish

    return publish.run_preview(args)


def _publish(args: argparse.Namespace) -> int:
    from ws.release import publish

    return publish.run_publish(args)


def _preview_move(args: argparse.Namespace) -> int:
    from ws.release import move

    return move.run_preview(args)


def _move(args: argparse.Namespace) -> int:
    from ws.release import move

    return move.run_move(args)


def _status(args: argparse.Namespace) -> int:
    from ws.release import status

    return status.run_status(args)


def _move_arguments(parser: argparse.ArgumentParser) -> None:
    _project(parser)
    parser.add_argument("old", metavar="OLD")
    parser.add_argument("new", metavar="NEW")
    parser.add_argument("--reason", required=True, help="why the release moves")
    parser.add_argument("--delete-old-branches", action="store_true")


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("release", help="Build, publish, move and report a release.")
    commands = parser.add_subparsers(dest="release_command", required=True)

    branches = commands.add_parser("branches", help="List the task branches of the repos.")
    _project(branches)
    branches.add_argument(
        "--task", dest="tasks", action="extend", nargs="+", default=[], metavar="TS-N"
    )
    branches.add_argument(
        "--from-items", dest="items", action="extend", nargs="+", default=[], metavar="SLUG"
    )
    _repos(branches)
    branches.set_defaults(handler=_branches)

    new = commands.add_parser("new", help="Build the release branches of a day.")
    _project(new)
    new.add_argument("day", metavar="DAY")
    _repos(new)
    _envs(new)
    new.set_defaults(handler=_new)

    preview = commands.add_parser("preview", help="Plan a write and print its approval code.")
    steps = preview.add_subparsers(dest="preview_command", required=True)
    preview_publish = steps.add_parser("publish", help="Plan the PRs of a release.")
    _project(preview_publish)
    preview_publish.add_argument("day", metavar="DAY")
    _repos(preview_publish)
    _envs(preview_publish)
    preview_publish.set_defaults(handler=_preview_publish)
    preview_move = steps.add_parser("move", help="Plan the move of a release to another day.")
    _move_arguments(preview_move)
    preview_move.set_defaults(handler=_preview_move)

    publish = commands.add_parser(
        "publish", help="Push the branches and open the PRs.", allow_abbrev=False
    )
    _project(publish)
    publish.add_argument("day", metavar="DAY")
    _repos(publish)
    _envs(publish)
    publish.add_argument("--approve", required=True, metavar="CODE")
    publish.set_defaults(handler=_publish)

    move = commands.add_parser("move", help="Move a published release.", allow_abbrev=False)
    _move_arguments(move)
    move.add_argument("--approve", required=True, metavar="CODE")
    move.set_defaults(handler=_move)

    status = commands.add_parser("status", help="Report the release of a day.")
    _project(status)
    status.add_argument("day", nargs="?", default=None, metavar="DAY")
    status.add_argument("--links", action="store_true")
    status.set_defaults(handler=_status)
