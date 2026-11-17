"""Read-only collector of the activity behind the daily standup: commits, branches, PRs, plans."""

import json
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ws.userconfig import StandupConfig
from ws.workdays import previous_workday, workdays_before

KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
NEXT_STEP_HEADING = "## Próximo passo"
PR_SEARCH_LIMIT = 100
PR_QUERY = (
    "query($q:String!){search(query:$q,type:ISSUE,first:100){issueCount nodes{"
    "... on PullRequest{number title state mergedAt updatedAt headRefName url repository{name}}}}}"
)
PERIOD_PR_QUERY = (
    "query($q:String!,$after:String){search(query:$q,type:ISSUE,first:100,after:$after){"
    "issueCount pageInfo{hasNextPage endCursor} nodes{... on PullRequest{number title state "
    "mergedAt createdAt closedAt updatedAt baseRefName headRefName url repository{name}}}}}"
)
PERIOD_PR_PAGES = 3
FIELD_SEPARATOR = "\x1f"


def keys_in(text: str) -> list[str]:
    return list(dict.fromkeys(KEY.findall(text)))


def _git(repo: Path, *args: str, ok: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode not in ok:
        raise RuntimeError(f"git {args[0]} failed in {repo}: {result.stderr.strip()}")
    return result.stdout


def _lines(output: str) -> list[str]:
    # splitlines() would also break on \x85, \u2028 and \x1c-\x1e, which can appear in a subject.
    return [line for line in output.split("\n") if line]


def _is_repo(path: Path) -> bool:
    return not path.name.startswith(".") and path.is_dir() and (path / ".git").exists()


def find_repos(cfg: StandupConfig, workspace: Path, warnings: list[str]) -> list[Path]:
    own = workspace.resolve()
    repos: list[Path] = []
    for root in cfg.repo_roots:
        if not root.is_dir():
            warnings.append(f"repo root {root} does not exist")
            continue
        repos.extend(
            child for child in root.iterdir() if _is_repo(child) and child.resolve() != own
        )
    return sorted(repos, key=lambda repo: repo.name)


def _author_email(repo: Path) -> str | None:
    # Exit 1 is git's answer for "not set".
    email = _git(repo, "config", "user.email", ok=(0, 1)).strip()
    return email or None


def _own_commits(repo: Path, email: str, since: date, until: date | None = None) -> list[dict]:
    # The stash commits carry the user's author and the branch name, but are not work done.
    bounds = [f"--since={since.isoformat()} 00:00:00"]
    if until is not None:
        bounds.append(f"--until={until.isoformat()} 23:59:59")
    out = _git(
        repo,
        "log",
        "--exclude=refs/stash",
        "--all",
        *bounds,
        f"--author=<{email}>",
        "--fixed-strings",
        "--date=short",
        f"--format=%H{FIELD_SEPARATOR}%ad{FIELD_SEPARATOR}%s",
    )
    commits = []
    for line in _lines(out):
        sha, day, subject = line.split(FIELD_SEPARATOR, 2)
        commits.append(
            {
                "repo": repo.name,
                "sha": sha,
                "date": day,
                "subject": subject,
                "keys": keys_in(subject),
            }
        )
    return commits


def _created_on(common_dir: Path, name: str) -> date | None:
    """Day of the first reflog entry of the branch; None when there is no readable reflog."""
    try:
        with (common_dir / "logs" / "refs" / "heads" / name).open(
            encoding="utf-8", errors="replace"
        ) as handle:
            first = handle.readline()
        stamp, zone = first.split("\t", 1)[0].rsplit(" ", 2)[1:]
        offset = timedelta(hours=int(zone[1:3]), minutes=int(zone[3:5]))
        if zone[0] == "-":
            offset = -offset
        return datetime.fromtimestamp(int(stamp), timezone(offset)).date()
    except (OSError, ValueError, IndexError, OverflowError):
        return None


def _branches(
    repo: Path, stale_since: date, listed: set[tuple[str, str]], until: date | None = None
) -> list[dict]:
    common_dir = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    out = _git(
        repo,
        "for-each-ref",
        f"--format=%(refname:short){FIELD_SEPARATOR}%(committerdate:short)",
        "refs/heads",
    )
    branches = []
    for line in _lines(out):
        name, tip = line.split(FIELD_SEPARATOR, 1)
        keys = keys_in(name)
        if not keys or (common_dir, name) in listed:
            continue
        created = _created_on(Path(common_dir), name)
        if until is None:
            recent = tip >= stale_since.isoformat() or (
                created is not None and created >= stale_since
            )
        else:
            tip_in = stale_since.isoformat() <= tip <= until.isoformat()
            created_in = created is not None and stale_since <= created <= until
            recent = tip_in or created_in
        if not recent:
            continue
        listed.add((common_dir, name))
        branches.append({"repo": repo.name, "name": name, "keys": keys})
    return branches


def _parse_prs(answer: str, warnings: list[str]) -> list[dict]:
    found = json.loads(answer)["data"]["search"]
    prs = [
        {
            "repo": node["repository"]["name"],
            "number": node["number"],
            "title": node["title"],
            "state": node["state"].lower(),
            "merged_at": node["mergedAt"],
            "updated_at": node["updatedAt"],
            "url": node["url"],
            "keys": keys_in(f"{node['title']} {node['headRefName']}"),
        }
        for node in found["nodes"]
        if node
    ]
    if found["issueCount"] > PR_SEARCH_LIMIT:
        warnings.append(f"gh: {found['issueCount']} PRs found, only the first 100 were read")
    return prs


def _pull_requests(gh: str, stale_since: date, warnings: list[str]) -> list[dict]:
    search = f"is:pr author:@me updated:>={stale_since.isoformat()}"
    try:
        result = subprocess.run(
            [gh, "api", "graphql", "-f", f"query={PR_QUERY}", "-f", f"q={search}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            lines = result.stderr.strip().splitlines()
            raise RuntimeError(lines[0] if lines else f"exit {result.returncode}")
        return _parse_prs(result.stdout, warnings)
    except (OSError, RuntimeError) as error:
        warnings.append(f"gh: PRs left out ({error})")
    except (ValueError, LookupError, TypeError, AttributeError) as error:
        warnings.append(f"gh: PRs left out (unexpected answer: {type(error).__name__} {error})")
    return []


def _gh_graphql(gh: str, query: str, search: str, after: str | None) -> str:
    command = [gh, "api", "graphql", "-f", f"query={query}", "-f", f"q={search}"]
    if after:
        command += ["-f", f"after={after}"]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines()
        raise RuntimeError(lines[0] if lines else f"exit {result.returncode}")
    return result.stdout


def _local_day(stamp: str | None) -> date | None:
    return None if stamp is None else datetime.fromisoformat(stamp).astimezone().date()


def _pr_in_period(pr: dict, since: date, until: date) -> bool:
    if pr["state"] == "open":
        return True
    days = (_local_day(pr[name]) for name in ("created_at", "merged_at", "closed_at"))
    return any(day is not None and since <= day <= until for day in days)


def _period_pr(node: dict) -> dict:
    return {
        "repo": node["repository"]["name"],
        "number": node["number"],
        "title": node["title"],
        "state": node["state"].lower(),
        "base": node["baseRefName"],
        "created_at": node["createdAt"],
        "closed_at": node["closedAt"],
        "merged_at": node["mergedAt"],
        "updated_at": node["updatedAt"],
        "url": node["url"],
        "keys": keys_in(f"{node['title']} {node['headRefName']}"),
    }


def _period_pull_requests(gh: str, since: date, until: date, warnings: list[str]) -> list[dict]:
    search = f"is:pr author:@me updated:>={since.isoformat()}"
    prs: list[dict] = []
    after = None
    try:
        for _ in range(PERIOD_PR_PAGES):
            found = json.loads(_gh_graphql(gh, PERIOD_PR_QUERY, search, after))["data"]["search"]
            prs.extend(_period_pr(node) for node in found["nodes"] if node)
            if not found["pageInfo"]["hasNextPage"]:
                break
            after = found["pageInfo"]["endCursor"]
        else:
            warnings.append(
                f"gh: {found['issueCount']} PRs found, only the first "
                f"{PERIOD_PR_PAGES * 100} were read"
            )
    except (OSError, RuntimeError) as error:
        warnings.append(f"gh: PRs left out ({error})")
    except (ValueError, LookupError, TypeError, AttributeError) as error:
        warnings.append(f"gh: PRs left out (unexpected answer: {type(error).__name__} {error})")
    return [pr for pr in prs if _pr_in_period(pr, since, until)]


def _section(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    if heading not in lines:
        return None
    body: list[str] = []
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith(("# ", "## ")):
            break
        body.append(line)
    return "\n".join(body).strip()


def _next_steps(workspace: Path, warnings: list[str]) -> list[dict]:
    steps = []
    for path in sorted((workspace / "projects").glob("*/CONTINUE.md")):
        text = _section(path.read_text(encoding="utf-8"), NEXT_STEP_HEADING)
        if text is None:
            warnings.append(f"project {path.parent.name}: CONTINUE.md has no '{NEXT_STEP_HEADING}'")
            continue
        steps.append({"project": path.parent.name, "text": text})
    return steps


def collect(
    cfg: StandupConfig,
    today: date,
    workspace: Path,
    gh: str = "gh",
    *,
    since: date | None = None,
    until: date | None = None,
) -> dict:
    period = since is not None
    if until is not None and since is None:
        raise ValueError("until needs since")
    if since is not None:
        until = until or today
        stale_since = since
    else:
        since = previous_workday(today)
        stale_since = workdays_before(today, cfg.stale_workdays)
    warnings: list[str] = []
    commits: list[dict] = []
    branches: list[dict] = []
    last_activity: dict[str, str] = {}
    seen: set[str] = set()
    listed_branches: set[tuple[str, str]] = set()
    for repo in find_repos(cfg, workspace, warnings):
        try:
            branches.extend(
                _branches(repo, stale_since, listed_branches, until if period else None)
            )
            email = _author_email(repo)
            found = (
                []
                if email is None
                else _own_commits(repo, email, min(since, stale_since), until if period else None)
            )
        except RuntimeError as error:
            warnings.append(f"repo {repo.name}: left out ({error})")
            continue
        if email is None:
            warnings.append(f"repo {repo.name}: git user.email is not set, commits left out")
        for item in found:
            if item["sha"] in seen:
                continue
            seen.add(item["sha"])
            if period and item["date"] > until.isoformat():
                continue
            if item["date"] >= since.isoformat():
                commits.append(item)
            if item["date"] >= stale_since.isoformat():
                for key in item["keys"]:
                    last_activity[key] = max(item["date"], last_activity.get(key, ""))
    if period:
        window = {"since": since.isoformat(), "until": until.isoformat(), "kind": "period"}
        prs = _period_pull_requests(gh, since, until, warnings)
    else:
        window = {"since": since.isoformat(), "until": today.isoformat(), "kind": "daily"}
        prs = _pull_requests(gh, stale_since, warnings)
    return {
        "window": window,
        "commits": commits,
        "branches": branches,
        "prs": prs,
        "last_activity": last_activity,
        "next_steps": _next_steps(workspace, warnings),
        "warnings": warnings,
    }
