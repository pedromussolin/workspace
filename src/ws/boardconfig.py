"""The `[board]` table of config.toml: environments, Jira status names and per-repo overrides."""

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

from ws import userconfig
from ws.config import config_dir
from ws.taskmodel import RUNG, STATUS_AT_RUNG, Status
from ws.userconfig import ConfigInvalid

DEFAULT_REMOTE = "origin"
DEFAULT_LOOKBACK_DAYS = 120
DEFAULT_DEPLOY_BRANCH = "master"


class BoardMissing(Exception):
    pass


@dataclass(frozen=True)
class Environment:
    name: str
    status: Status
    branches: tuple[str, ...]
    deploy_repo: str | None
    deploy_branch: str
    image_tag: re.Pattern[str] | None

    @property
    def rung(self) -> int:
        return RUNG[self.status]


@dataclass(frozen=True)
class BoardConfig:
    remote: str
    lookback_days: int
    fetch: bool
    environments: tuple[Environment, ...]
    repo_branches: dict[str, dict[str, tuple[str, ...]]]
    statuses: dict[Status, str]
    ignore_repos: tuple[str, ...]
    direct_deploy_repos: tuple[str, ...]
    repo_deploy: dict[str, str]

    def branches_for(self, repo: str, env: Environment) -> tuple[str, ...]:
        return self.repo_branches.get(repo, {}).get(env.name, env.branches)

    def deploy_repo_for(self, repo: str, env: Environment) -> str:
        if repo in self.repo_deploy:
            return self.repo_deploy[repo]
        return (env.deploy_repo or "").format(repo=repo)

    def ignored(self, repo: str) -> bool:
        return any(fnmatch.fnmatchcase(repo, glob) for glob in self.ignore_repos)

    def direct_deploy(self, repo: str) -> bool:
        return any(fnmatch.fnmatchcase(repo, glob) for glob in self.direct_deploy_repos)


def _invalid(path: Path, where: str, problem: str) -> ConfigInvalid:
    return ConfigInvalid(f"{path}: {where} {problem}")


