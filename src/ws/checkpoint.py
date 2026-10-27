"""Validates and publishes a project folder at the end of an iteration (`ws checkpoint`)."""

import re
import subprocess
from pathlib import Path

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


class CheckpointError(Exception):
    """A refusal; the message is printed as is."""


def _git(
    *args: str, ok: tuple[int, ...] = (0,), root: Path | None = None
) -> subprocess.CompletedProcess[str]:
    root = root or repo_root()
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode not in ok:
        raise RuntimeError(f"git {args[0]} failed: {(result.stderr or result.stdout).strip()}")
    return result


def project_dir(slug: str) -> Path:
    if not SLUG.match(slug):
        raise CheckpointError(f"invalid slug {slug!r}: use lowercase letters, digits and hyphens")
    folder = repo_root() / "projects" / slug
    if folder.is_symlink() or not folder.is_dir():
        raise CheckpointError(f"projects/{slug} is not a project folder")
    return folder


def check(slug: str) -> dict:
    folder = project_dir(slug)
    problems: list[str] = []
    continue_md = folder / "CONTINUE.md"
    if not continue_md.is_file():
        problems.append(f"projects/{slug} has no CONTINUE.md (not a project with checkpoints)")
    else:
        text = continue_md.read_text(encoding="utf-8")
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
        if "R" in code or "C" in code:
            result.append((code, entries[index]))
            index += 1
        result.append((code, path))
    return result


def _normalize_includes(slug: str, include: list[str]) -> set[str]:
    prefix = f"projects/{slug}/"
    return {p if p.startswith(prefix) else prefix + p for p in include}


def _refused(slug: str, entries: list[tuple[str, str]], include: set[str]) -> list[dict]:
    prefix = f"projects/{slug}/"
    refused = []
    for code, path in entries:
        if code != "??" or not path.startswith(prefix) or path in include:
            continue
        if path[len(prefix) :].split("/", 1)[0] not in HEAVY_FOLDERS:
            continue
        file = repo_root() / path
        if file.stat().st_size > LARGE_BYTES:
            refused.append({"path": path, "reason": "larger than 200 KB"})
        elif b"\0" in file.read_bytes()[:8000]:
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


def _pull_rebase() -> None:
    result = _git("pull", "--rebase", "origin", "main", ok=(0, 1))
    if result.returncode == 0:
        return
    conflicts = _git("diff", "--name-only", "--diff-filter=U").stdout.split()
    if not conflicts:
        raise RuntimeError(f"git pull failed: {(result.stderr or result.stdout).strip()}")
    _git("rebase", "--abort")
    raise CheckpointError(
        "pull --rebase conflicted; rebase aborted, the local commit is kept. Conflicting paths:\n"
        + "\n".join(conflicts)
    )


def _recheck(slug: str) -> None:
    verdict = check(slug)
    if not verdict["ok"]:
        raise CheckpointError(
            "the check fails after the pull (nothing pushed):\n" + "\n".join(verdict["problems"])
        )


def _push() -> None:
    result = _git("push", "origin", "main", ok=(0, 1))
    if result.returncode == 0:
        return
    rejected = "[rejected]" in result.stderr and (
        "non-fast-forward" in result.stderr or "fetch first" in result.stderr
    )
    if not rejected:
        raise CheckpointError(f"push refused:\n{(result.stderr or result.stdout).strip()}")
    _pull_rebase()
    result = _git("push", "origin", "main", ok=(0, 1))
    if result.returncode != 0:
        raise CheckpointError(f"push refused:\n{(result.stderr or result.stdout).strip()}")


def commit(slug: str, message: str, include: list[str] | None = None) -> dict:
    project_dir(slug)
    if _current_branch() != "main":
        raise CheckpointError("not on branch main: a checkpoint is committed only on main")
    _validate_message(message)
    verdict = check(slug)
    if not verdict["ok"]:
        raise CheckpointError("the check fails:\n" + "\n".join(verdict["problems"]))
    entries = _status()
    prefix = f"projects/{slug}/"
    outside = sorted({path for _, path in entries if not path.startswith(prefix)})
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
    _git("add", "-A", "--", f"projects/{slug}")
    committed = _git("diff", "--cached", "--quiet", ok=(0, 1)).returncode == 1
    if committed:
        result = _git("commit", "-m", message, ok=(0, 1))
        if result.returncode != 0:
            raise CheckpointError(f"commit refused:\n{(result.stdout + result.stderr).strip()}")
    _pull_rebase()
    _recheck(slug)
    _push()
    return {"committed": committed, "pushed": True}
