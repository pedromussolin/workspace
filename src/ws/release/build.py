"""`ws release new`: builds the release branches locally, merging the task branches in order.

Nothing here pushes or calls `gh`. A merge conflict stops the command at once and leaves the
merge in progress in its worktree; the user resolves it, commits, and runs the command again.
Two Alembic heads at a clean sandbox merge count as a conflict: the `-sdbx` is made and the user
adds the merge migration there.
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ws.release import ReleaseRefused, ReleaseSetup, folder, gitops, rules, text
from ws.release import run as run_release
from ws.release.settings import ReleaseConfig, RepoEntry, load_release_config

PUBLISHED = "published.json"


@dataclass
class Conflict(Exception):
    repo: str
    worktree: Path
    files: list[str]
    heads: list[str] = field(default_factory=list)


def _local(branch: str) -> str:
    return f"refs/heads/{branch}"


def _origin(branch: str) -> str:
    return f"refs/remotes/{gitops.REMOTE}/{branch}"


def _ref(repo: Path, branch: str) -> str | None:
    for ref in (_local(branch), _origin(branch)):
        if gitops.rev(repo, ref):
            return ref
    return None


def load_published(release: Path) -> dict:
    """The whole `published.json` (empty when absent); a bad file is a setup problem."""
    path = release / PUBLISHED
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise ReleaseSetup(f"{path}: {error}") from None
    if not isinstance(data, dict):
        raise ReleaseSetup(f"{path}: expected a JSON object")
    return data


def read_published(release: Path) -> dict:
    repos = load_published(release).get("repos")
    return repos if isinstance(repos, dict) else {}


def _code_branch(includes: tuple[str, ...], day: date) -> str:
    return includes[0] if len(includes) == 1 else f"release/{text.compact(day)}"


def _needs_copy(entry: RepoEntry, tip: str, sandbox: str) -> bool:
    """A git conflict with `sandbox`, or two Alembic heads at the clean merge."""
    tree, files = gitops.merge_tree(entry.path, tip, sandbox)
    return bool(files) or bool(rules.sandbox_heads(entry, tip, tree))


def _sandbox_conflicts(config: ReleaseConfig, entry: RepoEntry, code: str) -> bool:
    """Whether the code branch as it is now needs the `-sdbx` copy (False if either is absent)."""
    ref, sandbox = _ref(entry.path, code), _origin(config.sandbox_branch)
    tip = gitops.rev(entry.path, ref) if ref else None
    if tip is None or gitops.rev(entry.path, sandbox) is None:
        return False
    return _needs_copy(entry, tip, sandbox)


def _check_setup(
    config: ReleaseConfig,
    entry: RepoEntry,
    includes: tuple[str, ...],
    day: date,
    published: dict,
    copy_used: bool,
) -> None:
    """`copy_used`: the sandbox conflicts, so the `-sdbx` copy will be the sandbox head."""
    repo, name = entry.path, entry.name
    code = _code_branch(includes, day)
    release_branch = f"release/{text.compact(day)}"
    before = published.get(name)
    if isinstance(before, dict) and before.get("shape") == "single" and len(includes) > 1:
        raise ReleaseSetup(
            f"{name} was published from {before.get('code_branch')} (PR #{before.get('code_pr')}); "
            "with more task branches it needs a release branch: decide how to move on"
        )
    if len(includes) == 1 and gitops.rev(repo, _local(release_branch)):
        raise ReleaseSetup(
            f"{name}: {release_branch} exists but the repo has one include now: "
            "decide how to move on"
        )
    for branch in [code, f"{code}-sdbx"] if copy_used else [code]:
        local = gitops.rev(repo, _local(branch))
        if local is None and gitops.rev(repo, _origin(branch)):
            raise ReleaseSetup(
                f"{name}: {branch} is on origin but not here; pull it (git switch {branch}) first"
            )
        where = gitops.checked_out_at(repo, branch) if local else None
        if where and gitops.merging(where):
            raise ReleaseSetup(f"{name}: a merge is in progress in {where}; finish it first")
        if where and not gitops.clean(where) and _will_merge(config, entry, includes, branch):
            raise ReleaseSetup(f"{name}: {where} has uncommitted changes; commit or stash them")


def _will_merge(config: ReleaseConfig, entry: RepoEntry, includes: tuple[str, ...], branch: str):
    """False only for a single-include branch that master has not moved past: nothing is merged."""
    if len(includes) > 1 or branch != includes[0]:
        return True
    ref = _ref(entry.path, branch)
    return gitops.count(entry.path, f"{ref}..{_origin(config.base_branch)}") > 0


def _worktree(release: Path, entry: RepoEntry, branch: str, suffix: str, start: str | None) -> Path:
    """The worktree where `branch` is checked out, adding one under the release folder if none."""
    where = gitops.checked_out_at(entry.path, branch)
    if where:
        return where
    path = release / f"{entry.name}{suffix}"
    folder.ensure_dir(release)
    gitops.add_worktree(entry.path, path, branch, start)
    return path


def _merge(entry: RepoEntry, wt: Path, ref: str, subject: str, body: str = "") -> None:
    files = gitops.merge(wt, ref, subject, body)
    if files:
        raise Conflict(entry.name, wt, files)


def _keys(branches: tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(key for branch in branches for key in text.keys_of(branch)))


def _merge_base(entry: RepoEntry, wt: Path, base: str, keys: list[str]) -> None:
    if gitops.count(wt, f"HEAD..{base}") > 0:
        subject, body = text.release_merge_message(keys, text.MASTER_TEXT)
        _merge(entry, wt, base, subject, body)


def _build_code(
    config: ReleaseConfig, entry: RepoEntry, includes: tuple[str, ...], day: date, release: Path
) -> None:
    repo = entry.path
    base = _origin(config.base_branch)
    if len(includes) == 1:
        branch = includes[0]
        if gitops.count(repo, f"{_ref(repo, branch)}..{base}") == 0:
            return
        start = None if gitops.rev(repo, _local(branch)) else _origin(branch)
        wt = _worktree(release, entry, branch, "", start)
        _merge_base(entry, wt, base, _keys(includes))
        return
    code = f"release/{text.compact(day)}"
    start = None if gitops.rev(repo, _local(code)) else base
    wt = _worktree(release, entry, code, "", start)
    for branch in includes:
        ref = _ref(repo, branch)
        if ref and not gitops.is_ancestor(wt, ref, "HEAD"):
            key = text.keys_of(branch)[0]
            _merge(entry, wt, ref, text.task_merge_subject(key, branch))
    _merge_base(entry, wt, base, _keys(includes))


def _build_sdbx(
    config: ReleaseConfig, entry: RepoEntry, includes: tuple[str, ...], code: str, release: Path
) -> None:
    repo = entry.path
    sandbox = _origin(config.sandbox_branch)
    tip = gitops.rev(repo, _local(code))
    if tip is None or gitops.rev(repo, sandbox) is None:
        return
    if not _needs_copy(entry, tip, sandbox):
        return
    sdbx = f"{code}-sdbx"
    keys = _keys(includes)
    exists = gitops.rev(repo, _local(sdbx)) is not None
    if not exists and gitops.rev(repo, _origin(sdbx)):
        raise ReleaseSetup(
            f"{entry.name}: {sdbx} is on origin but not here; pull it (git switch {sdbx}) first"
        )
    wt = _worktree(release, entry, sdbx, "-sdbx", None if exists else tip)
    if exists and not gitops.is_ancestor(wt, _local(code), "HEAD"):
        subject, body = text.release_merge_message(keys, text.copy_text(code))
        _merge(entry, wt, _local(code), subject, body)
    if not gitops.is_ancestor(wt, sandbox, "HEAD"):
        subject, body = text.release_merge_message(keys, text.sandbox_text(code))
        _merge(entry, wt, sandbox, subject, body)
    heads = rules.heads_at(entry, _local(sdbx))
    if len(heads) > 1 and len(rules.heads_at(entry, _local(code))) <= 1:
        raise Conflict(entry.name, wt, [], heads)


def _stale(entry: RepoEntry, code: str, multi: bool, copy_used: bool) -> list[str]:
    """A local release branch or `-sdbx` behind its origin copy ("Update branch" on GitHub)."""
    branches = ([code] if multi else []) + ([f"{code}-sdbx"] if copy_used else [])
    return [p for b in branches for p in rules.against_origin(entry.path, entry.name, b)[0]]


def run_new(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        config = load_release_config()
        day = text.day_argument(args.day)
        if day < text.today():
            raise ReleaseRefused(f"{text.compact(day)} is in the past")
        slug = folder.resolve_slug(args.project, Path.cwd())
        release = folder.release_dir(slug, day)
        names = tuple(entry.name for entry in config.repos)
        wanted = folder.read_release(release, names)
        selected = folder.select_repos(config, wanted, args.repos)
        warnings: list[str] = []
        for name in selected:
            error = gitops.fetch(config.entry(name).path)
            if error:
                warnings.append(f"{name}: fetch failed: {error}")
        published = read_published(release)
        copy_used: dict[str, bool] = {}
        for name in selected:
            entry, includes = config.entry(name), wanted.include[name]
            copy_used[name] = _sandbox_conflicts(config, entry, _code_branch(includes, day))
            _check_setup(config, entry, includes, day, published, copy_used[name])

        states: list[dict] = []
        built: list[str] = []
        blocked: list[str] = []
        suggested: dict[str, list[str]] = {}
        payload: dict = {"date": text.compact(day), "repos": states, "warnings": warnings}
        for name in selected:
            entry, includes = config.entry(name), wanted.include[name]
            code = _code_branch(includes, day)
            problems, _, order = rules.order_check(entry, includes, _origin(config.base_branch))
            problems += _stale(entry, code, len(includes) > 1, copy_used[name])
            if problems:
                blocked.append(name)
                if order != list(includes):
                    suggested[name] = order
            else:
                try:
                    _build_code(config, entry, includes, day, release)
                    _build_sdbx(config, entry, includes, code, release)
                except Conflict as stop:
                    payload["conflict"] = {
                        "repo": stop.repo,
                        "worktree": str(stop.worktree),
                        "merging": gitops.merging(stop.worktree),
                        "files": stop.files,
                    }
                    if stop.heads:
                        payload["conflict"]["alembic_heads"] = stop.heads
                        payload["conflict"]["message"] = (
                            f"{stop.repo}: {len(stop.heads)} alembic heads at the sandbox merge: "
                            f"{', '.join(stop.heads)}; add a merge migration whose down_revision "
                            f"is ({', '.join(stop.heads)}) in {stop.worktree}, commit it and run "
                            "ws release new again"
                        )
                    payload["built"] = built
                    payload["not_started"] = selected[selected.index(name) + 1 :]
                    return payload, 3
                except gitops.GitFailed as error:
                    left = selected[selected.index(name) + 1 :]
                    raise ReleaseSetup(
                        f"{name}: {error}; built before it: {', '.join(built) or 'none'}; "
                        f"not started: {', '.join(left) or 'none'}"
                    ) from None
                built.append(name)
            states.append(rules.assess(config, entry, includes, day, release).as_json())
        if suggested:
            payload["suggested_order"] = suggested
        if blocked:
            payload["not_built"] = blocked
        ready = all(state["ready"] for state in states)
        return payload, 0 if ready and not blocked else 1

    return run_release("new", action)
