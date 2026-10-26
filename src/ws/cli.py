"""Entry point of the ws command. Each subcommand sets a handler that returns the exit code."""

import argparse
import sys
from datetime import date
from pathlib import Path

from ws import bootstrap, config, gittools, names, project, secrets, slot
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


def _add_project(subparsers) -> None:
    parser = subparsers.add_parser("project", help="Planning project commands.")
    commands = parser.add_subparsers(dest="project_command", required=True)
    new = commands.add_parser("new", help="Create projetos/<slug> from the project template.")
    new.add_argument("slug", help="lowercase letters and digits separated by hyphens")
    new.set_defaults(handler=_cmd_project_new)


def _cmd_project_new(args) -> int:
    try:
        created = project.new_project(args.slug, repo_root(), date.today())
    except (ValueError, FileExistsError) as error:
        print(error, file=sys.stderr)
        return 1
    print(created)
    return 0


def _slots_arg(text: str) -> int:
    try:
        return slot.parse_slots(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _add_slot(subparsers) -> None:
    parser = subparsers.add_parser(
        "slot",
        help="Run a heavy command in one of N slots.",
        description=(
            "Wait for a free slot (a file lock), run the command, release the slot. The command "
            "inherits the lock, so the slot stays taken until it exits even if ws is killed; "
            "SIGTERM, SIGHUP and SIGINT are forwarded to it."
        ),
        usage="ws slot [-h] [-n N] -- CMD [ARG ...]",
    )
    parser.add_argument(
        "-n",
        "--slots",
        type=_slots_arg,
        metavar="N",
        help="number of slots (default: $WS_SLOTS, else 2)",
    )
    parser.add_argument("cmd", nargs="+", metavar="CMD", help="command to run, after --")
    parser.set_defaults(handler=_cmd_slot)


def _cmd_slot(args: argparse.Namespace) -> int:
    try:
        slots = args.slots if args.slots is not None else slot.default_slots()
    except ValueError as exc:
        print(f"ws slot: {exc}", file=sys.stderr)
        return 2
    return slot.run_in_slot(args.cmd, slots, slot.default_lock_dir())


def _add_git(subparsers) -> None:
    git = subparsers.add_parser("git", help="Git helpers for assembling branches.")
    git_commands = git.add_subparsers(dest="git_command", required=True)

    assemble = git_commands.add_parser(
        "assemble", help="Cherry-pick a work-in-progress branch over a base into a clean branch."
    )
    assemble.add_argument("--repo", help="Repository path (default: current git top level).")
    assemble.add_argument("--base", required=True, help="Base the final branch starts from.")
    assemble.add_argument(
        "--from", dest="source", required=True, metavar="WIP", help="Branch to cherry-pick."
    )
    assemble.add_argument(
        "--to", dest="target", required=True, metavar="FINAL", help="Branch to create."
    )
    assemble.add_argument(
        "--subjects",
        type=Path,
        metavar="FILE.json",
        help="JSON object mapping old commit subjects to new ones.",
    )
    assemble.set_defaults(handler=_cmd_git_assemble)

    rehearsal = git_commands.add_parser(
        "merge-rehearsal", help="Merge branches over a base in a throwaway worktree."
    )
    rehearsal.add_argument("--repo", help="Repository path (default: current git top level).")
    rehearsal.add_argument("--base", required=True, help="Base the merges start from.")
    rehearsal.add_argument(
        "--worktree",
        type=Path,
        help="Worktree to use (default: <cache>/merge-rehearsal/<repo name>).",
    )
    rehearsal.add_argument(
        "--resolutions",
        type=Path,
        help="Directory with executable <branch, / as _>.sh conflict resolution scripts.",
    )
    rehearsal.add_argument("--check", help="Command to run in the worktree after the merges.")
    rehearsal.add_argument("branches", nargs="+", metavar="BRANCH", help="Branches to merge.")
    rehearsal.set_defaults(handler=_cmd_git_merge_rehearsal)


def _repo_arg(args: argparse.Namespace) -> Path:
    if args.repo:
        return Path(args.repo).resolve()
    return gittools.toplevel(Path.cwd())


def _cmd_git_assemble(args: argparse.Namespace) -> int:
    try:
        repo = _repo_arg(args)
        subjects = gittools.load_subjects(args.subjects) if args.subjects else {}
        final_subjects = gittools.assemble(repo, args.base, args.source, args.target, subjects)
    except gittools.SubjectTooLong as exc:
        limit = gittools.MAX_SUBJECT_LENGTH
        print(f"Subjects longer than {limit} characters; nothing was changed:", file=sys.stderr)
        for subject in exc.subjects:
            print(f"  ({len(subject)}) {subject}", file=sys.stderr)
        return 1
    except gittools.CherryPickConflict as exc:
        files = ", ".join(gittools.conflicted_files(repo))
        print(f"Conflict while cherry-picking {exc.sha}.", file=sys.stderr)
        print(f"Conflicted files: {files}", file=sys.stderr)
        print(
            "Resolve it and run `git cherry-pick --continue`, or `git cherry-pick --abort`.",
            file=sys.stderr,
        )
        return 1
    except (gittools.GitError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print("\n".join(final_subjects))
    return 0


def _cmd_git_merge_rehearsal(args: argparse.Namespace) -> int:
    try:
        repo = _repo_arg(args)
        worktree = args.worktree or config.cache_dir() / "merge-rehearsal" / repo.name
        return gittools.merge_rehearsal(
            repo, args.base, args.branches, worktree, args.resolutions, args.check
        )
    except (gittools.GitError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _add_mask(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("mask", help="Replace real names with their analogs.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--in-place", action="store_true", help="rewrite FILE instead of printing")
    mode.add_argument(
        "--check", action="store_true", help="list the real names found; exit 1 if there are any"
    )
    parser.add_argument(
        "file", nargs="?", default="-", metavar="FILE", help="file to read, or - for stdin"
    )
    parser.set_defaults(handler=_cmd_mask)


def _read_input(file: str) -> str:
    if file == "-":
        return sys.stdin.read()
    return Path(file).read_bytes().decode("utf-8")


def _cmd_mask(args: argparse.Namespace) -> int:
    if args.in_place and args.file == "-":
        print("ws mask: --in-place needs a file", file=sys.stderr)
        return 2
    try:
        table = names.load_names()
    except names.NamesTableMissing as error:
        print(error, file=sys.stderr)
        return 2
    try:
        text = _read_input(args.file)
    except (OSError, UnicodeDecodeError) as error:
        print(f"ws mask: cannot read {args.file}: {error}", file=sys.stderr)
        return 2
    if args.check:
        found = names.find_real_names(text, table)
        for name in found:
            print(f"{args.file}: {name}")
        return 1 if found else 0
    masked = names.mask_text(text, table)
    if not args.in_place:
        sys.stdout.write(masked)
    elif masked != text:
        Path(args.file).write_bytes(masked.encode("utf-8"))
    return 0


def _add_check_secrets(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    parser = subparsers.add_parser(
        "check-secrets", help="Look for secrets, real names and company domains."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--staged", action="store_true", help="added lines of the staged diff (default)"
    )
    mode.add_argument("--all", action="store_true", help="every file in the index")
    mode.add_argument(
        "--message",
        type=Path,
        metavar="FILE",
        help="a commit message file, as the commit-msg hook gets it",
    )
    mode.add_argument(
        "--range",
        metavar="REVS",
        help=(
            "each non-merge commit of a rev-list expression (words split on spaces, "
            "e.g. 'origin/main..HEAD'): added lines, message and e-mails"
        ),
    )
    parser.add_argument("paths", nargs="*", type=Path, metavar="PATH", help="files to check")
    parser.set_defaults(handler=_cmd_check_secrets)


def _check_with_mode(
    args: argparse.Namespace, repo: Path, table: names.NamesTable
) -> list[secrets.Finding]:
    if args.message:
        text = args.message.read_bytes().decode("utf-8", errors="replace")
        return secrets.check_message(repo, text, table)
    if args.range is not None:
        return secrets.check_range(repo, args.range.split(), table)
    mode = "paths" if args.paths else "all" if args.all else "staged"
    return secrets.check_repo(repo, mode, table, args.paths)


def _run_check_secrets(args: argparse.Namespace) -> int:
    if args.paths and (args.staged or args.all or args.message or args.range is not None):
        print(
            "ws check-secrets: use either --staged, --all, --message, --range or PATH arguments",
            file=sys.stderr,
        )
        return 2
    try:
        table = names.load_names()
    except names.NamesTableMissing as error:
        print(f"{error}; the check fails closed", file=sys.stderr)
        return 2
    repo = secrets.repo_toplevel(Path.cwd())
    findings = _check_with_mode(args, repo, table)
    for finding in findings:
        where = f"{finding.commit[:10]}:" if finding.commit else ""
        matched = " ".join(finding.match.split())
        print(f"{where}{finding.path}:{finding.line}: {finding.rule}: {matched}")
    if findings:
        print(f"{len(findings)} finding(s): fix them or add a reviewed line to .secrets-allow")
    return 1 if findings else 0


def _cmd_check_secrets(args: argparse.Namespace) -> int:
    # The git hook blocks on any non-zero exit, so an internal error must not become exit 0.
    try:
        return _run_check_secrets(args)
    except Exception as error:
        print(f"check-secrets failed ({error}); blocking", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ws", description="Personal workspace tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_setup(subparsers)
    _add_project(subparsers)
    _add_slot(subparsers)
    _add_git(subparsers)
    _add_mask(subparsers)
    _add_check_secrets(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)
