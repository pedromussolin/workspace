"""Handoff of a chat to a new one (part A of the session automations spec).

`collect` reads the state of the repos, worktrees and open PRs; `find_handoffs` lists the handoff
files the session hook points at. Everything here is read-only except `new_handoff` and `refresh`,
which write only the private handoff file.
"""

import glob
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from ws import config
from ws.userconfig import StandupConfig

GIT_TIMEOUT = 15
FIELD = "\x1f"
LOCAL_BRANCH_DAYS = 14
UNCOMMITTED_CAP = 10
HANDOFF_FILE = "HANDOFF-*.md"
CLOSED_MARK = "Status: encerrado"
HEAD_LINES = 10
HOOK_ERROR_DAYS = 7
PR_LIMIT = 50
PR_QUERY = (
    "query($q:String!){search(query:$q,type:ISSUE,first:50){issueCount nodes{"
    "... on PullRequest{number title url baseRefName headRefName isDraft reviewDecision "
    "updatedAt repository{name}}}}}"
)
TRACK = re.compile(r"ahead (\d+)|behind (\d+)|gone")


class HandoffError(Exception):
    """A handoff command refused or could not read what it was given."""


class _GitFailed(Exception):
    pass


def _tilde(path: Path | str) -> str:
    text = str(path)
    home = str(Path.home())
    if text == home:
        return "~"
    return "~" + text[len(home) :] if text.startswith(home + os.sep) else text


def _git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=GIT_TIMEOUT,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except subprocess.TimeoutExpired:
        raise _GitFailed(f"git {args[0]} timed out after {GIT_TIMEOUT} s") from None
    except OSError as error:
        raise _GitFailed(f"git {args[0]}: {error}") from None
    if result.returncode != 0:
        raise _GitFailed(f"git {args[0]} failed: {result.stderr.strip() or result.returncode}")
    return result.stdout


def _git_ok(repo: Path, *args: str) -> str | None:
    """The output, or None when git exits non-zero (an expected 'not set')."""
    try:
        return _git(repo, *args)
    except _GitFailed as error:
        if "timed out" in str(error):
            raise
        return None


def _is_repo(path: Path) -> bool:
    return not path.name.startswith(".") and path.is_dir() and (path / ".git").exists()


def _find_repos(cfg: StandupConfig, workspace: Path, warnings: list[str]) -> list[Path]:
    repos: dict[Path, Path] = {}
    for root in cfg.repo_roots:
        if not root.is_dir():
            warnings.append(f"repo root {_tilde(root)} does not exist")
            continue
        for child in sorted(root.iterdir(), key=lambda item: item.name):
            if _is_repo(child):
                repos[child.resolve()] = child
    if (workspace / ".git").exists():
        repos.setdefault(workspace.resolve(), workspace)
    return list(repos.values())


def _track(text: str) -> tuple[int, int, bool]:
    ahead = behind = 0
    gone = False
    for match in TRACK.finditer(text):
        if match.group(1):
            ahead = int(match.group(1))
        elif match.group(2):
            behind = int(match.group(2))
        else:
            gone = True
    return ahead, behind, gone


def _uncommitted(repo: Path) -> dict:
    out = _git(repo, "status", "--porcelain=v1", "-z")
    records = out.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4:
            continue
        paths.append(record[3:])
        if record[0] in "RC" or record[1] in "RC":
            index += 1
    return {
        "count": len(paths),
        "paths": paths[:UNCOMMITTED_CAP],
        "more": max(0, len(paths) - UNCOMMITTED_CAP),
    }


def _branch_table(repo: Path) -> dict[str, dict]:
    out = _git(
        repo,
        "for-each-ref",
        f"--format=%(refname:short){FIELD}%(upstream:short){FIELD}%(upstream:track){FIELD}"
        f"%(committerdate:unix){FIELD}%(committerdate:short)",
        "refs/heads",
    )
    table = {}
    for line in out.split("\n"):
        if not line:
            continue
        name, upstream, track, stamp, day = line.split(FIELD)
        ahead, behind, gone = _track(track)
        table[name] = {
            "upstream": upstream or None,
            "ahead": ahead,
            "behind": behind,
            "gone": gone,
            "stamp": int(stamp or 0),
            "day": day,
        }
    return table


