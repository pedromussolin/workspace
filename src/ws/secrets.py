"""Confidentiality check: secret patterns, real names and company domains in text and staged diffs.

Every function here reads or reports; the git hook and `ws check-secrets` decide what to do with
the findings. Errors are never swallowed here, so callers can fail closed.
"""

import ast
import bisect
import os
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ws.names import NamesTable, blocked_domain_matches, real_name_matches

ALLOWLIST_FILE = ".secrets-allow"
BINARY_PROBE_BYTES = 8000
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

PATTERN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "secret-assignment",
        re.compile(
            r"""(?<![A-Za-z0-9])(?:[A-Za-z0-9]+_)*(?:pg)?"""
            r"""(?:password|passwd|senha|secret|api[_-]?key|token)(?:_[A-Za-z0-9]+)*"""
            r"""["']?\s*[:=]\s*["']?(?![0-9]+\b)[^\s"'<]{4,}""",
            re.IGNORECASE,
        ),
    ),
    ("token-prefix", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|ATATT[A-Za-z0-9_\-=]{20,})")),
    ("url-credentials", re.compile(r"://[^\s/@]+@")),
    ("io-host", re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.io\b")),
    ("private-ip", re.compile(r"\b10(?:\.\d{1,3}){3}\b")),
    (
        "home-path",
        re.compile(
            r"/home/[A-Za-z_][\w.-]*"
            r"|/mnt/[a-z]/(?i:users)/[A-Za-z_][\w.-]*"
            r"|\b[A-Za-z]:[\\/]+(?i:users)[\\/]+[A-Za-z_][\w.-]*"
            r"|\\\\+(?:wsl\.localhost|wsl\$)\\+[^\\\s]+\\+home\\+[A-Za-z_][\w.-]*"
        ),
    ),
)
KNOWN_RULES = frozenset(rule for rule, _ in PATTERN_RULES) | {"real-name", "blocked-domain"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    match: str
    # Column span of the match in its line. It is what the allowlist is matched against, and it
    # is raw even when `match` is redacted.
    span: tuple[int, int] = field(default=(0, 0), compare=False, repr=False)


@dataclass(frozen=True)
class AllowRule:
    path_glob: str
    rule: str
    pattern: re.Pattern[str]


@lru_cache(maxsize=256)
def _glob_regex(glob: str) -> re.Pattern[str]:
    """`*` and `?` stay inside one folder, `**` crosses folders, `**/` also matches no folder."""
    parts = []
    position = 0
    while position < len(glob):
        if glob.startswith("**/", position):
            parts.append("(?:.*/)?")
            position += 3
        elif glob.startswith("**", position):
            parts.append(".*")
            position += 2
        elif glob[position] == "*":
            parts.append("[^/]*")
            position += 1
        elif glob[position] == "?":
            parts.append("[^/]")
            position += 1
        else:
            parts.append(re.escape(glob[position]))
            position += 1
    return re.compile("".join(parts))


def _covers_every_path(glob: str) -> bool:
    return not glob.strip("*/")


def parse_allowlist(text: str) -> list[AllowRule]:
    rules = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) != 3 or (parts[1] != "*" and parts[1] not in KNOWN_RULES):
            raise ValueError(
                f"{ALLOWLIST_FILE} line {number}: expected '<path-glob> <rule|*> <regex>'"
            )
        if parts[1] == "*" and _covers_every_path(parts[0]):
            raise ValueError(
                f"{ALLOWLIST_FILE} line {number}: a rule * entry needs a path glob that "
                "does not cover every file"
            )
        try:
            rules.append(AllowRule(parts[0], parts[1], re.compile(parts[2])))
        except re.error as error:
            raise ValueError(f"{ALLOWLIST_FILE} line {number}: {error}") from error
    return rules


def load_allowlist(repo: Path) -> list[AllowRule]:
    """The allowlist of the work tree; staged checks read the index instead."""
    path = repo / ALLOWLIST_FILE
    if not path.is_file():
        return []
    return parse_allowlist(path.read_text(encoding="utf-8"))


def _overlaps(pattern: re.Pattern[str], line: str, span: tuple[int, int]) -> bool:
    start, end = span
    return any(found.start() < end and found.end() > start for found in pattern.finditer(line))


def _is_allowed(finding: Finding, line: str, allow: list[AllowRule]) -> bool:
    """An entry allows a finding only when its regex matches over the finding's own text."""
    return any(
        _glob_regex(rule.path_glob).fullmatch(finding.path)
        and rule.rule in ("*", finding.rule)
        and _overlaps(rule.pattern, line, finding.span)
        for rule in allow
    )


def _redact(rule: str, line: str, found: re.Match[str]) -> str:
    """The text to report for a match; a secret value never leaves this function."""
    text = found.group()
    if rule == "secret-assignment":
        head = re.match(r"""[^:=]*[:=]\s*["']?""", text)
        name_prefix = re.search(r"[\w-]*$", line[: found.start()])
        return f"{name_prefix[0]}{head[0]}***"
    if rule == "token-prefix":
        return f"{text[:4]}***"
    if rule == "url-credentials":
        # Built in parts: written whole, this line would match the url-credentials rule itself.
        return "://" + "***@"
    return text


