"""`ws review pack REF`: the review package of a card, read-only on its repos, private on disk.

Per repo it reads what the task branch changed against the merge base with the remote base
(committed, staged, unstaged and untracked), sorts the files by category and adds the migrations,
the env vars and the test files. With the card's context it writes `pack.json` (mode 600, folders
700) under the data folder, never in the workspace repo, and prints the same JSON. Git only
fetches and reads; nothing goes to the tracker. Spec: docs/specs/2026-11-15-card-review-design.md.
"""

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ws import cardstart, gittools, items, userconfig
from ws.boardconfig import BoardConfig, BoardMissing, load_board
from ws.config import REPO_NAME, config_dir, data_dir, repo_root
from ws.envcheck import EnvCheckSettings, RepoProfile, SetupError, files_at, load_settings
from ws.gittools import GitError
from ws.itemfile import ItemError
from ws.project import SLUG_PATTERN
from ws.reviewcard import card_context
from ws.reviewdiff import (
    Checkout,
    Collected,
    FileChange,
    ReviewRefused,
    collect,
    diff_command,
    find_checkout,
)
from ws.reviewpaths import CATEGORIES, category_for
from ws.reviewsignals import env_report, migration_report, new_side, profile_for
from ws.tracker import port
from ws.tracker.port import TrackerError, TrackerSetup
from ws.tracker.vocab import REF

DEFAULT_PROJECT = "standalone"
SPEC = "docs/specs/2026-11-15-card-review-design.md"
PACK = "pack.json"
REVIEW = "review.md"
PRIVATE_FOLDER = 0o700
CREATED = ("added", "copied")
NO_TESTS = "code changed with no test file changed"


@dataclass
class _Notes:
    flags: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Tree:
    """One repo's files at the merge base and after the change, for the signals.

    The new side comes from the work tree when the branch is checked out (changed files read from
    disk over the base), else from the branch's commit. A binary file is never read as source.
    """

    repo: Path
    checkout: Checkout
    collected: Collected

    def sides(self, wanted: Callable[[str], bool]) -> tuple[dict[str, bytes], dict[str, bytes]]:
        changes = self.collected.files
        binary = {change.path for change in changes if change.binary}
        base = files_at(self.repo, self.collected.merge_base, only=wanted)
        if self.checkout.worktree is None:
            branch = self.checkout.branch
            return base, files_at(self.repo, branch, only=lambda p: wanted(p) and p not in binary)
        gone = [change.path for change in changes]
        gone += [c.old_path for c in changes if c.status == "renamed" and c.old_path]
        present = [
            change.path
            for change in changes
            if change.status != "deleted" and not change.binary and wanted(change.path)
        ]
        return base, new_side(base, self.checkout.worktree, gone, present)


def review_folder(project: str, ref: str) -> Path:
    return data_dir() / "projects" / project / "reviews" / ref


def write_pack(folder: Path, data: dict) -> Path:
    """`pack.json` (600) by a temp file and `os.replace`; folders 700 from `projects` down.

    An earlier `review.md` is deleted: it described the previous pack.
    """
    top = data_dir() / "projects"
    top.parent.mkdir(parents=True, exist_ok=True)
    chain = [top]
    for part in folder.relative_to(top).parts:
        chain.append(chain[-1] / part)
    for each in chain:
        each.mkdir(mode=PRIVATE_FOLDER, exist_ok=True)
        each.chmod(PRIVATE_FOLDER)
    handle, temporary = tempfile.mkstemp(prefix=".pack-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(_json(data) + "\n")
        os.replace(temporary, folder / PACK)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    (folder / REVIEW).unlink(missing_ok=True)
    return folder / PACK


def run_pack(ref: str, repos: list[str], project: str | None) -> int:
    problems = _input_problems(ref, repos, project)
    if problems:
        print(_json(_data(ref, None, None, None, None, [], _Notes(problems=problems))))
        return 1
    try:
        return _run(ref, repos, project)
    except BoardMissing:
        return _fail(f"no [board] table in {config_dir() / 'config.toml'}; add one (see {SPEC})", 2)
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid, TrackerSetup) as error:
        return _fail(error, 2)
    except TrackerError as error:
        return _fail(error, 3)


def _fail(message: object, status: int) -> int:
    print(f"ws review pack: {message}", file=sys.stderr)
    return status


