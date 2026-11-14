"""`ws release branches`: the task branches of the given cards and a suggested merge order.

Read-only: the only git write is the `fetch --prune` of remote-tracking refs. Branch presence on
`origin` comes from those refs, never from GitHub.
"""

import argparse
import sys
from pathlib import Path

from ws import items
from ws.config import repo_root
from ws.release import ReleaseSetup, gitops, migrations, run
from ws.release.settings import ReleaseConfig, RepoEntry, load_release_config

SDBX = "-sdbx"
CLOSED = {"done", "cancelled"}


def _refs(project: items.Project, item, kind: str) -> list[str]:
    refs = []
    for target in item.links[kind]:
        try:
            ref = items.link_ref(repo_root(), project, target)
        except items.ItemError as error:
            print(f"ws release branches: {item.card} {kind} {target}: {error}", file=sys.stderr)
            continue
        if ref:
            refs.append(ref)
    return refs


def _item_rows(project: items.Project) -> list[dict]:
    rows = []
    for item in project.items:
        status = item.cache.get("status")
        if not item.card or not item.tracked or status in CLOSED:
            continue
        blocks = _refs(project, item, "blocks")
        blocked_by = _refs(project, item, "blocked_by")
        rows.append(
            {
                "card": item.card,
                "item": item.path.name,
                "status": status,
                "blocks": blocks,
                "blocked_by": blocked_by,
            }
        )
    return rows


def _collect(args: argparse.Namespace) -> tuple[list[str], list[dict]]:
    keys = list(dict.fromkeys(args.tasks))
    rows: list[dict] = []
    for slug in args.items:
        try:
            project = items.load_project(repo_root(), slug)
        except items.ProjectMissing as error:
            raise ReleaseSetup(str(error)) from error
        rows += _item_rows(project)
    for row in rows:
        if row["card"] not in keys:
            keys.append(row["card"])
    if not keys:
        raise ReleaseSetup("pass --task TS-N or --from-items SLUG")
    for key in keys:
        if not gitops.TASK_KEY.fullmatch(key):
            raise ReleaseSetup(f"{key!r} is not a task key like TS-101")
    return keys, rows


def _names(repo: Path, key: str) -> dict[str, dict[str, bool]]:
    local, remote = gitops.branches_with(repo, key)
    found: dict[str, dict[str, bool]] = {}
    for name in local:
        found.setdefault(name, {})["local"] = True
    prefix = f"{gitops.REMOTE}/"
    for name in remote:
        if name.startswith(prefix) and name != f"{prefix}HEAD":
            found.setdefault(name[len(prefix) :], {})["remote"] = True
    return found


def _tip(repo: Path, name: str) -> str | None:
    return gitops.rev(repo, name) or gitops.rev(repo, f"{gitops.REMOTE}/{name}")


def _migrations(
    entry: RepoEntry, repo: Path, tip: str, base: dict[str, migrations.Revision]
) -> list[dict]:
    assert entry.alembic
    tip_revs = migrations.revisions(gitops.sources_at(repo, tip, entry.alembic))
    return [
        {"revision": rev, "down": list(tip_revs[rev].down)}
        for rev in sorted(tip_revs)
        if rev not in base
    ]


def _repo_report(
    config: ReleaseConfig, entry: RepoEntry, keys: list[str], hints: set[tuple[str, str]]
) -> dict:
    repo = entry.path
    problems: list[str] = []
    warning = gitops.fetch(repo)
    if warning:
        problems.append(f"fetch failed: {warning}")
    base_ref = f"{gitops.REMOTE}/{config.base_branch}"
    base_tip = gitops.rev(repo, base_ref)
    if base_tip is None:
        problems.append(f"{base_ref} does not exist")
    base_revs: dict[str, migrations.Revision] = {}
    if entry.alembic and base_tip:
        try:
            base_revs = migrations.revisions(gitops.sources_at(repo, base_tip, entry.alembic))
        except migrations.MigrationUnreadable as error:
            problems.append(str(error))

    found: list[tuple[str, str, dict[str, bool]]] = []
    for key in keys:
        for name, where in sorted(_names(repo, key).items()):
            if not name.endswith(SDBX) and not any(n == name for _, n, _ in found):
                found.append((key, name, where))

    tips: dict[str, str] = {}
    rows: list[dict] = []
    revs_of: dict[str, set[str]] = {}
    downs_of: dict[str, set[str]] = {}
    for key, name, where in found:
        tip = _tip(repo, name)
        if tip is None:
            continue
        tips[name] = tip
        local, remote = where.get("local", False), where.get("remote", False)
        row = {
            "branch": name,
            "key": key,
            "local": local,
            "remote": remote,
            "ahead": gitops.count(repo, f"{base_ref}..{tip}") if base_tip else 0,
            "merged": bool(base_tip) and gitops.is_ancestor(repo, tip, base_ref),
            "sdbx": None,
            "contains": [],
            "migrations": [],
        }
        if local and remote:
            origin_tip = gitops.rev(repo, f"{gitops.REMOTE}/{name}")
            if origin_tip and origin_tip != tip and gitops.is_ancestor(repo, tip, origin_tip):
                problems.append(f"{name}: local branch is behind origin; pull it")
        copy = _tip(repo, name + SDBX)
        if copy:
            row["sdbx"] = {"branch": name + SDBX, "contains": gitops.is_ancestor(repo, tip, copy)}
        if entry.alembic:
            try:
                row["migrations"] = _migrations(entry, repo, tip, base_revs)
            except migrations.MigrationUnreadable as error:
                problems.append(f"{name}: {error}")
        revs_of[name] = {m["revision"] for m in row["migrations"]}
        downs_of[name] = {d for m in row["migrations"] for d in m["down"]} - revs_of[name]
        rows.append(row)

    names = [row["branch"] for row in rows]
    edges: set[tuple[str, str]] = set()
    for row in rows:
        for other in names:
            if other != row["branch"] and tips[other] != tips[row["branch"]]:
                if gitops.is_ancestor(repo, tips[other], tips[row["branch"]]):
                    row["contains"].append(other)
                    edges.add((other, row["branch"]))
        for other in names:
            if other != row["branch"] and downs_of[row["branch"]] & revs_of[other]:
                edges.add((other, row["branch"]))
    keyed = {row["branch"]: row["key"] for row in rows}
    for first, second in hints:
        for a in names:
            for b in names:
                if keyed[a] == first and keyed[b] == second:
                    edges.add((a, b))
    order, cycle = migrations.suggested_order(names, edges)
    problems += cycle
    return {"repo": entry.name, "branches": rows, "suggested_order": order, "problems": problems}


def _hints(rows: list[dict]) -> set[tuple[str, str]]:
    hints: set[tuple[str, str]] = set()
    cards = {row["card"] for row in rows}
    for row in rows:
        for blocked in row["blocks"]:
            if blocked in cards:
                hints.add((row["card"], blocked))
        for blocker in row["blocked_by"]:
            if blocker in cards:
                hints.add((blocker, row["card"]))
    return hints


def run_branches(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        config = load_release_config()
        keys, rows = _collect(args)
        entries = [config.entry(name) for name in args.repos] if args.repos else config.repos
        hints = _hints(rows)
        repos = [_repo_report(config, entry, keys, hints) for entry in entries]
        seen = {row["key"] for repo in repos for row in repo["branches"]}
        payload = {
            "repos": repos,
            "items": [{k: r[k] for k in ("card", "item", "status", "blocks")} for r in rows],
            "unmatched": [key for key in keys if key not in seen],
        }
        return payload, 0

    return run("branches", action)
