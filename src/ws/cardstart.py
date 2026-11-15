"""`ws card start`: the start rules (branch name, repos, card change, undo lines) and the command.

The command checks everything first, then makes the branches (local git only), then writes the
card's draft and runs its preview. It never sends anything to the tracker, commits or pushes.
"""

import json
import re
import shlex
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ws import card as cards_store
from ws import gittools, items, userconfig
from ws.boardconfig import BoardConfig, BoardMissing, load_board
from ws.carddraft import DraftError
from ws.config import REPO_NAME, config_dir, repo_root
from ws.gittools import GitError
from ws.itemfile import Item, ItemError
from ws.taskmodel import Status
from ws.tracker import port
from ws.tracker.port import Card, Tracker, TrackerError, TrackerSetup
from ws.tracker.vocab import REF

SPEC = "docs/specs/2026-11-15-card-start-design.md"
WORKTREES = ".worktrees"
SWITCHING = ("create", "track", "reuse")
KINDS = ("feature", "fix", "chore", "refact", "test", "hotfix")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SANDBOX_SUFFIX = "-sdbx"
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


def ends_in_sandbox(name: str) -> bool:
    return f"-{name}".endswith(SANDBOX_SUFFIX)


def _sandbox_problem(subject: str) -> str:
    return f"{subject} ends in {SANDBOX_SUFFIX}, the sandbox copy's suffix; pass another --desc"


def is_task_branch(name: str, ref: str) -> bool:
    if ends_in_sandbox(name):
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
    """Git lines that revert what the steps made; a branch that already existed is never deleted."""
    lines: list[str] = []
    for step in steps:
        repo = f"git -C {shlex.quote(str(step.path))}"
        if step.action in ("current", "elsewhere"):
            continue
        if step.action in ("worktree", "reuse") and step.worktree is not None:
            lines.append(f"{repo} worktree remove {shlex.quote(str(step.worktree))}")
            if step.action == "worktree":
                lines.append(f"{repo} branch -D {branch}")
            continue
        flag = "--detach " if step.detached else ""
        lines.append(f"{repo} switch {flag}{shlex.quote(step.previous)}")
        if step.action in ("create", "track"):
            lines.append(f"{repo} branch -D {branch}")
    return lines


@dataclass
class _Repo:
    """One repo of the task: where it is, what it holds and what this run plans for it."""

    name: str
    base: str
    path: Path | None = None
    root: Path | None = None
    action: str | None = None
    worktree: Path | None = None
    start_point: str | None = None
    track: bool = False
    local: list[str] = field(default_factory=list)
    remote: list[str] = field(default_factory=list)
    previous: str = ""
    detached: bool = False

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "path": str(self.path) if self.path else None,
            "base": self.base,
            "action": self.action,
            "worktree": str(self.worktree) if self.worktree else None,
        }

    def step(self) -> RepoStep:
        return RepoStep(
            self.name,
            self.path,
            self.base,
            self.action,
            self.previous,
            self.detached,
            self.worktree,
        )


@dataclass
class _Run:
    ref: str
    dry_run: bool
    card: Card | None = None
    change: str | None = None
    today: date | None = None
    branch: str | None = None
    repos_from: str | None = None
    repos: list[_Repo] = field(default_factory=list)
    draft: Path | None = None
    preview: cards_store.Preview | None = None
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    undo: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        found = self.card
        draft = str(self.draft) if self.draft else None
        code = self.preview.code if self.preview else None
        apply = f"ws card apply {shlex.quote(draft)} --approve {code}" if draft and code else None
        return {
            "ref": self.ref,
            "title": found.title if found else None,
            "status": found.status.value if found else None,
            "start": found.start.isoformat() if found and found.start else None,
            "branch": self.branch,
            "repos_from": self.repos_from,
            "repos": [repo.to_json() for repo in self.repos],
            "card_change": self.change,
            "draft": draft,
            "preview": self.preview.text if self.preview else None,
            "code": code,
            "apply": apply,
            "dry_run": self.dry_run,
            "problems": self.problems,
            "warnings": self.warnings,
            "undo": self.undo,
        }


def run_start(
    ref: str, repos: list[str], kind: str | None, desc: str | None, worktree: bool, dry_run: bool
) -> int:
    run = _Run(ref, dry_run)
    try:
        status = _start(run, repos, kind, desc, worktree)
    except BoardMissing:
        return _fail(f"no [board] table in {config_dir() / 'config.toml'}; add one (see {SPEC})", 2)
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid, TrackerSetup) as error:
        return _fail(error, 2)
    except TrackerError as error:
        return _fail(error, 3)
    print(json.dumps(run.to_json(), ensure_ascii=False, indent=2))
    return status