def _json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _input_problems(ref: str, repos: list[str], project: str | None) -> list[str]:
    problems = []
    if not REF.fullmatch(ref):
        problems.append(f"{ref!r} is not a card reference like TS-123")
    problems.extend(
        f"--repo {name!r} is not a repo name" for name in repos if not REPO_NAME.fullmatch(name)
    )
    if project is not None and not SLUG_PATTERN.fullmatch(project):
        problems.append(f"--project {project!r} must be lowercase words joined by hyphens")
    return problems


def _run(ref: str, flag_repos: list[str], flag_project: str | None) -> int:
    """Settings and the card first (exit 2 or 3 write nothing), then each repo, then the pack."""
    board = load_board()
    roots = userconfig.load_standup().repo_roots
    settings = load_settings()
    tracker = port.open_tracker()
    card, card_warnings = card_context(tracker, ref)
    notes = _Notes(warnings=list(card_warnings))
    if card is None:
        notes.problems.append(f"{ref} was not found in the tracker's project")
    root = repo_root()
    title = card["title"] if card else ""
    choice = cardstart.repos_for_card(root, ref, title, flag_repos, board.prefix_repos)
    notes.problems.extend(choice.problems)
    notes.warnings.extend(choice.warnings)
    project = flag_project or _item_project(root, ref, choice, notes)
    repos = [_repo(name, ref, board, roots, settings, notes) for name in choice.names]
    folder = review_folder(project, ref)
    data = _data(ref, card, project, folder, choice.source, repos, notes)
    try:
        write_pack(folder, data)
    except OSError as error:
        return _fail(f"could not write {folder / PACK}: {error}", 2)
    print(_json(data))
    return 1 if notes.problems else 0


def _item_project(root: Path, ref: str, choice: cardstart.RepoChoice, notes: _Notes) -> str:
    """The project of the card's item; with `--repo` the item was not looked up, so look now."""
    item = choice.item
    if item is None and choice.source == "flag":
        try:
            item, found = items.find_card_item(root, ref)
        except ItemError as error:
            notes.problems.append(f"{error}; or pass --project")
            return DEFAULT_PROJECT
        notes.warnings.extend(found)
    return item.path.parent.parent.name if item is not None else DEFAULT_PROJECT


def _data(
    ref: str,
    card: dict | None,
    project: str | None,
    folder: Path | None,
    repos_from: str | None,
    repos: list[dict],
    notes: _Notes,
) -> dict:
    return {
        "ref": ref,
        "card": card,
        "project": project,
        "folder": str(folder) if folder else None,
        "pack_path": str(folder / PACK) if folder else None,
        "review_path": str(folder / REVIEW) if folder else None,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "repos_from": repos_from,
        "repos": repos,
        "flags": notes.flags,
        "problems": notes.problems,
        "warnings": notes.warnings,
    }


def _repo(
    name: str,
    ref: str,
    board: BoardConfig,
    roots: tuple[Path, ...],
    settings: EnvCheckSettings,
    notes: _Notes,
) -> dict:
    """One repo's part of the pack; what cannot be read is a problem for this repo alone."""
    base = board.base_for(name)
    entry = {
        "name": name,
        "path": None,
        "worktree": None,
        "branch": None,
        "base": base,
        "base_ref": f"{board.remote}/{base}",
        "fetched": False,
        "merge_base": None,
        "diff_command": None,
        "commits": [],
        "files": [],
        "by_category": {},
        "migrations": None,
        "env": None,
        "tests": None,
    }
    path = cardstart.locate_repo(name, roots)
    if path is None:
        listed = ", ".join(str(root) for root in roots)
        notes.problems.append(
            f"{name}: not found under {listed}; check the name or [standup] repo_roots"
        )
        return entry
    entry["path"] = str(path)
    try:
        _read(entry, path, ref, board, profile_for(name, path, settings), notes)
    except (ReviewRefused, GitError, SetupError) as error:
        notes.problems.append(f"{name}: {error}")
    return entry


