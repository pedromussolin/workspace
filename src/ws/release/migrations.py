"""Alembic migration chain and merge order checks. Pure: no git, no I/O."""

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Revision:
    revision: str
    down: tuple[str, ...]
    path: str


class MigrationUnreadable(Exception):
    """A migration file that cannot be read statically; the message names the path."""


def _assigned(tree: ast.Module, name: str):
    found = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                found = node.value
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == name
                and node.value is not None
            ):
                found = node.value
    return found


def _literal(node, path: str, name: str):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError) as exc:
        raise MigrationUnreadable(f"{path}: {name} is not a literal") from exc


def parse_revision(source: str, path: str) -> Revision | None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise MigrationUnreadable(f"{path}: {exc.msg} (line {exc.lineno})") from exc
    rev_node = _assigned(tree, "revision")
    if rev_node is None:
        return None
    revision = _literal(rev_node, path, "revision")
    if not isinstance(revision, str):
        raise MigrationUnreadable(f"{path}: revision is not a string")
    down_node = _assigned(tree, "down_revision")
    down = None if down_node is None else _literal(down_node, path, "down_revision")
    if down is None:
        downs: tuple[str, ...] = ()
    elif isinstance(down, str):
        downs = (down,)
    elif isinstance(down, (tuple, list)) and all(isinstance(d, str) for d in down):
        downs = tuple(down)
    else:
        raise MigrationUnreadable(f"{path}: down_revision is not a string or a tuple of strings")
    return Revision(revision, downs, path)


def revisions(sources: dict[str, str]) -> dict[str, Revision]:
    out: dict[str, Revision] = {}
    for path, source in sources.items():
        parsed = parse_revision(source, path)
        if parsed is not None:
            out[parsed.revision] = parsed
    return out


def heads(revs: dict[str, Revision]) -> list[str]:
    downs = {d for r in revs.values() for d in r.down}
    return sorted(r for r in revs if r not in downs)


def chain_problems(
    base: dict[str, Revision], steps: list[tuple[str, dict[str, Revision]]]
) -> list[str]:
    problems: list[str] = []
    known = set(base)
    for index, (label, tip) in enumerate(steps):
        new = sorted(r for r in tip if r not in known)
        own = known | set(new)
        for rev in new:
            for down in tip[rev].down:
                if down in own:
                    continue
                other = next((lbl for lbl, later in steps[index + 1 :] if down in later), None)
                if other is not None:
                    problems.append(
                        f"{label}: migration {rev} needs {down}, which only {other} brings; "
                        f"merge {other} first"
                    )
                else:
                    problems.append(
                        f"{label}: migration {rev} needs {down}, "
                        "which neither master nor an include has"
                    )
        known = own
    return problems


def containment_problems(names: list[str], contains: dict[str, set[str]]) -> list[str]:
    problems: list[str] = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if b in contains.get(a, set()):
                problems.append(f"{a} already contains {b}; list {b} before {a}")
    return problems


def suggested_order(names: list[str], before: set[tuple[str, str]]) -> tuple[list[str], list[str]]:
    placed: list[str] = []
    remaining = list(names)
    while remaining:
        pick = next(
            (n for n in remaining if all(a in placed for a, b in before if b == n and a in names)),
            None,
        )
        if pick is None:
            x, y = (remaining + remaining)[:2]
            return list(names), [f"the order has a cycle: {x}, {y}"]
        placed.append(pick)
        remaining.remove(pick)
    return placed, []
