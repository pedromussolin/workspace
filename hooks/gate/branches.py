"""The environment-branch policy of the gate, shared by the Bash and the MCP rules.

The model never writes to an environment branch (a `git push`, a GitHub file write, a ref
update): everything goes through a task branch and a PR that the user merges. The one exception
is a repository listed in `direct_push_repos` (the `*-argocd` deploy repos), where the write asks
with a warning.

Both keys live in `[gate]` of `~/.config/workspace/config.toml`. Without `environment_branches`
the policy is off and the gate behaves as before, so another clone is not broken by it; without
`direct_push_repos` no repository is an exception. `direct_push_repos` holds `fnmatch` patterns
matched against the repository name: the last part of its URL, without `.git`.
"""

import fnmatch
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BRANCH_EN = "the default branch"
DEFAULT_BRANCH_PT = "a branch padrão"
UNKNOWN_REPO_EN = "a repository the gate could not name"
UNKNOWN_TARGET = "ATENÇÃO: não consegui ver a branch de destino"


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