def _strings(value: object, path: Path, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise _invalid(path, where, "must be a list of non-empty strings")
    return tuple(value)


def _table(value: object, path: Path, where: str) -> dict:
    if not isinstance(value, dict):
        raise _invalid(path, where, "must be a table")
    return value


def _image_tag(value: object, path: Path, where: str) -> re.Pattern[str]:
    if not isinstance(value, str) or not value:
        raise _invalid(path, where, "must be a non-empty string")
    try:
        pattern = re.compile(value)
    except re.error as error:
        raise _invalid(path, where, f"is not a valid regular expression: {error}") from None
    if pattern.groups != 1:
        raise _invalid(path, where, f"must have exactly one group, has {pattern.groups}")
    return pattern


def _environment(raw: object, index: int, path: Path) -> Environment:
    where = f"board.environments[{index}]"
    table = _table(raw, path, where)
    name = table.get("name")
    if not isinstance(name, str) or not name:
        raise _invalid(path, f"{where}.name", "must be a non-empty string")
    status_name = table.get("status")
    allowed = [STATUS_AT_RUNG[rung] for rung in sorted(STATUS_AT_RUNG)]
    if status_name not in allowed:
        names = ", ".join(status.value for status in allowed)
        raise _invalid(path, f"{where}.status", f"is {status_name!r}; use one of {names}")
    has_branches = "branches" in table
    has_deploy = "deploy_repo" in table
    if has_branches == has_deploy:
        raise _invalid(path, where, "must have either branches or deploy_repo, not both or none")
    if has_branches:
        for key in ("image_tag", "deploy_branch"):
            if key in table:
                raise _invalid(path, f"{where}.{key}", "only goes with deploy_repo")
        return Environment(
            name,
            Status(status_name),
            _strings(table["branches"], path, f"{where}.branches"),
            None,
            DEFAULT_DEPLOY_BRANCH,
            None,
        )
    deploy_repo = table["deploy_repo"]
    if not isinstance(deploy_repo, str) or not deploy_repo:
        raise _invalid(path, f"{where}.deploy_repo", "must be a non-empty string")
    deploy_branch = table.get("deploy_branch", DEFAULT_DEPLOY_BRANCH)
    if not isinstance(deploy_branch, str) or not deploy_branch:
        raise _invalid(path, f"{where}.deploy_branch", "must be a non-empty string")
    if "image_tag" not in table:
        raise _invalid(path, f"{where}.image_tag", "is required with deploy_repo")
    return Environment(
        name,
        Status(status_name),
        (),
        deploy_repo,
        deploy_branch,
        _image_tag(table["image_tag"], path, f"{where}.image_tag"),
    )


def _environments(table: dict, path: Path) -> tuple[Environment, ...]:
    raw = table.get("environments")
    if not isinstance(raw, list) or not raw:
        raise _invalid(path, "board.environments", "must be a non-empty list of tables")
    environments = tuple(_environment(item, index, path) for index, item in enumerate(raw))
    for index, env in enumerate(environments):
        if any(env.name == other.name for other in environments[:index]):
            raise _invalid(path, f"board.environments[{index}].name", f"{env.name!r} is repeated")
        if index and env.rung <= environments[index - 1].rung:
            raise _invalid(
                path,
                f"board.environments[{index}].status",
                f"must rise along the list; {env.status.value} does not follow "
                f"{environments[index - 1].status.value}",
            )
    return environments


def _statuses(table: dict, environments: tuple[Environment, ...], path: Path) -> dict[Status, str]:
    raw = _table(table.get("statuses", {}), path, "board.statuses")
    needed = [Status.IN_PROGRESS, *(env.status for env in environments)]
    statuses: dict[Status, str] = {}
    for status in needed:
        name = raw.get(status.value)
        if not isinstance(name, str) or not name:
            raise _invalid(
                path,
                f"board.statuses.{status.value}",
                "must be a non-empty string (Jira status name)",
            )
        statuses[status] = name
    return statuses


def _repos(
    table: dict, environments: tuple[Environment, ...], path: Path
) -> tuple[dict[str, dict[str, tuple[str, ...]]], dict[str, str]]:
    raw = _table(table.get("repos", {}), path, "board.repos")
    known = {env.name for env in environments}
    repo_branches: dict[str, dict[str, tuple[str, ...]]] = {}
    repo_deploy: dict[str, str] = {}
    for repo, override in raw.items():
        where = f"board.repos.{repo}"
        override = _table(override, path, where)
        if "deploy_repo" in override:
            deploy_repo = override["deploy_repo"]
            if not isinstance(deploy_repo, str) or not deploy_repo:
                raise _invalid(path, f"{where}.deploy_repo", "must be a non-empty string")
            repo_deploy[repo] = deploy_repo
        branches = _table(override.get("branches", {}), path, f"{where}.branches")
        for env_name, names in branches.items():
            if env_name not in known:
                raise _invalid(
                    path,
                    f"{where}.branches.{env_name}",
                    f"names no environment; use one of {', '.join(sorted(known))}",
                )
            repo_branches.setdefault(repo, {})[env_name] = _strings(
                names, path, f"{where}.branches.{env_name}"
            )
    return repo_branches, repo_deploy


def parse_board(table: dict, path: Path) -> BoardConfig:
    remote = table.get("remote", DEFAULT_REMOTE)
    if not isinstance(remote, str) or not remote:
        raise _invalid(path, "board.remote", "must be a non-empty string")
    lookback = table.get("lookback_days", DEFAULT_LOOKBACK_DAYS)
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 1:
        raise _invalid(path, "board.lookback_days", "must be a positive integer")
    fetch = table.get("fetch", True)
    if not isinstance(fetch, bool):
        raise _invalid(path, "board.fetch", "must be true or false")
    ignore_repos = _strings(table.get("ignore_repos", []), path, "board.ignore_repos")
    direct = _strings(table.get("direct_deploy_repos", []), path, "board.direct_deploy_repos")
    environments = _environments(table, path)
    statuses = _statuses(table, environments, path)
    repo_branches, repo_deploy = _repos(table, environments, path)
    return BoardConfig(
        remote,
        lookback,
        fetch,
        environments,
        repo_branches,
        statuses,
        ignore_repos,
        direct,
        repo_deploy,
    )


def load_board() -> BoardConfig:
    table = userconfig.load_table("board")
    if not table:
        raise BoardMissing("config.toml has no [board] table")
    return parse_board(table, config_dir() / "config.toml")
