import hashlib
import re
import shutil
import subprocess
from pathlib import Path

from adopt_items.maprows import Row

PEOPLE = {"ana": "dev-aaaaaaaaaa", "bia": "dev-bbbbbbbbbb"}
HEADER = [
    "project", "file", "card", "action", "type", "epic", "title",
    "assignee", "reporter", "links", "status", "scope", "done_when", "notes",
]  # fmt: skip


def row(**kw) -> Row:
    base = dict(
        source="a.tsv", line=2, project="p", file=None, origin_project=None, card="TS-1",
        action="manter", type_="task", epic=None, assignee="ana", reporter="bia", links=(),
        status="a fazer", scope="", heading="H", done_when="", title="H",
    )  # fmt: skip
    base.update(kw)
    return Row(**base)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


NEUTRAL_TYPES = ("task", "bug", "hotfix", "improvement", "feature")


def make_repo(root: Path, **projects: dict[str, str]) -> Path:
    """A git repo whose `projects/<name>/tasks/` hold the given {file name: text}.

    It gets a stand-in `templates/item/<type>.md` per type unless the folder is already there.
    """
    templates = root / "templates" / "item"
    if not templates.exists():
        templates.mkdir(parents=True)
        for type_ in NEUTRAL_TYPES:
            (templates / f"{type_}.md").write_text("## Contexto\n\n## Pronto quando\n")
    for project, files in projects.items():
        tasks = root / "projects" / project / "tasks"
        tasks.mkdir(parents=True)
        (root / "projects" / project / "README.md").write_text(
            f"# {project}\n\n## Tarefas\n\n| # | Tarefa |\n|---|---|\n| 01 | a |\n\nDepois.\n"
        )
        for name, text in files.items():
            (tasks / name).write_bytes(text.encode())
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return root


class FakeRunner:
    def __init__(self, repo: Path, clean: bool = True, check: tuple[int, str] = (0, "{}")):
        self.repo, self.clean, self.check = repo, clean, check
        self.calls: list[tuple] = []

    def is_clean(self) -> bool:
        self.calls.append(("is_clean",))
        return self.clean

    def git_mv(self, src: str, dst: str) -> None:
        self.calls.append(("git_mv", src, dst))
        (self.repo / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(self.repo / src, self.repo / dst)

    def item_new(self, project, type_, epic, assignee, reporter, heading, slug) -> str:
        self.calls.append(("item_new", project, type_, epic, assignee, reporter, heading, slug))
        tasks = self.repo / "projects" / project / "tasks"
        tasks.mkdir(exist_ok=True)
        numbers = [int(m.group(1)) for p in tasks.iterdir() if (m := re.match(r"(\d+)-", p.name))]
        path = tasks / f"{max(numbers, default=0) + 1:02d}-{slug}.md"
        path.write_text(
            f'+++\ntype = "{type_}"\n+++\n# {heading}\n\n## Contexto\n\n## Pronto quando\n'
        )
        return path.relative_to(self.repo).as_posix()

    def mask(self, text: str) -> str:
        self.calls.append(("mask", text))
        return text.replace("secret", "SECRET")

    def item_check(self, projects: list[str]) -> tuple[int, str]:
        self.calls.append(("item_check", tuple(projects)))
        return self.check


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()
