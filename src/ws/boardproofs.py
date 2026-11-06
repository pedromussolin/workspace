"""Board proofs: which commits of a repo are in an environment, one function per proof."""

import os
import re
import signal
import subprocess
from datetime import date
from pathlib import Path

from ws.boardconfig import BoardConfig, BranchProof, CommandProof, Environment, FileProof, TagProof

Markers = list[tuple[str, set[str]]]
SHA = re.compile(r"[0-9a-fA-F]{7,40}")


def run_git(
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


def first_line(text: str) -> str:
    found = [line for line in text.split("\n") if line.strip()]
    return found[0].strip() if found else "unknown error"


def git_out(repo: Path, *args: str) -> str:
    result = run_git(repo, *args)
    if result.returncode != 0:
        raise RuntimeError(first_line(result.stderr))
    return result.stdout


def lines(output: str) -> list[str]:
    return [line for line in output.split("\n") if line]


def _reachable(repo: Path, ref: str, since: date) -> set[str]:
    return set(lines(git_out(repo, "rev-list", f"--since={since.isoformat()}", ref)))


def _branch(repo: Path, proof: BranchProof, cfg: BoardConfig, walk_since: date) -> Markers | None:
    """The tip of the first branch of `proof` that exists on the remote."""
    for branch in proof.branches:
        ref = f"refs/remotes/{cfg.remote}/{branch}"
        if run_git(repo, "rev-parse", "--verify", "-q", ref).returncode == 0:
            return [(branch, _reachable(repo, ref, walk_since))]
    return None


def _tag(repo: Path, proof: TagProof, walk_since: date) -> Markers | None:
    """The most recent tag (creation date, then the highest name) matching the glob."""
    newest = git_out(
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


def _file(
    repo: Path, proof: FileProof, cfg: BoardConfig, walk_since: date, warnings: list[str]
) -> Markers | None:
    """The history of each image tag of `repo` found in the deploy repo's branch.

    No tag resolving here means the deploy repo serves another app (ignored); some resolving and
    some not means a deploy this clone cannot see, so the environment holds every commit.
    """
    deploy_name = proof.deploy_repo.format(repo=repo.name)
    deploy = repo.parent / deploy_name
    if not (deploy / ".git").exists():
        warnings.append(f"deploy {repo.name}: {deploy_name} not found")
        return None
    ref = f"{cfg.remote}/{proof.deploy_branch}"
    found_lines: list[str] = []
    if run_git(deploy, "rev-parse", "--verify", "-q", ref).returncode == 0:
        found = run_git(deploy, "grep", "-h", "-o", "-E", "-e", proof.image_tag.pattern, ref, "--")
        if found.returncode not in (0, 1):
            warnings.append(f"deploy {repo.name}: {first_line(found.stderr)}")
            return []
        found_lines = lines(found.stdout)
    tags: dict[str, str] = {}
    for line in found_lines:
        match = proof.image_tag.search(line)
        if match:
            tags.setdefault(match.group(1), match.group(0))
    full, missing = [], []
    for sha, text in sorted(tags.items(), key=lambda item: item[1]):
        resolved = run_git(repo, "rev-parse", "--verify", "-q", f"{sha}^{{commit}}")
        if resolved.returncode == 0:
            full.append((text, resolved.stdout.strip()))
        else:
            missing.append(text)
    if not full:
        warnings.append(f"deploy {repo.name}: no image tag of this repo in {deploy_name}")
        return None
    warnings.extend(f"deploy {repo.name}: tag {text} not found in this repo" for text in missing)
    unresolved: Markers = [(text, set()) for text in missing]
    return unresolved + [(text, _reachable(repo, sha, walk_since)) for text, sha in full]


def _argv(proof: CommandProof, repo: str, env: str) -> list[str]:
    expanded = [item.format(repo=repo, env=env) for item in proof.argv]
    return [
        os.path.expanduser(text) if item.startswith("~") else text
        for item, text in zip(proof.argv, expanded, strict=True)
    ]


def _kill_group(process: subprocess.Popen[str]) -> None:
    """Kills the command and whatever it started (its own session), then reaps it."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.communicate()


def _command(
    repo: Path, env: Environment, proof: CommandProof, walk_since: date, warnings: list[str]
) -> Markers | None:
    """The shas a read-only command prints, one per line; any doubt holds every commit."""

    def failed(error: str) -> Markers:
        warnings.append(f"proof {repo.name}/{env.name}: {error}")
        return []

    try:
        process = subprocess.Popen(
            _argv(proof, repo.name, env.name),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
    except OSError as error:
        return failed(str(error))
    try:
        stdout, stderr = process.communicate(timeout=proof.timeout)
    except subprocess.TimeoutExpired:
        _kill_group(process)
        return failed(f"timeout after {proof.timeout}s")
    if process.returncode != 0:
        detail = f": {first_line(stderr)}" if stderr.strip() else ""
        return failed(f"exit {process.returncode}{detail}")
    shas = list(dict.fromkeys(line.strip() for line in stdout.split("\n") if line.strip()))
    full = []
    for sha in shas:
        if not SHA.fullmatch(sha):
            return failed(f"{sha!r} is not a sha")
        resolved = run_git(repo, "rev-parse", "--verify", "-q", f"{sha}^{{commit}}")
        if resolved.returncode != 0:
            return failed(f"{sha} not found in this repo")
        full.append((sha, resolved.stdout.strip()))
    return [(sha, _reachable(repo, commit, walk_since)) for sha, commit in full] or None


def markers(
    repo: Path, env: Environment, cfg: BoardConfig, walk_since: date, warnings: list[str]
) -> Markers | None:
    """What `env`'s proof gives in `repo`: (marker, commits reachable from it).

    A commit is in the environment when every marker reaches it. None: nothing to prove here (the
    environment is unavailable in the repo). A proof that failed gives no markers, or a marker
    that reaches nothing: the environment stays in the repo and holds every commit (fail closed).
    """
    if isinstance(env.proof, BranchProof):
        return _branch(repo, env.proof, cfg, walk_since)
    if isinstance(env.proof, TagProof):
        return _tag(repo, env.proof, walk_since)
    if isinstance(env.proof, FileProof):
        return _file(repo, env.proof, cfg, walk_since, warnings)
    return _command(repo, env, env.proof, walk_since, warnings)
