"""Git operations of `ws release`: thin wrappers over the `git` program.

Every call runs `git -c core.quotepath=false -C <repo>`. Nothing here pushes: the release writes
to GitHub elsewhere. `merge_tree` merges in the object database only, so it never touches a
working tree.
"""

import re
import subprocess
from pathlib import Path

from ws.boardproofs import first_line, run_git
from ws.codeposition import FETCH_TIMEOUT_SECONDS, fetch_env

TASK_KEY = re.compile(r"[A-Z][A-Z0-9]+-\d+")
REMOTE = "origin"


class GitFailed(Exception):
    """A git command that had to succeed did not; the message is its first error line."""


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = run_git(repo, *args)
    if check and result.returncode != 0:
        raise GitFailed(first_line(result.stderr or result.stdout))
    return result


def fetch(repo: Path) -> str | None:
    """`fetch --prune origin`; `None` when it worked, else the first line of the error."""
    try:
        result = run_git(
            repo,
            "fetch",
            "--prune",
            "--quiet",
            REMOTE,
            timeout=FETCH_TIMEOUT_SECONDS,
            env=fetch_env(repo),
        )
    except subprocess.TimeoutExpired:
        return f"timeout after {FETCH_TIMEOUT_SECONDS}s"
    except OSError as error:
        return str(error)
    return None if result.returncode == 0 else first_line(result.stderr)


def rev(repo: Path, ref: str) -> str | None:
    result = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    return git(repo, "merge-base", "--is-ancestor", older, newer, check=False).returncode == 0


def count(repo: Path, spec: str) -> int:
    return int(git(repo, "rev-list", "--count", spec).stdout.strip())


def commits(
    repo: Path, spec: str, *, merges: bool | None = None, first_parent: bool = False
) -> list[tuple[str, str]]:
    """(sha, subject) of `spec`, oldest first; `merges` True keeps only merges, False drops them."""
    args = ["log", "--reverse", "--format=%H%x00%s"]
    if merges is True:
        args.append("--merges")
    elif merges is False:
        args.append("--no-merges")
    if first_parent:
        args.append("--first-parent")
    out = git(repo, *args, spec).stdout
    return [tuple(line.split("\x00", 1)) for line in out.splitlines() if line]  # type: ignore[misc]


def message(repo: Path, sha: str) -> str:
    return git(repo, "log", "-1", "--format=%B", sha).stdout.rstrip("\n")


def diff_names(repo: Path, a: str, b: str) -> list[str]:
    return git(repo, "diff", "--name-only", a, b).stdout.splitlines()


def read_at(repo: Path, treeish: str, path: str) -> str | None:
    result = git(repo, "show", f"{treeish}:{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def sources_at(repo: Path, treeish: str, folder: str) -> dict[str, str]:
    """Every `.py` under `folder` at `treeish` (a commit or a tree id): file name -> text."""
    names = git(repo, "ls-tree", "-r", "--name-only", treeish, "--", folder, check=False)
    found: dict[str, str] = {}
    for path in names.stdout.splitlines():
        if path.endswith(".py"):
            text = read_at(repo, treeish, path)
            if text is not None:
                found[path.rsplit("/", 1)[-1]] = text
    return found


def merge_tree(repo: Path, ours: str, theirs: str) -> tuple[str | None, list[str]]:
    """Merges in the object database: (tree id, []) when clean, else (None, conflicted paths)."""
    result = git(repo, "merge-tree", "--write-tree", "--name-only", ours, theirs, check=False)
    lines = result.stdout.split("\n")
    if result.returncode == 0:
        return lines[0].strip(), []
    if result.returncode != 1:
        raise GitFailed(first_line(result.stderr or result.stdout))
    files: list[str] = []
    for line in lines[1:]:
        if not line:
            break
        files.append(line)
    return None, files


def merging(worktree: Path) -> bool:
    return (
        git(worktree, "rev-parse", "--verify", "--quiet", "MERGE_HEAD", check=False).returncode == 0
    )


def clean(worktree: Path) -> bool:
    return git(worktree, "status", "--porcelain", "--untracked-files=no").stdout.strip() == ""


def checked_out_at(repo: Path, branch: str) -> Path | None:
    """The worktree (the clone itself or an added one) that has `branch` checked out."""
    out = git(repo, "worktree", "list", "--porcelain").stdout
    path: Path | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree ") :]).resolve()
        elif line == f"branch refs/heads/{branch}":
            return path
    return None


def add_worktree(repo: Path, path: Path, branch: str, start: str | None = None) -> None:
    """Checks `branch` out at `path`; with `start`, creates it there first, without upstream."""
    if start is None:
        git(repo, "worktree", "add", str(path), branch)
    else:
        git(repo, "worktree", "add", "--no-track", "-b", branch, str(path), start)


def merge(worktree: Path, ref: str, subject: str, body: str = "") -> list[str]:
    """`merge --no-ff`; the conflicted paths (merge left in progress) or `[]` when clean."""
    args = ["merge", "--no-ff", "-m", subject]
    if body:
        args += ["-m", body]
    result = git(worktree, *args, ref, check=False)
    if result.returncode == 0:
        return []
    files = git(worktree, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
    if not files:
        raise GitFailed(first_line(result.stderr or result.stdout))
    return files


def upstream(repo: Path, branch: str) -> str | None:
    result = git(repo, "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def branches_with(repo: Path, key: str) -> tuple[list[str], list[str]]:
    """Local and `origin/` branch names that carry `key` (a whole key: TS-10 is not TS-101)."""

    def names(*refs: str) -> list[str]:
        out = git(repo, "for-each-ref", "--format=%(refname:short)", *refs).stdout.splitlines()
        return [n for n in out if key in TASK_KEY.findall(n)]

    return names("refs/heads"), names(f"refs/remotes/{REMOTE}")
