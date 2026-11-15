"""State of a repo in a release and the rules R2 to R6, R10 and R11 checked against it.

Read-only: every git call here reads. Problem texts start with `{repo}: `; the callers decide what
to do with them (`new` stops, `publish` refuses, `status` prints).
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ws.release import folder as release_folder
from ws.release import gitops, migrations, text
from ws.release.folder import PrDraft
from ws.release.settings import ReleaseConfig, RepoEntry

TEMPLATE_PATH = ".github/pull_request_template.md"
DEFAULT_HEADINGS = ["## O que traz", "## Antes de subir", "## Ordem e efeitos", "## Como validei"]
SANDBOX_SUFFIX = " (sdbx)"
MAX_SANDBOX_TITLE = 100
SINGLE_TITLE = re.compile(r"^(feat|chore|refact|fix|test)\(TS-\d+\): .+")


@dataclass
class RepoState:
    repo: str
    shape: str
    includes: tuple[str, ...]
    code_branch: str
    tip: str | None
    worktree: str | None
    sandbox_head: str
    sdbx: str | None
    sdbx_differs: tuple[str, ...]
    ahead: int
    behind: int
    remote: bool
    heads: dict[str, list[str]]
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=lambda: list(DEFAULT_HEADINGS))

    @property
    def ready(self) -> bool:
        return self.tip is not None and not self.problems

    def as_json(self) -> dict:
        return {
            "repo": self.repo,
            "shape": self.shape,
            "includes": list(self.includes),
            "code_branch": self.code_branch,
            "tip": self.tip,
            "worktree": self.worktree,
            "sandbox_head": self.sandbox_head,
            "sdbx": self.sdbx,
            "sdbx_differs": list(self.sdbx_differs),
            "ahead": self.ahead,
            "behind": self.behind,
            "remote": self.remote,
            "heads": self.heads,
            "problems": self.problems,
            "warnings": self.warnings,
            "ready": self.ready,
        }


def _local(branch: str) -> str:
    return f"refs/heads/{branch}"


def _remote(branch: str) -> str:
    return f"refs/remotes/{gitops.REMOTE}/{branch}"


def _ref(repo: Path, branch: str) -> str | None:
    """The local branch when there is one (it may be ahead of origin), else the origin copy."""
    for ref in (_local(branch), _remote(branch)):
        if gitops.rev(repo, ref):
            return ref
    return None


def heads_problem(repo: str, where: str, heads: list[str]) -> str | None:
    if len(heads) < 2:
        return None
    return f"{repo}: {len(heads)} alembic heads at {where}: {', '.join(heads)}"


def against_origin(repo: Path, name: str, branch: str) -> tuple[list[str], list[str]]:
    """Problems and warnings of a local branch compared with its `origin` copy."""
    ref, origin = _local(branch), _remote(branch)
    local, remote = gitops.rev(repo, ref), gitops.rev(repo, origin)
    if local is None or remote is None or local == remote:
        return [], []
    if gitops.is_ancestor(repo, local, remote):
        return [f"{name}: local {branch} is behind origin/{branch}; pull it first"], []
    if gitops.is_ancestor(repo, remote, local):
        n = gitops.count(repo, f"{origin}..{ref}")
        return [], [
            f"{name}: local {branch} has {n} commits not on origin; they go into the release"
        ]
    return [f"{name}: local {branch} and origin/{branch} diverged"], []


def order_check(
    entry: RepoEntry, includes: tuple[str, ...] | list[str], base_ref: str
) -> tuple[list[str], list[str], list[str]]:
    """R11 and the chain part of R10 on the includes, before anything is merged.

    Returns (problems, warnings, suggested order).
    """
    repo, name = entry.path, entry.name
    names = list(includes)
    problems: list[str] = []
    warnings: list[str] = []
    refs: dict[str, str] = {}
    for branch in names:
        ref = _ref(repo, branch)
        if ref is None:
            problems.append(f"{name}: {branch} exists neither locally nor on origin")
            continue
        refs[branch] = ref
        found, noted = against_origin(repo, name, branch)
        problems += found
        warnings += noted
    if len(refs) < len(names):
        return problems, warnings, names

    allowed = {key for branch in names for key in text.keys_of(branch)}
    for branch in names:
        foreign: list[str] = []
        for _, subject in gitops.commits(repo, f"{base_ref}..{refs[branch]}", merges=False):
            foreign += [k for k in text.keys_of(subject) if k not in allowed and k not in foreign]
        problems += [
            f"{name}: {branch} carries commits of {key}, which is not in this repo's include list"
            for key in foreign
        ]

    own = {b: gitops.count(repo, f"{base_ref}..{refs[b]}") > 0 for b in names}
    shown = base_ref.removeprefix("refs/remotes/")
    problems += [
        f"{name}: {b} is already in {shown}; take it out of the release"
        for b in names
        if not own[b]
    ]
    contains = {
        a: {b for b in names if b != a and own[b] and gitops.is_ancestor(repo, refs[b], refs[a])}
        for a in names
    }
    problems += [f"{name}: {p}" for p in migrations.containment_problems(names, contains)]
    before = {(b, a) for a, inner in contains.items() for b in inner}
    order, cycle = migrations.suggested_order(names, before)
    problems += [f"{name}: {p}" for p in cycle]

    if entry.alembic:
        try:
            base = migrations.revisions(gitops.sources_at(repo, base_ref, entry.alembic))
            steps = [
                (b, migrations.revisions(gitops.sources_at(repo, refs[b], entry.alembic)))
                for b in names
            ]
            problems += [f"{name}: {p}" for p in migrations.chain_problems(base, steps)]
        except migrations.MigrationUnreadable as error:
            problems.append(f"{name}: {error}")
    return problems, warnings, order


def mirror(
    entry: RepoEntry, code: str, sdbx: str, config: ReleaseConfig
) -> tuple[list[str], list[str]]:
    """R4: the `-sdbx` only adds `sandbox`; (problems, files where it differs from the code)."""
    repo, name = entry.path, entry.name
    sandbox = _remote(config.sandbox_branch)
    base = _remote(config.base_branch)
    code_ref, sdbx_ref = _ref(repo, code) or code, _ref(repo, sdbx) or sdbx
    problems: list[str] = []
    if not gitops.is_ancestor(repo, code_ref, sdbx_ref):
        problems.append(f"{name}: {sdbx} does not contain {code}")
    if not gitops.is_ancestor(repo, sandbox, sdbx_ref):
        problems.append(f"{name}: {sdbx} does not contain origin/{config.sandbox_branch}")
    from_sandbox = {sha for sha, _ in gitops.commits(repo, f"{code_ref}..{sandbox}")}
    merge_migration: str | None = None
    for sha, subject in gitops.commits(repo, f"{code_ref}..{sdbx_ref}", merges=False):
        if sha in from_sandbox:
            continue
        if merge_migration is None:
            merge_migration = _merge_migration(entry, sha)
            if merge_migration is not None:
                continue
        problems.append(f"{name}: {sdbx} has commits of its own: {sha[:7]} {subject}")
    differs = gitops.diff_names(repo, code_ref, sdbx_ref)
    sandbox_files = set(gitops.diff_names(repo, base, sandbox))
    for path in differs:
        if path not in sandbox_files and path != merge_migration:
            problems.append(
                f"{name}: {sdbx} differs from {code} in {path}, "
                f"which {config.sandbox_branch} does not change"
            )
    return problems, differs


def _merge_migration(entry: RepoEntry, sha: str) -> str | None:
    """The path when commit `sha` only adds one Alembic migration under the repo's `alembic`
    folder whose `down_revision` is exactly the heads just before it (two or more): the merge
    migration the user adds in the `-sdbx` when the sandbox side has two heads."""
    if not entry.alembic:
        return None
    changed = gitops.changed_files(entry.path, sha)
    if len(changed) != 1:
        return None
    status, path = changed[0]
    folder = entry.alembic.rstrip("/") + "/"
    if status != "A" or not path.startswith(folder) or not path.endswith(".py"):
        return None
    try:
        added = migrations.parse_revision(gitops.read_at(entry.path, sha, path) or "", path)
    except migrations.MigrationUnreadable:
        return None
    before = heads_at(entry, f"{sha}^")
    if added is None or len(before) < 2:
        return None
    if len(added.down) != len(before) or set(added.down) != set(before):
        return None
    return path


def sandbox_heads(entry: RepoEntry, tip: str, tree: str | None) -> list[str]:
    """The Alembic heads of a clean sandbox merge (`tree`) when the code has one head and the
    merge has two or more: `sandbox` has a migration master lacks. `new` treats it as a conflict.
    """
    merged = heads_at(entry, tree) if tree else []
    return merged if len(merged) >= 2 and len(heads_at(entry, tip)) <= 1 else []


def heads_at(entry: RepoEntry, ref: str) -> list[str]:
    """The Alembic heads at `ref` ([] without `alembic`, or when a migration is unreadable)."""
    if not entry.alembic:
        return []
    try:
        return migrations.heads(
            migrations.revisions(gitops.sources_at(entry.path, ref, entry.alembic))
        )
    except migrations.MigrationUnreadable:
        return []


def template_headings(entry: RepoEntry, tip: str | None, base_branch: str = "master") -> list[str]:
    content = gitops.read_at(entry.path, tip or f"{gitops.REMOTE}/{base_branch}", TEMPLATE_PATH)
    if content is None:
        return list(DEFAULT_HEADINGS)
    found: list[str] = []
    fence: str | None = None
    for line in content.splitlines():
        marker = line.lstrip()[:3]
        if marker in ("```", "~~~"):
            fence = None if fence == marker else fence or marker
        elif fence is None and line.startswith("## "):
            found.append(line.rstrip())
    return found or list(DEFAULT_HEADINGS)


def _commit_problems(name: str, repo: Path, commits: list[tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    for sha, subject in commits:
        short = sha[:7]
        if len(subject) > text.MAX_SUBJECT:
            problems.append(
                f"{name}: commit {short} has {len(subject)} characters in the subject; "
                f"the limit is {text.MAX_SUBJECT}"
            )
        if not text.SUBJECT.match(subject):
            problems.append(f"{name}: commit {short} subject does not match type(TS-N): text")
        if "co-authored-by:" in gitops.message(repo, sha).lower():
            problems.append(f"{name}: commit {short} carries a Co-Authored-By trailer")
    return problems


def _own_commits(
    entry: RepoEntry, shape: str, base: str, code_ref: str, sdbx_ref: str | None, sandbox: str
) -> list[tuple[str, str]]:
    """R5 scope (Ruling 9): what the tool makes, not what the user's task branches carry."""
    repo = entry.path
    found = gitops.commits(repo, f"{base}..{code_ref}", merges=True, first_parent=True)
    if shape == "single":
        found = [(s, m) for s, m in found if text.MASTER_TEXT in m]
    if sdbx_ref:
        from_sandbox = {sha for sha, _ in gitops.commits(repo, f"{code_ref}..{sandbox}")}
        found += [
            c for c in gitops.commits(repo, f"{code_ref}..{sdbx_ref}") if c[0] not in from_sandbox
        ]
    return found


