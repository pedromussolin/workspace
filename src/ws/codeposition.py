"""Where the commits of a card are: only a branch, the sandbox, master or a production image tag."""

import math
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from ws.boardconfig import BoardConfig, Environment
from ws.standup import keys_in
from ws.taskmodel import RUNG, Status

FETCH_TIMEOUT_SECONDS = 120
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


def _run(repo: Path, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )


def _has_remote(repo: Path, remote: str) -> bool:
    return _run(repo, "remote", "get-url", remote).returncode == 0


def _first_line(text: str) -> str:
    lines = [line for line in text.split("\n") if line.strip()]
    return lines[0].strip() if lines else "unknown error"


def _fetch_one(repo: Path, remote: str) -> str | None:
    try:
        result = _run(repo, "fetch", "--prune", "--quiet", remote, timeout=FETCH_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return f"timeout after {FETCH_TIMEOUT_SECONDS}s"
    except OSError as error:
        return str(error)
    return None if result.returncode == 0 else _first_line(result.stderr)


def fetch(repos: list[Path], remote: str) -> dict[str, str]:
    """Fetches `remote` in every repo that has it; returns repo name -> error for failures."""
    with_remote = [repo for repo in repos if _has_remote(repo, remote)]
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        errors = list(pool.map(lambda repo: _fetch_one(repo, remote), with_remote))
    return {repo.name: error for repo, error in zip(with_remote, errors, strict=True) if error}


def _git_out(repo: Path, *args: str, ok: tuple[int, ...] = (0,)) -> str:
    result = _run(repo, *args)
    if result.returncode not in ok:
        raise RuntimeError(_first_line(result.stderr))
    return result.stdout


def _lines(output: str) -> list[str]:
    return [line for line in output.split("\n") if line]


def _commits(repo: Path, keys: set[str], since: date) -> list[tuple[str, str, set[str]]]:
    output = _git_out(
        repo,
        "log",
        "--exclude=refs/stash",
        "--all",
        "--no-merges",
        f"--since={since.isoformat()}",
        f"--format=%H{FIELD_SEPARATOR}%s",
    )
    found = []
    for line in _lines(output):
        sha, _, subject = line.partition(FIELD_SEPARATOR)
        wanted = set(keys_in(subject)) & keys
        if wanted:
            found.append((sha, subject, wanted))
    return found


def _reachable(repo: Path, ref: str, since: date) -> set[str]:
    return set(_lines(_git_out(repo, "rev-list", f"--since={since.isoformat()}", ref)))


def _branch_sets(
    repo: Path, cfg: BoardConfig, walk_since: date
) -> list[tuple[Environment, set[str]]]:
    available = []
    for env in cfg.environments:
        if not env.branches:
            continue
        for branch in cfg.branches_for(repo.name, env):
            ref = f"refs/remotes/{cfg.remote}/{branch}"
            if _run(repo, "rev-parse", "--verify", "-q", ref).returncode == 0:
                available.append((env, _reachable(repo, ref, walk_since)))
                break
    return available


def _tagged_commits(
    repo: Path, env: Environment, cfg: BoardConfig, walk_since: date, warnings: list[str]
) -> set[str] | None:
    """Commits contained in every image tag of `repo` found in the deploy repo's branch."""
    deploy_name = cfg.deploy_repo_for(repo.name, env)
    deploy = repo.parent / deploy_name
    if not (deploy / ".git").exists():
        warnings.append(f"deploy {repo.name}: {deploy_name} not found")
        return None
    ref = f"{cfg.remote}/{env.deploy_branch}"
    found = _run(deploy, "grep", "-hoE", env.image_tag.pattern, ref)
    if found.returncode not in (0, 1, 128):
        raise RuntimeError(_first_line(found.stderr))
    tags = set()
    for line in _lines(found.stdout) if found.returncode == 0 else []:
        match = env.image_tag.search(line)
        if match:
            tags.add(match.group(1))
    full = []
    for tag in sorted(tags):
        resolved = _run(repo, "rev-parse", "--verify", "-q", f"{tag}^{{commit}}")
        if resolved.returncode == 0:
            full.append(resolved.stdout.strip())
    if not full:
        warnings.append(f"deploy {repo.name}: no image tag of this repo in {deploy_name}")
        return None
    shas = _reachable(repo, full[0], walk_since)
    for sha in full[1:]:
        shas &= _reachable(repo, sha, walk_since)
    return shas


def _environment_branches(repo: Path, cfg: BoardConfig) -> set[str]:
    names: set[str] = set()
    for env in cfg.environments:
        for branch in cfg.branches_for(repo.name, env):
            names.update({branch, f"{cfg.remote}/{branch}"})
    return names


def _holding_branch(repo: Path, sha: str, cfg: BoardConfig) -> str | None:
    output = _git_out(repo, "branch", "-a", "--contains", sha, "--format=%(refname:short)")
    skip = _environment_branches(repo, cfg) | {cfg.remote}
    for name in _lines(output):
        if name in skip or name.endswith("/HEAD") or name.startswith("("):
            continue
        return name
    return None


def _repo_pieces(
    repo: Path,
    cfg: BoardConfig,
    walk_since: date,
    commits: list[tuple[str, str, set[str]]],
    warnings: list[str],
) -> list[tuple[_Piece, set[str]]]:
    sets: list[tuple[int, set[str]]] = []
    if _has_remote(repo, cfg.remote):
        branch_sets = _branch_sets(repo, cfg, walk_since)
        sets = [(env.rung, shas) for env, shas in branch_sets]
        if cfg.direct_deploy(repo.name) and branch_sets:
            sets.append((DONE_RUNG, branch_sets[-1][1]))
        for env in cfg.environments:
            if env.image_tag is not None and not cfg.direct_deploy(repo.name):
                tagged = _tagged_commits(repo, env, cfg, walk_since, warnings)
                if tagged is not None:
                    sets.append((env.rung, tagged))
    cap = max((rung for rung, _ in sets), default=0)
    pieces = []
    for sha, subject, wanted in commits:
        reached = max((rung for rung, shas in sets if sha in shas), default=0)
        pieces.append((_Piece(repo.name, sha, subject, reached, cap), wanted))
    return pieces


def _value(piece: _Piece) -> float:
    return math.inf if piece.reached == piece.cap else piece.reached


def _environment_at(cfg: BoardConfig, rung: int) -> str | None:
    return next((env.name for env in cfg.environments if env.rung == rung), None)


def _position(
    pieces: list[_Piece],
    cfg: BoardConfig,
    stale: set[str],
    repos: dict[str, Path],
) -> Position:
    low = min(_value(piece) for piece in pieces)
    if low == math.inf:
        rung = max(piece.cap for piece in pieces)
    else:
        rung = int(low)
    rung = max(rung, 1)
    holding = None
    if low != math.inf:
        held = next(piece for piece in pieces if _value(piece) == low)
        holding = Holding(
            held.repo,
            held.sha[:7],
            held.subject,
            _environment_at(cfg, held.reached) if held.reached else None,
            _holding_branch(repos[held.repo], held.sha, cfg),
        )
    names = sorted({piece.repo for piece in pieces})
    return Position(
        rung,
        None if rung == 1 else _environment_at(cfg, rung),
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
            commits = _commits(repo, keys, since)
            if not commits:
                continue
            found = _repo_pieces(repo, cfg, walk_since, commits, warnings)
        except (RuntimeError, OSError) as error:
            warnings.append(f"repo {repo.name}: left out ({error})")
            continue
        for piece, wanted in found:
            for key in wanted:
                by_key.setdefault(key, []).append(piece)
    result = {}
    for key, pieces in by_key.items():
        try:
            result[key] = _position(pieces, cfg, stale, by_name)
        except (RuntimeError, OSError) as error:
            warnings.append(f"repo {pieces[0].repo}: left out ({error})")
    return result, warnings
