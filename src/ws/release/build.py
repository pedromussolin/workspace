"""`ws release new`: builds the release branches locally, merging the task branches in order.

Nothing here pushes or calls `gh`. A merge conflict stops the command at once and leaves the
merge in progress in its worktree; the user resolves it, commits, and runs the command again.
Each selected environment gets its copy of the code branch (`<code><suffix>`), always: the code
branch merged, then the environment branch. Two Alembic heads at a clean environment merge count
as a conflict: the user adds the merge migration in the copy.
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ws.release import ReleaseRefused, ReleaseSetup, folder, gitops, rules, text
from ws.release import run as run_release
from ws.release.settings import Environment, ReleaseConfig, RepoEntry, load_release_config

PUBLISHED = "published.json"


@dataclass
class Conflict(Exception):
    repo: str
    worktree: Path
    files: list[str]
    heads: list[str] = field(default_factory=list)
    env: str = ""


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


def _check_setup(
    config: ReleaseConfig,
    entry: RepoEntry,
    includes: tuple[str, ...],
    day: date,
    published: dict,
    envs: tuple[Environment, ...],
) -> None:
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
    for branch in [code, *(f"{code}{env.suffix}" for env in envs)]:
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


def _build_copy(
    entry: RepoEntry,
    includes: tuple[str, ...],
    code: str,
    release: Path,
    env: Environment,
) -> str | None:
    """The copy of `code` for `env`: the code branch, then `origin/<env.branch>`. A warning when
    origin lacks the environment branch (the copy is skipped)."""
    repo = entry.path
    env_ref = _origin(env.branch)
    code_ref = _ref(repo, code)
    if code_ref is None:
        return None
    if gitops.rev(repo, env_ref) is None:
        return f"{entry.name}: origin/{env.branch} does not exist; the {env.name} copy is skipped"
    tip = gitops.rev(repo, code_ref)
    copy = f"{code}{env.suffix}"
    keys = _keys(includes)
    exists = gitops.rev(repo, _local(copy)) is not None
    if not exists and gitops.rev(repo, _origin(copy)):
        raise ReleaseSetup(
            f"{entry.name}: {copy} is on origin but not here; pull it (git switch {copy}) first"
        )
    wt = _worktree(release, entry, copy, env.suffix, None if exists else tip)
    if exists and not gitops.is_ancestor(wt, code_ref, "HEAD"):
        subject, body = text.release_merge_message(keys, text.copy_text(code))
        _merge(entry, wt, code_ref, subject, body)
    if not gitops.is_ancestor(wt, env_ref, "HEAD"):
        subject, body = text.release_merge_message(keys, text.environment_text(code, env.branch))
        _merge(entry, wt, env_ref, subject, body)
    heads = rules.heads_at(entry, _local(copy))
    if len(heads) > 1 and len(rules.heads_at(entry, code_ref)) <= 1:
        raise Conflict(entry.name, wt, [], heads, env.name)
    return None


def _stale(entry: RepoEntry, code: str, multi: bool, envs: tuple[Environment, ...]) -> list[str]:
    """A local release branch or copy behind its origin copy ("Update branch" on GitHub)."""
    branches = ([code] if multi else []) + [f"{code}{env.suffix}" for env in envs]
    return [p for b in branches for p in rules.against_origin(entry.path, entry.name, b)[0]]


def run_new(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        config = load_release_config()
        day = text.day_argument(args.day)
        if day < text.today():
            raise ReleaseRefused(f"{text.compact(day)} is in the past")
        slug = folder.resolve_slug(args.project, Path.cwd())
        release = folder.release_dir(slug, day)
        envs = config.select(args.envs)
        names = tuple(entry.name for entry in config.repos)
        wanted = folder.read_release(release, names)
        selected = folder.select_repos(config, wanted, args.repos)
        warnings: list[str] = []
        for name in selected:
            error = gitops.fetch(config.entry(name).path)
            if error:
                warnings.append(f"{name}: fetch failed: {error}")
        published = read_published(release)
        for name in selected:
            entry, includes = config.entry(name), wanted.include[name]
            _check_setup(config, entry, includes, day, published, envs)

        states: list[dict] = []
        built: list[str] = []
        blocked: list[str] = []
        suggested: dict[str, list[str]] = {}
        payload: dict = {"date": text.compact(day), "repos": states, "warnings": warnings}
        for name in selected:
            entry, includes = config.entry(name), wanted.include[name]
            code = _code_branch(includes, day)
            problems, _, order = rules.order_check(entry, includes, _origin(config.base_branch))
            problems += _stale(entry, code, len(includes) > 1, envs)
            if problems:
                blocked.append(name)
                if order != list(includes):
                    suggested[name] = order
            else:
                try:
                    _build_code(config, entry, includes, day, release)
                    for env in envs:
                        skipped = _build_copy(entry, includes, code, release, env)
                        if skipped:
                            warnings.append(skipped)
                except Conflict as stop:
                    payload["conflict"] = {
                        "repo": stop.repo,
                        "worktree": str(stop.worktree),
                        "merging": gitops.merging(stop.worktree),
                        "files": stop.files,
                    }
                    if stop.heads:
                        payload["conflict"]["alembic_heads"] = stop.heads
                        listed = ", ".join(stop.heads)
                        payload["conflict"]["message"] = (
                            f"{stop.repo}: {len(stop.heads)} alembic heads at the {stop.env} "
                            f"copy: {listed}; add a merge migration whose down_revision is "
                            f"({listed}) in {stop.worktree}, commit it and run "
                            f"ws release new --env {stop.env} again"
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
            states.append(rules.assess(config, entry, includes, day, release, envs).as_json())
        if suggested:
            payload["suggested_order"] = suggested
        if blocked:
            payload["not_built"] = blocked
        ready = all(state["ready"] for state in states)
        return payload, 0 if ready and not blocked else 1

    return run_release("new", action)
