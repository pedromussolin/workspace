"""`ws release move`: puts a published release on another day, on GitHub.

Multi-branch repos get `release/NEW[-sdbx]` copied from `origin` at the same commit, and each old
PR is recreated with the new date and replaced; single-branch repos only have the `Release:` line
of their open PRs rewritten. Everything goes through the plan of `ws.release.plan`, so the
preview, the approval and the sending are the ones `publish` uses. The state of a rerun comes
from `origin` and from the PR lists of GitHub, never from a journal: what is already done is left
out of the plan."""

import argparse
import re
import shlex
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ws.release import ReleaseRefused, ReleaseSetup, gitops, text
from ws.release import folder as release_folder
from ws.release import plan as writeplan
from ws.release import run as run_release
from ws.release.github import Gh, GhFailed, GhMissing, GhUncertain, PullRequest
from ws.release.plan import Call, WritePlan
from ws.release.settings import ReleaseConfig, RepoEntry, load_release_config

CROSS_REPO = re.compile(r"(?<![\w/.-])([\w.-]+/[\w.-]+)#(\d+)\b")
SAME_REPO = re.compile(r"(?<![\w/&#])#(\d+)\b")
RELEASE_LINE = re.compile(r"^Release: .*$", re.MULTILINE)


def replace_numbers(text: str, renumber: dict[tuple[str, int], str], slug: str) -> str:
    """`slug#N` and, in `slug`'s own PRs, `#N` become `{pr:REF}` when the PR is renumbered."""

    def cross(match: re.Match) -> str:
        ref = renumber.get((match.group(1), int(match.group(2))))
        return f"{{pr:{ref}}}" if ref else match.group(0)

    def same(match: re.Match) -> str:
        ref = renumber.get((slug, int(match.group(1))))
        return f"{{pr:{ref}}}" if ref else match.group(0)

    return SAME_REPO.sub(same, CROSS_REPO.sub(cross, text))


def residual_dates(text: str, old: str) -> list[str]:
    """The lines of `text` that still name the old day as `DD/MM` or `DD/MM/YYYY`."""
    day = release_day(old)
    pattern = re.compile(rf"(?<![\d/]){day:%d/%m}(?:/{day:%Y})?(?![\d/])")
    return [line.strip() for line in text.splitlines() if pattern.search(line)]


def release_day(value: str) -> date:
    try:
        return text.parse_day(value)
    except ValueError as error:
        raise ReleaseRefused(str(error)) from None


def _origin(branch: str) -> str:
    return f"refs/remotes/{gitops.REMOTE}/{branch}"


def _swap(value: str, old: str, new: str) -> str:
    return re.sub(rf"\b{old}\b", new, value)


@dataclass
class Item:
    """An old PR and what the move does with it. `existing` is the open PR already made from
    `release/NEW` in its place."""

    entry: RepoEntry
    old: PullRequest
    ref: str | None
    existing: PullRequest | None
    detail: PullRequest
    comments: list[str]
    current: str = ""


Branches = dict[str, tuple[str, str | None]]


def _origin_branches(entry: RepoEntry, old: str, new: str) -> Branches:
    """`release/OLD[-sdbx]` on origin: old branch -> (new branch, sha already at the new one)."""
    found = {}
    for suffix in ("", "-sdbx"):
        source, target = f"release/{old}{suffix}", f"release/{new}{suffix}"
        if gitops.rev(entry.path, _origin(source)):
            found[source] = (target, gitops.rev(entry.path, _origin(target)))
    return found


