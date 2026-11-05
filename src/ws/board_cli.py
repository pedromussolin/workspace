"""`ws board`: Jira cards follow the code. `status` reads; `drafts` only writes draft files."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from ws import codeposition, jira, userconfig
from ws.boardconfig import BoardMissing, load_board
from ws.boardrules import plan_moves
from ws.config import config_dir, repo_root
from ws.standup import find_repos
from ws.taskmodel import RUNG, Status

SPEC = "docs/specs/2026-11-05-board-sync-design.md"
EPIC_WARNING = "cards without is_epic: epics known only as parents; run ws task list again"


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("board", help="Make Jira cards follow the code.")
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


def _fail(command: str, message: object) -> int:
    print(f"ws board {command}: {message}", file=sys.stderr)
    return 2


def _read_cards(path: Path) -> list[dict]:
    cards = json.loads(path.read_text(encoding="utf-8"))["cards"]
    if not isinstance(cards, list) or not all(isinstance(card, dict) for card in cards):
        raise ValueError("cards must be a list of objects")
    return cards


def _status(args: argparse.Namespace) -> int:
    try:
        config = userconfig.load_config()
        cfg = load_board()
    except BoardMissing:
        return _fail(
            "status",
            f'no [board] table in {config_dir() / "config.toml"}; add one (see {SPEC}, "Config")',
        )
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid) as error:
        return _fail("status", error)
    try:
        cards = _read_cards(args.cards)
        tasks = [
            jira.task_from_card(card, config.jira.site, config.jira.status_overrides)
            for card in cards
        ]
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
    keys = {task.key for task in tasks if task.status in RUNG and task.status != Status.DONE}
    stale: set[str] = set()
    if cfg.fetch:
        errors = codeposition.fetch(repos, cfg.remote)
        warnings.extend(f"fetch {repo}: {error}" for repo, error in errors.items())
        stale = set(errors)
    found, more = codeposition.positions(repos, keys, cfg, today, stale)
    warnings.extend(more)
    plan = plan_moves(tasks, found, cfg, today)
    print(json.dumps({**plan, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 0
