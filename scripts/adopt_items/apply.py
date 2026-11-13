"""Executor of the items conversion: runs a `Plan` against a repo, step by step."""

import os
import shlex
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Protocol

from .frontmatter import (
    _quote,
    fill_sections,
    has_front_matter,
    insert_front_matter,
    replace_front_matter,
)
from .plan import NEW_PROJECT, OLD_PROJECT, Item, Plan, dropped_lines
from .relink import ROOT_FILES, affected_files, new_path, rename_slug, rewrite_links

MARKER_START = "<!-- ws:items -->"
MARKER_END = "<!-- /ws:items -->"
PENDING_FILE = "adopt-pending.tsv"


class ApplyError(Exception):
    pass


class Runner(Protocol):
    def git_mv(self, src: str, dst: str) -> None: ...

    def item_new(
        self,
        project: str,
        type_: str,
        epic: str | None,
        assignee: str | None,
        reporter: str | None,
        heading: str,
        slug: str,
    ) -> str:
        """Creates the item; returns its repo-relative path, as `ws item new` prints it."""
        ...

    def mask(self, text: str) -> str: ...

    def item_check(self, projects: list[str]) -> tuple[int, str]: ...

    def is_clean(self) -> bool: ...


class SubprocessRunner:
    def __init__(self, repo: Path, ws: list[str] | None = None):
        self.repo = repo
        self.ws = ws or [sys.executable, "-m", "ws"]
        self.env = {**os.environ, "WS_REPO_ROOT": str(repo)}

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True
        )

    def git_mv(self, src: str, dst: str) -> None:
        (self.repo / dst).parent.mkdir(parents=True, exist_ok=True)
        self._git("mv", src, dst)

    def item_new(self, project, type_, epic, assignee, reporter, heading, slug) -> str:
        command = [*self.ws, "item", "new", project, "--type", type_, "--heading", heading]
        command += ["--slug", slug]
        for flag, value in (("--epic", epic), ("--assignee", assignee), ("--reporter", reporter)):
            if value:
                command += [flag, value]
        done = subprocess.run(command, capture_output=True, text=True, env=self.env)
        if done.returncode != 0:
            raise ApplyError(f"ws item new failed for {project}/{slug}: {done.stderr.strip()}")
        return done.stdout.strip()

    def mask(self, text: str) -> str:
        done = subprocess.run(
            [*self.ws, "mask", "-"], input=text, capture_output=True, text=True, env=self.env
        )
        if done.returncode != 0:
            raise ApplyError(f"ws mask failed: {done.stderr.strip()}")
        return done.stdout

    def item_check(self, projects: list[str]) -> tuple[int, str]:
        done = subprocess.run(
            [*self.ws, "item", "check", *projects], capture_output=True, text=True, env=self.env
        )
        return done.returncode, done.stdout + done.stderr

    def is_clean(self) -> bool:
        return not self._git("status", "--porcelain").stdout.strip()


def revert_command(repo: Path) -> str:
    """Undoes an apply: `projects/` and the tracked root files a link rewrite may change."""
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--", *ROOT_FILES], capture_output=True, text=True
    ).stdout.splitlines()
    paths = " ".join(["projects", *(name for name in ROOT_FILES if name in listed)])
    where = shlex.quote(str(repo))
    return (
        f"git -C {where} restore --source=HEAD --staged --worktree {paths}"
        f" && git -C {where} clean -fd projects"
    )


def _original(plan: Plan, path: str) -> str:
    """Where `path` (a final repo-relative path) lives before the plan runs."""
    for src, dst in plan.moves:
        if dst == path:
            path = src
            break
    if plan.rename:
        old, new = plan.rename
        if path == new or path.startswith(new + "/"):
            path = old + path[len(new) :]
    return path


def moved_map(plan: Plan) -> dict[str, str]:
    """Every move in original coordinates (before the folder rename)."""
    moved = {}
    if plan.rename:
        moved[plan.rename[0]] = plan.rename[1]
    for src, dst in plan.moves:
        moved[_original(plan, src)] = dst
    return moved


def precheck(
    plan: Plan, repo: Path, runner: Runner, warnings: list[str] | None = None
) -> list[str]:
    """Problems that stop an apply; with `warnings`, a dirty tree is reported there instead."""
    problems = []
    for project in plan.project_tomls:
        names = {project} | ({OLD_PROJECT} if project == NEW_PROJECT else set())
        for name in sorted(names):
            if (repo / "projects" / name / "project.toml").exists():
                problems.append(f"projects/{name}/project.toml already exists")
    if not runner.is_clean():
        message = "the git tree is not clean: commit or stash first"
        (problems if warnings is None else warnings).append(message)
    for item in plan.items:
        if item.origin != "file":
            continue
        path = repo / _original(plan, item.path)
        if path.is_file() and has_front_matter(path.read_bytes().decode("utf-8")):
            problems.append(f"{item.path} already has front matter")
    return problems


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _toml_text(entry: dict) -> str:
    text = f"epics = [{', '.join(_quote(e) for e in entry['epics'])}]\n"
    if entry.get("initiative"):
        text += f"initiative = {_quote(entry['initiative'])}\n"
    if entry.get("prefixes"):
        text += "\n[prefixes]\n"
        text += "".join(f"{k} = {_quote(v)}\n" for k, v in entry["prefixes"].items())
    return text