def _read(
    entry: dict, path: Path, ref: str, board: BoardConfig, profile: RepoProfile, notes: _Notes
) -> None:
    name, base_ref = entry["name"], entry["base_ref"]
    try:
        gittools.fetch(path, board.remote)
        entry["fetched"] = True
    except GitError as error:
        notes.warnings.append(f"{name}: fetch failed; using the last fetched {base_ref}: {error}")
    if not gittools.has_ref(path, f"refs/remotes/{base_ref}"):
        notes.problems.append(f'{name}: {base_ref} does not exist; set [board.repos."{name}"] base')
        return
    checkout = find_checkout(path, ref)
    entry["branch"] = checkout.branch
    if checkout.worktree is None:
        notes.warnings.append(
            f"{name}: {checkout.branch} is not checked out in any work tree; only its commits "
            "are read and abs_path is null"
        )
    else:
        entry["worktree"] = str(checkout.worktree)
    collected = collect(path, checkout, base_ref)
    entry["merge_base"] = collected.merge_base
    entry["diff_command"] = diff_command(path, checkout, collected.merge_base)
    entry["commits"] = [{"sha": c.sha, "subject": c.subject} for c in collected.commits]
    overrides = board.review_categories_for(name)
    files = [_file(change, checkout.worktree, overrides) for change in collected.files]
    entry["files"] = files
    entry["by_category"] = _by_category(files)
    entry["tests"] = _tests(files)
    tree = _Tree(path, checkout, collected)
    entry["migrations"] = _migrations(tree, overrides, name, notes)
    entry["env"] = _env(tree, profile, name, notes)
    categories = {change["category"] for change in files}
    if categories and "test" not in categories:
        notes.flags.append(f"{name}: {NO_TESTS}")


def _file(change: FileChange, worktree: Path | None, overrides: dict) -> dict:
    """`abs_path` is the file to open: null when deleted or when no work tree holds the branch."""
    opened = worktree is not None and change.status != "deleted"
    return {
        "path": change.path,
        "old_path": change.old_path,
        "abs_path": str(worktree / change.path) if opened else None,
        "status": change.status,
        "added": change.added,
        "deleted": change.deleted,
        "binary": change.binary,
        "stages": list(change.stages),
        "hunks": list(change.hunks),
        "category": category_for(change.path, overrides),
    }


def _by_category(files: list[dict]) -> dict:
    out = {}
    for category in CATEGORIES:
        chosen = [change for change in files if change["category"] == category]
        if chosen:
            out[category] = {
                "files": len(chosen),
                "added": sum(change["added"] or 0 for change in chosen),
                "deleted": sum(change["deleted"] or 0 for change in chosen),
            }
    return out


def _tests(files: list[dict]) -> dict:
    chosen = [change for change in files if change["category"] == "test"]
    return {
        "added": [change["path"] for change in chosen if change["status"] in CREATED],
        "changed": [change["path"] for change in chosen if change["status"] not in CREATED],
    }


def _texts(files: dict[str, bytes]) -> dict[str, str]:
    return {path: content.decode("utf-8", errors="replace") for path, content in files.items()}


def _migrations(tree: _Tree, overrides: dict, name: str, notes: _Notes) -> dict:
    """Alembic files only: a migration category outside `.py` cannot be parsed for revisions."""

    def wanted(path: str) -> bool:
        return path.endswith(".py") and category_for(path, overrides) == "migration"

    base, new = tree.sides(wanted)
    report, flags, warnings = migration_report(_texts(base), _texts(new))
    notes.flags.extend(f"{name}: {flag}" for flag in flags)
    notes.warnings.extend(f"{name}: {warning}" for warning in warnings)
    return report


def _env(tree: _Tree, profile: RepoProfile, name: str, notes: _Notes) -> dict | None:
    """Env var names over the whole Python tree, only when a `.py` or shell file changed."""

    def wanted(path: str) -> bool:
        return path.endswith(".py") or path in profile.shell_files

    changes = tree.collected.files
    changed = {p for change in changes for p in (change.path, change.old_path) if p and wanted(p)}
    if not changed:
        return None
    base, new = tree.sides(wanted)
    report, flags, warnings = env_report(base, new, profile, changed)
    notes.flags.extend(f"{name}: {flag}" for flag in flags)
    notes.warnings.extend(f"{name}: {warning}" for warning in warnings)
    return report


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "review", help="Review a card's changes before they are committed (read-only on repos)."
    )
    commands = parser.add_subparsers(dest="review_command", required=True)
    pack = commands.add_parser(
        "pack",
        help="Collect the card's review package into pack.json under the data folder and print "
        "it (JSON; git only fetches and reads; never writes to the tracker).",
    )
    pack.add_argument("ref", help="The card, like TS-123.")
    pack.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="NAME",
        help="A repo of the task (repeatable); replaces the item's repos and the title prefix.",
    )
    pack.add_argument(
        "--project",
        metavar="SLUG",
        help=f"Project folder of the pack; default: the item's project, else {DEFAULT_PROJECT}.",
    )
    pack.set_defaults(handler=lambda args: run_pack(args.ref, args.repo, args.project))