def _taken(
    entry: RepoEntry,
    gh: Gh,
    old: str,
    new: str,
    old_prs: list[PullRequest],
    branches: Branches,
) -> list[str]:
    problems = []
    for source, (target, there) in branches.items():
        if there and there != gitops.rev(entry.path, _origin(source)):
            problems.append(f"{entry.name}: {target} exists on origin at another commit")
    for suffix in ("", "-sdbx"):
        target = f"release/{new}{suffix}"
        if gitops.rev(entry.path, f"refs/heads/{target}") and gitops.rev(
            entry.path, f"refs/heads/release/{old}{suffix}"
        ):
            problems.append(f"{entry.name}: the local branch {target} exists")
        ours = {pr.base for pr in old_prs if pr.head == f"release/{old}{suffix}"}
        for pr in gh.prs(entry.slug, head=target, state="open"):
            if pr.base not in ours:
                problems.append(f"{entry.name}: PR #{pr.number} already uses {target}")
    return problems


def _old_prs(entry: RepoEntry, gh: Gh, heads: list[str]) -> list[PullRequest]:
    found: dict[int, PullRequest] = {}
    for head in heads:
        for pr in gh.prs(entry.slug, head=head):
            found[pr.number] = pr
    return [found[number] for number in sorted(found)]


def _is_open(pr: PullRequest) -> bool:
    return pr.state.upper() == "OPEN"


def _is_merged(pr: PullRequest) -> bool:
    return pr.merged_at is not None or pr.state.upper() == "MERGED"


def _grew(config: ReleaseConfig, entry: RepoEntry, head: str) -> bool:
    sandbox, tip = _origin(config.sandbox_branch), _origin(head)
    if not gitops.rev(entry.path, sandbox) or not gitops.rev(entry.path, tip):
        return False
    return gitops.count(entry.path, f"{sandbox}..{tip}") > 0


def _replaced_by(comments: list[str], made: list[PullRequest]) -> PullRequest | None:
    """The open PR a closed old PR names in its `Substituído por <url>` comment."""
    for pr in made:
        if any(comment.startswith(f"Substituído por {pr.url}:") for comment in comments):
            return pr
    return None


def _recreated(config: ReleaseConfig, entry: RepoEntry, prs: list[PullRequest]) -> set[int]:
    """The merged PRs that get a new sandbox PR: the last PR of its head and base, whatever the
    state of the earlier ones, and only when its branch has commits the sandbox lacks."""
    last: dict[tuple[str, str], PullRequest] = {}
    for pr in prs:
        last[(pr.head, pr.base)] = max(
            (pr, last.get((pr.head, pr.base), pr)), key=lambda item: item.number
        )
    return {
        pr.number
        for pr in last.values()
        if _is_merged(pr) and pr.base == config.sandbox_branch and _grew(config, entry, pr.head)
    }


def _items(
    config: ReleaseConfig, entry: RepoEntry, gh: Gh, old: str, new: str, prs: list[PullRequest]
) -> list[Item]:
    items = []
    recreated = _recreated(config, entry, prs)
    for pr in prs:
        merged, opened = _is_merged(pr), _is_open(pr)
        wanted = pr.number in recreated if merged else True
        made = (
            gh.prs(entry.slug, head=_swap(pr.head, old, new), base=pr.base, state="open")
            if wanted
            else []
        )
        comments = gh.comments(entry.slug, pr.number) if merged or not opened else []
        existing = made[0] if made else None
        if not (merged or opened):
            existing = _replaced_by(comments, made)
            if existing is None:
                continue
        ref = f"{entry.name}-{pr.number}" if wanted else None
        current = gh.pr(entry.slug, existing.number).body if existing else ""
        items.append(
            Item(entry, pr, ref, existing, gh.pr(entry.slug, pr.number), comments, current)
        )
    return items


def _with_release_line(body: str, day: date) -> str:
    return RELEASE_LINE.sub(lambda _: release_folder.release_line(day), body)