def _parse_worktrees(out: str) -> list[dict]:
    blocks = []
    for chunk in out.split("\n\n"):
        entry: dict = {"locked": False, "prunable": False, "branch": None, "detached": False}
        for line in chunk.splitlines():
            key, _, value = line.partition(" ")
            if key == "worktree":
                entry["path"] = value
            elif key == "HEAD":
                entry["head"] = value[:7]
            elif key == "branch":
                entry["branch"] = value.removeprefix("refs/heads/")
            elif key == "detached":
                entry["detached"] = True
            elif key in ("locked", "prunable"):
                entry[key] = True
        if "path" in entry:
            blocks.append(entry)
    return blocks


def _ahead_of_default(repo: Path, default: str | None, branch: str) -> int | None:
    if default is None:
        return None
    for base in (f"origin/{default}", default):
        out = _git_ok(repo, "rev-list", "--count", f"{base}..{branch}")
        if out is not None:
            return int(out.strip())
    return None


def _worktrees(
    repo: Path, branches: dict[str, dict], main_branch: str | None, default: str | None
) -> tuple[list, set]:
    entries = _parse_worktrees(_git(repo, "worktree", "list", "--porcelain"))[1:]
    found = []
    checked_out = {main_branch} if main_branch else set()
    for entry in entries:
        branch = entry["branch"]
        info = branches.get(branch or "", {})
        if branch:
            checked_out.add(branch)
        state = None if entry["prunable"] else _uncommitted(Path(entry["path"]))["count"]
        ahead = info.get("ahead", 0)
        if branch and info and info["upstream"] is None:
            ahead = _ahead_of_default(repo, default, branch) or 0
        found.append(
            {
                "path": _tilde(entry["path"]),
                "branch": branch,
                "head": entry.get("head", ""),
                "uncommitted": state,
                "ahead": ahead,
                "behind": info.get("behind", 0),
                "locked": entry["locked"],
                "prunable": entry["prunable"],
            }
        )
    return found, checked_out


def _local_branches(
    repo: Path,
    branches: dict[str, dict],
    default: str | None,
    skip: set[str],
    now: datetime,
) -> list[dict]:
    since = (now - timedelta(days=LOCAL_BRANCH_DAYS)).timestamp()
    found = []
    for name, info in branches.items():
        if name in skip or name == default or info["stamp"] < since:
            continue
        if info["upstream"] is None:
            ahead = _ahead_of_default(repo, default, name)
            if ahead == 0:
                continue
        elif info["ahead"] > 0:
            ahead = info["ahead"]
        else:
            continue
        found.append(
            {
                "name": name,
                "ahead": ahead,
                "upstream": info["upstream"],
                "last_commit": info["day"],
            }
        )
    return sorted(found, key=lambda item: item["name"])


def _repo_state(repo: Path, now: datetime) -> dict:
    current = _git(repo, "branch", "--show-current").strip() or None
    detached = None if current else _git(repo, "rev-parse", "--short", "HEAD").strip()
    head_ref = _git_ok(repo, "symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD")
    default = head_ref.strip().removeprefix("origin/") if head_ref else None
    branches = _branch_table(repo)
    info = branches.get(current or "", {})
    worktrees, checked_out = _worktrees(repo, branches, current, default)
    stashes = len([line for line in _git(repo, "stash", "list").split("\n") if line])
    return {
        "name": repo.name,
        "path": _tilde(repo),
        "branch": current,
        "detached": detached,
        "default_branch": default,
        "upstream": info.get("upstream"),
        "ahead": info.get("ahead", 0),
        "behind": info.get("behind", 0),
        "gone": info.get("gone", False),
        "uncommitted": _uncommitted(repo),
        "stashes": stashes,
        "worktrees": worktrees,
        "local_branches": _local_branches(repo, branches, default, checked_out, now),
    }


def _has_something_to_say(state: dict) -> bool:
    default = state["default_branch"]
    off_default = state["detached"] is not None or (
        state["branch"] != default if default else state["branch"] not in ("main", "master")
    )
    return bool(
        off_default
        or state["ahead"]
        or state["behind"]
        or state["gone"]
        or state["uncommitted"]["count"]
        or state["stashes"]
        or state["worktrees"]
        or state["local_branches"]
    )


def _parse_prs(answer: str, warnings: list[str]) -> list[dict]:
    found = json.loads(answer)["data"]["search"]
    if found["issueCount"] > PR_LIMIT:
        warnings.append(f"gh: {found['issueCount']} open PRs found, only the first {PR_LIMIT} read")
    return [
        {
            "repo": node["repository"]["name"],
            "number": node["number"],
            "title": node["title"],
            "url": node["url"],
            "base": node["baseRefName"],
            "head": node["headRefName"],
            "draft": node["isDraft"],
            "review": node["reviewDecision"],
            "updated": node["updatedAt"],
        }
        for node in found["nodes"]
        if node
    ]


