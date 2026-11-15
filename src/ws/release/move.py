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
    """An old PR and what the move does with it."""

    entry: RepoEntry
    old: PullRequest
    head: str
    ref: str | None
    existing: PullRequest | None
    detail: PullRequest


def _origin_branches(entry: RepoEntry, old: str, new: str) -> dict[str, tuple[str, str | None]]:
    """`release/OLD[-sdbx]` on origin: old branch -> (new branch, sha already at the new one)."""
    found = {}
    for suffix in ("", "-sdbx"):
        source, target = f"release/{old}{suffix}", f"release/{new}{suffix}"
        if gitops.rev(entry.path, _origin(source)):
            found[source] = (target, gitops.rev(entry.path, _origin(target)))
    return found


def _taken(entry: RepoEntry, gh: Gh, old: str, new: str, old_prs: list[PullRequest]) -> list[str]:
    problems = []
    for source, (target, there) in _origin_branches(entry, old, new).items():
        if there and there != gitops.rev(entry.path, _origin(source)):
            problems.append(f"{entry.name}: {target} exists on origin at another commit")
    for suffix in ("", "-sdbx"):
        target = f"release/{new}{suffix}"
        if gitops.rev(entry.path, f"refs/heads/{target}"):
            problems.append(f"{entry.name}: the local branch {target} exists")
        ours = {pr.base for pr in old_prs if pr.head == f"release/{old}{suffix}"}
        for pr in gh.prs(entry.slug, head=target):
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


def _items(
    config: ReleaseConfig, entry: RepoEntry, gh: Gh, old: str, new: str, prs: list[PullRequest]
) -> list[Item]:
    items = []
    for pr in prs:
        if _is_merged(pr):
            wanted = pr.base == config.sandbox_branch and _grew(config, entry, pr.head)
        elif _is_open(pr):
            wanted = True
        else:
            continue
        made = gh.prs(entry.slug, head=_swap(pr.head, old, new), base=pr.base) if wanted else []
        existing = min(made, key=lambda item: not _is_open(item), default=None)
        ref = f"{entry.name}-{pr.number}" if wanted else None
        items.append(Item(entry, pr, pr.head, ref, existing, gh.pr(entry.slug, pr.number)))
    return items


def _single_edits(
    config: ReleaseConfig, entry: RepoEntry, gh: Gh, code: str, new: date, facts: list[dict]
) -> list[Call]:
    calls = []
    found: dict[int, PullRequest] = {}
    for head in (code, f"{code}-sdbx"):
        for pr in gh.prs(entry.slug, head=head, state="open"):
            if pr.base in (config.base_branch, config.sandbox_branch):
                found[pr.number] = pr
    for number in sorted(found):
        body = gh.pr(entry.slug, number).body
        changed = RELEASE_LINE.sub(release_folder.release_line(new), body)
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
        facts.append({"repo": entry.name, "pr": number, "text": changed})
    return calls


def _push_calls(entry: RepoEntry, old: str, new: str) -> tuple[list[Call], dict[str, str]]:
    calls, tips = [], {}
    for source, (target, there) in _origin_branches(entry, old, new).items():
        sha = gitops.rev(entry.path, _origin(source)) or ""
        tips[target] = sha
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


def _item_calls(
    item: Item,
    old: str,
    new: str,
    renumber: dict[tuple[str, int], str],
    reason: str,
    pushing: set[str],
) -> list[Call]:
    entry, pr = item.entry, item.old
    shown = text.display(release_day(new))
    calls = []
    if item.ref and item.existing is None:
        title = replace_numbers(_swap(item.detail.title, old, new), renumber, entry.slug)
        body = replace_numbers(_swap(item.detail.body, old, new), renumber, entry.slug)
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
    elif pr.head in pushing:
        comment = f"A release passou a ser a de {shown}, {reason}."
        calls.append(
            Call(
                repo=entry.name,
                program="gh",
                args=("pr", "comment", str(pr.number), "-R", entry.slug, "--body", comment),
                line=f"{entry.name}: comentar a PR #{pr.number}, já mergeada",
            )
        )
    return calls


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
    wanted = release_folder.read_release(release_folder.release_dir(slug, old_day), names)
    if release_folder.release_dir(slug, new_day).exists():
        raise ReleaseRefused(f"{release_folder.release_dir(slug, new_day)} already exists")

    problems: list[str] = []
    multi = [config.entry(name) for name in wanted.repos if len(wanted.include[name]) > 1]
    heads = [f"release/{old}", f"release/{old}-sdbx"]
    old_prs = {entry.name: _old_prs(entry, gh, heads) for entry in multi}
    for entry in multi:
        problems += _taken(entry, gh, old, new, old_prs[entry.name])

    items: list[Item] = []
    pushes: dict[str, list[Call]] = {}
    tips: dict[str, dict[str, str]] = {}
    for entry in multi:
        pushes[entry.name], tips[entry.name] = _push_calls(entry, old, new)
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
        if not _is_open(item.old):
            continue
        for line in residual_dates(
            _swap(item.detail.title, old, new) + "\n" + _swap(item.detail.body, old, new), old
        ):
            residual.append({"repo": item.entry.name, "pr": item.old.number, "text": line})

    calls: list[Call] = []
    for name in wanted.repos:
        entry = config.entry(name)
        if entry in multi:
            calls += pushes[name]
            pushing = {
                source
                for source, (_, there) in _origin_branches(entry, old, new).items()
                if not there
            }
            for item in (i for i in items if i.entry is entry):
                calls += _item_calls(item, old, new, renumber, reason, pushing)
        else:
            facts: list[dict] = []
            code = wanted.include[name][0]
            calls += _single_edits(config, entry, gh, code, new_day, facts)
            residual += [
                {"repo": name, "pr": fact["pr"], "text": line}
                for fact in facts
                for line in residual_dates(fact["text"], old)
            ]
    calls += writeplan.second_pass(calls)
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
        },
        problems=problems,
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


def run_preview(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        config, gh, slug, warnings = _setup(args)
        plan = _build(args, config, slug, gh)
        payload, code = writeplan.show_preview(plan, _next_command(args, slug))
        payload["residual_dates"] = plan.facts["residual_dates"]
        payload["warnings"] = warnings
        return payload, code

    return run_release("move", action)


def run_move(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        config, gh, slug, warnings = _setup(args)
        payload, code = writeplan.approve(
            args.approve, "move", lambda: _build(args, config, slug, gh), gh, config
        )
        payload["warnings"] = warnings
        return payload, code

    return run_release("move", action)
