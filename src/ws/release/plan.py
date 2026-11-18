"""The write plan of `ws release publish|move`: preview, approval and the one place that sends.

A command builds a `WritePlan` (the git pushes, `gh` writes and local steps it wants);
`show_preview` checks every call is inside the shapes `guard` allows and stores the plan under a
code, `approve` rebuilds it live, checks it is still the same plan and guards it again, and
`execute` sends it. `guard` is an allowlist: what it does not name is refused, so nothing here
spells out the forbidden forms."""

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ws import approval, bootstrap, humans
from ws.boardproofs import first_line, run_git
from ws.codeposition import fetch_env
from ws.config import claude_settings_path, data_dir
from ws.release import ReleaseRefused, ReleaseSetup, gitops
from ws.release import folder as release_folder
from ws.release.github import UNCERTAIN_STDERR, Gh, GhFailed, GhMissing, GhUncertain
from ws.release.settings import ReleaseConfig, load_release_config

TASK_BRANCH = r"(feature|chore|refact|hotfix|fix|test)/TS-\d+-[A-Za-z0-9._-]+"
GIT_TIMEOUT_SECONDS = 120
GIT_REJECTED = re.compile(r"^ ! \[(remote )?rejected\]", re.MULTILINE)
GIT_DROPPED = re.compile(
    r"connection was reset|hung up unexpectedly|broken pipe|early EOF|RPC failed",
    re.IGNORECASE,
)
PR_NUMBER = re.compile(r"\d+|\{num:[^{}\s]+\}")
PUBLISHED = "published.json"
QUESTIONS = {"publish": "Publicar no GitHub?", "move": "Mover a release no GitHub?"}


def now() -> datetime:
    return datetime.now(UTC)


def session_id() -> int:
    return approval.session_id()


def store() -> Path:
    return data_dir() / "release" / "pending"


@dataclass(frozen=True)
class Shapes:
    """The branch and path shapes a release write may touch: the release branch and one copy per
    configured environment suffix."""

    pushable: re.Pattern[str]
    release_only: re.Pattern[str]
    release_ref: re.Pattern[str]
    release_path: re.Pattern[str]
    protected: frozenset[str]


def shapes_of(config: ReleaseConfig) -> Shapes:
    suffixes = "|".join(re.escape(env.suffix) for env in config.environments)
    optional = f"({suffixes})?" if suffixes else "()"
    release = rf"release/\d{{8}}{optional}"
    return Shapes(
        pushable=re.compile(rf"{release}|{TASK_BRANCH}"),
        release_only=re.compile(release),
        release_ref=re.compile(
            rf"refs/remotes/origin/release/\d{{8}}({suffixes}|):refs/heads/release/\d{{8}}\1"
        ),
        release_path=re.compile(rf"(/[^/\s]+)*/?release-\d{{8}}{optional}(/[^/\s]+)?"),
        protected=frozenset(config.protected),
    )


@dataclass(frozen=True)
class Call:
    """One write. `args` leave out the program. A `local` call is `(handler name, *arguments)`.
    `answers` names the ref whose PR a `pr create` makes."""

    repo: str
    program: str
    args: tuple[str, ...]
    line: str
    cwd: str | None = None
    body: str | None = None
    answers: str | None = None


@dataclass
class WritePlan:
    action: str
    slug: str
    days: tuple[str, ...]
    tips: dict[str, dict[str, str]]
    calls: list[Call]
    drafts: list[dict]
    facts: dict
    problems: list[str] = field(default_factory=list)

    def material(self) -> dict:
        return {
            "action": self.action,
            "slug": self.slug,
            "days": list(self.days),
            "tips": self.tips,
            "calls": [asdict(call) for call in self.calls],
            "drafts": self.drafts,
            "facts": self.facts,
        }

    @property
    def summary(self) -> list[str]:
        return [call.line for call in self.calls]

    @property
    def code(self) -> str:
        return approval.digest(self.material())


def known_entry(slug: str, number: int, url: str) -> list:
    """How a placeholder `{pr:REF}`, `{url:REF}` or `{num:REF}` is filled: `slug#N`, url, N."""
    return [f"{slug}#{number}", url, int(number)]


def fetch_repos(config: ReleaseConfig, names: Iterable[str]) -> list[str]:
    """Fetches each repo; a failure is a warning, never a stop."""
    warnings = []
    for name in names:
        error = gitops.fetch(config.entry(name).path)
        if error:
            warnings.append(f"{name}: fetch failed: {error}")
    return warnings