def _single_edits(
    config: ReleaseConfig, entry: RepoEntry, gh: Gh, code: str, new: date
) -> tuple[list[Call], list[int]]:
    """The edits that change the `Release:` line, and the PRs that have no such line."""
    calls, missing = [], []
    found: dict[int, PullRequest] = {}
    for head in (code, f"{code}-sdbx"):
        for pr in gh.prs(entry.slug, head=head, state="open"):
            if pr.base in (config.base_branch, config.sandbox_branch):
                found[pr.number] = pr
    for number in sorted(found):
        body = gh.pr(entry.slug, number).body
        if not RELEASE_LINE.search(body):
            missing.append(number)
            continue
        changed = _with_release_line(body, new)
        if changed == body:
            continue
        calls.append(
            Call(
                repo=entry.name,
                program="gh",
                args=("pr", "edit", str(number), "-R", entry.slug),
                line=f"{entry.name}: trocar a data da release na PR #{number}",
                body=changed,
            )
        )
    return calls, missing


def _push_calls(entry: RepoEntry, branches: Branches) -> tuple[list[Call], dict[str, str]]:
    calls, tips = [], {}
    for source, (target, there) in branches.items():
        tips[target] = gitops.rev(entry.path, _origin(source)) or ""
        if there:
            continue
        calls.append(
            Call(
                repo=entry.name,
                program="git",
                args=("push", "origin", f"{_origin(source)}:refs/heads/{target}"),
                line=f"{entry.name}: copiar {source} para {target}",
                cwd=str(entry.path),
            )
        )
    return calls, tips


def _expected(item: Item, old: str, new: str, day: date, renumber: dict) -> tuple[str, str]:
    """The title and body the replacement PR has, with `{pr:REF}` where a number is not known."""
    slug = item.entry.slug
    title = replace_numbers(_swap(item.detail.title, old, new), renumber, slug)
    body = _with_release_line(_swap(item.detail.body, old, new), day)
    return title, replace_numbers(body, renumber, slug)


def _item_calls(
    item: Item, old: str, new: str, day: date, renumber: dict, reason: str
) -> list[Call]:
    entry, pr = item.entry, item.old
    shown = text.display(day)
    calls = []
    if item.ref and item.existing is None:
        title, body = _expected(item, old, new, day, renumber)
        args = (
            "pr",
            "create",
            "-R",
            entry.slug,
            "--base",
            pr.base,
            "--head",
            _swap(pr.head, old, new),
            "--title",
            title,
        )
        for label in item.detail.labels:
            args += ("--label", label)
        for person in item.detail.assignees:
            args += ("--assignee", person)
        calls.append(
            Call(
                repo=entry.name,
                program="gh",
                args=args,
                line=f"{entry.name}: abrir a PR da release {shown} (substitui a #{pr.number})",
                body=body,
                answers=item.ref,
            )
        )
    if _is_open(pr):
        comment = (
            f"Substituído por {{url:{item.ref}}}: a release passou a ser a de {shown}, {reason}."
        )
        calls.append(
            Call(
                repo=entry.name,
                program="gh",
                args=("pr", "close", str(pr.number), "-R", entry.slug, "--comment", comment),
                line=f"{entry.name}: fechar a PR #{pr.number}, substituída",
            )
        )
    elif _is_merged(pr):
        comment = f"A release passou a ser a de {shown}, {reason}."
        if comment not in item.comments:
            calls.append(
                Call(
                    repo=entry.name,
                    program="gh",
                    args=("pr", "comment", str(pr.number), "-R", entry.slug, "--body", comment),
                    line=f"{entry.name}: comentar a PR #{pr.number}, já mergeada",
                )
            )
    return calls


def _same_body(left: str, right: str) -> bool:
    def norm(value: str) -> str:
        return value.replace("\r\n", "\n").rstrip("\n")

    return norm(left) == norm(right)


