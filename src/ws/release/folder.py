"""The release folder: `release.toml`, the PR drafts and their placeholders."""

import hashlib
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from ws.config import data_dir, repo_root
from ws.project import SLUG_PATTERN
from ws.release import ReleaseRefused, ReleaseSetup

if TYPE_CHECKING:
    from ws.release.settings import ReleaseConfig

TS_KEY = re.compile(r"TS-\d+")
PR_KEYS = {"title", "tasks", "labels", "assignees"}
REF_SHAPE = re.compile(r"\{([a-z_]+)(?::([^{}\s]*))?\}")
REF_NAMES = ("pr", "url", "num")
PLAIN_NAMES = ("tasks", "release_date")


def resolve_slug(project: str | None, cwd: Path) -> str:
    if project:
        if not SLUG_PATTERN.fullmatch(project):
            raise ReleaseSetup(f"--project {project!r} is not a project slug (a-z, 0-9 and -)")
        return project
    here = cwd.resolve()
    for root in (repo_root(), data_dir()):
        base = (root / "projects").resolve()
        if here.is_relative_to(base) and here != base:
            slug = here.relative_to(base).parts[0]
            if SLUG_PATTERN.fullmatch(slug):
                return slug
    raise ReleaseSetup("pass --project SLUG")


def release_dir(slug: str, day: date) -> Path:
    return data_dir() / "projects" / slug / f"release-{day:%Y%m%d}"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


@dataclass(frozen=True)
class ReleaseFile:
    repos: tuple[str, ...]
    include: dict[str, tuple[str, ...]]


def read_release(folder: Path, known: tuple[str, ...]) -> ReleaseFile:
    path = folder / "release.toml"
    try:
        data = tomllib.loads(path.read_bytes().decode())
    except (FileNotFoundError, NotADirectoryError):
        raise ReleaseSetup(f"{path} not found") from None
    except UnicodeDecodeError:
        raise ReleaseRefused(f"{path}: not UTF-8 text") from None
    except tomllib.TOMLDecodeError as error:
        raise ReleaseRefused(f"{path}: {error}") from None
    problems: list[str] = []
    repos = data.get("repos")
    if not isinstance(repos, list) or not repos or not all(isinstance(r, str) for r in repos):
        problems.append("repos must be a non-empty list of names")
        repos = []
    for index, repo in enumerate(repos):
        if repo not in known:
            problems.append(f"unknown repo {repo}")
        if repo in repos[:index]:
            problems.append(f"repo {repo} appears twice in repos")
    include: dict[str, tuple[str, ...]] = {}
    raw = data.get("include", {})
    if not isinstance(raw, dict):
        problems.append("include must be a table")
        raw = {}
    for repo, branches in raw.items():
        if repo not in repos:
            problems.append(f"include for {repo}, which is not in repos")
            continue
        if not isinstance(branches, list) or not all(isinstance(b, str) for b in branches):
            problems.append(f"include.{repo} must be a list of branch names")
            continue
        if not branches:
            problems.append(f"include.{repo} is empty")
            continue
        seen: set[str] = set()
        for branch in branches:
            if branch in seen:
                problems.append(f"include.{repo}: {branch} appears twice")
            seen.add(branch)
            if not TS_KEY.search(branch):
                problems.append(f"include.{repo}: {branch} has no TS key")
        include[repo] = tuple(branches)
    for repo in dict.fromkeys(repos):
        if repo not in raw:
            problems.append(f"{repo} is in repos but has no include list")
    if problems:
        raise ReleaseRefused("release.toml: " + "; ".join(problems))
    return ReleaseFile(tuple(repos), include)


def select_repos(config: "ReleaseConfig", wanted: ReleaseFile, names: list[str]) -> list[str]:
    """The repos to act on, in config (deploy) order: those of `release.toml`, narrowed by
    `--repo` (`names`); a `--repo` outside `release.toml` cannot be evaluated."""
    outside = [name for name in dict.fromkeys(names) if name not in wanted.repos]
    if outside:
        raise ReleaseSetup(f"--repo {', '.join(outside)}: not in release.toml")
    return [
        entry.name
        for entry in config.repos
        if entry.name in wanted.repos and (not names or entry.name in names)
    ]