def _alembic_heads(state: RepoState, entry: RepoEntry, tip: str, side: str | None) -> None:
    try:
        revs = migrations.revisions(gitops.sources_at(entry.path, tip, entry.alembic))
        state.heads["code"] = migrations.heads(revs)
        if side:
            revs = migrations.revisions(gitops.sources_at(entry.path, side, entry.alembic))
            state.heads["sandbox"] = migrations.heads(revs)
    except migrations.MigrationUnreadable as error:
        state.problems.append(f"{entry.name}: {error}")
        return
    for key, where in (("code", state.code_branch), ("sandbox", "the sandbox merge")):
        problem = heads_problem(entry.name, where, state.heads.get(key, []))
        if problem and key == "sandbox":
            problem += "; run ws release new"
        if problem:
            state.problems.append(problem)


def assess(
    config: ReleaseConfig,
    entry: RepoEntry,
    includes: tuple[str, ...],
    day: date,
    folder: Path,
) -> RepoState:
    """Reads the repo: nothing is created, merged or pushed. `folder` is the release folder."""
    repo, name = entry.path, entry.name
    base, sandbox = _remote(config.base_branch), _remote(config.sandbox_branch)
    shape = "single" if len(includes) == 1 else "multi"
    release_branch = f"release/{text.compact(day)}"
    code_branch = includes[0] if shape == "single" else release_branch
    code_ref = _ref(repo, code_branch)
    tip = gitops.rev(repo, code_ref) if code_ref else None
    sdbx_name = f"{code_branch}-sdbx"
    sdbx_ref = _ref(repo, sdbx_name)
    state = RepoState(
        repo=name,
        shape=shape,
        includes=tuple(includes),
        code_branch=code_branch,
        tip=tip,
        worktree=None,
        sandbox_head=code_branch,
        sdbx=sdbx_name if sdbx_ref else None,
        sdbx_differs=(),
        ahead=0,
        behind=0,
        remote=gitops.rev(repo, _remote(code_branch)) is not None,
        heads={},
    )
    order_problems, order_warnings, _ = order_check(entry, includes, base)
    state.problems += order_problems
    state.warnings += order_warnings

    if shape == "single" and _ref(repo, release_branch):
        state.problems.append(
            f"{name}: {release_branch} exists but the repo has one include; "
            "a single include uses its own branch"
        )
    _tracking(state, repo, code_branch, config)
    if tip is None or code_ref is None:
        return state
    if shape == "multi":
        found, noted = against_origin(repo, name, code_branch)
        state.problems += found
        state.warnings += noted

    checked_out = gitops.checked_out_at(repo, code_branch)
    state.worktree = str(checked_out) if checked_out else None
    state.behind = gitops.count(repo, f"{tip}..{base}")
    state.ahead = gitops.count(repo, f"{base}..{tip}")
    if state.behind:
        state.problems.append(
            f"{name}: master moved, merge it ({state.behind} commits of origin/master missing)"
        )
    if shape == "multi" and state.ahead == 0:
        state.problems.append(
            f"{name}: {code_branch} has no commits ahead of origin/{config.base_branch}"
        )
    state.headings = template_headings(entry, tip, config.base_branch)

    tree: str | None = None
    conflicts: list[str] = []
    if gitops.rev(repo, sandbox) is None:
        state.problems.append(
            f"{name}: {gitops.REMOTE}/{config.sandbox_branch} does not exist; "
            "the sandbox side cannot be checked"
        )
    else:
        tree, conflicts = gitops.merge_tree(repo, tip, sandbox)
    side = sandbox_heads(entry, tip, tree) if not conflicts else []
    used: str | None = None
    if (conflicts or side) and sdbx_ref:
        used, state.sandbox_head = sdbx_ref, sdbx_name
        _tracking(state, repo, sdbx_name, config)
        found, noted = against_origin(repo, name, sdbx_name)
        state.problems += found
        state.warnings += noted
        problems, differs = mirror(entry, code_branch, sdbx_name, config)
        state.problems += problems
        state.sdbx_differs = tuple(differs)
    elif conflicts:
        state.problems.append(
            f"{name}: {code_branch} conflicts with origin/{config.sandbox_branch} in "
            f"{', '.join(conflicts)}; run ws release new"
        )
    elif sdbx_ref and tree and not gitops.is_ancestor(repo, sdbx_ref, sandbox):
        state.warnings.append(f"{sdbx_name} is not needed: {config.sandbox_branch} merges cleanly")

    state.problems += _commit_problems(
        name, repo, _own_commits(entry, shape, base, code_ref, used, sandbox)
    )
    if entry.alembic:
        _alembic_heads(state, entry, tip, used or tree)
    return state