def _fix_calls(
    items: list[Item], old: str, new: str, day: date, renumber: dict, known: dict
) -> list[Call]:
    """One edit per replacement PR an earlier run made, from the body it has now: the dates,
    the `Release:` line and the numbers are brought up to date and what a person added stays."""
    calls = []
    done: set[tuple[str, int]] = set()
    for item in items:
        if item.existing is None or item.ref is None:
            continue
        if (item.entry.slug, item.existing.number) in done:
            continue
        done.add((item.entry.slug, item.existing.number))
        slug = item.entry.slug
        body = replace_numbers(
            _with_release_line(_swap(item.current, old, new), day), renumber, slug
        )
        pending = [ref for ref in release_folder.pending_refs(body) if ref not in known]
        body = release_folder.resolve_refs(body, known)
        if not pending and _same_body(body, item.current):
            continue
        calls.append(
            Call(
                repo=item.entry.name,
                program="gh",
                args=("pr", "edit", str(item.existing.number), "-R", slug),
                line=f"segunda passada: {item.entry.name}: corrigir a PR #{item.existing.number}",
                body=body,
            )
        )
    return calls


def _title_problems(calls: list[Call], known: dict) -> list[str]:
    """A title is an argument: a placeholder in it has to name a PR made before the create."""
    problems, made = [], set(known)
    for call in calls:
        if call.args[:2] != ("pr", "create") or not call.answers:
            continue
        title = call.args[call.args.index("--title") + 1]
        if [ref for ref in release_folder.pending_refs(title) if ref not in made]:
            number = call.answers.rsplit("-", 1)[-1]
            problems.append(
                f"{call.repo}: the title of the new PR for #{number} cites a PR created later"
            )
        made.add(call.answers)
    return problems


def build_plan(
    config: ReleaseConfig,
    slug: str,
    old: str,
    new: str,
    reason: str,
    delete_old: bool,
    gh: Gh,
) -> WritePlan:
    old_day, new_day = release_day(old), release_day(new)
    old, new = text.compact(old_day), text.compact(new_day)
    if old == new:
        raise ReleaseRefused("OLD and NEW are the same day")
    if new_day < text.today():
        raise ReleaseRefused(f"{new} is in the past")
    names = tuple(entry.name for entry in config.repos)
    old_dir = release_folder.release_dir(slug, old_day)
    new_dir = release_folder.release_dir(slug, new_day)
    moved = not (old_dir / "release.toml").exists() and (new_dir / "release.toml").exists()
    wanted = release_folder.read_release(new_dir if moved else old_dir, names)
    if not _new_folder_free(old_dir, new_dir, list(config.repos)):
        raise ReleaseRefused(f"{new_dir} already exists")

    entries = [entry for entry in config.repos if entry.name in wanted.repos]
    multi = [entry for entry in entries if len(wanted.include[entry.name]) > 1]
    heads = [f"release/{old}", f"release/{old}-sdbx"]
    problems: list[str] = []
    branches = {entry.name: _origin_branches(entry, old, new) for entry in multi}
    old_prs = {entry.name: _old_prs(entry, gh, heads) for entry in multi}
    for entry in multi:
        problems += _taken(entry, gh, old, new, old_prs[entry.name], branches[entry.name])

    items: list[Item] = []
    pushes: dict[str, list[Call]] = {}
    tips: dict[str, dict[str, str]] = {}
    for entry in multi:
        pushes[entry.name], tips[entry.name] = _push_calls(entry, branches[entry.name])
        items += _items(config, entry, gh, old, new, old_prs[entry.name])

    renumber = {(item.entry.slug, item.old.number): item.ref for item in items if item.ref}
    known = {
        item.ref: [
            f"{item.entry.slug}#{item.existing.number}",
            item.existing.url,
            item.existing.number,
        ]
        for item in items
        if item.ref and item.existing
    }
    residual: list[dict] = []
    for item in items:
        if item.ref:
            title, body = _expected(item, old, new, new_day, renumber)
            for line in residual_dates(title + "\n" + body, old):
                residual.append({"repo": item.entry.name, "pr": item.old.number, "text": line})

    calls: list[Call] = []
    without_line: list[dict] = []
    for entry in entries:
        if entry in multi:
            calls += pushes[entry.name]
            for item in (i for i in items if i.entry is entry):
                calls += _item_calls(item, old, new, new_day, renumber, reason)
        else:
            code = wanted.include[entry.name][0]
            edits, missing = _single_edits(config, entry, gh, code, new_day)
            calls += edits
            without_line += [{"repo": entry.name, "pr": number} for number in missing]
            for call in edits:
                for line in residual_dates(call.body or "", old):
                    residual.append({"repo": entry.name, "pr": int(call.args[2]), "text": line})
    calls += writeplan.second_pass(calls)
    calls += _fix_calls(items, old, new, new_day, renumber, known)
    problems += _title_problems(calls, known)
    closing = {(call.repo, int(call.args[2])) for call in calls if call.args[:2] == ("pr", "close")}
    if delete_old:
        for entry in multi:
            deletes, found = _delete_calls(entry, gh, old, branches[entry.name], closing)
            calls += deletes
            problems += found
    local, moves = [], []
    for entry in entries:
        if entry in multi:
            local += _branch_calls(entry, old, new, branches[entry.name])
        found, trouble = _worktree_calls(entry, old, new, old_dir, new_dir)
        local += found
        moves += found
        problems += trouble
    folder, left = _folder_calls(old_dir, new_dir, old, new, local, moves)
    calls += folder
    return WritePlan(
        action="move",
        slug=slug,
        days=(old, new),
        tips=tips,
        calls=calls,
        drafts=[],
        facts={
            "known": known,
            "reason": reason,
            "delete_old": delete_old,
            "residual_dates": residual,
            "without_release_line": without_line,
            "left_in_old": left,
        },
        problems=problems,
    )


