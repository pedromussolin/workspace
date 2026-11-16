"""`ws board`: tasks follow the code. `status` reads; `drafts` only writes draft files."""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from ws import card as cards_store
from ws import codeposition, tracker, userconfig
from ws.boardconfig import BoardConfig, BoardMissing, load_board, unmapped_status
from ws.boardrules import plan_moves
from ws.config import config_dir, repo_root
from ws.standup import find_repos
from ws.taskmodel import RUNG, Status, Task
from ws.tracker.errors import TrackerSetup
from ws.userconfig import toml_string

SPEC = "docs/specs/2026-11-05-board-sync-design.md"
KEY = re.compile(r"[A-Z][A-Z0-9]+-\d+")
EPIC_WARNING = "cards without is_epic: epics known only as parents; run ws task list again"


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("board", help="Make tracker tasks follow the code.")
    commands = parser.add_subparsers(dest="board_command", required=True)
    status = commands.add_parser(
        "status",
        help="What the code proves about each open card: moves, held, limited, to confirm (JSON).",
    )
    status.add_argument("--cards", type=Path, required=True, help="Output of `ws task list`.")
    status.add_argument(
        "--today", type=date.fromisoformat, default=None, help="YYYY-MM-DD; default: today"
    )
    status.set_defaults(handler=_status)
    drafts = commands.add_parser(
        "drafts", help="Write one `move` draft per move of a `status` output, for ws card preview."
    )
    drafts.add_argument("--board", type=Path, required=True, help="Output of `ws board status`.")
    drafts.set_defaults(handler=_drafts)


def _fail(command: str, message: object) -> int:
    print(f"ws board {command}: {message}", file=sys.stderr)
    return 2


def _read_cards(path: Path) -> list[dict]:
    cards = json.loads(path.read_text(encoding="utf-8"))["cards"]
    if not isinstance(cards, list) or not all(isinstance(card, dict) for card in cards):
        raise ValueError("cards must be a list of objects")
    return cards


def _misread(
    cards: list[dict], tasks: list[Task], cfg: BoardConfig, warnings: list[str], table: str
) -> set[str]:
    """Cards in a `[board.statuses]` name that the tracker's mapping reads as another status.

    Their position is not computed and they are not asked to confirm: a wrong reading could move
    them back.
    """
    board_status = {name: status for status, name in cfg.statuses.items()}
    keys = set()
    for card, task in zip(cards, tasks, strict=True):
        expected = board_status.get(card["status_name"])
        if expected is not None and task.status != expected:
            warnings.append(
                f'card {task.key}: status "{card["status_name"]}" reads as {task.status.value}; '
                f"check {table}"
            )
            keys.add(task.key)
    return keys


def _status(args: argparse.Namespace) -> int:
    try:
        config = userconfig.load_config()
        cfg = load_board()
        section = userconfig.load_tracker_table()[3]
    except BoardMissing:
        return _fail(
            "status",
            f'no [board] table in {config_dir() / "config.toml"}; add one (see {SPEC}, "Config")',
        )
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid) as error:
        return _fail("status", error)
    try:
        overrides = tracker.status_overrides(config)
    except TrackerSetup as error:
        return _fail("status", error)
    # status_overrides refuses a config whose kind has no adapter, so the section names that
    # kind's table: `[tracker.<kind>]`, or the old `[jira]` the user still has.
    table = f"[{section}.status_overrides]"
    problem = unmapped_status(cfg, overrides, table)
    if problem is not None:
        return _fail("status", problem)
    try:
        cards = _read_cards(args.cards)
        tasks = [tracker.task_from_listing(card, config) for card in cards]
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _fail("status", f"cannot read {args.cards}: {error}")
    today = args.today or date.today()
    warnings: list[str] = []
    if any("is_epic" not in card for card in cards):
        warnings.append(EPIC_WARNING)
    repos = [
        repo
        for repo in find_repos(config.standup, repo_root(), warnings)
        if not cfg.ignored(repo.name)
    ]
    misread = _misread(cards, tasks, cfg, warnings, table)
    keys = {task.key for task in tasks if task.status in RUNG and task.status != Status.DONE}
    keys -= misread
    stale: set[str] = set()
    if cfg.fetch:
        errors = codeposition.fetch(repos, cfg)
        warnings.extend(f"fetch {repo}: {error}" for repo, error in errors.items())
        stale = set(errors)
    found, more = codeposition.positions(repos, keys, cfg, today, stale)
    warnings.extend(more)
    plan = plan_moves(tasks, found, cfg, today)
    plan["to_confirm"] = [item for item in plan["to_confirm"] if item["key"] not in misread]
    print(json.dumps({**plan, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 0


def _draft_text(move: object) -> tuple[str, str]:
    if not isinstance(move, dict):
        raise ValueError("a move must be an object")
    key, to_name = move.get("key"), move.get("to_name")
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ValueError(f"move key {key!r} is not a task key")
    if not isinstance(to_name, str) or not to_name.strip():
        raise ValueError(f"move {key}: to_name must be a non-empty string")
    text = f'+++\nop = "move"\nkey = {toml_string(key)}\nto = {toml_string(to_name)}\n+++\n'
    return f"move-{key}.md", text


def _drafts(args: argparse.Namespace) -> int:
    try:
        moves = json.loads(args.board.read_text(encoding="utf-8"))["moves"]
        if not isinstance(moves, list):
            raise ValueError("moves must be a list")
        files = [_draft_text(move) for move in moves]
        names = [name for name, _ in files]
        if len(set(names)) != len(names):
            raise ValueError("two moves for the same card")
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _fail("drafts", f"cannot use {args.board}: {error}")
    if not files:
        print(json.dumps({"folder": None, "count": 0}))
        return 0
    try:
        folder = cards_store.drafts_folder(f"sync-{datetime.now():%Y%m%d-%H%M%S}")
    except FileExistsError as error:
        print(f"ws board drafts: the folder already exists, run again: {error}", file=sys.stderr)
        return 1
    for name, text in files:
        (folder / name).write_text(text, encoding="utf-8")
    print(json.dumps({"folder": str(folder), "count": len(files)}, ensure_ascii=False))
    return 0