def _fail(message: object, status: int) -> int:
    print(f"ws card start: {message}", file=sys.stderr)
    return status


def _start(
    run: _Run, flag_repos: list[str], kind: str | None, desc: str | None, use_worktree: bool
) -> int:
    """Every check before the first change; then the branches; then the card's draft."""
    run.problems.extend(_input_problems(run.ref, flag_repos, kind, desc))
    if run.problems:
        return 1
    board = load_board()
    roots = userconfig.load_standup().repo_roots
    tracker = port.open_tracker()
    run.card = tracker.card(run.ref)
    if run.card is None:
        run.problems.append(f"{run.ref} was not found in the tracker's project")
        return 1
    _check_card(run, tracker)
    if run.change is not None and not run.problems:
        run.today = tracker.today()
    names = _repo_names(run, flag_repos, board)
    computed = None
    if names:
        slug = desc if desc is not None else branch_slug(run.card.title)
        computed = _computed_branch(run, kind or kind_for(run.card.type), slug)
    run.repos = [_locate(name, board, roots, run.problems) for name in names]
    if run.problems:
        return 1
    for repo in run.repos:
        _read(repo, board.remote, run.problems)
    if run.problems:
        return 1
    if names:
        run.branch = _choose_branch(run, computed, explicit=kind is not None or desc is not None)
    if run.branch is not None:
        for repo in run.repos:
            _plan(run, repo, board.remote, use_worktree)
    if run.problems or run.dry_run:
        return 1 if run.problems else 0
    if not _make_branches(run):
        return 1
    return _card_draft(run, board)


def _input_problems(ref: str, repos: list[str], kind: str | None, desc: str | None) -> list[str]:
    problems = []
    if not REF.fullmatch(ref):
        problems.append(f"{ref!r} is not a card reference like TS-123")
    problems.extend(
        f"--repo {name!r} is not a repo name" for name in repos if not REPO_NAME.fullmatch(name)
    )
    if kind is not None and kind not in KINDS:
        problems.append(f"--kind {kind!r} is not one of {', '.join(KINDS)}")
    if desc is not None and (not SLUG.fullmatch(desc) or len(desc) > MAX_SLUG):
        problems.append(
            f"--desc {desc!r} must be lowercase words joined by hyphens ({SLUG.pattern}), "
            f"at most {MAX_SLUG} characters"
        )
    elif desc is not None and ends_in_sandbox(desc):
        problems.append(_sandbox_problem(f"--desc {desc!r}"))
    return problems


def _check_card(run: _Run, tracker: Tracker) -> None:
    found = run.card
    if found.level != 0:
        run.problems.append(
            f"{run.ref} is not a card (level {found.level}); start a card, not an epic"
        )
    if tracker.me() not in (found.assignee, found.reporter):
        run.problems.append(
            f"{run.ref} is not yours: you are neither its assignee nor its reporter"
        )
    try:
        run.change = card_change(found.status, found.start, "start_date" in tracker.capabilities)
    except StartRefused as error:
        run.problems.append(str(error))
        return
    if run.change is None and found.start is None:
        run.warnings.append("the tracker cannot set a start date; the card is left as it is")


@dataclass(frozen=True)
class RepoChoice:
    """The task's repos and where they came from; `source` is None when the item was unusable.

    `item` is the item whose `card` is the reference; it is not looked up when `--repo` is given.
    """

    names: list[str]
    source: str | None
    item: Item | None
    problems: list[str]
    warnings: list[str]


def repos_for_card(
    root: Path, ref: str, title: str, flag: list[str], prefix_repos: dict[str, tuple[str, ...]]
) -> RepoChoice:
    """`--repo`, else the item's `repos`, else the title prefix; else a problem naming the three."""
    item = None
    item_repos = None
    warnings: list[str] = []
    if not flag:
        try:
            item, notes = items.find_card_item(root, ref)
        except ItemError as error:
            return RepoChoice([], None, None, [str(error)], warnings)
        warnings.extend(notes)
        if item is not None and "repos" in item.front and item.repos is None:
            where = items.rel(root, item.path)
            problem = f"{where}: repos must be a list; run ws item check"
            return RepoChoice([], None, item, [problem], warnings)
        if item is not None:
            item_repos = item.repos
            bad = [
                name
                for name in item_repos or []
                if not isinstance(name, str) or not REPO_NAME.fullmatch(name)
            ]
            if bad:
                where = items.rel(root, item.path)
                problem = f"{where}: repos has {bad[0]!r}, not a repo name; run ws item check"
                return RepoChoice([], None, item, [problem], warnings)
    names, source = resolve_repos(flag, item_repos, title, prefix_repos)
    problems = []
    if source == "none":
        prefix = title_prefix(title)
        listed = f'list "{prefix}"' if prefix else "list a title prefix"
        problems.append(
            f"no repos for {ref}: pass --repo NAME, add repos = [...] to its item under "
            f"projects/<slug>/tasks/, or {listed} in [board.prefix_repos]"
        )
    return RepoChoice(names, source, item, problems, warnings)


