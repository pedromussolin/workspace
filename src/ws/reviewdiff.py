"""What changed on a card's task branch in one repo, read from git for the review pack."""

import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from ws import cardstart, gittools
from ws.config import data_dir
from ws.gittools import GitError

MAX_BLOCKS = 20
STAGES = ("committed", "staged", "unstaged", "untracked")
BINARY_SNIFF_BYTES = 8000
CHUNK_BYTES = 1024 * 1024
UNTRACKED_PATCH_BYTES = 1024 * 1024
DIFF_FLAGS = ("--no-ext-diff", "--no-textconv", "--no-color")
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


def _git(cwd: Path, *args: str, index: Path | None = None, accept: tuple[int, ...] = (0,)) -> bytes:
    """`index` is the private index copy: git may refresh and rewrite the index it reads."""
    command = ["git", "--no-optional-locks", "-c", "core.quotePath=false"]
    env = None
    if index is not None:
        command += ["-c", "core.splitIndex=false"]
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
    try:
        result = subprocess.run(
            [*command, *args], cwd=cwd, env=env, capture_output=True, check=False
        )
    except OSError as error:
        raise GitError(f"git {' '.join(args)}: {error}") from error
    if result.returncode not in accept:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(f"git {' '.join(args)}: {detail}")
    return result.stdout


def _diff(cwd: Path, index: Path, *args: str) -> bytes:
    return _git(cwd, "diff", *DIFF_FLAGS, *args, index=index)


@contextmanager
def _private_index(tree: Path) -> Iterator[Path]:
    """A copy of the tree's index in a 700 folder under the data dir, removed afterwards.

    `git diff` refreshes stale stat data in the index it reads and writes it back under
    `index.lock`, even with `--no-optional-locks`; on the copy that write never reaches the repo.
    The copy keeps the index's mtime, which git's racy-file check compares with.
    """
    source = tree / _text(_git(tree, "rev-parse", "--git-path", "index")).strip()
    parent = data_dir()
    parent.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix=".review-index-", dir=parent))
    try:
        copy = folder / "index"
        if source.exists():
            shutil.copy2(source, copy)
        yield copy
    finally:
        shutil.rmtree(folder, ignore_errors=True)


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
    """`base_ref` is used as given, such as `refs/remotes/upstream/master`."""
    if not gittools.has_ref(repo, base_ref):
        raise ReviewRefused(f"{base_ref} not found; fetch first")
    try:
        return _text(_git(repo, "merge-base", base_ref, checkout.branch)).strip()
    except GitError as error:
        raise ReviewRefused(
            f"no common ancestor between {checkout.branch} and {base_ref}"
        ) from error


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
    if path.endswith("/"):
        return None, True
    full = worktree / path
    try:
        if full.is_symlink():
            return 1, False
        with open(full, "rb") as handle:
            chunk = handle.read(CHUNK_BYTES)
            if b"\0" in chunk[:BINARY_SNIFF_BYTES]:
                return None, True
            lines = 0
            last = b""
            while chunk:
                lines += chunk.count(b"\n")
                last = chunk[-1:]
                chunk = handle.read(CHUNK_BYTES)
    except OSError:
        return 0, False
    return lines + (1 if last and last != b"\n" else 0), False


def collect(
    repo: Path, checkout: Checkout, base_ref: str, patch: BinaryIO | None = None
) -> Collected:
    """The branch's changes against the merge base with `base_ref`; git never writes the repo.

    Every read that looks at the index runs on a private copy of it. With `patch`, the whole diff
    goes there too, untracked files as additions.
    """
    merge_base = _merge_base(repo, checkout, base_ref)
    cwd = checkout.worktree or repo
    with _private_index(cwd) as index:
        changes = _changes(repo, checkout, merge_base, index)
        if patch is not None:
            _write_patch(cwd, checkout, merge_base, index, changes, patch)
    log = _git(repo, "log", "--reverse", "--format=%H%x1f%s", f"{merge_base}..{checkout.branch}")
    commits = []
    for line in _text(log).splitlines():
        sha, _, subject = line.partition("\x1f")
        commits.append(Commit(sha, subject))
    return Collected(
        merge_base=merge_base,
        files=tuple(sorted(changes, key=lambda change: change.path)),
        commits=tuple(commits),
    )