def _tracking(state: RepoState, repo: Path, branch: str, config: ReleaseConfig) -> None:
    upstream = gitops.upstream(repo, branch)
    if upstream in (f"origin/{config.base_branch}", f"origin/{config.sandbox_branch}"):
        state.problems.append(
            f"{state.repo}: {branch} tracks {upstream}; branches cut from master are --no-track"
        )


def pr_text_problems(
    state: RepoState,
    kind: str,
    draft: PrDraft,
    body: str,
    day: date,
    site: str,
    refs: set[str],
    slugs: dict[str, str],
) -> list[str]:
    """R6 on one PR draft; `body` is the rendered body, `draft.body` the file's own."""
    name = state.repo
    problems: list[str] = []
    title = draft.title
    if kind != "code":
        if not title.endswith(SANDBOX_SUFFIX):
            problems.append(f"{name}: sandbox title must end with {SANDBOX_SUFFIX!r}")
        else:
            title = title[: -len(SANDBOX_SUFFIX)]
        if len(draft.title) > MAX_SANDBOX_TITLE:
            problems.append(f"{name}: sandbox title has more than {MAX_SANDBOX_TITLE} characters")
    if state.shape == "multi":
        if not re.match(rf"^release {text.compact(day)}: .+", title) or text.keys_of(title):
            problems.append(f"{name}: title must be 'release {text.compact(day)}: text', no key")
    else:
        if not SINGLE_TITLE.match(title):
            problems.append(f"{name}: title must be 'type(TS-N): text'")
        line = release_folder.release_line(day)
        if line not in body:
            problems.append(f"{name}: the description lacks '{line}'")
    wanted = {key for branch in state.includes for key in text.keys_of(branch)}
    for key in sorted(wanted - set(draft.tasks)):
        problems.append(f"{name}: tasks lacks {key}, which an include carries")
    for key in draft.tasks:
        if f"{site}/browse/{key}" not in body:
            problems.append(f"{name}: the description lacks the link of {key}")
    lines = {line.strip() for line in body.splitlines()}
    for heading in state.headings:
        if heading not in lines:
            problems.append(f"{name}: the description lacks the heading {heading!r}")
    for bad in release_folder.bad_placeholders(body, refs):
        problems.append(f"{name}: unresolved or unknown placeholder {bad}")
    for repo_name, slug in slugs.items():
        for match in re.finditer(rf"{re.escape(slug)}#\d+", draft.body):
            problems.append(f"{name}: {match.group(0)} written literally; write {{pr:{repo_name}}}")
    return problems
