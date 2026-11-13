"""Command line of the one-off items conversion: a dry run by default, `--apply` to write."""

import argparse
import shutil
import sys
from pathlib import Path

from .apply import ApplyError, Runner, SubprocessRunner, apply, precheck
from .maprows import PROJECT_DIR, load_people, load_rows
from .plan import NEW_PROJECT, OLD_PROJECT, PlanError, build_plan, render_plan

DEFAULT_MAP = Path.home() / ".local/share/workspace/projects/workspace/board-map"
REPO = Path(__file__).resolve().parents[2]


def outside_moves() -> list[tuple[Path, Path]]:
    home = Path.home()
    private = home / ".config/workspace/private"
    data = home / ".local/share/workspace/projects"
    return [
        (private / f"{OLD_PROJECT}.md", private / f"{NEW_PROJECT}.md"),
        (data / OLD_PROJECT, data / NEW_PROJECT),
    ]


def load_docs(path: Path) -> list[tuple[str, str, str]]:
    if not path.is_file():
        return []
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = line.split("\t")
        if len(cells) >= 3 and cells[0] != "project" and not line.startswith("#"):
            found.append((cells[0].strip(), cells[1].strip(), cells[2].strip()))
    return found


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adopt-items.py",
        description="Converts projects/ into items. A dry run unless --apply is given.",
    )
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP, help="board map folder")
    parser.add_argument("--people", type=Path, help="people file (default: <map>/people.toml)")
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--apply", action="store_true", help="perform the plan")
    parser.add_argument(
        "--outside", action="store_true", help="with --apply, also run the moves outside the repo"
    )
    return parser


def _outside(run: bool, say) -> None:
    for src, dst in outside_moves():
        say(f"outside: mv {src} {dst}")
        if not run:
            continue
        if not src.exists():
            say(f"  skipped: {src} does not exist")
        elif dst.exists():
            say(f"  skipped: {dst} already exists")
        else:
            shutil.move(src, dst)


def _toml_problems(rows, repo: Path) -> list[str]:
    names = {PROJECT_DIR.get(r.project, r.project) for r in rows if r.project != "epico"}
    if OLD_PROJECT in names:
        names.add(NEW_PROJECT)
    return [
        f"projects/{n}/project.toml already exists"
        for n in sorted(names)
        if (repo / "projects" / n / "project.toml").exists()
    ]


def main(argv: list[str] | None = None, runner: Runner | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = args.repo.resolve()
    runner = runner or SubprocessRunner(repo)
    say = print
    try:
        rows = load_rows(args.map)
        people = load_people(args.people or args.map / "people.toml")
    except (OSError, ValueError) as error:
        say(f"cannot read the map: {error}")
        return 1
    docs = load_docs(args.map / "docs.tsv")
    try:
        plan = build_plan(rows, repo, people, docs)
    except PlanError as error:
        for problem in [*error.problems, *_toml_problems(rows, repo)]:
            say(f"problem: {problem}")
        return 1
    if not args.apply:
        sys.stdout.write(render_plan(plan))
        warnings: list[str] = []
        problems = precheck(plan, repo, runner, warnings)
        for warning in warnings:
            say(f"warn: {warning}")
        for problem in problems:
            say(f"problem: {problem}")
        _outside(False, say)
        return 1 if problems else 0
    try:
        apply(plan, repo, runner, args.map)
    except ApplyError as error:
        say(f"stopped: {error}")
        return 1
    _outside(args.outside, say)
    return 0
