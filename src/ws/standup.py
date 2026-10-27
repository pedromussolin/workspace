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
    "... on PullRequest{number title state mergedAt headRefName url repository{name}}}}}"
)
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


def _find_repos(cfg: StandupConfig, workspace: Path, warnings: list[str]) -> list[Path]:
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


def _own_commits(repo: Path, email: str, since: date) -> list[dict]:
    # The stash commits carry the user's author and the branch name, but are not work done.
    out = _git(
        repo,
        "log",
        "--exclude=refs/stash",
        "--all",
        f"--since={since.isoformat()} 00:00:00",
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


def _branches(repo: Path, stale_since: date, listed: set[tuple[str, str]]) -> list[dict]:
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
        if tip < stale_since.isoformat() and (created is None or created < stale_since):
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
            "url": node["url"],
            "keys": keys_in(f"{node['title']} {node['headRefName']}"),
        }
        for node in found["nodes"]
        if node
    ]
    if found["issueCount"] > PR_SEARCH_LIMIT:
        warnings.append(f"gh: {found['issueCount']} PRs found, only the first 100 were read")
    return prs


def _pull_requests(gh: str, since: date, warnings: list[str]) -> list[dict]:
    search = f"is:pr author:@me updated:>={since.isoformat()}"
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


def _section(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    if heading not in lines:
        return None
    body: list[str] = []
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith("## "):
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


def collect(cfg: StandupConfig, today: date, workspace: Path, gh: str = "gh") -> dict:
    since = previous_workday(today)
    stale_since = workdays_before(today, cfg.stale_workdays)
    warnings: list[str] = []
    commits: list[dict] = []
    branches: list[dict] = []
    last_activity: dict[str, str] = {}
    seen: set[str] = set()
    listed_branches: set[tuple[str, str]] = set()
    for repo in _find_repos(cfg, workspace, warnings):
        try:
            branches.extend(_branches(repo, stale_since, listed_branches))
            email = _author_email(repo)
            found = [] if email is None else _own_commits(repo, email, min(since, stale_since))
        except RuntimeError as error:
            warnings.append(f"repo {repo.name}: left out ({error})")
            continue
        if email is None:
            warnings.append(f"repo {repo.name}: git user.email is not set, commits left out")
        for item in found:
            if item["sha"] in seen:
                continue
            seen.add(item["sha"])
            if item["date"] >= since.isoformat():
                commits.append(item)
            if item["date"] >= stale_since.isoformat():
                for key in item["keys"]:
                    last_activity[key] = max(item["date"], last_activity.get(key, ""))
    return {
        "window": {"since": since.isoformat(), "until": today.isoformat()},
        "commits": commits,
        "branches": branches,
        "prs": _pull_requests(gh, since, warnings),
        "last_activity": last_activity,
        "next_steps": _next_steps(workspace, warnings),
        "warnings": warnings,
    }