def _delete_calls(
    entry: RepoEntry, gh: Gh, old: str, branches: Branches, closing: set[tuple[str, int]]
) -> tuple[list[Call], list[str]]:
    """`release/OLD[-sdbx]` leaves `origin` only when no PR from it stays open and no open PR has
    it as base; the PRs this plan closes count as closed."""
    calls, problems = [], []
    for source in branches:
        open_from = [
            pr.number
            for pr in gh.prs(entry.slug, head=source, state="open")
            if (entry.name, pr.number) not in closing
        ]
        open_base = [pr.number for pr in gh.prs(entry.slug, base=source, state="open")]
        if open_from:
            problems.append(
                f"{entry.name}: {source} stays: PR #{open_from[0]} from it is still open"
            )
        elif open_base:
            problems.append(f"{entry.name}: {source} stays: it is the base of PR #{open_base[0]}")
        else:
            calls.append(
                Call(
                    repo=entry.name,
                    program="git",
                    args=("push", "origin", "--delete", source),
                    line=f"{entry.name}: apagar {source} na origin",
                    cwd=str(entry.path),
                )
            )
    return calls, problems


def _upstream_set(entry: RepoEntry, branch: str) -> bool:
    def config(key: str) -> str:
        return gitops.git(
            entry.path, "config", "--get", f"branch.{branch}.{key}", check=False
        ).stdout.strip()

    return config("remote") == gitops.REMOTE and config("merge") == f"refs/heads/{branch}"


def _registered(entry: RepoEntry) -> set[Path]:
    out = gitops.git(entry.path, "worktree", "list", "--porcelain").stdout
    return {
        Path(line[len("worktree ") :]).resolve()
        for line in out.splitlines()
        if line.startswith("worktree ")
    }