def _repo_names(run: _Run, flag: list[str], board: BoardConfig) -> list[str]:
    choice = repos_for_card(repo_root(), run.ref, run.card.title, flag, board.prefix_repos)
    run.warnings.extend(choice.warnings)
    run.problems.extend(choice.problems)
    run.repos_from = choice.source
    return choice.names


def _computed_branch(run: _Run, kind: str, slug: str) -> str | None:
    """The branch name from the kind and the slug; None when the title gives no slug."""
    if not slug:
        return None
    name = branch_name(kind, run.ref, slug)
    if ends_in_sandbox(name):
        run.problems.append(_sandbox_problem(f"the branch {name}"))
        return None
    return name


def locate_repo(name: str, roots: tuple[Path, ...]) -> Path | None:
    """The first `<root>/<name>` that is a git repo, in the order of `[standup] repo_roots`."""
    return next((root / name for root in roots if (root / name / ".git").exists()), None)


def _locate(name: str, board: BoardConfig, roots: tuple[Path, ...], problems: list[str]) -> _Repo:
    repo = _Repo(name, board.base_for(name))
    path = locate_repo(name, roots)
    if path is not None:
        repo.path, repo.root = path, path.parent
        return repo
    listed = ", ".join(str(root) for root in roots)
    problems.append(f"{name} was not found under {listed}; check the name or [standup] repo_roots")
    return repo


def _read(repo: _Repo, remote: str, problems: list[str]) -> None:
    """Fetch, then read the base, the branches and HEAD: the last reads before any change."""
    try:
        gittools.fetch(repo.path, remote)
        if not gittools.has_ref(repo.path, f"refs/remotes/{remote}/{repo.base}"):
            problems.append(
                f"{remote}/{repo.base} does not exist in {repo.name}; "
                f'set [board.repos."{repo.name}"] base'
            )
            return
        repo.local = gittools.local_branches(repo.path)
        repo.remote = gittools.remote_branches(repo.path, remote)
        repo.previous, repo.detached = gittools.head(repo.path)
    except GitError as error:
        problems.append(f"{repo.name}: {error}")


def _choose_branch(run: _Run, computed: str | None, explicit: bool) -> str | None:
    """The computed name when a repo has it, else the task's only existing branch, if any.

    `computed` is None when the title gives no slug: the only existing branch still serves a
    rerun. An explicit `--kind` or `--desc` is never overridden in silence: when it names another
    branch than the task's only one, that is a problem.
    """
    existing = sorted(
        {
            name
            for repo in run.repos
            for name in (*repo.local, *repo.remote)
            if is_task_branch(name, run.ref)
        }
    )
    if computed is not None and (computed in existing or not existing):
        return computed
    if not existing:
        run.problems.append("the title gives no slug; pass --desc")
        return None
    if len(existing) == 1 and explicit:
        run.problems.append(
            f"{run.ref} already has the branch {existing[0]}; drop --kind/--desc to reuse it, "
            "or remove it first"
        )
        return None
    if len(existing) == 1:
        instead = f"instead of {computed}" if computed else "(the title gives no slug)"
        run.warnings.append(f"{run.ref} already has the branch {existing[0]}; using it {instead}")
        return existing[0]
    run.problems.append(
        f"{run.ref} has more than one task branch ({', '.join(existing)}); "
        "pick one with --kind and --desc"
    )
    return None


