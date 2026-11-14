"""`ws item`: the commands on the items of the planning projects.

`new`, `check`, `table` and `set-card` work offline; `check --tracker`, `drafts`, `pull` and
`sync` read the tracker, and none of them writes to it."""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from ws import itemrecord, items, itemsync, itemtracker
from ws.config import repo_root
from ws.identity import dev_id
from ws.itemfile import ItemError
from ws.items import Project, ProjectMissing
from ws.itemsync import PULL_FIELDS
from ws.tracker import port
from ws.tracker.port import People, TrackerError, TrackerSetup
from ws.tracker.vocab import CARD_TYPES
from ws.userconfig import ConfigInvalid, ConfigMissing, UserConfig, load_config

SETUP = 2
TRACKER = 3


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

    check = commands.add_parser(
        "check", help="Check the items of the projects (offline unless --tracker)."
    )
    check.add_argument("projects", nargs="*")
    check.add_argument("--tracker", action="store_true", help="also compare with the tracker")
    check.set_defaults(handler=_cmd_check)

    drafts = commands.add_parser(
        "drafts", help="Write the drafts that move the tracker to the items."
    )
    drafts.add_argument("projects", nargs="*")
    drafts.add_argument("--only", help="comma-separated card refs or item paths")
    drafts.set_defaults(handler=_cmd_drafts)

    table = commands.add_parser("table", help="Fill the items table between the README markers.")
    table.add_argument("project")
    table.set_defaults(handler=_cmd_table)

    pull = commands.add_parser("pull", help="Copy the tracker's values of chosen fields.")
    pull.add_argument("item")
    pull.add_argument("--fields", required=True, help="comma-separated: " + ",".join(PULL_FIELDS))
    pull.set_defaults(handler=_cmd_pull)

    sync = commands.add_parser("sync", help="Refresh the [tracker] table of the items.")
    sync.add_argument("projects", nargs="*")
    sync.set_defaults(handler=_cmd_sync)

    set_card = commands.add_parser("set-card", help="Write the card of an item, or release it.")
    set_card.add_argument("item")
    target = set_card.add_mutually_exclusive_group(required=True)
    target.add_argument("ref", nargs="?")
    target.add_argument("--none", action="store_true", help="release an uncertain record")
    set_card.set_defaults(handler=_cmd_set_card)


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
        own = dev_id(_config().identity_email) if "me" in (args.assignee, args.reporter) else ""
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
        people = People.from_config(_config(), own_account="")
        projects = _projects(args.projects, root)
    except (ConfigMissing, ConfigInvalid, ProjectMissing) as error:
        return _fail(error, SETUP)
    if args.tracker:
        return _cmd_check_tracker(projects, root)
    problems = items.check_offline(projects, root, people)
    report = {
        "problems": problems,
        "drift": [],
        "pending": items.pending_offline(projects, root),
        "orphans": [],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if problems else 0


def _compared(projects: list[Project], root: Path):
    tracker = port.open_tracker()
    people = People.from_config(_config(), tracker.me())
    return tracker, itemtracker.compare(projects, root, tracker, people)


def _cmd_check_tracker(projects: list[Project], root: Path) -> int:
    try:
        _, report = _compared(projects, root)
    except (TrackerSetup, ConfigMissing, ConfigInvalid) as error:
        return _fail(error, SETUP)
    except TrackerError as error:
        return _fail(error, TRACKER)
    print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    return 1 if report.problems else 0


def _cmd_drafts(args) -> int:
    root = repo_root()
    try:
        projects = _projects(args.projects, root)
        only = {ref.strip() for ref in args.only.split(",") if ref.strip()} if args.only else None
        tracker, report = _compared(projects, root)
        result = itemtracker.write_drafts(report, projects, root, tracker, only, datetime.now())
    except (TrackerSetup, ConfigMissing, ConfigInvalid, ProjectMissing) as error:
        return _fail(error, SETUP)
    except TrackerError as error:
        return _fail(error, TRACKER)
    except ItemError as error:
        return _fail(error, 1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


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


def _item_rel(root: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            return items.rel(root, path)
        except ValueError:
            raise ItemError(f"{value} is outside the repo") from None
    return value


def _cmd_pull(args) -> int:
    root = repo_root()
    try:
        config = _config()
        tracker = port.open_tracker()
        people = People.from_config(config, own_account=tracker.me())
        report = itemsync.pull(
            root, _item_rel(root, args.item), args.fields.split(","), tracker, people
        )
    except (ConfigMissing, ConfigInvalid, TrackerSetup) as error:
        return _fail(error, SETUP)
    except ItemError as error:
        return _fail(error, 1)
    except TrackerError as error:
        return _fail(error, TRACKER)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _cmd_sync(args) -> int:
    root = repo_root()
    try:
        projects = _projects(args.projects, root)
        tracker = port.open_tracker()
        report = itemsync.sync(projects, root, tracker, date.today())
    except (ConfigMissing, ConfigInvalid, ProjectMissing, TrackerSetup) as error:
        return _fail(error, SETUP)
    except TrackerError as error:
        return _fail(error, TRACKER)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["problems"] else 0


def _cmd_set_card(args) -> int:
    root = repo_root()
    try:
        name = _item_rel(root, args.item)
        if args.none:
            if itemrecord.recorded(name) is None:
                raise ItemError(f"{name} has no uncertain record to release")
        else:
            itemrecord.write_back(root, name, args.ref)
        itemrecord.clear(name)
    except ItemError as error:
        return _fail(error, 1)
    print(json.dumps({"path": name, "card": None if args.none else args.ref}))
    return 0
