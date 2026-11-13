"""`ws item`: the offline commands on the items of the planning projects."""

import argparse
import json
import sys
from pathlib import Path

from ws import items
from ws.config import repo_root
from ws.identity import dev_id
from ws.itemfile import ItemError
from ws.items import Project, ProjectMissing
from ws.tracker.vocab import CARD_TYPES
from ws.userconfig import ConfigInvalid, ConfigMissing, UserConfig, load_config

SETUP = 2


class _Directory:
    """The people of `config.toml` by dev id; the runner's own dev id is always known."""

    def __init__(self, config: UserConfig):
        self._people = config.people
        self._kind = config.tracker_kind
        self.own = dev_id(config.identity_email)

    def problem(self, person: str) -> str | None:
        if person == self.own:
            return None
        found = self._people.get(person)
        if found is None:
            return (
                f"unknown person {person!r}: run ws people add <e-mail> and paste the block "
                "into config.toml"
            )
        if not found.ids.get(self._kind):
            return (
                f"person {person!r} has no {self._kind} id; run ws people add <e-mail> and "
                "paste the block into config.toml"
            )
        return None


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("item", help="Items of the planning projects.")
    commands = parser.add_subparsers(dest="item_command", required=True)

    new = commands.add_parser("new", help="Create the next numbered item of a project.")
    new.add_argument("project")
    new.add_argument("--type", required=True, dest="type_", help="|".join(CARD_TYPES))
    new.add_argument("--epic", help="epic ref; an item may be created before its epic exists")
    new.add_argument("--assignee", default="me", help="dev id or me (default: me)")
    new.add_argument("--reporter", default="me", help="dev id or me (default: me)")
    new.add_argument("--heading", required=True)
    new.add_argument("--slug", help="file name after the number (default: the folded heading)")
    new.set_defaults(handler=_cmd_new)

    check = commands.add_parser("check", help="Check the items of the projects offline.")
    check.add_argument("projects", nargs="*")
    check.set_defaults(handler=_cmd_check)

    table = commands.add_parser("table", help="Fill the items table between the README markers.")
    table.add_argument("project")
    table.set_defaults(handler=_cmd_table)


def _projects(names: list[str], root: Path) -> list[Project]:
    return [items.load_project(root, slug) for slug in names or items.project_slugs(root)]


def _config() -> UserConfig:
    return load_config()


def _fail(error: object, code: int) -> int:
    print(error, file=sys.stderr)
    return code


def _cmd_new(args) -> int:
    root = repo_root()
    try:
        directory = _Directory(_config()) if "me" in (args.assignee, args.reporter) else None
        own = directory.own if directory else ""
        assignee = own if args.assignee == "me" else args.assignee
        reporter = own if args.reporter == "me" else args.reporter
        path = items.new_item(
            root,
            args.project,
            type_=args.type_,
            epic=args.epic,
            assignee=assignee,
            reporter=reporter,
            heading=args.heading,
            name=args.slug,
        )
    except (ConfigMissing, ConfigInvalid, ProjectMissing) as error:
        return _fail(error, SETUP)
    except ItemError as error:
        return _fail(error, 1)
    print(items.rel(root, path))
    return 0


def _cmd_check(args) -> int:
    root = repo_root()
    try:
        directory = _Directory(_config())
        projects = _projects(args.projects, root)
    except (ConfigMissing, ConfigInvalid, ProjectMissing) as error:
        return _fail(error, SETUP)
    problems = items.check_offline(projects, root, directory)
    report = {
        "problems": problems,
        "drift": [],
        "pending": items.pending_offline(projects, root),
        "orphans": [],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if problems else 0


def _cmd_table(args) -> int:
    root = repo_root()
    try:
        project = items.load_project(root, args.project)
    except ProjectMissing as error:
        return _fail(error, SETUP)
    try:
        changed = items.write_table(project)
    except ItemError as error:
        return _fail(error, 1)
    report = {
        "path": items.rel(root, project.folder / "README.md"),
        "rows": len(project.items),
        "changed": changed,
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0
