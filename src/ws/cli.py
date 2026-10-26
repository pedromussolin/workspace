"""Entry point of the ws command. Each subcommand sets a handler that returns the exit code."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from ws import (
    bootstrap,
    config,
    dictionary,
    gittools,
    names,
    newwords,
    project,
    review,
    secrets,
    slot,
)
from ws.config import claude_skills_dir, config_dir, repo_root


def _add_setup(subparsers) -> None:
    parser = subparsers.add_parser(
        "setup",
        help="Wire this clone and fix what can be fixed: hooks, skill links and private config.",
        description=(
            "Fixes by itself the git hooks path and the executable bit of the hooks, the skill "
            "links and the modes of the private config. Prints a `fixed:` line per change and a "
            "`needs you:` line per "
            "problem left, among them the Claude Code gates as one JSON block that Claude "
            "applies after you approve; ws never writes ~/.claude/settings.json. Exits 0 when "
            "nothing is left."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="read-only, no network: change nothing, list what setup would fix (`would fix:`) "
        "and what needs you; exit 1 unless everything is already in place",
    )
    parser.set_defaults(handler=_cmd_setup)


def _cmd_setup(args: argparse.Namespace) -> int:
    result = bootstrap.run_setup(repo_root(), config_dir(), claude_skills_dir(), check=args.check)
    label = "would fix" if args.check else "fixed"
    for line in result.fixed:
        print(f"{label}: {line}")
    for need in result.needs:
        print(f"needs you: {need}")
    if result.needs or (args.check and result.fixed):
        return 1
    print("ok")
    return 0


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
        help="JSON object mapping old commit subjects, or shas (full or abbreviated), to new ones.",
    )
    assemble.set_defaults(handler=_cmd_git_assemble)

    rehearsal = git_commands.add_parser(
        "merge-rehearsal",
        help="Merge branches over a base in a throwaway worktree.",
        description=(
            "Merge the branches over the base in a throwaway worktree, apply known conflict "
            "resolutions and run a check. The worktree is a fresh checkout with no dependencies "
            "installed (no node_modules, no virtualenv): the check must install what it needs."
        ),
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
        help=(
            "Directory with executable <branch, / as _>.sh conflict resolution scripts; "
            "each must stage what it resolves and exit 0."
        ),
    )
    rehearsal.add_argument(
        "--check",
        help="Shell command to run in the worktree after the merges; nothing is installed there.",
    )
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
    except gittools.EmptyCherryPick as exc:
        print(
            f"Cherry-picking {exc.sha} gave an empty commit: it is already in the base.",
            file=sys.stderr,
        )
        print(
            "Run `git cherry-pick --skip` to drop it (then pick the remaining commits by hand), "
            "or `git cherry-pick --abort`.",
            file=sys.stderr,
        )
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


def _add_names(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "names",
        help="New-word check and the names table.",
        description=(
            "A new word is a capitalized word of three letters or more, in an added line or a "
            "commit message, that is not in the pushed state, in .known-words or among the "
            "analogs of names.toml. Run these commands inside the repo."
        ),
    )
    commands = parser.add_subparsers(dest="names_command", required=True)

    check = commands.add_parser(
        "check",
        help="List the new words of staged lines, a message file or a range (the hooks run it).",
    )
    mode = check.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="added lines of the staged diff")
    mode.add_argument(
        "--message", type=Path, metavar="FILE", help="a commit message file, as commit-msg gets it"
    )
    mode.add_argument(
        "--range",
        metavar="REVS",
        help="each commit of a rev-list expression (words split on spaces): lines and message",
    )
    check.add_argument(
        "--against",
        metavar="REV",
        help=(
            "revision whose text is the vocabulary; empty means nothing is pushed "
            "(default: the upstream, else origin/main, else nothing)"
        ),
    )
    check.add_argument(
        "--tip",
        default="HEAD",
        metavar="REV",
        help="commit whose .known-words counts, for --range (default: HEAD)",
    )
    check.add_argument(
        "--warn",
        action="store_true",
        help="only print: exit 0 even when there are new words or the check fails",
    )
    check.set_defaults(handler=_cmd_names_check)

    pending = commands.add_parser(
        "pending", help="List the new words of the unpushed commits, with where each appears."
    )
    _add_scope_args(pending)
    pending.add_argument("--json", action="store_true", help="print a JSON list")
    pending.set_defaults(handler=_cmd_names_pending)

    known = commands.add_parser("known", help="Add harmless words to .known-words.")
    known.add_argument("words", nargs="+", metavar="WORD")
    known.set_defaults(handler=_cmd_names_known)

    add = commands.add_parser("add", help="Add a real name and its analog to names.toml.")
    add.add_argument("real", metavar="REAL")
    add.add_argument("--analog", required=True, help="the fictitious name that replaces it")
    add.add_argument(
        "--case-sensitive",
        action="store_true",
        help="match only this spelling (and all caps), for a name that is also a common word",
    )
    add.set_defaults(handler=_cmd_names_add)

    review_parser = commands.add_parser(
        "review", help="Answer the pending new words one by one in the terminal."
    )
    _add_scope_args(review_parser)
    review_parser.set_defaults(handler=_cmd_names_review)


def _add_scope_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--range",
        metavar="REVS",
        help="commits to read (default: @{upstream}..HEAD, else origin/main..HEAD)",
    )
    parser.add_argument(
        "--against", metavar="REV", help="revision whose text is the vocabulary (default: the base)"
    )


def _names_scope(args: argparse.Namespace, repo: Path) -> tuple[list[str], str | None]:
    revs, base = newwords.default_scope(repo)
    if args.range is not None:
        revs = args.range.split()
    if args.against is not None:
        base = args.against or None
    return revs, base


def _print_new_words(words: list[newwords.NewWord], blocking: bool, stream) -> None:
    for line in newwords.format_report(words, blocking, dictionary.missing()):
        print(line, file=stream)


def _note_missing_dictionaries(words: list[newwords.NewWord]) -> None:
    """Tell, on stderr, that the list is longer than it needs to be; stdout stays the list."""
    missing = dictionary.missing()
    if words and missing:
        print(newwords.missing_dictionaries_note(missing), file=sys.stderr)


def _run_names_check(args: argparse.Namespace) -> int:
    table = names.load_names()
    repo = secrets.repo_toplevel(Path.cwd())
    against = newwords.resolve_base(repo) if args.against is None else args.against or None
    if args.staged:
        words = newwords.check_staged(repo, table, against)
    elif args.message:
        text = args.message.read_bytes().decode("utf-8", errors="replace")
        words = newwords.check_message(repo, text, table, against)
    else:
        words = newwords.check_range(repo, args.range.split(), table, against, args.tip)
    if words:
        _print_new_words(
            words, blocking=not args.warn, stream=sys.stderr if args.warn else sys.stdout
        )
    return 1 if words and not args.warn else 0


def _cmd_names_check(args: argparse.Namespace) -> int:
    try:
        return _run_names_check(args)
    except Exception as error:
        # The pre-push hook blocks on any non-zero exit; the commit hooks only warn.
        if args.warn:
            print(f"new-word warning failed ({error}); not blocking", file=sys.stderr)
            return 0
        print(f"names check failed ({error}); blocking", file=sys.stderr)
        return 1


def _pending(args: argparse.Namespace, repo: Path) -> tuple[list[newwords.NewWord], list[str]]:
    table = names.load_names()
    revs, base = _names_scope(args, repo)
    return newwords.check_range(repo, revs, table, base), revs


def _cmd_names_pending(args: argparse.Namespace) -> int:
    try:
        repo = secrets.repo_toplevel(Path.cwd())
        words, _ = _pending(args, repo)
    except (names.NamesTableMissing, RuntimeError, ValueError) as error:
        print(f"ws names pending: {error}", file=sys.stderr)
        return 2
    if args.json:
        listing = [
            {
                "word": item.word,
                "places": [
                    {"commit": place.commit, "path": place.path, "line": place.line}
                    for place in item.places
                ],
            }
            for item in words
        ]
        print(json.dumps(listing, ensure_ascii=False, indent=2))
        return 0
    for item in words:
        print(f"{item.word}: {newwords.format_places(item)}")
    _note_missing_dictionaries(words)
    return 0


def _cmd_names_known(args: argparse.Namespace) -> int:
    try:
        repo = secrets.repo_toplevel(Path.cwd())
        added, skipped = newwords.add_known_words(repo, args.words)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"ws names known: {error}", file=sys.stderr)
        return 2
    if added:
        print(f"added to {newwords.KNOWN_WORDS_FILE}: {', '.join(added)} (commit the file)")
    if skipped:
        print(f"already listed: {', '.join(skipped)}")
    return 0


def _cmd_names_add(args: argparse.Namespace) -> int:
    path = config_dir() / "names.toml"
    try:
        names.add_name(path, args.real, args.analog, args.case_sensitive)
    except (names.NamesTableMissing, ValueError, OSError) as error:
        print(f"ws names add: {error}", file=sys.stderr)
        return 2
    print(f"added {args.real.strip()} with analog {args.analog.strip()} to {path}")
    return 0


def _cmd_names_review(args: argparse.Namespace) -> int:
    try:
        repo = secrets.repo_toplevel(Path.cwd())
        words, revs = _pending(args, repo)
        _note_missing_dictionaries(words)
        return review.run_review(repo, words, revs)
    except (names.NamesTableMissing, RuntimeError, ValueError, OSError) as error:
        print(f"ws names review: {error}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ws", description="Personal workspace tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_setup(subparsers)
    _add_project(subparsers)
    _add_slot(subparsers)
    _add_git(subparsers)
    _add_mask(subparsers)
    _add_check_secrets(subparsers)
    _add_names(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)
