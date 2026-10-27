"""Validates and publishes a project folder at the end of an iteration (`ws checkpoint`)."""

import os
import re
import subprocess
from pathlib import Path

from ws.bootstrap import GITHOOKS_DIR
from ws.config import repo_root
from ws.standup import _section

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REQUIRED_SECTIONS = {
    "## Onde parei": "O que foi feito e o que está em andamento, com a data.",
    "## Próximo passo": (
        "A próxima ação concreta, escrita para que um chat novo comece sem perguntar nada."
    ),
}
NEXT_STEP_HEADING = "## Próximo passo"
NEXT_STEP_MAX_LINES = 15
NEXT_STEP_MAX_CHARS = 1500
MESSAGE_PREFIXES = ("docs:", "chore:", "feat:", "fix:", "test:")
MESSAGE_MAX = 72
LARGE_BYTES = 200 * 1024
HEAVY_FOLDERS = ("evidence", "attachments")
KNOWN_WORDS = ".known-words"
REQUIRED_HOOKS = ("pre-commit", "commit-msg", "pre-push")
NETWORK_TIMEOUT = 120
NETWORK_COMMANDS = ("fetch", "pull", "push")


class CheckpointError(Exception):
    """A refusal; the message is printed as is."""


def _git(
    *args: str, ok: tuple[int, ...] = (0,), root: Path | None = None
) -> subprocess.CompletedProcess[str]:
    root = root or repo_root()
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env={**os.environ, "LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0"},
            timeout=NETWORK_TIMEOUT if args[0] in NETWORK_COMMANDS else None,
        )
    except subprocess.TimeoutExpired:
        if args[0] == "pull" and _in_rebase():
            _git("rebase", "--abort", ok=(0, 1, 128))
        raise CheckpointError(
            f"git {args[0]} timed out after {NETWORK_TIMEOUT} s (nothing was lost; run again)"
        ) from None
    if result.returncode not in ok:
        raise RuntimeError(f"git {args[0]} failed: {(result.stderr or result.stdout).strip()}")
    return result


def project_dir(slug: str) -> Path:
    if not SLUG.fullmatch(slug):
        raise CheckpointError(f"invalid slug {slug!r}: use lowercase letters, digits and hyphens")
    folder = repo_root() / "projects" / slug
    if folder.is_symlink() or not folder.is_dir():
        raise CheckpointError(f"projects/{slug} is not a project folder")
    return folder


def check(slug: str) -> dict:
    folder = project_dir(slug)
    problems: list[str] = []
    continue_md = folder / "CONTINUE.md"
    text = None
    if not continue_md.is_file():
        problem = f"projects/{slug} has no CONTINUE.md (not a project with checkpoints)"
        return {"ok": False, "problems": [problem]}
    else:
        try:
            text = continue_md.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append("CONTINUE.md is not valid UTF-8")
    if text is not None:
        for heading, placeholder in REQUIRED_SECTIONS.items():
            body = _section(text, heading)
            if body is None:
                problems.append(f"CONTINUE.md has no '{heading}'")
            elif not body:
                problems.append(f"CONTINUE.md: '{heading}' is empty")
            elif " ".join(body.split()) == placeholder:
                problems.append(f"CONTINUE.md: '{heading}' is still the template's placeholder")
        step = _section(text, NEXT_STEP_HEADING)
        if step:
            lines = [line for line in step.splitlines() if line.strip()]
            if len(lines) > NEXT_STEP_MAX_LINES:
                problems.append(
                    f"CONTINUE.md: '{NEXT_STEP_HEADING}' has {len(lines)} lines "
                    f"(max {NEXT_STEP_MAX_LINES})"
                )
            if len(step) > NEXT_STEP_MAX_CHARS:
                problems.append(
                    f"CONTINUE.md: '{NEXT_STEP_HEADING}' has {len(step)} characters "
                    f"(max {NEXT_STEP_MAX_CHARS})"
                )
    if not (folder / "decisions.md").is_file():
        problems.append(f"projects/{slug} has no decisions.md")
    return {"ok": not problems, "problems": problems}


