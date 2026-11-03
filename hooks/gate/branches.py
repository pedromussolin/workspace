"""The environment-branch policy of the gate, shared by the Bash and the MCP rules.

The model never writes to an environment branch (a `git push`, a GitHub file write, a ref
update): everything goes through a task branch and a PR that the user merges. The one exception
is a repository listed in `direct_push_repos` (the `*-argocd` deploy repos), where the write asks
with a warning. A PR whose base is an environment branch is never merged by the model, in any
repository; its base is read with `gh pr view` (`BaseLookup`, the binary overridable with
`WS_GATE_GH_BIN` for the tests).

Both keys live in `[gate]` of `~/.config/workspace/config.toml`. Without `environment_branches`
the policy is off and the gate behaves as before, so another clone is not broken by it; without
`direct_push_repos` no repository is an exception. `direct_push_repos` holds `fnmatch` patterns
matched against the repository name: the last part of its URL, without `.git`.
"""

import contextlib
import fnmatch
import os
import re
import shutil
import signal
import subprocess
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BRANCH_EN = "the default branch"
DEFAULT_BRANCH_PT = "a branch padrão"
UNKNOWN_REPO_EN = "a repository the gate could not name"
UNKNOWN_TARGET = "ATENÇÃO: não consegui ver a branch de destino"
UNKNOWN_BASE = "ATENÇÃO: não consegui ver a base da PR"
# The hook has 5 s; the lookup runs alongside the MCP confidentiality check, not after it.
LOOKUP_TIMEOUT = 3.0
BRANCH_NAME = re.compile(r"[A-Za-z0-9._/+-]{1,255}")
PULL_URL = re.compile(r"/pull/(\d+)(?:[/?#]|$)")
# gh runs git in the folder: the repository's own fsmonitor and hooks must not run from the gate.
GIT_SAFETY = {
    "GIT_CONFIG_COUNT": "2",
    "GIT_CONFIG_KEY_0": "core.fsmonitor",
    "GIT_CONFIG_VALUE_0": "false",
    "GIT_CONFIG_KEY_1": "core.hooksPath",
    "GIT_CONFIG_VALUE_1": "/dev/null",
}


@dataclass(frozen=True)
class Policy:
    branches: frozenset[str]
    direct: tuple[str, ...]

    def is_environment(self, branch: str) -> bool:
        """Whether `branch` is an environment branch; a refspec glob (`*`) counts when it can
        match one."""
        if "*" in branch:
            return any(fnmatch.fnmatchcase(name, branch) for name in self.branches)
        return branch in self.branches

    def allows_direct(self, repo: str | None) -> bool:
        return bool(repo) and any(fnmatch.fnmatchcase(repo, pattern) for pattern in self.direct)


def _config_dir() -> Path:
    value = os.environ.get("WS_CONFIG_DIR")
    return Path(value) if value else Path.home() / ".config" / "workspace"


def _strings(value: object) -> list[str] | None:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return None


def policy() -> Policy | None:
    """The policy from config.toml, or None when it is off (no list, or a config that cannot be
    read: the write still asks, as before the policy)."""
    try:
        with open(_config_dir() / "config.toml", "rb") as handle:
            gate = tomllib.load(handle).get("gate", {})
    except (OSError, ValueError):
        return None
    if not isinstance(gate, dict):
        return None
    branches = _strings(gate.get("environment_branches"))
    if branches is None:
        return None
    direct = _strings(gate.get("direct_push_repos")) or []
    return Policy(frozenset(branches), tuple(direct))


def repo_name(url: str) -> str | None:
    """`git@host:org/x-argocd.git` and `https://host/org/x-argocd` give `x-argocd`."""
    text = url.strip().rstrip("/").removesuffix(".git")
    name = text.replace(":", "/").rsplit("/", 1)[-1]
    return name or None


def _subject(branch: str | None, flag: str) -> tuple[str, str]:
    """The written branch in English (the denial) and in PT-BR (the box)."""
    if flag:
        return f"git push {flag} writes every environment branch", f"git push {flag}"
    if branch is None:
        return f"{DEFAULT_BRANCH_EN} is an environment branch", f"({DEFAULT_BRANCH_PT})"
    return f"{branch} is an environment branch", branch


def judge(rules: Policy, branch: str | None, repo: str | None, flag: str = "") -> tuple[str, str]:
    """For a write to `branch` of `repo`: (box warning, "") when it may ask, ("", denial) when it
    is blocked, ("", "") when the branch is not an environment one. `branch` None is the default
    branch, which counts as an environment one; `flag` is a `git push --all` or `--mirror`."""
    if not (flag or branch is None or rules.is_environment(branch)):
        return "", ""
    english, portuguese = _subject(branch, flag)
    if rules.allows_direct(repo):
        return f"ATENÇÃO: branch de ambiente {portuguese} no repo {repo}", ""
    return "", (
        f"Blocked: {english} of {repo or UNKNOWN_REPO_EN}; "
        "push a task branch and open a PR for the user to merge."
    )


def _gh_binary() -> str | None:
    return os.environ.get("WS_GATE_GH_BIN") or shutil.which("gh")


class BaseLookup:
    """The base branch of a PR, read with `gh pr view REF --json baseRefName` (read-only).

    It starts at once, so it can run while the gate does other work, and `result` waits for it
    until `LOOKUP_TIMEOUT` after the start. `ref` is a number, a URL or a branch (None: the PR of
    the current branch, read in `cwd`); `repo` is `owner/name` or None (the repo of `cwd`).
    """

    def __init__(self, ref: str | None, repo: str | None, cwd: str | None) -> None:
        self.started = time.monotonic()
        self.process: subprocess.Popen[str] | None = None
        binary = _gh_binary()
        folder = cwd if cwd and os.path.isdir(cwd) else None
        if binary is None or (folder is None and not (repo or ref)):
            return
        query = ["pr", "view", "--json", "baseRefName", "--jq", ".baseRefName"]
        query += [f"--repo={repo}"] if repo else []
        query += ["--", ref] if ref else []
        environment = (
            os.environ
            | GIT_SAFETY
            | {
                "GH_PROMPT_DISABLED": "1",
                "GH_NO_UPDATE_NOTIFIER": "1",
                "GH_PAGER": "cat",
                "NO_COLOR": "1",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        try:
            self.process = subprocess.Popen(
                [binary, *query],
                cwd=folder or "/",
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            self.process = None

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            with contextlib.suppress(OSError):
                os.killpg(self.process.pid, signal.SIGKILL)
            self.process.communicate()

    def result(self) -> str | None:
        """The base branch, or None when gh failed, printed something else or ran out of time."""
        if self.process is None:
            return None
        left = self.started + LOOKUP_TIMEOUT - time.monotonic()
        try:
            output, _ = self.process.communicate(timeout=max(left, 0.01))
        except subprocess.TimeoutExpired:
            self.stop()
            return None
        base = output.strip()
        return base if self.process.returncode == 0 and BRANCH_NAME.fullmatch(base) else None


def judge_merge(rules: Policy, base: str | None, ref: str | None) -> tuple[str, str]:
    """For a PR merge: (box line, "") or ("", denial). A PR into an environment branch is the
    user's to merge, in every repository."""
    if base is None:
        return UNKNOWN_BASE, ""
    if not rules.is_environment(base):
        return f"Base: {base}", ""
    number = PULL_URL.search(ref or "")
    if ref and ref.isdigit():
        label = f"#{ref}"
    elif number:
        label = f"#{number.group(1)}"
    else:
        label = f"of branch {ref}" if ref else "of the current branch"
    return "", f"Blocked: PR {label} merges into {base}, an environment branch; the user merges it."
