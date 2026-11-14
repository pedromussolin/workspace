"""`ws release new`: builds the release branches locally, merging the task branches in order.

Nothing here pushes or calls `gh`. A merge conflict stops the command at once and leaves the
merge in progress in its worktree; the user resolves it, commits, and runs the command again.
"""

import argparse
import json
from dataclasses import dataclass
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


def _local(branch: str) -> str:
    return f"refs/heads/{branch}"


def _origin(branch: str) -> str:
    return f"refs/remotes/{gitops.REMOTE}/{branch}"


def _ref(repo: Path, branch: str) -> str | None:
    for ref in (_local(branch), _origin(branch)):
        if gitops.rev(repo, ref):
            return ref
    return None


def _published(release: Path) -> dict:
    path = release / PUBLISHED
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise ReleaseSetup(f"{path}: {error}") from None
    repos = data.get("repos") if isinstance(data, dict) else None
    return repos if isinstance(repos, dict) else {}


def _check_setup(
    config: ReleaseConfig, entry: RepoEntry, includes: tuple[str, ...], day: date, published: dict
) -> None:
    repo, name = entry.path, entry.name
    code = includes[0] if len(includes) == 1 else f"release/{text.compact(day)}"
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
    for branch in dict.fromkeys((code, f"{code}-sdbx")):
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
    _, conflicts = gitops.merge_tree(repo, tip, sandbox)
    if not conflicts:
        return
    sdbx = f"{code}-sdbx"
    keys = _keys(includes)
    exists = gitops.rev(repo, _local(sdbx)) is not None
    wt = _worktree(release, entry, sdbx, "-sdbx", None if exists else tip)
    if exists and not gitops.is_ancestor(wt, _local(code), "HEAD"):
        subject, body = text.release_merge_message(keys, text.copy_text(code))
        _merge(entry, wt, _local(code), subject, body)
    if not gitops.is_ancestor(wt, sandbox, "HEAD"):
        subject, body = text.release_merge_message(keys, text.sandbox_text(code))
        _merge(entry, wt, sandbox, subject, body)


def run_new(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        config = load_release_config()
        try:
            day = text.future_day(args.day)
        except ValueError as error:
            raise ReleaseRefused(str(error)) from None
        slug = folder.resolve_slug(args.project, Path.cwd())
        release = folder.release_dir(slug, day)
        names = tuple(entry.name for entry in config.repos)
        wanted = folder.read_release(release, names)
        selected = [n for n in wanted.repos if not args.repos or n in args.repos]
        unknown = [n for n in args.repos if n not in wanted.repos]
        if unknown:
            raise ReleaseSetup(f"{', '.join(unknown)} not in {release / 'release.toml'}")
        warnings: list[str] = []
        for name in selected:
            error = gitops.fetch(config.entry(name).path)
            if error:
                warnings.append(f"{name}: fetch failed: {error}")
        published = _published(release)
        for name in selected:
            _check_setup(config, config.entry(name), wanted.include[name], day, published)

        states: list[dict] = []
        built: list[str] = []
        suggested: dict[str, list[str]] = {}
        payload: dict = {"date": text.compact(day), "repos": states, "warnings": warnings}
        for name in selected:
            entry, includes = config.entry(name), wanted.include[name]
            problems, _, order = rules.order_check(entry, includes, _origin(config.base_branch))
            if problems:
                suggested[name] = order
            else:
                try:
                    _build_code(config, entry, includes, day, release)
                    code = includes[0] if len(includes) == 1 else f"release/{text.compact(day)}"
                    _build_sdbx(config, entry, includes, code, release)
                except Conflict as stop:
                    payload["conflict"] = {
                        "repo": stop.repo,
                        "worktree": str(stop.worktree),
                        "merging": gitops.merging(stop.worktree),
                        "files": stop.files,
                    }
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
        return payload, 0 if all(state["ready"] for state in states) else 1

    return run_release("new", action)