def _status() -> list[tuple[str, str]]:
    output = _git("status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    entries = output.split("\0")
    result: list[tuple[str, str]] = []
    index = 0
    while index < len(entries) and entries[index]:
        code, path = entries[index][:2], entries[index][3:]
        index += 1
        result.append((code, path))
        if "R" in code or "C" in code:
            result.append(("D ", entries[index]))
            index += 1
    return result


def _normalize_includes(slug: str, include: list[str]) -> set[str]:
    prefix = f"projects/{slug}/"
    return {p if p.startswith(prefix) else prefix + p for p in include}


def _refused(slug: str, entries: list[tuple[str, str]], include: set[str]) -> list[dict]:
    prefix = f"projects/{slug}/"
    refused = []
    for code, path in entries:
        is_new = code == "??" or code[0] in "ARC"
        if not is_new or not path.startswith(prefix) or path in include:
            continue
        file = repo_root() / path
        if not file.is_file():
            continue
        heavy = path[len(prefix) :].split("/", 1)[0] in HEAVY_FOLDERS
        if heavy and file.stat().st_size > LARGE_BYTES:
            refused.append({"path": path, "reason": "larger than 200 KB"})
            continue
        with file.open("rb") as handle:
            if b"\0" in handle.read(8000):
                refused.append({"path": path, "reason": "binary"})
    return refused


def diff(slug: str, include: list[str] | None = None) -> dict:
    project_dir(slug)
    prefix = f"projects/{slug}/"
    entries = [(c, p) for c, p in _status() if p.startswith(prefix)]
    stat = _git("diff", "HEAD", "--stat", "--", f"projects/{slug}").stdout
    return {
        "files": [{"path": path, "status": code.strip()} for code, path in entries],
        "diffstat": stat,
        "refused": _refused(slug, entries, _normalize_includes(slug, include or [])),
    }


def _validate_message(message: str) -> None:
    if not message.startswith(MESSAGE_PREFIXES) or not message.split(":", 1)[1].strip():
        raise CheckpointError(f"message must start with one of {', '.join(MESSAGE_PREFIXES)}")
    if len(message) > MESSAGE_MAX or "\n" in message:
        raise CheckpointError(f"message must be one line of at most {MESSAGE_MAX} characters")


def _current_branch() -> str | None:
    result = _git("symbolic-ref", "--short", "-q", "HEAD", ok=(0, 1))
    return result.stdout.strip() or None


def _git_path_exists(name: str) -> bool:
    path = _git("rev-parse", "--git-path", name).stdout.strip()
    return (repo_root() / path).exists()


def _in_rebase() -> bool:
    return _git_path_exists("rebase-merge") or _git_path_exists("rebase-apply")


def _pull_rebase() -> None:
    result = _git("pull", "--rebase", "origin", "main", ok=(0, 1, 128))
    if result.returncode == 0:
        return
    output = (result.stderr or result.stdout).strip()
    if not _in_rebase():
        if "cannot pull with rebase" in output and "unstaged changes" in output:
            raise CheckpointError("outro processo mudou arquivos durante o pull; rode de novo")
        raise RuntimeError(f"git pull failed: {output}")
    conflicts = _git("diff", "--name-only", "--diff-filter=U", "-z").stdout.split("\0")
    _git("rebase", "--abort")
    raise CheckpointError(
        "pull --rebase failed; rebase aborted, the local commit is kept. Conflicting paths:\n"
        + "\n".join(c for c in conflicts if c)
        + f"\n{output}"
    )


def _recheck(slug: str) -> None:
    verdict = check(slug)
    if not verdict["ok"]:
        raise CheckpointError(
            "the check fails after the pull (nothing pushed):\n" + "\n".join(verdict["problems"])
        )


def _unpushed(slug: str) -> list[str]:
    """The commits `origin/main..HEAD` as "sha subject"; refuses when one is not the project's."""
    lines = _git("log", "--format=%h %s", "origin/main..HEAD").stdout.splitlines()
    foreign = []
    for line in lines:
        sha = line.split(" ", 1)[0]
        touched = _git(
            "diff-tree", "-r", "--no-renames", "--name-only", "-z", "--no-commit-id", "--root", sha
        ).stdout.split("\0")
        if any(p and not p.startswith(f"projects/{slug}/") and p != KNOWN_WORDS for p in touched):
            foreign.append(line)
    if foreign:
        raise CheckpointError(
            "unpushed commits touch paths outside the project; push them separately first:\n"
            + "\n".join(foreign)
        )
    return lines


def _push(slug: str) -> list[str]:
    ahead = _unpushed(slug)
    if not ahead:
        return []
    result = _git("push", "origin", "main", ok=(0, 1))
    if result.returncode == 0:
        return ahead
    rejected = "[rejected]" in result.stderr and (
        "non-fast-forward" in result.stderr or "fetch first" in result.stderr
    )
    if not rejected:
        raise CheckpointError(f"push refused:\n{(result.stderr or result.stdout).strip()}")
    _pull_rebase()
    _recheck(slug)
    ahead = _unpushed(slug)
    result = _git("push", "origin", "main", ok=(0, 1))
    if result.returncode != 0:
        raise CheckpointError(f"push refused:\n{(result.stderr or result.stdout).strip()}")
    return ahead


def _check_amendable(slug: str) -> None:
    if _git("fetch", "origin", "main", ok=(0, 1, 128)).returncode != 0:
        raise CheckpointError("--amend: could not fetch origin/main to find the unpushed commits")
    ahead = _git("rev-list", "origin/main..HEAD").stdout.split()
    if len(ahead) != 1:
        raise CheckpointError(
            f"--amend needs exactly one unpushed commit, found {len(ahead)}: a pushed commit "
            "is never amended"
        )
    if len(_git("rev-list", "--parents", "-n", "1", "HEAD").stdout.split()) > 2:
        raise CheckpointError("--amend: the unpushed commit is a merge commit")
    touched = _git(
        "diff-tree", "-r", "--no-renames", "--name-only", "-z", "--no-commit-id", "--root", "HEAD"
    ).stdout.split("\0")
    foreign = [
        p for p in touched if p and not p.startswith(f"projects/{slug}/") and p != KNOWN_WORDS
    ]
    if foreign:
        raise CheckpointError(
            "--amend: the unpushed commit touches other paths:\n" + "\n".join(foreign)
        )


def _check_hooks_installed() -> None:
    root = repo_root()
    hooks = root / GITHOOKS_DIR
    configured = _git("config", "--get", "--type=path", "core.hooksPath", ok=(0, 1)).stdout.strip()
    installed = bool(configured) and (root / configured).resolve() == hooks.resolve()
    if installed:
        installed = all(os.access(hooks / name, os.X_OK) for name in REQUIRED_HOOKS)
    if not installed:
        raise CheckpointError(
            "the repo's git hooks are not installed (the confidentiality checks would be "
            "skipped): run `ws setup`"
        )


def commit(slug: str, message: str, include: list[str] | None = None, amend: bool = False) -> dict:
    project_dir(slug)
    _check_hooks_installed()
    if _current_branch() != "main":
        raise CheckpointError("not on branch main: a checkpoint is committed only on main")
    _validate_message(message)
    verdict = check(slug)
    if not verdict["ok"]:
        raise CheckpointError("the check fails:\n" + "\n".join(verdict["problems"]))
    if _git_path_exists("MERGE_HEAD") or _in_rebase():
        raise CheckpointError("a merge or rebase is in progress: finish or abort it first")
    entries = _status()
    unmerged = sorted(p for c, p in entries if "U" in c or c in ("AA", "DD"))
    if unmerged:
        raise CheckpointError("unmerged paths:\n" + "\n".join(unmerged))
    prefix = f"projects/{slug}/"
    outside = sorted({p for _, p in entries if not p.startswith(prefix) and p != KNOWN_WORDS})
    if outside:
        raise CheckpointError(
            "changes outside the project, commit them separately:\n" + "\n".join(outside)
        )
    refused = _refused(slug, entries, _normalize_includes(slug, include or []))
    if refused:
        raise CheckpointError(
            "new large or binary files, pass them with --include:\n"
            + "\n".join(f"{item['path']} ({item['reason']})" for item in refused)
        )
    if amend:
        _check_amendable(slug)
    _git("add", "-A", "--", f"projects/{slug}")
    if any(path == KNOWN_WORDS for _, path in entries):
        _git("add", "--", KNOWN_WORDS)
    committed = amend or _git("diff", "--cached", "--quiet", ok=(0, 1)).returncode == 1
    if committed:
        flags = ["--amend"] if amend else []
        result = _git("commit", *flags, "-m", message, ok=(0, 1))
        if result.returncode != 0:
            raise CheckpointError(f"commit refused:\n{(result.stdout + result.stderr).strip()}")
    _pull_rebase()
    _recheck(slug)
    pushed = _push(slug)
    return {"committed": committed, "pushed": bool(pushed), "commits_pushed": pushed}
