"""Regras puras do `ws card start`: nome da branch, repos, mudança no card e linhas de desfazer."""

import re
import shlex
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ws.taskmodel import Status

KINDS = ("feature", "fix", "chore", "refact", "test", "hotfix")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_SLUG = 40
SLUG_WORDS = 5
STOP_WORDS = frozenset(
    "a o as os um uma de da do das dos e em no na nos nas para pra por pelo pela com ao aos "
    "que se ou".split()
)
PREFIX = re.compile(r"\s*\[([^\]]*)\]")
LEADING_PREFIXES = re.compile(r"^(?:\s*\[[^\]]*\])+")


class StartRefused(Exception):
    pass


def title_prefix(title: str) -> str | None:
    found = PREFIX.match(title)
    return found.group(1) if found else None


def branch_slug(title: str) -> str:
    text = LEADING_PREFIXES.sub("", title)
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    words = [w for w in re.findall(r"[a-z0-9]+", folded) if w not in STOP_WORDS]
    kept: list[str] = []
    for word in words[:SLUG_WORDS]:
        if len("-".join([*kept, word])) > MAX_SLUG:
            break
        kept.append(word)
    return "-".join(kept)


def kind_for(card_type: str | None) -> str:
    return "fix" if card_type == "bug" else "feature"


def branch_name(kind: str, ref: str, slug: str) -> str:
    return f"{kind}/{ref}-{slug}"


def is_task_branch(name: str, ref: str) -> bool:
    if name.endswith("-sdbx"):
        return False
    kind, _, rest = name.partition("/")
    if kind not in KINDS or not rest.startswith(f"{ref}-"):
        return False
    return SLUG.fullmatch(rest[len(ref) + 1 :]) is not None


def resolve_repos(
    flag: list[str],
    item_repos: list[str] | None,
    title: str,
    prefix_repos: dict[str, tuple[str, ...]],
) -> tuple[list[str], str]:
    if flag:
        return list(dict.fromkeys(flag)), "flag"
    if item_repos is not None:
        return list(dict.fromkeys(item_repos)), "item"
    prefix = title_prefix(title)
    if prefix is not None and prefix in prefix_repos:
        return list(dict.fromkeys(prefix_repos[prefix])), "prefix"
    return [], "none"


def card_change(status: Status, start: date | None, can_set_start: bool) -> str | None:
    if status in (Status.TODO, Status.BLOCKED):
        return "move"
    if status in (Status.DONE, Status.CANCELLED):
        raise StartRefused(f"card is {status.value}: reopen it in the tracker first")
    if start is None and can_set_start:
        return "start"
    return None


def draft_text(ref: str, change: str, in_progress: str, today: date) -> str:
    if change == "move":
        body = f'op = "move"\nkey = "{ref}"\nto = "{in_progress}"\n'
    else:
        body = f'op = "edit"\nkey = "{ref}"\nstart = {today.isoformat()}\n'
    return f"+++\n{body}+++\n"


@dataclass(frozen=True)
class RepoStep:
    name: str
    path: Path
    base: str
    action: str
    previous: str
    detached: bool
    worktree: Path | None


def undo_commands(steps: list[RepoStep], branch: str) -> list[str]:
    lines: list[str] = []
    for step in steps:
        repo = f"git -C {shlex.quote(str(step.path))}"
        if step.action == "current":
            continue
        if step.action == "worktree" and step.worktree is not None:
            lines.append(f"{repo} worktree remove {shlex.quote(str(step.worktree))}")
            lines.append(f"{repo} branch -D {branch}")
            continue
        flag = "--detach " if step.detached else ""
        lines.append(f"{repo} switch {flag}{shlex.quote(step.previous)}")
        if step.action in ("create", "track"):
            lines.append(f"{repo} branch -D {branch}")
    return lines
