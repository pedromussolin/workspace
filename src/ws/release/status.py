"""`ws release status`: where a release stands, and the PR links for the GMUD.

Read-only: the only git write is the `fetch --prune` of remote-tracking refs, and `gh` is only
read. Without a day it lists the releases of the project; with one it reports each repo.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from ws.config import data_dir
from ws.release import ReleaseSetup, gitops, rules, run, text
from ws.release import folder as release_folder
from ws.release.github import Gh, GhFailed, GhMissing, GhUncertain, PullRequest
from ws.release.settings import ReleaseConfig, RepoEntry, load_release_config

FOLDER = re.compile(r"release-(\d{8})")


def _release_head(config: ReleaseConfig) -> re.Pattern[str]:
    suffixes = "|".join(re.escape(env.suffix) for env in config.environments)
    return re.compile(rf"release/(\d{{8}})(?:{suffixes})?" if suffixes else r"release/(\d{8})")


def links(config: ReleaseConfig, prs: dict[str, PullRequest]) -> list[str]:
    """`prs` is keyed by `repo` and `repo-ENV`: the code PRs in the given order, then each
    environment in config order."""
    names = {entry.name for entry in config.repos}
    lines = []
    for env in (None, *config.environments):
        for ref, pr in prs.items():
            if env is None:
                name, label = ref, None
            else:
                name = ref.removesuffix(f"-{env.name}")
                label = env.name
                if name == ref:
                    continue
            if name not in names or (env is None) != (label is None):
                continue
            repo = config.entry(name).repo_name
            lines.append(f"{repo + (f' ({label})' if label else '')}, PR #{pr.number}: {pr.url}")
    return lines


def _pick(found: list[PullRequest]) -> PullRequest | None:
    live = [pr for pr in found if pr.state != "CLOSED" or pr.merged_at]
    return max(live, key=lambda pr: pr.number) if live else None


def _pr_json(gh: Gh, slug: str, pr: PullRequest, kind: str) -> dict:
    extra = gh.checks(slug, pr.number)
    return {
        "kind": kind,
        "number": pr.number,
        "state": pr.state,
        "base": pr.base,
        "url": pr.url,
        "mergeable": extra["mergeable"],
        "checks": extra["checks"],
    }


def _releases(config: ReleaseConfig, slug: str, gh: Gh) -> dict:
    rows: dict[str, dict] = {}

    def row(day: str, folder: bool = False) -> dict:
        return rows.setdefault(day, {"date": day, "folder": folder, "branches": [], "open_prs": []})

    base = data_dir() / "projects" / slug
    if base.is_dir():
        for path in sorted(base.iterdir()):
            match = FOLDER.fullmatch(path.name)
            if match and path.is_dir():
                row(match.group(1), folder=True)
    warnings: list[str] = []
    release_head = _release_head(config)
    for entry in config.repos:
        error = gitops.fetch(entry.path)
        if error:
            warnings.append(f"{entry.name}: fetch failed: {error}")
        for branch in gitops.remote_branches(entry.path, "release/"):
            match = release_head.fullmatch(branch)
            if match:
                row(match.group(1))["branches"].append({"repo": entry.name, "branch": branch})
        for pr in gh.prs(entry.slug, state="open"):
            match = release_head.fullmatch(pr.head)
            if match:
                row(match.group(1))["open_prs"].append(
                    {"repo": entry.name, "number": pr.number, "base": pr.base, "url": pr.url}
                )
    return {"releases": [rows[key] for key in sorted(rows)], "warnings": warnings}


def _is_merged(
    config: ReleaseConfig, entry: RepoEntry, branch: str, pr: PullRequest | None
) -> bool:
    """The code PR is merged, or every copy of the code branch is already in `origin/master`."""
    if pr is not None and (pr.merged_at or pr.state.upper() == "MERGED"):
        return True
    base = f"refs/remotes/{gitops.REMOTE}/{config.base_branch}"
    refs = (f"refs/heads/{branch}", f"refs/remotes/{gitops.REMOTE}/{branch}")
    tips = [tip for tip in (gitops.rev(entry.path, ref) for ref in refs) if tip]
    return bool(tips) and all(gitops.is_ancestor(entry.path, tip, base) for tip in tips)


def _merged_row(entry: RepoEntry, includes: tuple[str, ...], code_branch: str) -> dict:
    tip = gitops.rev(entry.path, f"refs/remotes/{gitops.REMOTE}/{code_branch}")
    return {
        "repo": entry.name,
        "shape": "single" if len(includes) == 1 else "multi",
        "includes": list(includes),
        "code_branch": code_branch,
        "tip": tip or gitops.rev(entry.path, f"refs/heads/{code_branch}"),
        "merged": True,
        "environments": {},
        "problems": [],
        "warnings": [],
    }


def _envs_in_scope(config: ReleaseConfig, entry: RepoEntry, code_branch: str) -> tuple:
    """The default environments, and any other whose copy of the code branch exists here or on
    origin."""
    return tuple(
        env
        for env in config.environments
        if env.default
        or any(
            gitops.rev(entry.path, ref)
            for ref in (
                f"refs/heads/{code_branch}{env.suffix}",
                f"refs/remotes/{gitops.REMOTE}/{code_branch}{env.suffix}",
            )
        )
    )


def _day(config: ReleaseConfig, slug: str, day: date, gh: Gh, with_links: bool) -> tuple[dict, int]:
    folder = release_folder.release_dir(slug, day)
    release = release_folder.read_release(folder, tuple(repo.name for repo in config.repos))
    repos: list[dict] = []
    found: dict[str, PullRequest] = {}
    for name in release_folder.select_repos(config, release, []):
        entry, includes = config.entry(name), release.include[name]
        warning = gitops.fetch(entry.path)
        code_branch = includes[0] if len(includes) == 1 else f"release/{text.compact(day)}"
        code = _pick(gh.prs(entry.slug, head=code_branch, base=config.base_branch))
        envs = _envs_in_scope(config, entry, code_branch)
        if _is_merged(config, entry, code_branch, code):
            row = _merged_row(entry, includes, code_branch)
        else:
            row = {
                **rules.assess(config, entry, includes, day, folder, envs).as_json(),
                "merged": False,
            }
        row["warnings"] = row["warnings"] + ([f"fetch failed: {warning}"] if warning else [])
        row["prs"] = []
        wanted = [("code", name, code)]
        for env in envs:
            heads = dict.fromkeys((f"{code_branch}{env.suffix}", code_branch))
            prs = [pr for head in heads for pr in gh.prs(entry.slug, head=head, base=env.branch)]
            wanted.append((env.name, f"{name}-{env.name}", _pick(prs)))
        for kind, ref, pr in wanted:
            if pr:
                found[ref] = pr
                row["prs"].append(_pr_json(gh, entry.slug, pr, kind))
            elif with_links:
                missing = f"{name}: no {kind} PR for {code_branch}; the links are incomplete"
                row["warnings"].append(missing)
                print(f"ws release status: {missing}", file=sys.stderr)
        repos.append(row)
    payload: dict = {"date": text.compact(day), "repos": repos}
    if with_links:
        payload["links"] = links(config, found)
    return payload, 1 if any(row["problems"] for row in repos) else 0


def run_status(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        config = load_release_config()
        gh = Gh()
        try:
            gh.require_auth()
            slug = release_folder.resolve_slug(args.project, Path.cwd())
            if args.day is None:
                return _releases(config, slug, gh), 0
            return _day(config, slug, text.day_argument(args.day), gh, args.links)
        except (GhMissing, GhFailed, GhUncertain) as error:
            raise ReleaseSetup(f"gh: {error}") from error

    return run("status", action)
