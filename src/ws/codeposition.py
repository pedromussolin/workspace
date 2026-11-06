"""Where the commits of a card are: outside every environment, or in the ones their proofs give."""

import math
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from ws.boardconfig import BoardConfig, BranchProof, Environment
from ws.boardproofs import Markers, first_line, git_out, lines, markers, run_git
from ws.standup import keys_in
from ws.taskmodel import RUNG, Status

FETCH_TIMEOUT_SECONDS = 60
BATCH_SSH = "ssh -o BatchMode=yes -o ConnectTimeout=10"
FETCH_WORKERS = 8
CLOCK_SKEW_DAYS = 30
DONE_RUNG = RUNG[Status.DONE]
FIELD_SEPARATOR = "\x1f"


@dataclass(frozen=True)
class Holding:
    repo: str
    commit: str
    subject: str
    reached: str | None
    branch: str | None
    tag: str | None = None


@dataclass(frozen=True)
class Position:
    rung: int
    environment: str | None
    holding: Holding | None
    repos: tuple[str, ...]
    stale: bool
    limited: bool


@dataclass(frozen=True)
class _Piece:
    repo: str
    sha: str
    subject: str
    reached: int
    cap: int
    tag: str | None = None


def _has_remote(repo: Path, remote: str) -> bool:
    return run_git(repo, "remote", "get-url", remote).returncode == 0