def session(
    project: str | None, repo_names: Callable[[ReleaseConfig, str], Iterable[str]]
) -> tuple[ReleaseConfig, Gh, str, list[str]]:
    """What a write command starts with: the config, a logged-in `gh`, the project slug, and the
    fetch of the repos `repo_names(config, slug)` gives (failures as warnings)."""
    config = load_release_config()
    gh = Gh()
    try:
        gh.require_auth()
    except GhMissing as error:
        raise ReleaseSetup(f"gh: {error}") from error
    slug = release_folder.resolve_slug(project, Path.cwd())
    return config, gh, slug, fetch_repos(config, repo_names(config, slug))


def read_release(folder: Path, names: tuple[str, ...]) -> release_folder.ReleaseFile:
    """`release.toml` of `folder`; a missing one means the release cannot be evaluated (exit 2)."""
    if not (folder / "release.toml").is_file():
        raise ReleaseSetup(f"{folder / 'release.toml'} not found")
    return release_folder.read_release(folder, names)


def write_published(folder: Path, data: dict) -> None:
    """Writes `published.json` whole, through a temporary file, so a reader never sees half."""
    release_folder.ensure_dir(folder)
    path = folder / PUBLISHED
    temporary = path.with_name(PUBLISHED + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@contextmanager
def warnings_on_refusal(warnings: list[str]) -> Iterator[None]:
    """A refusal raised inside carries the warnings, so a failed fetch is not hidden behind it."""
    try:
        yield
    except ReleaseRefused as error:
        if error.payload is not None:
            error.payload["warnings"] = warnings
        elif warnings:
            error.payload = {"warnings": warnings}
        raise


def _same_body(left: str, right: str) -> bool:
    def norm(value: str) -> str:
        return value.replace("\r\n", "\n").rstrip("\n")

    return norm(left) == norm(right)


def refresh_edit(
    repo: str,
    slug: str,
    number: int,
    current: str,
    wanted: str,
    known: dict,
    refs: set[str],
    line: str,
) -> Call | None:
    """The `pr edit` that turns the body PR `number` has now into `wanted`: the placeholders of
    PRs known by now are filled in and those of `refs` still to be created wait for the send.
    `None` when that would leave the body as it is."""
    body = release_folder.resolve_refs(wanted, known)
    waiting = refs.intersection(release_folder.pending_refs(body))
    if not waiting and _same_body(body, current):
        return None
    return Call(
        repo=repo,
        program="gh",
        args=("pr", "edit", str(number), "-R", slug),
        line=line,
        body=body,
    )


def create_slug(call: Call) -> str | None:
    args = call.args
    return args[args.index("-R") + 1] if "-R" in args and args.index("-R") + 1 < len(args) else None


def second_pass(calls: list[Call]) -> list[Call]:
    """For each create whose body names a PR a later create opens, an edit that fills it in."""
    edits = []
    for index, call in enumerate(calls):
        if call.args[:2] != ("pr", "create") or not call.answers or call.body is None:
            continue
        later = {other.answers for other in calls[index + 1 :] if other.answers}
        slug = create_slug(call)
        if slug and later.intersection(release_folder.pending_refs(call.body)):
            edits.append(
                Call(
                    repo=call.repo,
                    program="gh",
                    args=("pr", "edit", f"{{num:{call.answers}}}", "-R", slug),
                    line=f"segunda passada: {call.line}",
                    body=call.body,
                )
            )
    return edits


def guard(plan: WritePlan, config: ReleaseConfig, local_names: tuple[str, ...] = ()) -> str | None:
    """The last line of defence: the call that is outside the allowed shapes, or `None`."""
    slugs = {repo.slug for repo in config.repos}
    shapes = shapes_of(config)
    for call in plan.calls:
        if not _allowed(call, slugs, shapes, local_names):
            return f"{call.program} {' '.join(call.args)}"
    return None


def _allowed(call: Call, slugs: set[str], shapes: Shapes, local_names: tuple[str, ...]) -> bool:
    args = call.args
    if call.program == "local":
        return bool(args) and args[0] in local_names
    if call.program == "git":
        return call.cwd is not None and _git_allowed(args, shapes)
    if call.program == "gh":
        return _gh_allowed(args, slugs, shapes)
    return False


def _git_allowed(args: tuple[str, ...], shapes: Shapes) -> bool:
    release = shapes.release_only
    match args:
        case ("push", "-u", "origin", branch):
            return branch not in shapes.protected and shapes.pushable.fullmatch(branch) is not None
        case ("push", "origin", spec):
            return shapes.release_ref.fullmatch(spec) is not None
        case ("push", "origin", "--delete", branch):
            return release.fullmatch(branch) is not None
        case ("branch", "-m", old, new):
            return all(release.fullmatch(name) for name in (old, new))
        case ("branch", "-u", upstream, branch):
            return (
                upstream.startswith("origin/")
                and release.fullmatch(upstream.removeprefix("origin/")) is not None
                and release.fullmatch(branch) is not None
            )
        case ("worktree", "move", source, target):
            return all(_release_path(path, shapes) for path in (source, target))
    return False


def _release_path(path: str, shapes: Shapes) -> bool:
    return ".." not in path.split("/") and shapes.release_path.fullmatch(path) is not None


def _gh_allowed(args: tuple[str, ...], slugs: set[str], shapes: Shapes) -> bool:
    match args:
        case ("pr", "create", "-R", slug, "--base", base, "--head", head, "--title", title, *rest):
            return (
                slug in slugs
                and base in shapes.protected
                and head not in shapes.protected
                and shapes.pushable.fullmatch(head) is not None
                and bool(title)
                and _create_extras(tuple(rest))
            )
        case ("pr", "edit", number, "-R", slug):
            return PR_NUMBER.fullmatch(number) is not None and slug in slugs
        case ("pr", "close", number, "-R", slug, "--comment", _):
            return PR_NUMBER.fullmatch(number) is not None and slug in slugs
        case ("pr", "comment", number, "-R", slug, "--body", _):
            return PR_NUMBER.fullmatch(number) is not None and slug in slugs
    return False


def _create_extras(rest: tuple[str, ...]) -> bool:
    if len(rest) % 2:
        return False
    return all(rest[i] in ("--label", "--assignee") and rest[i + 1] for i in range(0, len(rest), 2))


def preview_command(action: str) -> str:
    return f"ws release preview {action}"


def show_preview(
    plan: WritePlan, next_command: str, config: ReleaseConfig, local_names: tuple[str, ...] = ()
) -> tuple[dict, int]:
    """Stores the plan under its code. The guard runs here as at the approval, so no preview hands
    out a code the approval would refuse; an empty plan gets no code."""
    if (refused := guard(plan, config, local_names)) is not None:
        plan.problems.append(f"call outside the allowed shapes: {refused}")
    if plan.problems:
        raise ReleaseRefused("; ".join(plan.problems), {"problems": plan.problems})
    if not plan.calls:
        return {"nothing_to_send": True}, 0
    try:
        code = plan.code
    except (TypeError, ValueError) as error:
        raise ReleaseRefused(
            f"the plan holds a value that is not JSON-safe (string keys, no tuples): {error}"
        ) from None
    record = {
        "code": code,
        "action": plan.action,
        "created_at": now().isoformat(),
        "sid": session_id(),
        "material": plan.material(),
        "summary": plan.summary,
    }
    try:
        approval.ensure_store(store())
        approval.purge_expired(store(), now=now(), preview=preview_command(plan.action))
        approval.write_pending(store(), code, record)
    except OSError as error:
        raise ReleaseSetup(f"cannot store the pending preview in {store()}: {error}") from None
    calls = [f"{call.repo}: {call.program} {' '.join(call.args)}" for call in plan.calls]
    payload = {
        "code": code,
        "summary": plan.summary,
        "calls": calls,
        "next": f"{next_command} --approve {code}",
    }
    return payload, 0


def _confirm(summary: list[str], action: str) -> bool:
    print("\n".join(summary), file=sys.stderr)
    print(f"{QUESTIONS[action]} [s/N] ", end="", file=sys.stderr, flush=True)
    try:
        answer = input()
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return False
    return answer.strip().lower() in ("s", "sim")


def _record_for(code: str, action: str) -> dict:
    preview = preview_command(action)
    record, refusal = approval.read_pending(store(), code, now=now(), preview=preview)
    if refusal:
        raise ReleaseRefused(refusal)
    if record is None:
        raise ReleaseRefused(f"no pending preview for code {code}; run {preview} first")
    if now() - record["_created"] > approval.APPROVAL_WINDOW:
        (store() / f"{code}.json").unlink(missing_ok=True)
        raise ReleaseRefused(f"the preview expired (30 minutes); run {preview} again")
    try:
        matches = approval.digest(record["material"]) == code and record["summary"] == [
            call["line"] for call in record["material"]["calls"]
        ]
    except (KeyError, TypeError):
        matches = False
    if not matches:
        raise ReleaseRefused(f"the pending record was changed; run {preview} again")
    if record.get("action") != action:
        raise ReleaseRefused(
            f"the code {code} belongs to a {record.get('action')} preview, not {action}"
        )
    return record


def approve(
    code: str,
    action: str,
    build: Callable[[], WritePlan],
    gh: Gh,
    config: ReleaseConfig,
    local: dict[str, Callable[..., None]] | None = None,
) -> tuple[dict, int]:
    by_hand = humans.by_hand()
    if not by_hand and (problems := bootstrap.release_gate_problems(claude_settings_path())):
        raise ReleaseSetup(
            f"{'; '.join(problems)}. Run `ws setup` and add what it prints, so Claude Code asks "
            "you before every approval"
        )
    if not approval.CODE.fullmatch(code):
        raise ReleaseRefused(f"{code!r} is not an approval code (12 hex characters)")
    approval.ensure_store(store())
    record = _record_for(code, action)
    if not by_hand and (record.get("sid") is None or record.get("sid") == session_id()):
        raise ReleaseRefused(
            "the preview and the approval must be separate steps "
            "(run the approval in another command, after showing the preview)"
        )
    live = build()
    if live.problems:
        raise ReleaseRefused("; ".join(live.problems), {"problems": live.problems})
    if live.code != code:
        raise ReleaseRefused(
            "the plan differs from the preview (state or flags changed); run the preview again"
        )
    if (refused := guard(live, config, tuple(local or {}))) is not None:
        raise ReleaseRefused(f"call outside the allowed shapes: {refused}")
    if by_hand and not _confirm(live.summary, action):
        raise ReleaseRefused("nothing was sent")
    try:
        (store() / f"{code}.json").unlink()
    except FileNotFoundError:
        raise ReleaseRefused(f"the preview {code} was already used") from None
    return execute(live, gh, local)


class LocalFailed(Exception):
    """A local handler raised."""


def _git(call: Call, args: tuple[str, ...]) -> None:
    repo = Path(call.cwd)
    try:
        done = run_git(repo, *args, timeout=GIT_TIMEOUT_SECONDS, env=fetch_env(repo))
    except subprocess.TimeoutExpired:
        raise GhUncertain(f"git {args[0]} timed out") from None
    if done.returncode != 0:
        text = done.stderr or done.stdout
        message = first_line(text)
        if not GIT_REJECTED.search(text) and (
            UNCERTAIN_STDERR.search(text) or GIT_DROPPED.search(text)
        ):
            raise GhUncertain(message)
        raise gitops.GitFailed(message)


def _pr_number(url: str | None) -> int:
    try:
        return int((url or "").rsplit("/", 1)[-1])
    except ValueError:
        raise GhUncertain("gh did not print a PR URL") from None


def _send(
    call: Call, gh: Gh, local: dict[str, Callable[..., None]], known: dict
) -> tuple[str | None, str | None]:
    """Sends one call; returns (the URL a create printed, the ref it answers)."""
    args = tuple(release_folder.resolve_refs(arg, known) for arg in call.args)
    body = release_folder.resolve_refs(call.body, known) if call.body is not None else None
    if call.program == "local":
        try:
            local[args[0]](*args[1:])
        except Exception as error:
            raise LocalFailed(str(error)) from error
        return None, None
    if call.program == "git":
        _git(call, args)
        return None, None
    if any(release_folder.pending_refs(arg) for arg in args):
        raise GhFailed("a placeholder in the arguments has no PR to point to")
    output = gh.write(args, body)
    return (output.splitlines()[-1] if output else ""), call.answers


def execute(
    plan: WritePlan, gh: Gh, local: dict[str, Callable[..., None]] | None = None
) -> tuple[dict, int]:
    """Sends the calls in order and stops at the first failure. Nothing is retried. `known` in the
    result is every PR a placeholder can name after the run: the plan's and the ones it made."""
    known = {
        ref: [value[0], value[1], int(value[2])]
        for ref, value in plan.facts.get("known", {}).items()
    }
    done: list[str] = []
    prs: dict[str, str] = {}
    result = {
        "done": done,
        "failed": None,
        "not_sent": [],
        "uncertain": False,
        "prs": prs,
        "known": known,
    }
    for index, call in enumerate(plan.calls):
        try:
            url, answers = _send(call, gh, local or {}, known)
            if answers:
                known[answers] = known_entry(create_slug(call) or "", _pr_number(url), url or "")
                prs[answers] = url or ""
        except GhUncertain as error:
            print(f"resultado incerto: confira no GitHub ({error})", file=sys.stderr)
            result["uncertain"] = True
            return _stopped(result, plan, index, call), 1
        except Exception as error:
            print(f"ws release: {call.line}: {error}", file=sys.stderr)
            return _stopped(result, plan, index, call), 1
        done.append(call.line)
    return result, 0


def _stopped(result: dict, plan: WritePlan, index: int, call: Call) -> dict:
    result["failed"] = call.line
    result["not_sent"] = [later.line for later in plan.calls[index + 1 :]]
    return result