def _branch_calls(entry: RepoEntry, old: str, new: str, branches: Branches) -> list[Call]:
    """The branch renames and upstreams still to do for `entry`, from the live state, so a
    rerun finishes."""
    calls = []
    for suffix in ("", "-sdbx"):
        source, target = f"release/{old}{suffix}", f"release/{new}{suffix}"
        on_origin = source in branches or gitops.rev(entry.path, _origin(target))
        has_source = gitops.rev(entry.path, f"refs/heads/{source}")
        if has_source and on_origin:
            calls.append(
                Call(
                    repo=entry.name,
                    program="git",
                    args=("branch", "-m", source, target),
                    line=f"{entry.name}: renomear a branch local {source} para {target}",
                    cwd=str(entry.path),
                )
            )
        if on_origin and (
            has_source
            or (gitops.rev(entry.path, f"refs/heads/{target}") and not _upstream_set(entry, target))
        ):
            calls.append(
                Call(
                    repo=entry.name,
                    program="git",
                    args=("branch", "-u", f"origin/{target}", target),
                    line=f"{entry.name}: apontar {target} para origin/{target}",
                    cwd=str(entry.path),
                )
            )
    return calls


def _worktree_calls(
    entry: RepoEntry, old: str, new: str, old_dir: Path, new_dir: Path
) -> tuple[list[Call], list[str]]:
    """The moves of the worktrees `entry` has under `release-OLD/`, multi-branch or not."""
    moves, problems = [], []
    registered = _registered(entry)
    for name in (entry.name, f"{entry.name}-sdbx"):
        if (old_dir / name).resolve() not in registered:
            continue
        if not (old_dir / name).is_dir():
            problems.append(
                f"{entry.name}: the worktree {old_dir / name} is registered but its folder is "
                "gone; run `git worktree prune`"
            )
            continue
        moves.append(
            Call(
                repo=entry.name,
                program="git",
                args=("worktree", "move", str(old_dir / name), str(new_dir / name)),
                line=f"{entry.name}: mover o worktree release-{old}/{name} para release-{new}",
                cwd=str(entry.path),
            )
        )
    return moves, problems


FOLDER_FILES = ("release.toml", "pr", "published.json")


def _left_in_old(old_dir: Path, moves: list[Call]) -> list[str]:
    """What stays in `release-OLD/` after the move: neither a moved file nor a moved worktree."""
    if not old_dir.is_dir():
        return []
    moving = {Path(call.args[2]).name for call in moves}
    return sorted(
        path.name
        for path in old_dir.iterdir()
        if path.name not in FOLDER_FILES and path.name not in moving
    )


def _folder_calls(
    old_dir: Path, new_dir: Path, old: str, new: str, local: list[Call], moves: list[Call]
) -> tuple[list[Call], list[str]]:
    """The local steps with the `move-folder` calls around them, and what stays in the old
    folder. The folder is touched only while there is something to move or it would end up empty
    (a move already done never swaps the dates of the new drafts again)."""
    left = _left_in_old(old_dir, moves)
    if not old_dir.exists():
        return local, left
    files = any((old_dir / name).exists() for name in FOLDER_FILES)
    shown = f"release.toml, pr/ e published.json de release-{old} para release-{new}"

    def call(mode: str, line: str) -> Call:
        args = ("move-folder", str(old_dir), str(new_dir), old, new, mode)
        return Call(repo="release", program="local", args=args, line=line)

    move_line = f"mover {shown} e trocar a data nos rascunhos"
    finish_line = f"remover a pasta release-{old}, se vazia"
    if left:
        return ([call("files", move_line)] if files else []) + local, left
    if not moves:
        both = f"mover {shown}, trocar a data nos rascunhos e remover a pasta antiga se vazia"
        return local + [call("all", both) if files else call("finish", finish_line)], left
    return ([call("files", move_line)] if files else []) + local + [
        call("finish", finish_line)
    ], left


