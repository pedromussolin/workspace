"""Link rewriting and project rename for the one-off items conversion."""

import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath

OLD_SLUG = "operations-screens-migration"
NEW_SLUG = "vm-migration"

_INLINE_LINK = re.compile(r'(!?\[[^\]]*\]\()(<[^>\n]*>|[^)\s]+)((?:\s+"[^"]*")?\s*\))')
_REF_LINK = re.compile(r"^(\s{0,3}\[[^\]]+\]:\s*)(\S+)")
_INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _blank_code(line: str) -> str:
    return _INLINE_CODE.sub(lambda m: "\0" * len(m.group(0)), line)


def _mapped(
    target: PurePosixPath, moved: dict[PurePosixPath, PurePosixPath]
) -> PurePosixPath | None:
    best: PurePosixPath | None = None
    for old in moved:
        if (target == old or old in target.parents) and (
            best is None or len(old.parts) > len(best.parts)
        ):
            best = old
    if best is None:
        return None
    return moved[best] / target.relative_to(best)


def new_path(path: str, moved: dict[str, str]) -> str:
    """Where `path` ends up: the most specific entry of `moved` (file or folder prefix) wins."""
    mapped = _mapped(
        PurePosixPath(path), {PurePosixPath(k): PurePosixPath(v) for k, v in moved.items()}
    )
    return path if mapped is None else mapped.as_posix()


def _rewrite_target(
    raw: str,
    source_old: PurePosixPath,
    source_new: PurePosixPath,
    moved: dict[PurePosixPath, PurePosixPath],
) -> str:
    wrapped = raw.startswith("<") and raw.endswith(">")
    inner = raw[1:-1] if wrapped else raw
    path, hash_, anchor = inner.partition("#")
    if not path or path.startswith("/") or _SCHEME.match(path):
        return raw
    resolved = posixpath.normpath(posixpath.join(source_old.parent.as_posix(), path))
    if resolved == ".." or resolved.startswith("../"):
        return raw
    target = PurePosixPath(resolved)
    new_target = _mapped(target, moved)
    if new_target is None:
        if source_new.parent == source_old.parent:
            return raw
        new_target = target
    relative = posixpath.relpath(new_target.as_posix(), source_new.parent.as_posix())
    if path.endswith("/"):
        relative += "/"
    result = relative + hash_ + anchor
    return f"<{result}>" if wrapped else result


def rewrite_links(
    text: str,
    source_old: PurePosixPath,
    source_new: PurePosixPath,
    moved: dict[PurePosixPath, PurePosixPath],
) -> str:
    out: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        blanked = _blank_code(line)
        edits: list[tuple[int, int, str]] = []
        for match in _INLINE_LINK.finditer(blanked):
            start, end = match.span(2)
            edits.append(
                (start, end, _rewrite_target(line[start:end], source_old, source_new, moved))
            )
        ref = _REF_LINK.match(blanked)
        if ref:
            start, end = ref.span(2)
            edits.append(
                (start, end, _rewrite_target(line[start:end], source_old, source_new, moved))
            )
        for start, end, new in sorted(edits, reverse=True):
            line = line[:start] + new + line[end:]
        out.append(line)
    return "".join(out)


def rename_slug(text: str, old: str, new: str) -> str:
    return text.replace(old, new)


def markdown_files(repo: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
    )
    files = []
    for name in result.stdout.split("\0"):
        if not name:
            continue
        in_projects = name.startswith("projects/") and name.endswith((".md", ".toml", ".tsv"))
        if in_projects or name in ("README.md", "CLAUDE.md"):
            files.append(repo / name)
    return sorted(files)


def affected_files(repo: Path, moved: dict[PurePosixPath, PurePosixPath]) -> list[Path]:
    found = []
    for path in markdown_files(repo):
        text = path.read_text(encoding="utf-8")
        old = PurePosixPath(path.relative_to(repo).as_posix())
        new = PurePosixPath(
            new_path(old.as_posix(), {k.as_posix(): v.as_posix() for k, v in moved.items()})
        )
        rewritten = rewrite_links(text, old, new, moved)
        if rewritten != text or OLD_SLUG in text:
            found.append(path)
    return found
