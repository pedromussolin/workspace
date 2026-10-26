"""Git helpers: assemble a clean branch from a work-in-progress one and rehearse merges."""

import json
import os
import re
import subprocess
from pathlib import Path

MAX_SUBJECT_LENGTH = 72
SHA_KEY = re.compile(r"[0-9a-fA-F]{4,40}")


class GitError(Exception):
    """A git command failed for a reason other than a conflict."""


class CherryPickConflict(Exception):
    """A cherry-pick stopped on a conflict; the repo is left mid-conflict for the user."""

    def __init__(self, sha: str) -> None:
        super().__init__(f"conflict while cherry-picking {sha}")
        self.sha = sha


class EmptyCherryPick(Exception):
    """A cherry-pick stopped because its changes are already in the base; the repo is left as is."""

    def __init__(self, sha: str) -> None:
        super().__init__(f"cherry-picking {sha} produced an empty commit")
        self.sha = sha


class SubjectTooLong(Exception):
    """Some final commit subjects are longer than the limit."""

    def __init__(self, subjects: list[str]) -> None:
        super().__init__(f"{len(subjects)} subject(s) longer than {MAX_SUBJECT_LENGTH} characters")
        self.subjects = subjects


def _git(
    cwd: Path, *args: str, check: bool = True, input: str | None = None
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False, input=input
    )
    if check and result.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result


def toplevel(path: Path) -> Path:
    return Path(_git(path, "rev-parse", "--show-toplevel").stdout.strip())


def conflicted_files(repo: Path) -> list[str]:
    return _git(repo, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()


def load_subjects(path: Path) -> dict[str, str]:
    """Read a JSON object mapping old subjects (or commit shas) to new subjects."""
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in data.items()
    ):
        raise ValueError(
            f"{path}: expected a JSON object mapping old subjects or shas to new subjects"
        )
    return data


def _message(repo: Path, rev: str) -> str:
    return _git(repo, "show", "--no-patch", "--format=%B", rev).stdout


def _in_progress(repo: Path, marker: str) -> bool:
    return _git(repo, "rev-parse", "--quiet", "--verify", marker, check=False).returncode == 0


def _replace_subject(message: str, subject: str) -> str:
    _, newline, body = message.partition("\n")
    return subject + newline + body


def _final_subject(sha: str, subject: str, subjects: dict[str, str]) -> str:
    """The new subject of a commit: a sha key (full or abbreviated) wins over its old subject."""
    for key, replacement in subjects.items():
        if SHA_KEY.fullmatch(key) and sha.startswith(key.lower()):
            return replacement
    return subjects.get(subject, subject)


def _nothing_staged(repo: Path) -> bool:
    return _git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0


def assemble(
    repo: Path, base: str, source: str, target: str, subjects: dict[str, str]
) -> list[str]:
    """Cherry-pick `base..source` onto a new branch `target` cut from `base`, oldest first.

    `subjects` maps an old subject, or a commit sha (full or abbreviated, which wins), to its
    replacement; only the first line of the message is replaced. Subjects, merge commits in the
    range and a dirty work tree are checked before anything changes, so a rejected run leaves
    the repo untouched.
    """
    shas = _git(repo, "rev-list", "--topo-order", "--reverse", f"{base}..{source}").stdout.split()
    final_subjects = []
    for sha in shas:
        subject = _message(repo, sha).partition("\n")[0]
        final_subjects.append(_final_subject(sha, subject, subjects))
    too_long = [s for s in final_subjects if len(s) > MAX_SUBJECT_LENGTH]
    if too_long:
        raise SubjectTooLong(too_long)
    merges = _git(repo, "rev-list", "--merges", f"{base}..{source}").stdout.split()
    if merges:
        listed = ", ".join(sha[:10] for sha in merges)
        raise GitError(
            f"{base}..{source} has merge commits ({listed}); cherry-pick cannot replay them"
        )
    if _git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise GitError("the work tree has uncommitted changes; commit or stash them first")

    _git(repo, "switch", "-c", target, "--no-track", base)
    for sha, final_subject in zip(shas, final_subjects, strict=True):
        picked = _git(repo, "cherry-pick", sha, check=False)
        if picked.returncode != 0:
            if not _in_progress(repo, "CHERRY_PICK_HEAD"):
                raise GitError(f"git cherry-pick {sha}: {picked.stderr.strip()}")
            if conflicted_files(repo):
                raise CherryPickConflict(sha)
            if _nothing_staged(repo):
                raise EmptyCherryPick(sha)
            raise GitError(f"git cherry-pick {sha}: {picked.stderr.strip()}")
        message = _message(repo, "HEAD")
        if message.partition("\n")[0] != final_subject:
            _git(
                repo, "commit", "--amend", "-F", "-", input=_replace_subject(message, final_subject)
            )
    return _git(repo, "log", "--reverse", "--format=%s", f"{base}..HEAD").stdout.splitlines()


