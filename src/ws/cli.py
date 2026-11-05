"""Entry point of the ws command. Each subcommand sets a handler that returns the exit code."""

import argparse
import getpass
import json
import os
import sys
from datetime import date
from pathlib import Path

from ws import (
    board_cli,
    bootstrap,
    card,
    checkpoint,
    config,
    deploycheck_cli,
    dictionary,
    envcheck_cli,
    gatecatalog,
    gittools,
    handoff_cli,
    jira,
    names,
    newwords,
    project,
    review,
    secrets,
    slot,
    standup,
    standupreport,
    taskmodel,
    taskstatus,
    userconfig,
    workdays,
)
from ws.config import claude_skills_dir, config_dir, repo_root


def _add_setup(subparsers) -> None:
    parser = subparsers.add_parser(
        "setup",
        help="Wire this clone and fix what can be fixed: hooks, skill links, config, dictionaries.",
        description=(
            "Fixes by itself the git hooks path and the executable bit of the hooks, the skill "
            "links, the modes of the private config and the common-word dictionaries (downloaded "
            "without root). Prints a `fixed:` line per change and a `needs you:` line per "
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
    new = commands.add_parser("new", help="Create projects/<slug> from the project template.")
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


def _add_config(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("config", help="Local config of ws.")
    commands = parser.add_subparsers(dest="config_command", required=True)
    stored = commands.add_parser("token", help="Store a service credential, typed hidden.")
    services = stored.add_subparsers(dest="service", required=True)
    for service, label in userconfig.TOKEN_SERVICES.items():
        command = services.add_parser(
            service,
            help=f"Read the {label} token from the terminal (hidden) and store it with mode 600.",
        )
        command.set_defaults(handler=_cmd_config_token)


def _cmd_config_token(args: argparse.Namespace) -> int:
    service = args.service
    label = userconfig.TOKEN_SERVICES[service]
    if not sys.stdin.isatty():
        print(f"run this in your own terminal: ws config token {service}", file=sys.stderr)
        return 2
    typed = getpass.getpass(f"{label} API key (hidden): ").strip()
    if not typed:
        print(f"ws config token {service}: empty token, nothing saved", file=sys.stderr)
        return 2
    try:
        path = userconfig.save_token(service, typed)
    except (userconfig.ConfigInvalid, OSError) as error:
        print(f"ws config token {service}: {error}", file=sys.stderr)
        return 2
    print(f"saved the {label} token in {path}")
    return 0


def _add_mcp_headers(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "mcp-headers",
        help="Print the HTTP headers of an MCP server (Claude Code's headersHelper).",
        description=(
            "Meant for Claude Code's headersHelper: prints the headers of the MCP server as one "
            "JSON object, with the token read from ~/.config/workspace/credentials, so the token "
            "never sits in the session environment. It refuses to run outside Claude Code "
            "(CLAUDE_CODE_MCP_SERVER_NAME unset), which only guards against casual use: the "
            "approval gate asks before any command that names `ws mcp-headers`."
        ),
    )
    parser.add_argument("server", choices=["github"], help="the MCP server")
    parser.set_defaults(handler=_cmd_mcp_headers)


def _cmd_mcp_headers(args: argparse.Namespace) -> int:
    if not os.environ.get("CLAUDE_CODE_MCP_SERVER_NAME"):
        print("ws mcp-headers is meant for Claude Code's headersHelper", file=sys.stderr)
        return 2
    try:
        bearer = userconfig.load_token(args.server)
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid) as error:
        print(f"ws mcp-headers {args.server}: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"Authorization": f"Bearer {bearer}"}))
    return 0


def _add_gate(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("gate", help="The Claude Code approval gate.")
    commands = parser.add_subparsers(dest="gate_command", required=True)
    catalog = commands.add_parser(
        "catalog",
        help="Show or classify the MCP tools the approval gate does not know.",
        description=(
            "Without a subcommand: lists the MCP servers configured in Claude Code that the "
            "catalog (hooks/gate/catalog.json) does not know, and the tools the gate asked "
            "about without finding them in it, with counts. `pass` and `ask` classify tools: "
            "they edit the catalog in this repo, nothing else."
        ),
    )
    catalog.add_argument("--json", action="store_true", help="print the report as JSON")
    catalog.set_defaults(handler=_cmd_gate_catalog)
    actions = catalog.add_subparsers(dest="catalog_command")
    for name, meaning in (("pass", "reads, never write outside the machine"), ("ask", "writes")):
        action = actions.add_parser(name, help=f"Classify tools as {meaning}.")
        action.add_argument("server", help="the tool-name prefix: mcp__<server>__<tool>")
        action.add_argument("tools", nargs="+", metavar="TOOL")
        action.set_defaults(handler=_cmd_gate_classify, target=name)


def _cmd_gate_catalog(args: argparse.Namespace) -> int:
    try:
        found = gatecatalog.report()
    except gatecatalog.CatalogError as error:
        print(f"ws gate catalog: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(found, indent=2, sort_keys=True))
        return 0
    missing, recorded = found["missing_servers"], found["unclassified"]
    if not missing and not recorded:
        print("Nothing to classify: the catalog knows every configured server and recorded tool.")
        return 0
    if missing:
        print("MCP servers configured and missing from the catalog (every call asks):")
        for server in missing:
            print(f"  {server}")
    if recorded:
        print("Tools the gate asked about and the catalog does not classify:")
        for server, tools in sorted(recorded.items()):
            print(f"  {server}")
            for tool, entry in sorted(tools.items()):
                print(f"    {tool}  ({entry['count']} asks, last {entry['last']})")
    print(
        "Next: ws gate catalog pass SERVER TOOL... for reads, "
        "ws gate catalog ask SERVER TOOL... for writes."
    )
    return 0


def _cmd_gate_classify(args: argparse.Namespace) -> int:
    try:
        change = gatecatalog.classify(args.server, args.tools, args.target)
    except gatecatalog.CatalogError as error:
        print(f"ws gate catalog {args.target}: {error}", file=sys.stderr)
        return 1
    where = f"{args.server}: {args.target}"
    if change.added:
        print(f"added to {where}: {', '.join(change.added)}")
    if change.already:
        print(f"already in {where}: {', '.join(change.already)}")
    if change.moved:
        other = "ask" if args.target == "pass" else "pass"
        print(f"removed from {args.server}: {other}: {', '.join(change.moved)}")
    if change.forgotten:
        print(f"removed from the unclassified record: {', '.join(change.forgotten)}")
    print("commit the file and run ws setup in your terminal to update the protected copy.")
    return 0


def _iso_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a date; use YYYY-MM-DD") from None


def _add_task(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="Tasks from the tracker.")
    commands = parser.add_subparsers(dest="task_command", required=True)
    listing = commands.add_parser(
        "list",
        help="Print my Jira tasks as compact cards (JSON), read through the REST API.",
    )
    listing.add_argument(
        "--since",
        type=_iso_date,
        metavar="YYYY-MM-DD",
        help="Include tasks finished since this day (default: the previous workday).",
    )
    listing.set_defaults(handler=_cmd_task_list)
    status = commands.add_parser(
        "status",
        help="List the Jira cards and which ones are stuck, from the collected activity (JSON).",
    )
    status.add_argument("--cards", type=Path, required=True, help="Output of `ws task list`.")
    status.add_argument(
        "--activity", type=Path, required=True, help="Output of `ws standup collect`."
    )
    status.add_argument(
        "--today",
        type=_iso_date,
        metavar="YYYY-MM-DD",
        help="Reference day (default: today).",
    )
    status.set_defaults(handler=_cmd_task_status)


def _cmd_task_list(args: argparse.Namespace) -> int:
    since = args.since or workdays.previous_workday(date.today())
    try:
        settings = userconfig.load_config().jira
        client = jira.JiraClient(settings.site, settings.email, userconfig.load_jira_token())
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid, jira.SiteRefused) as error:
        print(f"ws task list: {error}", file=sys.stderr)
        return 2
    try:
        account_id = client.myself()["accountId"]
        issues = client.search(jira.my_tasks_jql(since), jira.FIELDS)
        cards = [jira.card_from_issue(issue, account_id) for issue in issues]
    except (jira.JiraError, KeyError, ValueError) as error:
        print(f"ws task list: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"platform": "jira", "cards": cards}, ensure_ascii=False, indent=2))
    return 0


def _cmd_task_status(args: argparse.Namespace) -> int:
    try:
        config = userconfig.load_config()
        cards = json.loads(args.cards.read_text(encoding="utf-8"))["cards"]
        activity = json.loads(args.activity.read_text(encoding="utf-8"))
        tasks = [
            jira.task_from_card(card, config.jira.site, config.jira.status_overrides)
            for card in cards
        ]
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid) as error:
        print(f"ws task status: {error}", file=sys.stderr)
        return 2
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"ws task status: invalid input: {error}", file=sys.stderr)
        return 2
    result = taskstatus.evaluate(
        tasks, activity, args.today or date.today(), config.standup.stale_workdays
    )
    payload = {"tasks": [taskmodel.task_to_json(task) for task in tasks], **result}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _add_card(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "card", help="Create and update my Jira cards from drafts, with a preview and approval."
    )
    commands = parser.add_subparsers(dest="card_command", required=True)
    check = commands.add_parser("check", help="Check one draft against Jira and print the verdict.")
    check.add_argument("draft", help="Path of the draft file.")
    check.set_defaults(handler=lambda args: card.run_check(args.draft))
    epics = commands.add_parser("epics", help="List the open epics of my open cards (JSON).")
    epics.set_defaults(handler=lambda args: card.run_epics())
    preview = commands.add_parser(
        "preview",
        help="Check a draft or a folder of drafts, print the preview and the approval code.",
    )
    preview.add_argument("path", help="A draft file or a folder of drafts.")
    preview.set_defaults(handler=lambda args: card.run_preview(args.path))
    apply = commands.add_parser(
        "apply",
        allow_abbrev=False,
        help="Send what the preview with CODE showed (the approval; Claude Code asks first).",
    )
    apply.add_argument("path", help="The same draft file or folder that was previewed.")
    apply.add_argument("--approve", metavar="CODE", help="The code `ws card preview` printed.")
    apply.set_defaults(handler=lambda args: card.run_apply(args.path, args.approve))


def _add_standup(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("standup", help="Daily standup helpers.")
    commands = parser.add_subparsers(dest="standup_command", required=True)
    collected = commands.add_parser(
        "collect",
        help="Print the activity of the window as JSON: commits, branches, PRs, next steps.",
        description=(
            "Read-only. Looks at the git repos under the standup repo_roots (the author is each "
            "repo's own git user.email), at your open and recent PRs through `gh`, and at the "
            "next step of every projects/*/CONTINUE.md. Problems that leave data out are listed "
            "under `warnings`."
        ),
    )
    collected.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help="day to run the standup for (default: today)",
    )
    collected.set_defaults(handler=_cmd_standup_collect)
    report = commands.add_parser(
        "report",
        help="Group the activity by task: yesterday, today, blockers.",
        description=(
            "Turns the output of `ws standup collect` into JSON grouped by task. With --cards "
            "(the output of `ws task list`) it adds titles, statuses and blockers, and needs "
            "config.toml; without it the report comes from the activity alone. Status suggestions "
            "and `moves` come only from --board (the output of `ws board status`)."
        ),
    )
    report.add_argument("--activity", type=Path, required=True, help="output of standup collect")
    report.add_argument("--cards", type=Path, default=None, help="cards file; absent: no Jira")
    report.add_argument(
        "--board",
        type=Path,
        default=None,
        help="output of `ws board status`: status moves and cards to confirm come from it",
    )
    report.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help="day to run the standup for (default: today)",
    )
    report.add_argument(
        "--top",
        type=_positive_int,
        default=None,
        metavar="N",
        help="keep only the first N entries of yesterday and today (default: all)",
    )
    report.set_defaults(handler=_cmd_standup_report)


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _cmd_standup_collect(args: argparse.Namespace) -> int:
    missing = None
    try:
        cfg = userconfig.load_config().standup
    except userconfig.ConfigMissing as error:
        cfg = userconfig.StandupConfig(repo_roots=(Path.home() / "repos",))
        missing = (
            f"{error.path} is missing: using the defaults (repo_roots {Path.home() / 'repos'})"
        )
    except userconfig.ConfigInvalid as error:
        print(f"ws standup collect: {error}", file=sys.stderr)
        return 2
    try:
        result = standup.collect(cfg, args.today or date.today(), repo_root())
    except (RuntimeError, OSError) as error:
        print(f"ws standup collect: {error}", file=sys.stderr)
        return 1
    if missing:
        result["warnings"].insert(0, missing)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


def _cmd_standup_report(args: argparse.Namespace) -> int:
    stale_workdays = userconfig.DEFAULT_STALE_WORKDAYS
    try:
        tasks = None
        if args.cards is not None:
            config = userconfig.load_config()
            stale_workdays = config.standup.stale_workdays
        activity = json.loads(args.activity.read_text(encoding="utf-8"))
        if args.cards is not None:
            cards = json.loads(args.cards.read_text(encoding="utf-8"))["cards"]
            tasks = [
                jira.task_from_card(card, config.jira.site, config.jira.status_overrides)
                for card in cards
            ]
        board = None
        if args.board is not None:
            raw = json.loads(args.board.read_text(encoding="utf-8"))
            board = {name: raw[name] for name in ("moves", "to_confirm", "warnings")}
        result = standupreport.build_report(
            activity, tasks, args.today or date.today(), stale_workdays, args.top, board
        )
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid) as error:
        print(f"ws standup report: {error}", file=sys.stderr)
        return 2
    except KeyError as error:
        print(f"ws standup report: invalid input: missing key {error}", file=sys.stderr)
        return 2
    except (OSError, AttributeError, TypeError, ValueError) as error:
        print(f"ws standup report: invalid input: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


def _add_checkpoint(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("checkpoint", help="Validate and publish a project folder.")
    commands = parser.add_subparsers(dest="checkpoint_command", required=True)
    verdict = commands.add_parser(
        "check",
        help="JSON verdict on CONTINUE.md and decisions.md; exit 0 when ok, 1 otherwise.",
    )
    verdict.add_argument("slug")
    verdict.set_defaults(handler=_cmd_checkpoint_check)
    changes = commands.add_parser(
        "diff", help="What a commit would take: files, diffstat and refused large files."
    )
    changes.add_argument("slug")
    changes.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="PATH",
        help="accept a new large or binary file (repeatable)",
    )
    changes.set_defaults(handler=_cmd_checkpoint_diff)
    publish = commands.add_parser(
        "commit",
        help="Check, commit only the project, pull --rebase, check again and push to main.",
    )
    publish.add_argument("slug")
    publish.add_argument("-m", "--message", required=True)
    publish.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="PATH",
        help="accept a new large or binary file (repeatable)",
    )
    publish.add_argument(
        "--amend",
        action="store_true",
        help="rewrite the single unpushed checkpoint commit instead of adding one",
    )
    publish.set_defaults(handler=_cmd_checkpoint_commit)


def _run_checkpoint(name: str, action) -> int:
    try:
        result = action()
    except (checkpoint.CheckpointError, RuntimeError, OSError) as error:
        print(f"ws checkpoint {name}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", True) else 1


def _cmd_checkpoint_check(args: argparse.Namespace) -> int:
    return _run_checkpoint("check", lambda: checkpoint.check(args.slug))


def _cmd_checkpoint_diff(args: argparse.Namespace) -> int:
    return _run_checkpoint("diff", lambda: checkpoint.diff(args.slug, args.include))


def _cmd_checkpoint_commit(args: argparse.Namespace) -> int:
    return _run_checkpoint(
        "commit", lambda: checkpoint.commit(args.slug, args.message, args.include, args.amend)
    )


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
    _add_config(subparsers)
    _add_mcp_headers(subparsers)
    _add_gate(subparsers)
    _add_task(subparsers)
    _add_card(subparsers)
    _add_standup(subparsers)
    _add_checkpoint(subparsers)
    handoff_cli.register(subparsers)
    board_cli.register(subparsers)
    envcheck_cli.register(subparsers)
    deploycheck_cli.register(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)