def move_folder(old_dir: str, new_dir: str, old: str, new: str, mode: str) -> None:
    """The local handler of `move-folder`. `files` moves `release.toml`, `pr/` and
    `published.json` to the new folder and gives the drafts the new date; `finish` removes the old
    folder when it is empty and says what stays; `all` is both. It can run again after a failure."""
    source, target = Path(old_dir), Path(new_dir)
    if (
        source.name != f"release-{old}"
        or target.name != f"release-{new}"
        or source.parent != target.parent
    ):
        raise ValueError(f"{source} and {target} are not the release folders of {old} and {new}")
    if mode in ("files", "all"):
        for name in FOLDER_FILES:
            if (source / name).exists():
                if (target / name).exists():
                    raise FileExistsError(f"{target / name} already exists")
                release_folder.ensure_dir(target)
                (source / name).rename(target / name)
        for draft in sorted((target / "pr").glob("*.md")):
            before = draft.read_bytes().decode()
            after = _swap(before, old, new)
            if after != before:
                draft.write_bytes(after.encode())
    if mode in ("finish", "all") and source.is_dir():
        try:
            source.rmdir()
        except OSError:
            stays = ", ".join(sorted(path.name for path in source.iterdir()))
            print(f"{source} stays, it still holds: {stays}", file=sys.stderr)


def _new_folder_free(old_dir: Path, new_dir: Path, entries: list[RepoEntry]) -> bool:
    """`release-NEW/` is free, or holds only what an earlier run of this move put there: the moved
    files (`release.toml` first) and worktrees of the repos, with nothing also in `release-OLD/`."""
    if not new_dir.exists():
        return True
    held = {path.name for path in new_dir.iterdir()}
    repo_dirs = {f"{entry.name}{suffix}" for entry in entries for suffix in ("", "-sdbx")}
    if "release.toml" not in held or not held <= set(FOLDER_FILES) | repo_dirs:
        return False
    if any((old_dir / name).exists() for name in held):
        return False
    return all(
        (new_dir / name).resolve() in _registered(entry)
        for entry in entries
        for name in (entry.name, f"{entry.name}-sdbx")
        if name in held
    )


def _next_command(args: argparse.Namespace, slug: str) -> str:
    command = (
        f"ws release move {args.old} {args.new} --reason {shlex.quote(args.reason)} "
        f"--project {slug}"
    )
    return command + (" --delete-old-branches" if args.delete_old_branches else "")


def _setup(args: argparse.Namespace) -> tuple[ReleaseConfig, Gh, str, list[str]]:
    config = load_release_config()
    gh = Gh()
    try:
        gh.require_auth()
    except GhMissing as error:
        raise ReleaseSetup(f"gh: {error}") from error
    slug = release_folder.resolve_slug(args.project, Path.cwd())
    warnings = []
    for entry in config.repos:
        error = gitops.fetch(entry.path)
        if error:
            warnings.append(f"{entry.name}: fetch failed: {error}")
    return config, gh, slug, warnings


def _build(args: argparse.Namespace, config: ReleaseConfig, slug: str, gh: Gh) -> WritePlan:
    try:
        return build_plan(
            config, slug, args.old, args.new, args.reason, args.delete_old_branches, gh
        )
    except (GhFailed, GhUncertain, gitops.GitFailed) as error:
        raise ReleaseSetup(f"{error}") from error


def _missing_line(plan: WritePlan) -> list[str]:
    return [
        f"{item['repo']}: PR #{item['pr']} has no Release: line; its date was not changed"
        for item in plan.facts["without_release_line"]
    ]


def run_preview(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        config, gh, slug, warnings = _setup(args)
        plan = _build(args, config, slug, gh)
        payload, code = writeplan.show_preview(plan, _next_command(args, slug))
        payload["residual_dates"] = plan.facts["residual_dates"]
        payload["left_in_old"] = plan.facts["left_in_old"]
        payload["warnings"] = warnings + _missing_line(plan)
        return payload, code

    return run_release("move", action)


def run_move(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        config, gh, slug, warnings = _setup(args)
        payload, code = writeplan.approve(
            args.approve,
            "move",
            lambda: _build(args, config, slug, gh),
            gh,
            config,
            {"move-folder": move_folder},
        )
        payload["warnings"] = warnings
        payload["left_in_old"] = _left_in_old(
            release_folder.release_dir(slug, release_day(args.old)), []
        )
        return payload, code

    return run_release("move", action)
