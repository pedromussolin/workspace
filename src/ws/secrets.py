"""Confidentiality check: secret patterns, real names and company domains in text and staged diffs.

Every function here reads or reports; the git hook and `ws check-secrets` decide what to do with
the findings. Errors are never swallowed here, so callers can fail closed.
"""

import ast
import bisect
import codecs
import re
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

from ws.names import NamesTable, blocked_domain_matches, real_name_matches

ALLOWLIST_FILE = ".secrets-allow"
BINARY_RULE = "binary-file"
CO_AUTHOR_RULE = "co-authored-by"
MESSAGE_PATH = "message"
BINARY_PROBE_BYTES = 8000
GITLINK_MODE = "160000"
BATCH_SIZE = 256
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
CO_AUTHOR = re.compile(r"^[ \t]*co-authored-by[ \t]*:", re.IGNORECASE | re.MULTILINE)
# The block git puts into the message file of `git commit -v`, above the diff it ignores.
SCISSORS = (
    "# ------------------------ >8 ------------------------",
    "# Do not modify or remove the line above.",
    "# Everything below it will be ignored.",
)
GITLINK_HEADER = re.compile(rf"^(?:new file mode|new mode|index \w+\.\.\w+) {GITLINK_MODE}$")
# Git's own view of what changed. --text and --no-textconv keep a file that is marked binary or
# has a converter from being summarized as "differ"; --no-renames makes a moved file count as
# added, so its lines are checked again; only deletions are left out.
DIFF_FLAGS = (
    "-U0",
    "--no-color",
    "--no-ext-diff",
    "--text",
    "--no-textconv",
    "--no-renames",
    "--diff-filter=d",
    "--src-prefix=a/",
    "--dst-prefix=b/",
)
WIDE_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)

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
KNOWN_RULES = frozenset(rule for rule, _ in PATTERN_RULES) | {
    "real-name",
    "blocked-domain",
    BINARY_RULE,
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    match: str
    # Column span of the match in its line. It is what the allowlist is matched against, and it
    # is raw even when `match` is redacted.
    span: tuple[int, int] = field(default=(0, 0), compare=False, repr=False)
    commit: str = ""


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


def _git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        input=stdin,
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


def parse_additions(diff: str) -> dict[str, set[int]]:
    """File name to the numbers of its added lines, from a -U0 diff."""
    additions: dict[str, set[int]] = {}
    path = None
    gitlink = False
    pending = 0
    for line in diff.split("\n"):
        # Inside a hunk every line starts with +, - or \, so "+++ " is a header only outside one.
        if pending and line.startswith(("+", "-")):
            pending -= 1
        elif pending and line.startswith("\\"):
            continue
        elif line.startswith("diff --git "):
            path = None
            gitlink = False
        elif GITLINK_HEADER.match(line):
            gitlink = True
        elif line.startswith("+++ "):
            path = None if gitlink else _diff_path(line[4:])
        elif hunk := HUNK_HEADER.match(line):
            removed = 1 if hunk[1] is None else int(hunk[1])
            first = int(hunk[2])
            added = 1 if hunk[3] is None else int(hunk[3])
            pending = removed + added
            if path is not None and added:
                additions.setdefault(path, set()).update(range(first, first + added))
    return additions


def staged_additions(repo: Path) -> dict[str, set[int]]:
    diff = _git(repo, "diff", "--cached", *DIFF_FLAGS).decode("utf-8", errors="replace")
    return parse_additions(diff)


def _read_objects(repo: Path, names: list[str]) -> Iterator[bytes | None]:
    """The content of each object, in order, through `git cat-file --batch`; None if missing."""
    if any("\n" in name for name in names):
        raise RuntimeError("an object name with a line break cannot be read")
    for first in range(0, len(names), BATCH_SIZE):
        chunk = names[first : first + BATCH_SIZE]
        out = _git(repo, "cat-file", "--batch", stdin="\n".join(chunk).encode() + b"\n")
        position = 0
        for name in chunk:
            end = out.index(b"\n", position)
            header = out[position:end].split()
            position = end + 1
            if header[-1] == b"missing":
                yield None
            elif header[-1] == b"ambiguous":
                raise RuntimeError(f"object name {name!r} is ambiguous")
            else:
                size = int(header[2])
                yield out[position : position + size]
                position += size + 1


def _index_entries(repo: Path) -> dict[str, tuple[str, str]]:
    """Name to (mode, object id) of everything in the index."""
    entries = {}
    for record in _git(repo, "ls-files", "-s", "-z").split(b"\0"):
        if record:
            meta, _, raw = record.partition(b"\t")
            mode, oid, _stage = meta.decode().split(" ")
            entries[raw.decode("utf-8", errors="replace")] = (mode, oid)
    return entries


def _index_blobs(
    repo: Path, entries: dict[str, tuple[str, str]], names: Iterable[str]
) -> Iterator[tuple[str, bytes]]:
    """What the index holds for each name. A symlink comes as its target text."""
    wanted = []
    for name in names:
        if name not in entries:
            raise RuntimeError(f"{name} is not in the index")
        if entries[name][0] != GITLINK_MODE:
            wanted.append(name)
    contents = _read_objects(repo, [entries[name][1] for name in wanted])
    for name, data in zip(wanted, contents, strict=True):
        if data is None:
            raise RuntimeError(f"the object of {name} is missing")
        yield name, data


def _display_path(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def _sources(
    repo: Path, mode: str, paths: list[Path] | None, entries: dict[str, tuple[str, str]]
) -> Iterator[tuple[str, bytes, set[int] | None]]:
    if mode == "staged":
        additions = staged_additions(repo)
        for name, data in _index_blobs(repo, entries, additions):
            yield name, data, additions[name]
    elif mode == "all":
        for name, data in _index_blobs(repo, entries, entries):
            yield name, data, None
    elif mode == "paths":
        for path in paths or []:
            yield _display_path(repo, path), path.read_bytes(), None
    else:
        raise ValueError(f"unknown mode {mode!r}: use staged, all or paths")


def _decode(data: bytes) -> str | None:
    """The text of a file, or None when it is binary; UTF-16 and UTF-32 with a BOM are text."""
    for bom, encoding in WIDE_BOMS:
        if data.startswith(bom):
            return data.decode(encoding, errors="replace")
    if b"\0" in data[:BINARY_PROBE_BYTES]:
        return None
    return data.decode("utf-8", errors="replace")


def _scan_file(
    name: str, data: bytes, only_lines: set[int] | None, table: NamesTable, allow: list[AllowRule]
) -> list[Finding]:
    text = _decode(data)
    if text is None:
        # The content cannot be read here, so it needs a reviewed entry; the regex is matched
        # against the path, which stands in for the line.
        finding = Finding(name, 1, BINARY_RULE, "binary file", (0, len(name)))
        return [] if _is_allowed(finding, name, allow) else [finding]
    if data.startswith(tuple(bom for bom, _ in WIDE_BOMS)):
        # Git counts lines by the 0x0A byte, which is not always a line break in these encodings.
        only_lines = None
    return scan_text(name, text, table, allow, only_lines)


def _index_allowlist(repo: Path, entries: dict[str, tuple[str, str]]) -> list[AllowRule]:
    """The allowlist as staged: an exception counts only once it is part of what is committed."""
    if ALLOWLIST_FILE not in entries:
        return []
    ((_, data),) = _index_blobs(repo, entries, [ALLOWLIST_FILE])
    return parse_allowlist(data.decode("utf-8"))


def check_repo(
    repo: Path, mode: str, table: NamesTable, paths: list[Path] | None = None
) -> list[Finding]:
    entries = {} if mode == "paths" else _index_entries(repo)
    allow = load_allowlist(repo) if mode == "paths" else _index_allowlist(repo, entries)
    findings: list[Finding] = []
    for name, data, only_lines in _sources(repo, mode, paths, entries):
        findings.extend(_scan_file(name, data, only_lines, table, allow))
    return findings


def _without_comments(text: str) -> str:
    """Blank the lines git drops from a message (# ...) and the block under its scissors line."""
    lines = text.split("\n")
    for number in range(len(lines)):
        if tuple(lines[number : number + len(SCISSORS)]) == SCISSORS:
            lines = lines[:number]
            break
    return "\n".join("" if line.startswith("#") else line for line in lines)


def _message_findings(text: str, table: NamesTable, allow: list[AllowRule]) -> list[Finding]:
    findings = scan_text(MESSAGE_PATH, text, table, allow)
    for found in CO_AUTHOR.finditer(text):
        number = text.count("\n", 0, found.start()) + 1
        findings.append(Finding(MESSAGE_PATH, number, CO_AUTHOR_RULE, "Co-Authored-By trailer"))
    return sorted(findings, key=lambda finding: finding.line)


def check_message(repo: Path, text: str, table: NamesTable) -> list[Finding]:
    """Names, domains and secret patterns of a commit message; no Co-Authored-By trailer."""
    allow = _index_allowlist(repo, _index_entries(repo))
    return _message_findings(_without_comments(text), table, allow)


@dataclass(frozen=True)
class Commit:
    sha: str
    is_merge: bool
    author_email: str
    committer_email: str
    message: str


def _range_commits(repo: Path, revs: list[str]) -> list[Commit]:
    # Git refuses a NUL in a message, so -z can tell one commit from the next.
    out = _git(repo, "log", "--reverse", "-z", "--format=%H%n%P%n%ae%n%ce%n%B", *revs)
    commits = []
    for record in out.split(b"\0"):
        if record:
            text = record.decode("utf-8", errors="replace")
            sha, parents, author, committer, message = text.split("\n", 4)
            commits.append(Commit(sha, len(parents.split()) > 1, author, committer, message))
    return commits


def _email_findings(
    label: str, email: str, table: NamesTable, allow: list[AllowRule]
) -> list[Finding]:
    found = [
        Finding(label, 1, "blocked-domain", domain, (offset, offset + len(domain)))
        for offset, domain in blocked_domain_matches(email, table)
    ]
    return [finding for finding in found if not _is_allowed(finding, email, allow)]


def _check_commit(
    repo: Path, commit: Commit, table: NamesTable, allowlists: dict[bytes, list[AllowRule]]
) -> list[Finding]:
    additions: dict[str, set[int]] = {}
    if not commit.is_merge:
        diff = _git(repo, "show", "--format=", *DIFF_FLAGS, commit.sha)
        additions = parse_additions(diff.decode("utf-8", errors="replace"))
    specs = [f"{commit.sha}:{ALLOWLIST_FILE}", *(f"{commit.sha}:{name}" for name in additions)]
    allow_data, *contents = _read_objects(repo, specs)
    allow_data = allow_data or b""
    if allow_data not in allowlists:
        allowlists[allow_data] = parse_allowlist(allow_data.decode("utf-8"))
    allow = allowlists[allow_data]
    findings = []
    for (name, only_lines), data in zip(additions.items(), contents, strict=True):
        if data is None:
            raise RuntimeError(f"{name} is missing in commit {commit.sha}")
        findings.extend(_scan_file(name, data, only_lines, table, allow))
    findings.extend(_message_findings(commit.message, table, allow))
    findings.extend(_email_findings("author", commit.author_email, table, allow))
    findings.extend(_email_findings("committer", commit.committer_email, table, allow))
    return [replace(finding, commit=commit.sha) for finding in findings]


def check_range(repo: Path, revs: list[str], table: NamesTable) -> list[Finding]:
    """What each commit in a rev-list expression published.

    Every commit: its message, and its author and committer e-mails against the blocked domains.
    A commit that is not a merge also gets its added lines, against its first parent, checked: a
    merge brings in commits that are in the range themselves. The allowlist of each commit is
    the one in that commit's own tree.
    """
    if not revs:
        raise ValueError("a revision range is needed")
    allowlists: dict[bytes, list[AllowRule]] = {}
    findings = []
    for commit in _range_commits(repo, revs):
        findings.extend(_check_commit(repo, commit, table, allowlists))
    return findings