def _resolution_script(resolutions: Path | None, branch: str) -> Path | None:
    if resolutions is None:
        return None
    script = resolutions / f"{branch.replace('/', '_')}.sh"
    if script.is_file() and os.access(script, os.X_OK):
        return script.resolve()
    return None


def _common_dir(path: Path) -> Path:
    output = _git(path, "rev-parse", "--git-common-dir").stdout.strip()
    return (path / output).resolve()


def _require_worktree_of(repo: Path, worktree: Path) -> None:
    """Fail unless `worktree` is a linked worktree of `repo`, not another repo or its main tree."""
    try:
        top = toplevel(worktree).resolve()
        same_repo = top == worktree and _common_dir(worktree) == _common_dir(repo)
        main_top = toplevel(repo).resolve()
    except GitError:
        same_repo, top, main_top = False, worktree, repo
    if not same_repo:
        raise GitError(f"{worktree} exists but is not a worktree of {repo}; use another --worktree")
    if top == main_top:
        raise GitError(f"{worktree} is the main work tree of {repo}; use another --worktree")


def _prepare_worktree(repo: Path, base: str, worktree: Path) -> None:
    if worktree.exists() and any(worktree.iterdir()):
        _require_worktree_of(repo, worktree)
        return
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "prune")
    _git(repo, "worktree", "add", "--detach", str(worktree), base)


def merge_rehearsal(
    repo: Path,
    base: str,
    branches: list[str],
    worktree: Path,
    resolutions: Path | None,
    check: str | None,
) -> int:
    """Merge `branches` over `base` in a throwaway worktree, resolve known conflicts, run `check`.

    A resolution script runs inside the worktree, must stage what it resolved and must exit 0;
    the merge is then committed. Returns 0 on success, 1 when a conflict has no working
    resolution, or the exit code of `check`. The worktree is a fresh checkout: no dependencies
    are installed in it.
    """
    worktree = worktree.resolve()
    _prepare_worktree(repo, base, worktree)
    _git(worktree, "merge", "--abort", check=False)
    _git(worktree, "checkout", "--detach", base)

    for branch in branches:
        merged = _git(worktree, "merge", "--no-edit", branch, check=False)
        if merged.returncode == 0:
            print(f"ok {branch}")
            continue
        if not _in_progress(worktree, "MERGE_HEAD"):
            raise GitError(f"git merge {branch}: {merged.stderr.strip()}")
        files = conflicted_files(worktree)
        script = _resolution_script(resolutions, branch)
        if script is not None:
            ran = subprocess.run([str(script)], cwd=worktree, check=False)
            if ran.returncode != 0:
                print(f"CONFLICT {branch}: {', '.join(files)}")
                print(f"(resolution script {script.name} exited with code {ran.returncode})")
                print(f"(worktree stopped at the conflict: {worktree})")
                return 1
            if not conflicted_files(worktree):
                _git(worktree, "add", "-A")
                _git(worktree, "commit", "--no-edit")
                print(f"resolved {branch}: {', '.join(files)}")
                continue
            files = conflicted_files(worktree)
        print(f"CONFLICT {branch}: {', '.join(files)}")
        print(f"(worktree stopped at the conflict: {worktree})")
        return 1

    if check is None:
        return 0
    return subprocess.run(check, shell=True, cwd=worktree, check=False).returncode