def _fetch_one(repo: Path, cfg: BoardConfig) -> str | None:
    tags = "--tags" if cfg.uses_tags(repo.name) else "--no-tags"
    try:
        result = run_git(
            repo,
            "fetch",
            "--prune",
            "--quiet",
            tags,
            cfg.remote,
            timeout=FETCH_TIMEOUT_SECONDS,
            env={"GIT_SSH_COMMAND": BATCH_SSH, **os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.TimeoutExpired:
        return f"timeout after {FETCH_TIMEOUT_SECONDS}s"
    except OSError as error:
        return str(error)
    return None if result.returncode == 0 else first_line(result.stderr)


def fetch(repos: list[Path], cfg: BoardConfig) -> dict[str, str]:
    """Fetches the remote in every repo that has it; returns repo name -> error for failures.

    Tags come only to repos whose profile proves an environment by a tag.
    """
    with_remote = [repo for repo in repos if _has_remote(repo, cfg.remote)]
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        errors = list(pool.map(lambda repo: _fetch_one(repo, cfg), with_remote))
    return {repo.name: error for repo, error in zip(with_remote, errors, strict=True) if error}


def _commits(
    repo: Path, keys: set[str], remote: str, since: date
) -> list[tuple[str, str, set[str]]]:
    """Commits of branches and remote branches only: archived refs and stashes are not work."""
    output = git_out(
        repo,
        "log",
        "--branches",
        f"--remotes={remote}",
        "--no-merges",
        f"--since={since.isoformat()}",
        f"--format=%H{FIELD_SEPARATOR}%s",
    )
    found = []
    for line in lines(output):
        sha, _, subject = line.partition(FIELD_SEPARATOR)
        wanted = set(keys_in(subject)) & keys
        if wanted:
            found.append((sha, subject, wanted))
    return found


def _environment_branches(repo: Path, cfg: BoardConfig) -> set[str]:
    names: set[str] = set()
    for env in cfg.environments_for(repo.name):
        if isinstance(env.proof, BranchProof):
            for branch in env.proof.branches:
                names.update({branch, f"{cfg.remote}/{branch}"})
    return names


def _holding_branch(
    repo: Path, sha: str, key: str, cfg: BoardConfig, warnings: list[str]
) -> str | None:
    """The card's own branch first (a `-sdbx` copy only after it), then any work branch."""
    try:
        output = git_out(repo, "branch", "-a", "--contains", sha, "--format=%(refname:short)")
    except (RuntimeError, OSError) as error:
        warnings.append(f"repo {repo.name}: holding branch unknown ({error})")
        return None
    skip = _environment_branches(repo, cfg) | {cfg.remote}
    names = [
        name
        for name in lines(output)
        if name not in skip and not name.endswith("/HEAD") and not name.startswith("(")
    ]
    with_key = [name for name in names if key in keys_in(name)]
    own = [name for name in with_key if not name.endswith("-sdbx")]
    return next(iter(own or with_key or names), None)


def _lacking_tag(
    sha: str, reached: int, active: tuple[Environment, ...], proven: dict[str, Markers]
) -> str | None:
    """The marker of the next environment that lacks `sha`, once `sha` reached the one before it."""
    index = next((i for i, env in enumerate(active) if env.rung == reached), None)
    if index is None or index + 1 == len(active):
        return None
    following = active[index + 1]
    if isinstance(following.proof, BranchProof):
        return None
    given = proven.get(following.name, [])
    return next((text for text, shas in given if sha not in shas), None)


def _inside(given: Markers) -> set[str]:
    """The commits every marker reaches; none when the proof failed and gave no marker."""
    return set.intersection(*(shas for _, shas in given)) if given else set()


def _repo_pieces(
    repo: Path,
    cfg: BoardConfig,
    walk_since: date,
    commits: list[tuple[str, str, set[str]]],
    warnings: list[str],
) -> list[tuple[_Piece, set[str]]]:
    active = cfg.environments_for(repo.name)
    proven: dict[str, Markers] = {}
    if _has_remote(repo, cfg.remote):
        for env in active:
            given = markers(repo, env, cfg, walk_since, warnings)
            if given is not None:
                proven[env.name] = given
    sets = [(env.rung, _inside(proven[env.name])) for env in active if env.name in proven]
    cap = max((rung for rung, _ in sets), default=0)
    pieces = []
    for sha, subject, wanted in commits:
        reached = max((rung for rung, shas in sets if sha in shas), default=0)
        tag = _lacking_tag(sha, reached, active, proven)
        pieces.append((_Piece(repo.name, sha, subject, reached, cap, tag), wanted))
    return pieces


def _value(piece: _Piece) -> float:
    return math.inf if piece.reached == piece.cap else piece.reached


def _environment_at(cfg: BoardConfig, repo: str, rung: int) -> str | None:
    return next((env.name for env in cfg.environments_for(repo) if env.rung == rung), None)


def _position(
    key: str,
    pieces: list[_Piece],
    cfg: BoardConfig,
    stale: set[str],
    repos: dict[str, Path],
    warnings: list[str],
) -> Position:
    low = min(_value(piece) for piece in pieces)
    held = None if low == math.inf else next(piece for piece in pieces if _value(piece) == low)
    decider = held or max(pieces, key=lambda piece: piece.cap)
    rung = max(decider.cap if held is None else decider.reached, 1)
    holding = None
    if held is not None:
        holding = Holding(
            held.repo,
            held.sha[:7],
            held.subject,
            _environment_at(cfg, held.repo, held.reached) if held.reached else None,
            _holding_branch(repos[held.repo], held.sha, key, cfg, warnings),
            held.tag,
        )
    names = sorted({piece.repo for piece in pieces})
    return Position(
        rung,
        None if rung == 1 else _environment_at(cfg, decider.repo, rung),
        holding,
        tuple(names),
        any(name in stale for name in names),
        low == math.inf and rung < DONE_RUNG,
    )


def positions(
    repos: list[Path], keys: set[str], cfg: BoardConfig, today: date, stale: set[str]
) -> tuple[dict[str, Position], list[str]]:
    since = today - timedelta(days=cfg.lookback_days)
    walk_since = since - timedelta(days=CLOCK_SKEW_DAYS)
    warnings: list[str] = []
    by_key: dict[str, list[_Piece]] = {}
    by_name = {repo.name: repo for repo in repos}
    no_remote = sorted(repo.name for repo in repos if not _has_remote(repo, cfg.remote))
    if no_remote:
        warnings.append(
            f"no remote '{cfg.remote}' (only prove in progress): {', '.join(no_remote)}"
        )
    for repo in sorted(repos, key=lambda item: item.name):
        try:
            commits = _commits(repo, keys, cfg.remote, since)
            if not commits:
                continue
            found = _repo_pieces(repo, cfg, walk_since, commits, warnings)
        except (RuntimeError, OSError) as error:
            warnings.append(f"repo {repo.name}: left out ({error})")
            continue
        for piece, wanted in found:
            for key in wanted:
                by_key.setdefault(key, []).append(piece)
    return {
        key: _position(key, pieces, cfg, stale, by_name, warnings) for key, pieces in by_key.items()
    }, warnings