def _plan(run: _Run, repo: _Repo, remote: str, use_worktree: bool) -> None:
    """The repo's action, decided before any change.

    A dirty tree, or a rebase, merge, cherry-pick, revert or bisect half done, only matters when
    the repo switches: a rerun on the task branch (`current`) or a worktree leaves it alone.
    """
    branch = run.branch
    try:
        where = gittools.worktree_of(repo.path, branch)
        if where is not None and not where.exists():
            prune = f"git -C {shlex.quote(str(repo.path))} worktree prune"
            run.problems.append(
                f"{repo.name}: {branch} is checked out in {where}, which no longer exists; "
                f"run {prune}"
            )
            return
        if use_worktree:
            _plan_worktree(run, repo, remote, where)
            return
        if where is not None and where.resolve() != repo.path.resolve():
            repo.action, repo.worktree = "elsewhere", where
            run.warnings.append(f"{repo.name}: {branch} is checked out in {where}; left there")
        elif where is not None:
            repo.action = "current"
        elif branch in repo.local:
            repo.action = "reuse"
        elif branch in repo.remote:
            repo.action, repo.start_point = "track", f"refs/remotes/{remote}/{branch}"
            repo.track = True
        else:
            repo.action, repo.start_point = "create", f"refs/remotes/{remote}/{repo.base}"
        if repo.action not in SWITCHING:
            return
        operation = gittools.operation_in_progress(repo.path)
        if operation is not None:
            run.problems.append(
                f"{repo.name} is in the middle of {operation} in {repo.path}; finish or abort it "
                "first, or rerun with --worktree"
            )
        elif gittools.dirty(repo.path):
            run.problems.append(
                f"{repo.name} has uncommitted changes in {repo.path}; commit or stash them, "
                "or rerun with --worktree"
            )
    except GitError as error:
        run.problems.append(f"{repo.name}: {error}")


def _plan_worktree(run: _Run, repo: _Repo, remote: str, where: Path | None) -> None:
    """The branch goes to `<root>/.worktrees/<repo>-<REF>`, hidden from the daily's repo scan."""
    branch = run.branch
    target = repo.root / WORKTREES / f"{repo.name}-{run.ref}"
    if where is not None and where.resolve() == target.resolve():
        repo.action, repo.worktree = "current", target
    elif where is not None:
        repo.action, repo.worktree = "elsewhere", where
        run.warnings.append(f"{repo.name}: {branch} is checked out in {where}; left there")
    elif target.exists() or target.is_symlink():
        run.problems.append(
            f"{target} already exists and does not hold {branch}; move it away or rerun "
            "without --worktree"
        )
    elif branch in repo.local:
        repo.action, repo.worktree = "reuse", target
    elif branch in repo.remote:
        repo.action, repo.worktree = "worktree", target
        repo.start_point, repo.track = f"refs/remotes/{remote}/{branch}", True
    else:
        repo.action, repo.worktree = "worktree", target
        repo.start_point = f"refs/remotes/{remote}/{repo.base}"


def _make_branches(run: _Run) -> bool:
    done: list[RepoStep] = []
    for repo in run.repos:
        try:
            _make_branch(repo, run.branch)
        except GitError as error:
            run.problems.append(
                f"{repo.name}: {error} (stopped here; undo lists what this run changed)"
            )
            run.undo = undo_commands(done, run.branch)
            return False
        done.append(repo.step())
    run.undo = undo_commands(done, run.branch)
    return True


def _make_branch(repo: _Repo, branch: str) -> None:
    if repo.action in ("current", "elsewhere"):
        return
    if repo.worktree is not None:
        gittools.add_worktree(repo.path, repo.worktree, branch, repo.start_point, repo.track)
    elif repo.action == "reuse":
        gittools.switch(repo.path, branch)
    else:
        gittools.switch_new(repo.path, branch, repo.start_point, repo.track)


def _card_draft(run: _Run, board: BoardConfig) -> int:
    """Write and preview the card's draft; with no change, drop the draft of an earlier run."""
    name = f"start-{run.ref}.md"
    if run.change is None or run.today is None:
        try:
            if cards_store.remove_draft(name):
                run.warnings.append(f"removed {name} from an earlier run: the card needs no change")
        except OSError as error:
            run.warnings.append(f"could not remove {name} from an earlier run: {error}")
        return 0
    text = draft_text(run.ref, run.change, board.statuses[Status.IN_PROGRESS], run.today)
    try:
        run.draft = cards_store.write_draft(name, text)
    except (OSError, DraftError) as error:
        run.problems.append(f"could not write the card draft: {error}")
        return 1
    run.preview = cards_store.preview(str(run.draft))
    if run.preview.status != 0:
        run.problems.append(
            f"ws card preview refused the draft (exit {run.preview.status}); the branches stay, "
            "rerun ws card start after fixing it"
        )
        run.problems.extend(
            line.strip() for line in run.preview.text.splitlines() if line.startswith("  ")
        )
    return run.preview.status
