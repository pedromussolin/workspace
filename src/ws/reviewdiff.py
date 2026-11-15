"""What changed on a card's task branch in one repo, read from git for the review pack."""

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ws import cardstart, gittools
from ws.gittools import GitError

MAX_BLOCKS = 20
STAGES = ("committed", "staged", "unstaged", "untracked")
BINARY_SNIFF_BYTES = 8000
STATUS_NAMES = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "T": "type_changed",
}
HUNK_HEADER = re.compile(rb"^@@ -\S+ \+(\d+)(?:,\d+)? @@")


class ReviewRefused(Exception):
    """The branch to review cannot be found or read."""


@dataclass(frozen=True)
class Checkout:
    branch: str
    worktree: Path | None


@dataclass(frozen=True)
class FileChange:
    path: str
    old_path: str | None
    status: str
    added: int | None
    deleted: int | None
    binary: bool
    stages: tuple[str, ...]
    hunks: tuple[int, ...]


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str


@dataclass(frozen=True)
class Collected:
    merge_base: str
    files: tuple[FileChange, ...]
    commits: tuple[Commit, ...]


def _git(cwd: Path, *args: str) -> bytes:
    command = ["git", "-c", "core.quotePath=false", *args]
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, check=False)
    except OSError as error:
        raise GitError(f"git {' '.join(args)}: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(f"git {' '.join(args)}: {detail}")
    return result.stdout


def _diff(cwd: Path, *args: str) -> bytes:
    return _git(cwd, "diff", "--no-ext-diff", "--no-color", *args)


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _fields(raw: bytes) -> list[str]:
    return [_text(part) for part in raw.split(b"\0") if part]


def find_checkout(repo: Path, ref: str) -> Checkout:
    current, detached = gittools.head(repo)
    if not detached and cardstart.is_task_branch(current, ref):
        return Checkout(current, repo)
    branches = sorted(b for b in gittools.local_branches(repo) if cardstart.is_task_branch(b, ref))
    if not branches:
        raise ReviewRefused(f"no task branch for {ref} in {repo.name}; run ws card start {ref}")
    if len(branches) > 1:
        raise ReviewRefused(
            f"{ref} has more than one task branch in {repo.name}: {', '.join(branches)}"
        )
    branch = branches[0]
    worktree = gittools.worktree_of(repo, branch)
    if worktree is not None and not worktree.exists():
        raise ReviewRefused(
            f"{branch} is checked out in {worktree}, which no longer exists; "
            f"run git -C {repo} worktree prune"
        )
    return Checkout(branch, worktree)


def _merge_base(repo: Path, checkout: Checkout, base_ref: str) -> str:
    base = base_ref if base_ref.startswith("origin/") else f"origin/{base_ref}"
    return _text(_git(repo, "merge-base", base, checkout.branch)).strip()


def _status_entries(raw: bytes) -> list[tuple[str, str | None, str]]:
    parts = _fields(raw)
    entries = []
    index = 0
    while index < len(parts):
        letter = parts[index][0]
        if letter in "RC":
            entries.append((letter, parts[index + 1], parts[index + 2]))
            index += 3
        else:
            entries.append((letter, None, parts[index + 1]))
            index += 2
    return entries


def _numstat(raw: bytes) -> list[tuple[int | None, int | None]]:
    counts = []
    chunks = raw.split(b"\0")
    index = 0
    while index < len(chunks) and chunks[index]:
        added, deleted, rest = chunks[index].split(b"\t", 2)
        index += 3 if not rest else 1
        if added == b"-":
            counts.append((None, None))
        else:
            counts.append((int(added), int(deleted)))
    return counts


def _hunks(raw: bytes) -> list[tuple[int, ...]]:
    blocks: list[list[int]] = []
    for line in raw.split(b"\n"):
        if line.startswith(b"diff --git "):
            blocks.append([])
            continue
        match = HUNK_HEADER.match(line) if blocks else None
        if match:
            blocks[-1].append(max(int(match.group(1)), 1))
    return [tuple(block[:MAX_BLOCKS]) for block in blocks]


def _names(raw: bytes) -> set[str]:
    return set(_fields(raw))


def _untracked(worktree: Path, path: str) -> tuple[int | None, bool]:
    try:
        with open(worktree / path, "rb") as handle:
            head = handle.read(BINARY_SNIFF_BYTES)
            if b"\0" in head:
                return None, True
            lines = head.count(b"\n")
            rest = handle.read()
    except OSError:
        return 0, False
    lines += rest.count(b"\n")
    last = rest[-1:] or head[-1:]
    return lines + (1 if last and last != b"\n" else 0), False


def collect(repo: Path, checkout: Checkout, base_ref: str) -> Collected:
    merge_base = _merge_base(repo, checkout, base_ref)
    branch = checkout.branch
    worktree = checkout.worktree
    if worktree is None:
        diff_args: tuple[str, ...] = ("-M", merge_base, branch)
        cwd = repo
    else:
        diff_args = ("-M", merge_base)
        cwd = worktree
    entries = _status_entries(_diff(cwd, "--name-status", "-z", *diff_args))
    counts = _numstat(_diff(cwd, "--numstat", "-z", *diff_args))
    hunks = _hunks(_diff(cwd, "-U0", *diff_args))
    stage_sets: dict[str, set[str]] = {"committed": set()}
    if worktree is None:
        stage_sets["committed"] = {path for _, _, path in entries}
    else:
        stage_sets["committed"] = _names(_diff(cwd, "-M", "--name-only", "-z", merge_base, branch))
        stage_sets["staged"] = _names(_diff(cwd, "-M", "--name-only", "-z", "--cached"))
        stage_sets["unstaged"] = _names(_diff(cwd, "-M", "--name-only", "-z"))
    changes = []
    for (letter, old, path), (added, deleted), blocks in zip(entries, counts, hunks, strict=True):
        stages = tuple(name for name in STAGES if path in stage_sets.get(name, set()))
        changes.append(
            FileChange(
                path=path,
                old_path=old,
                status=STATUS_NAMES.get(letter, "modified"),
                added=added,
                deleted=deleted,
                binary=added is None,
                stages=stages,
                hunks=blocks,
            )
        )
    if worktree is not None:
        listing = _git(worktree, "ls-files", "--others", "--exclude-standard", "-z")
        for path in _fields(listing):
            added, binary = _untracked(worktree, path)
            changes.append(
                FileChange(
                    path=path,
                    old_path=None,
                    status="added",
                    added=added,
                    deleted=None if binary else 0,
                    binary=binary,
                    stages=("untracked",),
                    hunks=() if binary else (1,),
                )
            )
    log = _git(repo, "log", "--reverse", "--format=%H%x1f%s", f"{merge_base}..{branch}")
    commits = []
    for line in _text(log).splitlines():
        sha, _, subject = line.partition("\x1f")
        commits.append(Commit(sha, subject))
    return Collected(
        merge_base=merge_base,
        files=tuple(sorted(changes, key=lambda change: change.path)),
        commits=tuple(commits),
    )


def diff_command(repo: Path, checkout: Checkout, merge_base: str) -> str:
    if checkout.worktree is not None:
        return f"git -C {shlex.quote(str(checkout.worktree))} diff -M {merge_base}"
    return f"git -C {shlex.quote(str(repo))} diff -M {merge_base} {shlex.quote(checkout.branch)}"