def _diff_args(checkout: Checkout, merge_base: str) -> tuple[str, ...]:
    if checkout.worktree is None:
        return ("-M", merge_base, checkout.branch)
    return ("-M", merge_base)


def _changes(repo: Path, checkout: Checkout, merge_base: str, index: Path) -> list[FileChange]:
    worktree = checkout.worktree
    cwd = worktree or repo
    diff_args = _diff_args(checkout, merge_base)
    statuses = _diff(cwd, index, "--name-status", "-z", *diff_args)
    numstat = _diff(cwd, index, "--numstat", "-z", *diff_args)
    patch = _diff(cwd, index, "-U0", *diff_args)
    stage_sets: dict[str, set[str]] = {}
    if worktree is not None:
        names = ("-M", "--name-only", "-z")
        stage_sets["committed"] = _names(_diff(cwd, index, *names, merge_base, checkout.branch))
        stage_sets["staged"] = _names(_diff(cwd, index, *names, "--cached"))
        stage_sets["unstaged"] = _names(_diff(cwd, index, *names))
    try:
        changes = _tracked(statuses, numstat, patch, stage_sets)
    except (ValueError, IndexError, StopIteration) as error:
        detail = str(error) or type(error).__name__
        raise ReviewRefused(f"could not read the diff of {repo.name}: {detail}") from error
    if worktree is not None:
        listing = _git(worktree, "ls-files", "--others", "--exclude-standard", "-z", index=index)
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
                    hunks=(1,) if added else (),
                )
            )
    return changes


def _tracked(
    statuses: bytes, numstat: bytes, patch: bytes, stage_sets: dict[str, set[str]]
) -> list[FileChange]:
    """One entry per file of the diff, with its counts, stages and hunks.

    A type change (file to symlink or submodule) has two patch blocks, the old side removed and the
    new side added; it keeps the new side's hunks. Any other mismatch raises ValueError.
    """
    entries = _status_entries(statuses)
    counts = _numstat(numstat)
    blocks = iter(_hunks(patch))
    if not stage_sets:
        stage_sets = {"committed": {path for _, _, path in entries}}
    changes = []
    for (letter, old, path), (added, deleted) in zip(entries, counts, strict=True):
        hunks = next(blocks)
        if letter == "T":
            hunks = next(blocks)
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
                hunks=hunks,
            )
        )
    if next(blocks, None) is not None:
        raise ValueError("the patch has more files than the file list")
    return changes


def _write_patch(
    cwd: Path,
    checkout: Checkout,
    merge_base: str,
    index: Path,
    changes: list[FileChange],
    out: BinaryIO,
) -> None:
    """The work tree (or the branch) against the merge base, then each untracked text file as new.

    An untracked file over `UNTRACKED_PATCH_BYTES` gets a `#` line instead; a symlink or a nested
    repo is left out (the pack lists it).
    """
    out.write(_diff(cwd, index, *_diff_args(checkout, merge_base)))
    for change in changes:
        if change.stages != ("untracked",):
            continue
        full = cwd / change.path
        try:
            info = full.lstat()
        except OSError:
            continue
        if not stat.S_ISREG(info.st_mode):
            continue
        if info.st_size > UNTRACKED_PATCH_BYTES:
            note = f"# {change.path}: untracked, {info.st_size} bytes, over "
            out.write(f"{note}{UNTRACKED_PATCH_BYTES}; not shown\n".encode())
            continue
        args = ("diff", "--no-index", *DIFF_FLAGS, "--", os.devnull, change.path)
        out.write(_git(cwd, *args, accept=(0, 1)))


def diff_command(repo: Path, checkout: Checkout, merge_base: str) -> str:
    """For a person to rerun by hand; the skill reads the pack's `diff_file` instead.

    `diff.autoRefreshIndex=false` keeps git from rewriting the index (a file whose timestamp changed
    with the same content shows as a bare header).
    """
    flags = "-c diff.autoRefreshIndex=false diff --no-ext-diff --no-textconv -M"
    if checkout.worktree is not None:
        return f"git -C {shlex.quote(str(checkout.worktree))} {flags} {merge_base}"
    branch = shlex.quote(checkout.branch)
    return f"git -C {shlex.quote(str(repo))} {flags} {merge_base} {branch}"
