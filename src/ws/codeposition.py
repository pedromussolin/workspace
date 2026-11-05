"""Where the commits of a card are: only a branch, the sandbox, master or a production image tag."""

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FETCH_TIMEOUT_SECONDS = 120
FETCH_WORKERS = 8


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