def _line_findings(path: str, number: int, line: str, table: NamesTable) -> Iterator[Finding]:
    for rule, pattern in PATTERN_RULES:
        for found in pattern.finditer(line):
            yield Finding(path, number, rule, _redact(rule, line, found), found.span())
    for offset, domain in blocked_domain_matches(line, table):
        yield Finding(path, number, "blocked-domain", domain, (offset, offset + len(domain)))


def scan_text(
    path: str,
    text: str,
    table: NamesTable,
    allow: list[AllowRule],
    only_lines: set[int] | None = None,
) -> list[Finding]:
    # Only "\n" ends a line, as in git; str.splitlines() would shift the numbers.
    lines = text.split("\n")
    starts = [0]
    starts.extend(found.end() for found in re.finditer("\n", text))
    found_all = []
    for number, line in enumerate(lines, start=1):
        if only_lines is None or number in only_lines:
            found_all.extend(_line_findings(path, number, line, table))
    # Names run on the whole text so a name wrapped across two lines is still caught.
    for offset, matched in real_name_matches(text, table):
        number = bisect.bisect_right(starts, offset)
        if only_lines is None or number in only_lines:
            column = offset - starts[number - 1]
            end = min(column + len(matched), len(lines[number - 1]))
            found_all.append(Finding(path, number, "real-name", matched, (column, end)))
    found_all.sort(key=lambda finding: finding.line)
    return [
        finding for finding in found_all if not _is_allowed(finding, lines[finding.line - 1], allow)
    ]


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {args[0]} failed: {detail}")
    return result.stdout


def repo_toplevel(start: Path) -> Path:
    return Path(_git(start, "rev-parse", "--show-toplevel").decode("utf-8").strip())


def _diff_path(raw: str) -> str | None:
    # Git appends a tab to the names that contain a space, and quotes the ones with odd bytes.
    raw = raw.removesuffix("\t")
    if raw == "/dev/null":
        return None
    if raw.startswith('"'):
        raw = ast.literal_eval(raw)
    return raw.removeprefix("b/")


def staged_additions(repo: Path) -> dict[str, set[int]]:
    diff = _git(
        repo,
        "diff",
        "--cached",
        "-U0",
        "--no-color",
        "--no-ext-diff",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "--diff-filter=ACMR",
    ).decode("utf-8", errors="replace")
    additions: dict[str, set[int]] = {}
    path = None
    pending = 0
    for line in diff.split("\n"):
        # Inside a hunk every line starts with +, - or \, so "+++ " is a header only outside one.
        if pending and line.startswith(("+", "-")):
            pending -= 1
        elif pending and line.startswith("\\"):
            continue
        elif line.startswith("diff --git "):
            path = None
        elif line.startswith("+++ "):
            path = _diff_path(line[4:])
        elif hunk := HUNK_HEADER.match(line):
            removed = 1 if hunk[1] is None else int(hunk[1])
            first = int(hunk[2])
            added = 1 if hunk[3] is None else int(hunk[3])
            pending = removed + added
            if path is not None and added:
                additions.setdefault(path, set()).update(range(first, first + added))
    return additions


def _is_binary(data: bytes) -> bool:
    return b"\0" in data[:BINARY_PROBE_BYTES]


def _read_worktree(path: Path) -> bytes | None:
    if path.is_symlink():
        return os.readlink(path).encode("utf-8", errors="replace")
    if not path.is_file():
        return None
    return path.read_bytes()


def _display_path(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def _sources(
    repo: Path, mode: str, paths: list[Path] | None
) -> Iterator[tuple[str, bytes | None, set[int] | None]]:
    if mode == "staged":
        for name, lines in staged_additions(repo).items():
            yield name, _git(repo, "show", f":{name}"), lines
    elif mode == "all":
        for raw in _git(repo, "ls-files", "-z").split(b"\0"):
            if raw:
                name = raw.decode("utf-8", errors="replace")
                yield name, _read_worktree(repo / name), None
    elif mode == "paths":
        for path in paths or []:
            yield _display_path(repo, path), path.read_bytes(), None
    else:
        raise ValueError(f"unknown mode {mode!r}: use staged, all or paths")


def _index_allowlist(repo: Path) -> list[AllowRule]:
    """The allowlist as staged: an exception counts only once it is part of what is committed."""
    if not _git(repo, "ls-files", "-s", "-z", "--", ALLOWLIST_FILE):
        return []
    return parse_allowlist(_git(repo, "show", f":{ALLOWLIST_FILE}").decode("utf-8"))


def check_repo(
    repo: Path, mode: str, table: NamesTable, paths: list[Path] | None = None
) -> list[Finding]:
    allow = load_allowlist(repo) if mode == "paths" else _index_allowlist(repo)
    findings: list[Finding] = []
    for name, data, only_lines in _sources(repo, mode, paths):
        if data is None or _is_binary(data):
            continue
        text = data.decode("utf-8", errors="replace")
        findings.extend(scan_text(name, text, table, allow, only_lines))
    return findings
