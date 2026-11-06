"""Where the commits of a card are: outside every environment, or in the ones their proofs give."""

import math
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from ws.boardconfig import BoardConfig, BranchProof, Environment, FileProof, TagProof
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


def _run(
    repo: Path, *args: str, timeout: float | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
        env=env,
    )


def _has_remote(repo: Path, remote: str) -> bool:
    return _run(repo, "remote", "get-url", remote).returncode == 0


def _first_line(text: str) -> str:
    lines = [line for line in text.split("\n") if line.strip()]
    return lines[0].strip() if lines else "unknown error"


def _fetch_one(repo: Path, cfg: BoardConfig) -> str | None:
    tags = "--tags" if cfg.uses_tags(repo.name) else "--no-tags"
    try:
        result = _run(
            repo,
            "fetch",
            "--prune",
            "--quiet",
            tags,
            cfg.remote,
            timeout=FETCH_TIMEOUT_SECONDS,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.TimeoutExpired:
        return f"timeout after {FETCH_TIMEOUT_SECONDS}s"
    except OSError as error:
        return str(error)
    return None if result.returncode == 0 else _first_line(result.stderr)


def fetch(repos: list[Path], cfg: BoardConfig) -> dict[str, str]:
    """Fetches the remote in every repo that has it; returns repo name -> error for failures.

    Tags come only to repos whose profile proves an environment by a tag.
    """
    with_remote = [repo for repo in repos if _has_remote(repo, cfg.remote)]
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        errors = list(pool.map(lambda repo: _fetch_one(repo, cfg), with_remote))
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


def _branch_markers(
    repo: Path, proof: BranchProof, cfg: BoardConfig, walk_since: date
) -> list[tuple[str, set[str]]] | None:
    """The tip of the first branch of `proof` that exists on the remote."""
    for branch in proof.branches:
        ref = f"refs/remotes/{cfg.remote}/{branch}"
        if _run(repo, "rev-parse", "--verify", "-q", ref).returncode == 0:
            return [(branch, _reachable(repo, ref, walk_since))]
    return None


def _tag_markers(
    repo: Path, proof: TagProof, walk_since: date
) -> list[tuple[str, set[str]]] | None:
    """The most recent tag (creation date, then the highest name) matching the glob."""
    newest = _git_out(
        repo,
        "for-each-ref",
        "--sort=-v:refname",
        "--sort=-creatordate",
        "--count=1",
        "--format=%(refname)",
        f"refs/tags/{proof.pattern}",
    ).strip()
    if not newest:
        return None
    return [(newest.removeprefix("refs/tags/"), _reachable(repo, newest, walk_since))]


def _file_markers(
    repo: Path, proof: FileProof, cfg: BoardConfig, walk_since: date, warnings: list[str]
) -> list[tuple[str, set[str]]] | None:
    """The history of each image tag of `repo` found in the deploy repo's branch."""
    deploy_name = proof.deploy_repo.format(repo=repo.name)
    deploy = repo.parent / deploy_name
    if not (deploy / ".git").exists():
        warnings.append(f"deploy {repo.name}: {deploy_name} not found")
        return None
    ref = f"{cfg.remote}/{proof.deploy_branch}"
    lines: list[str] = []
    if _run(deploy, "rev-parse", "--verify", "-q", ref).returncode == 0:
        found = _run(deploy, "grep", "-h", "-o", "-E", "-e", proof.image_tag.pattern, ref, "--")
        if found.returncode not in (0, 1):
            warnings.append(f"deploy {repo.name}: {_first_line(found.stderr)}")
            return None
        lines = _lines(found.stdout)
    tags: dict[str, str] = {}
    for line in lines:
        match = proof.image_tag.search(line)
        if match:
            tags.setdefault(match.group(1), match.group(0))
    full = []
    for sha, text in sorted(tags.items(), key=lambda item: item[1]):
        resolved = _run(repo, "rev-parse", "--verify", "-q", f"{sha}^{{commit}}")
        if resolved.returncode == 0:
            full.append((text, resolved.stdout.strip()))
    if not full:
        warnings.append(f"deploy {repo.name}: no image tag of this repo in {deploy_name}")
        return None
    return [(text, _reachable(repo, sha, walk_since)) for text, sha in full]


def _markers(
    repo: Path, env: Environment, cfg: BoardConfig, walk_since: date, warnings: list[str]
) -> list[tuple[str, set[str]]] | None:
    """What `env`'s proof gives in `repo`: (marker, commits reachable from it); None proves nothing.

    A commit is in the environment when every marker reaches it.
    """
    if isinstance(env.proof, BranchProof):
        return _branch_markers(repo, env.proof, cfg, walk_since)
    if isinstance(env.proof, TagProof):
        return _tag_markers(repo, env.proof, walk_since)
    if isinstance(env.proof, FileProof):
        return _file_markers(repo, env.proof, cfg, walk_since, warnings)
    return None


def _environment_branches(repo: Path, cfg: BoardConfig) -> set[str]:
    names: set[str] = set()
    for env in cfg.environments_for(repo.name):
        if isinstance(env.proof, BranchProof):
            for branch in env.proof.branches:
                names.update({branch, f"{cfg.remote}/{branch}"})
    return names


def _holding_branch(repo: Path, sha: str, cfg: BoardConfig, warnings: list[str]) -> str | None:
    try:
        output = _git_out(repo, "branch", "-a", "--contains", sha, "--format=%(refname:short)")
    except (RuntimeError, OSError) as error:
        warnings.append(f"repo {repo.name}: holding branch unknown ({error})")
        return None
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
    proven: list[tuple[Environment, list[tuple[str, set[str]]]]] = []
    if _has_remote(repo, cfg.remote):
        for env in cfg.environments_for(repo.name):
            markers = _markers(repo, env, cfg, walk_since, warnings)
            if markers is not None:
                proven.append((env, markers))
    sets = [(env.rung, set.intersection(*(shas for _, shas in markers))) for env, markers in proven]
    cap = max((rung for rung, _ in sets), default=0)
    pieces = []
    for sha, subject, wanted in commits:
        reached = max((rung for rung, shas in sets if sha in shas), default=0)
        lacking = next(
            (
                text
                for env, markers in proven
                if not isinstance(env.proof, BranchProof)
                for text, shas in markers
                if sha not in shas
            ),
            None,
        )
        pieces.append((_Piece(repo.name, sha, subject, reached, cap, lacking), wanted))
    return pieces


def _value(piece: _Piece) -> float:
    return math.inf if piece.reached == piece.cap else piece.reached


def _environment_at(cfg: BoardConfig, repo: str, rung: int) -> str | None:
    return next((env.name for env in cfg.environments_for(repo) if env.rung == rung), None)


def _position(
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
            _holding_branch(repos[held.repo], held.sha, cfg, warnings),
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
    return {
        key: _position(pieces, cfg, stale, by_name, warnings) for key, pieces in by_key.items()
    }, warnings