@dataclass(frozen=True)
class PrDraft:
    path: Path
    title: str
    tasks: tuple[str, ...]
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    body: str
    sha256: str


def _str_list(value: object) -> tuple[str, ...] | None:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return tuple(value)
    return None


def read_pr(path: Path) -> PrDraft:
    raw = path.read_bytes()
    try:
        text = raw.decode()
    except UnicodeDecodeError:
        raise ReleaseRefused(f"{path}: not UTF-8 text") from None
    match = re.match(r"\+\+\+\n(.*?)^\+\+\+[ \t]*\n?", text, re.S | re.M)
    if not match:
        raise ReleaseRefused(f"{path}: missing +++ front matter")
    try:
        front = tomllib.loads(match.group(1))
    except tomllib.TOMLDecodeError as error:
        raise ReleaseRefused(f"{path}: {error}") from None
    problems: list[str] = []
    unknown = sorted(set(front) - PR_KEYS)
    if unknown:
        problems.append(f"unknown keys {', '.join(unknown)}")
    title = front.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append("title is required")
    tasks = _str_list(front.get("tasks"))
    if not tasks:
        problems.append("tasks is required and must be a non-empty list")
    else:
        for key in tasks:
            if not TS_KEY.fullmatch(key):
                problems.append(f"{key} is not a TS key")
    lists = {}
    for name in ("labels", "assignees"):
        value = _str_list(front.get(name, []))
        if value is None:
            problems.append(f"{name} must be a list of strings")
        lists[name] = value or ()
    if problems:
        raise ReleaseRefused(f"{path}: " + "; ".join(problems))
    return PrDraft(
        path=path,
        title=title,
        tasks=tasks,
        labels=lists["labels"],
        assignees=lists["assignees"],
        body=text[match.end() :],
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def pr_drafts(folder: Path, repo: str) -> dict[str, PrDraft]:
    pattern = re.compile(rf"{re.escape(repo)}(-sandbox(?:-(\d+))?)?\.md")
    found: dict[str, Path] = {}
    directory = folder / "pr"
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            match = pattern.fullmatch(path.name)
            if not match:
                continue
            if match.group(1) is None:
                found["code"] = path
            elif match.group(2) is None:
                found["sandbox"] = path
            elif int(match.group(2)) >= 2:
                found[f"sandbox-{int(match.group(2))}"] = path
    return {key: read_pr(path) for key, path in found.items()}


def tasks_block(tasks: tuple[str, ...], site: str) -> str:
    return "\n".join(f"- {key}: {site}/browse/{key}" for key in tasks)


def release_line(day: date) -> str:
    return f"Release: {day:%d/%m/%Y}"


def resolve_refs(text: str, known: dict[str, tuple[str, str, int]]) -> str:
    def replace(match: re.Match) -> str:
        name, ref = match.group(1), match.group(2)
        if name not in REF_NAMES or ref not in known:
            return match.group(0)
        slug_num, url, number = known[ref]
        return {"pr": slug_num, "url": url, "num": str(number)}[name]

    return REF_SHAPE.sub(replace, text)


def render(
    text: str,
    *,
    tasks: tuple[str, ...],
    site: str,
    day: date,
    known: dict[str, tuple[str, str, int]],
) -> str:
    text = text.replace("{tasks}", tasks_block(tasks, site))
    text = text.replace("{release_date}", f"{day:%d/%m/%Y}")
    return resolve_refs(text, known)


def pending_refs(text: str) -> list[str]:
    return [
        match.group(2)
        for match in REF_SHAPE.finditer(text)
        if match.group(1) in REF_NAMES and match.group(2)
    ]


def bad_placeholders(text: str, refs: set[str]) -> list[str]:
    bad = []
    for match in REF_SHAPE.finditer(text):
        name, ref = match.group(1), match.group(2)
        if name in PLAIN_NAMES:
            ok = ref is None
        else:
            ok = name in REF_NAMES and ref in refs
        if not ok:
            bad.append(match.group(0))
    return bad
