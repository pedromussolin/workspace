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
from ws.release.settings import ReleaseConfig, load_release_config

SANDBOX = "-sandbox"
RELEASE_HEAD = re.compile(r"release/(\d{8})(-sdbx)?")
FOLDER = re.compile(r"release-(\d{8})")


def links(config: ReleaseConfig, prs: dict[str, PullRequest]) -> list[str]:
    """`prs` is keyed by `repo` and `repo-sandbox`: code PRs in the given order, then sandbox."""
    lines = []
    for sandbox in (False, True):
        for ref, pr in prs.items():
            if ref.endswith(SANDBOX) != sandbox:
                continue
            name = config.entry(ref.removesuffix(SANDBOX)).repo_name
            label = f"{name} (sandbox)" if sandbox else name
            lines.append(f"{label}, PR #{pr.number}: {pr.url}")
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
    base = data_dir() / "projects" / slug
    if base.is_dir():
        for path in sorted(base.iterdir()):
            match = FOLDER.fullmatch(path.name)
            if match and path.is_dir():
                rows[match.group(1)] = {"date": match.group(1), "folder": True, "open_prs": []}
    for entry in config.repos:
        for pr in gh.prs(entry.slug, state="open"):
            match = RELEASE_HEAD.match(pr.head)
            if match:
                row = rows.setdefault(
                    match.group(1), {"date": match.group(1), "folder": False, "open_prs": []}
                )
                row["open_prs"].append(
                    {"repo": entry.name, "number": pr.number, "base": pr.base, "url": pr.url}
                )
    return {"releases": [rows[key] for key in sorted(rows)]}


def _day(config: ReleaseConfig, slug: str, day: date, gh: Gh, with_links: bool) -> tuple[dict, int]:
    folder = release_folder.release_dir(slug, day)
    if not folder.is_dir():
        raise ReleaseSetup(f"{folder} not found")
    release = release_folder.read_release(folder, tuple(repo.name for repo in config.repos))
    repos: list[dict] = []
    found: dict[str, PullRequest] = {}
    for name in release.repos:
        entry = config.entry(name)
        warning = gitops.fetch(entry.path)
        state = rules.assess(config, entry, release.include[name], day, folder)
        row = state.as_json()
        row["warnings"] = state.warnings + ([f"fetch failed: {warning}"] if warning else [])
        row["prs"] = []
        code = _pick(gh.prs(entry.slug, head=state.code_branch, base=config.base_branch))
        sandbox = _pick(gh.prs(entry.slug, head=state.sandbox_head, base=config.sandbox_branch))
        for kind, ref, pr in (("code", name, code), ("sandbox", name + SANDBOX, sandbox)):
            if pr:
                found[ref] = pr
                row["prs"].append(_pr_json(gh, entry.slug, pr, kind))
            elif with_links:
                missing = f"{name}: no {kind} PR for {state.code_branch}; the links are incomplete"
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
            try:
                day = text.parse_day(args.day)
            except ValueError as error:
                raise ReleaseSetup(str(error)) from error
            return _day(config, slug, day, gh, args.links)
        except (GhMissing, GhFailed, GhUncertain) as error:
            raise ReleaseSetup(f"gh: {error}") from error

    return run("status", action)