def add_markers(readme: Path) -> str:
    """Appends the empty marker block after the first table under `## Tarefas`."""
    text = _read(readme)
    if MARKER_START in text:
        return "present"
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.strip() == "## Tarefas"), None)
    if start is None:
        return "no ## Tarefas heading"
    end = None
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("## "):
            break
        if stripped.startswith("|"):
            end = i
        elif end is not None:
            break
    if end is None:
        return "no table under ## Tarefas"
    nl = "\r\n" if lines[end].endswith("\r\n") else "\n"
    if not lines[end].endswith("\n"):
        lines[end] += nl
    block = f"{nl}{MARKER_START}{nl}{MARKER_END}{nl}"
    lines.insert(end + 1, block)
    _write(readme, "".join(lines))
    return "added"


def apply(plan: Plan, repo: Path, runner: Runner, map_dir: Path) -> list[str]:
    lines: list[str] = []

    def out(line: str) -> None:
        print(line, flush=True)
        lines.append(line)

    problems = precheck(plan, repo, runner)
    if problems:
        raise ApplyError("\n".join(problems))
    out(f"revert: {revert_command(repo)}")
    for line in dropped_lines(plan):
        out(line)

    moved = moved_map(plan)
    moved_posix = {PurePosixPath(k): PurePosixPath(v) for k, v in moved.items()}
    affected = affected_files(repo, moved_posix)

    if plan.rename:
        out(f"git mv {plan.rename[0]} {plan.rename[1]}")
        runner.git_mv(*plan.rename)
    for src, dst in plan.moves:
        out(f"git mv {src} {dst}")
        runner.git_mv(src, dst)

    for old_file in affected:
        old = old_file.relative_to(repo).as_posix()
        new = new_path(old, moved)
        path = repo / new
        text = _read(path)
        rewritten = rename_slug(
            rewrite_links(text, PurePosixPath(old), PurePosixPath(new), moved_posix),
            OLD_PROJECT,
            NEW_PROJECT,
        )
        if rewritten != text:
            _write(path, rewritten)
            out(f"rewrite {new}")

    for item in plan.items:
        if item.origin == "file":
            path = repo / item.path
            _write(path, insert_front_matter(_read(path), _fields(item)))
            out(f"front matter {item.path}")

    for item in plan.items:
        if item.origin == "new":
            try:
                _create(item, repo, runner, out)
            except ApplyError as error:
                raise ApplyError(f"{error}\nrevert: {revert_command(repo)}") from error

    for project, entry in plan.project_tomls.items():
        _write(repo / "projects" / project / "project.toml", _toml_text(entry))
        out(f"project.toml {project}")
        readme = repo / "projects" / project / "README.md"
        if readme.is_file():
            result = add_markers(readme)
            if result != "added":
                out(f"README markers not added in projects/{project}/README.md: {result}")
            else:
                out(f"README markers projects/{project}/README.md")
        else:
            out(f"README markers not added: projects/{project}/README.md does not exist")

    stale = map_dir / PENDING_FILE
    if not plan.pending_epics and stale.exists():
        stale.unlink()
        out(f"removed stale {stale}")
    if plan.pending_epics:
        rows = "".join(f"{i.path}\t{epic}\n" for i, epic in plan.pending_epics)
        (map_dir / PENDING_FILE).write_text(rows, encoding="utf-8")
        out(f"{map_dir / PENDING_FILE}: {len(plan.pending_epics)} pending epics")

    code, output = runner.item_check(sorted(plan.project_tomls))
    if code != 0:
        print(output)
        raise ApplyError(f"ws item check exited {code}:\n{output}")
    out("ws item check: ok")
    return lines


def _fields(item: Item) -> dict:
    fields = dict(item.fields)
    if item.docs:
        fields["docs"] = list(item.docs)
    return fields


def _create(item: Item, repo: Path, runner: Runner, out) -> None:
    fields = item.fields
    printed = runner.item_new(
        item.project,
        fields["type"],
        fields.get("epic"),
        fields.get("assignee"),
        fields.get("reporter"),
        runner.mask(item.heading or ""),
        item.slug or "",
    )
    if printed != item.path:
        raise ApplyError(f"ws item new printed {printed}, expected {item.path}: stopping")
    path = repo / printed
    text = replace_front_matter(_read(path), _fields(item))
    scope = runner.mask(item.scope) if item.scope else None
    done_when = runner.mask(item.done_when) if item.done_when else None
    _write(path, fill_sections(text, scope, done_when))
    out(f"new item {printed}")