def _open_prs(gh: str, warnings: list[str]) -> list[dict]:
    try:
        result = subprocess.run(
            [gh, "api", "graphql", "-f", f"query={PR_QUERY}", "-f", "q=is:pr is:open author:@me"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=GIT_TIMEOUT * 2,
        )
        if result.returncode != 0:
            lines = result.stderr.strip().splitlines()
            raise RuntimeError(lines[0] if lines else f"exit {result.returncode}")
        return _parse_prs(result.stdout, warnings)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        warnings.append(f"gh: open PRs left out ({error or type(error).__name__})")
    except (ValueError, LookupError, TypeError, AttributeError) as error:
        warnings.append(f"gh: open PRs left out (unexpected answer: {type(error).__name__})")
    return []


def _hook_error_warning(now: datetime) -> str | None:
    log = config.cache_dir() / "hooks" / "errors.log"
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    since = now - timedelta(days=HOOK_ERROR_DAYS)
    counts: dict[str, int] = {}
    for line in lines:
        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue
        try:
            stamp = datetime.fromisoformat(parts[0])
        except ValueError:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.astimezone()
        if stamp >= since:
            counts[parts[1]] = counts.get(parts[1], 0) + 1
    if not counts:
        return None
    detail = ", ".join(f"{name} {count}" for name, count in sorted(counts.items()))
    return (
        f"hooks: {sum(counts.values())} failure(s) in the last {HOOK_ERROR_DAYS} days "
        f"({detail}); see {_tilde(log)}"
    )


def _title_and_closed(path: Path) -> tuple[str, bool]:
    title = ""
    closed = False
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for _ in range(HEAD_LINES):
                line = handle.readline()
                if not line:
                    break
                if not title and line.startswith("# "):
                    title = line[2:].strip()
                if line.strip() == CLOSED_MARK:
                    closed = True
    except OSError:
        pass
    return title, closed


def find_handoffs(
    data_dir: Path,
    extra_globs: list[str],
    *,
    limit: int,
    max_age_days: int | None,
    now: datetime,
    include_closed: bool = False,
) -> list[dict]:
    """The newest handoff files: `<data>/projects/*/HANDOFF-*.md` and the extra globs."""
    patterns = [str(data_dir / "projects" / "*" / HANDOFF_FILE)]
    patterns += [os.path.expanduser(item) for item in extra_globs]
    seen: dict[str, float] = {}
    for pattern in patterns:
        for name in glob.glob(pattern):
            try:
                seen.setdefault(name, os.stat(name).st_mtime)
            except OSError:
                continue
    oldest = None if max_age_days is None else (now - timedelta(days=max_age_days)).timestamp()
    found = []
    for name, mtime in sorted(seen.items(), key=lambda item: item[1], reverse=True):
        if oldest is not None and mtime < oldest:
            continue
        path = Path(name)
        title, closed = _title_and_closed(path)
        if closed and not include_closed:
            continue
        found.append(
            {
                "path": _tilde(path),
                "project": path.parent.name,
                "modified": datetime.fromtimestamp(mtime, now.tzinfo).isoformat(timespec="seconds"),
                "title": title,
                "closed": closed,
            }
        )
        if len(found) == limit:
            break
    return found


def collect(
    cfg: StandupConfig,
    workspace: Path,
    *,
    include_clean: bool = False,
    prs: bool = True,
    gh: str = "gh",
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now().astimezone()
    warnings: list[str] = []
    repos: list[dict] = []
    clean = 0
    for repo in _find_repos(cfg, workspace, warnings):
        try:
            state = _repo_state(repo, now)
        except _GitFailed as error:
            warnings.append(f"repo {repo.name}: left out ({error})")
            continue
        if include_clean or _has_something_to_say(state):
            repos.append(state)
        else:
            clean += 1
    hook_warning = _hook_error_warning(now)
    if hook_warning:
        warnings.append(hook_warning)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "fetched": False,
        "repos": repos,
        "clean_repos": clean,
        "prs": _open_prs(gh, warnings) if prs else [],
        "handoffs": find_handoffs(
            config.data_dir(),
            _extra_globs(),
            limit=5,
            max_age_days=None,
            now=now,
            include_closed=True,
        ),
        "warnings": warnings,
    }


def _extra_globs() -> list[str]:
    """`[handoff] extra_globs` of config.toml; a missing or invalid table means none."""
    from ws import userconfig

    try:
        value = userconfig.load_table("handoff").get("extra_globs", [])
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid):
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return []
