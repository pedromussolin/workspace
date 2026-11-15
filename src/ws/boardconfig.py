"""The `[board]` table of config.toml: profiles of environments, their proofs, per-repo settings."""

import fnmatch
import re
import string
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path

from ws import userconfig
from ws.config import REPO_NAME, config_dir
from ws.taskmodel import RUNG, STATUS_AT_RUNG, Status
from ws.userconfig import ConfigInvalid

DEFAULT_REMOTE = "origin"
DEFAULT_LOOKBACK_DAYS = 120
DEFAULT_DEPLOY_BRANCH = "master"
DEFAULT_BASE = "master"
DEFAULT_COMMAND_TIMEOUT = 20
BOARD_KEYS = (
    "remote",
    "lookback_days",
    "fetch",
    "default_profile",
    "profiles",
    "repos",
    "statuses",
    "prefix_repos",
)
FIRST_VERSION_KEYS = ("environments", "ignore_repos", "direct_deploy_repos")
FIRST_VERSION_REPO_KEYS = ("branches", "deploy_repo")
REPO_KEYS = ("ignore", "profile", "inactive", "base")
_BASE = re.compile(r"(?!-)(?!.*\.\.)[A-Za-z0-9._/-]+")
_PREFIX_KEY = re.compile(r"[^\[\]\s]+")
FIRST_VERSION = 'is from the first version; use [board.profiles.<name>] and [board.repos."<glob>"]'
PROOF_KEYS = {
    "branch": ("branches",),
    "tag": ("tag",),
    "file": ("deploy_repo", "deploy_branch", "image_tag"),
    "command": ("command", "timeout"),
}
ENVIRONMENT_STATUSES = tuple(STATUS_AT_RUNG[rung] for rung in sorted(STATUS_AT_RUNG))
MAPPED_STATUSES = (Status.VALIDATION, Status.READY_DEPLOY)


class BoardMissing(Exception):
    pass


@dataclass(frozen=True)
class BranchProof:
    branches: tuple[str, ...]


@dataclass(frozen=True)
class TagProof:
    pattern: str


@dataclass(frozen=True)
class FileProof:
    deploy_repo: str
    deploy_branch: str
    image_tag: re.Pattern[str]


@dataclass(frozen=True)
class CommandProof:
    argv: tuple[str, ...]
    timeout: int


Proof = BranchProof | TagProof | FileProof | CommandProof


@dataclass(frozen=True)
class Environment:
    name: str
    status: Status
    proof: Proof

    @property
    def rung(self) -> int:
        return RUNG[self.status]


@dataclass(frozen=True)
class Profile:
    name: str
    environments: tuple[Environment, ...]


@dataclass(frozen=True)
class RepoSettings:
    key: str
    ignore: bool
    profile: str | None
    inactive: tuple[str, ...]
    base: str | None = None


@dataclass(frozen=True)
class BoardConfig:
    remote: str
    lookback_days: int
    fetch: bool
    default_profile: str
    profiles: dict[str, Profile]
    repos: tuple[RepoSettings, ...]
    statuses: dict[Status, str]
    prefix_repos: dict[str, tuple[str, ...]] = dataclass_field(default_factory=dict)

    def settings_for(self, repo: str) -> RepoSettings | None:
        """The table whose key is `repo`, else the first glob (file order) matching it."""
        exact = next((settings for settings in self.repos if settings.key == repo), None)
        if exact is not None:
            return exact
        return next((s for s in self.repos if fnmatch.fnmatchcase(repo, s.key)), None)

    def base_for(self, repo: str) -> str:
        settings = self.settings_for(repo)
        return (settings and settings.base) or DEFAULT_BASE

    def ignored(self, repo: str) -> bool:
        settings = self.settings_for(repo)
        return settings is not None and settings.ignore

    def profile_for(self, repo: str) -> Profile:
        settings = self.settings_for(repo)
        return self.profiles[(settings and settings.profile) or self.default_profile]

    def environments_for(self, repo: str) -> tuple[Environment, ...]:
        """The environments of the repo's profile, without the ones it switches off."""
        settings = self.settings_for(repo)
        inactive = settings.inactive if settings else ()
        return tuple(env for env in self.profile_for(repo).environments if env.name not in inactive)

    def uses_tags(self, repo: str) -> bool:
        return any(isinstance(env.proof, TagProof) for env in self.environments_for(repo))


def _invalid(path: Path, where: str, problem: str) -> ConfigInvalid:
    return ConfigInvalid(f"{path}: {where} {problem}")


def _string(value: object, path: Path, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise _invalid(path, where, "must be a non-empty string")
    return value


def _strings(value: object, path: Path, where: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise _invalid(path, where, "must be a non-empty list of non-empty strings")
    return tuple(value)


def _table(value: object, path: Path, where: str) -> dict:
    if not isinstance(value, dict):
        raise _invalid(path, where, "must be a table")
    return value


def _unknown(table: dict, known: tuple[str, ...], path: Path, where: str) -> None:
    for key in table:
        if key not in known:
            raise _invalid(path, f"{where}.{key}", f"is not a known key; use {', '.join(known)}")


def _placeholders(value: str, allowed: tuple[str, ...], path: Path, where: str) -> None:
    """`value` may only use `{name}` for the names in `allowed`, with no conversion or format."""
    usable = ", ".join(f"{{{name}}}" for name in allowed)
    try:
        fields = [
            (field, spec, conversion)
            for _, field, spec, conversion in string.Formatter().parse(value)
            if field is not None
        ]
    except ValueError as error:
        raise _invalid(path, where, f"has a bad brace ({error}); use {usable}") from None
    for field, spec, conversion in fields:
        if field not in allowed or spec or conversion:
            raise _invalid(path, where, f"may only use {usable}; {value!r} has another")


def _image_tag(value: object, path: Path, where: str) -> re.Pattern[str]:
    text = _string(value, path, where)
    try:
        pattern = re.compile(text)
    except re.error as error:
        raise _invalid(path, where, f"is not a valid regular expression: {error}") from None
    if pattern.groups != 1:
        raise _invalid(path, where, f"must have exactly one group, has {pattern.groups}")
    return pattern


def _command(value: object, path: Path, where: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) for item in value)
        or not value[0]
    ):
        raise _invalid(path, where, "must be a non-empty list of strings (the program first)")
    for item in value:
        _placeholders(item, ("repo", "env"), path, where)
    return tuple(value)


def _timeout(value: object, path: Path, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _invalid(path, where, "must be a positive integer (seconds)")
    return value


def _proof(table: dict, kind: str, path: Path, where: str) -> Proof:
    for key in PROOF_KEYS[kind]:
        if key not in table and key not in ("deploy_branch", "timeout"):
            raise _invalid(path, f"{where}.{key}", f'is required with proof = "{kind}"')
    if kind == "branch":
        return BranchProof(_strings(table["branches"], path, f"{where}.branches"))
    if kind == "tag":
        return TagProof(_string(table["tag"], path, f"{where}.tag"))
    if kind == "file":
        deploy_repo = _string(table["deploy_repo"], path, f"{where}.deploy_repo")
        _placeholders(deploy_repo, ("repo",), path, f"{where}.deploy_repo")
        return FileProof(
            deploy_repo,
            _string(
                table.get("deploy_branch", DEFAULT_DEPLOY_BRANCH), path, f"{where}.deploy_branch"
            ),
            _image_tag(table["image_tag"], path, f"{where}.image_tag"),
        )
    return CommandProof(
        _command(table["command"], path, f"{where}.command"),
        _timeout(table.get("timeout", DEFAULT_COMMAND_TIMEOUT), path, f"{where}.timeout"),
    )


def _environment(raw: object, where: str, path: Path) -> Environment:
    table = _table(raw, path, where)
    name = _string(table.get("name"), path, f"{where}.name")
    status_name = table.get("status")
    if status_name not in ENVIRONMENT_STATUSES:
        names = ", ".join(status.value for status in ENVIRONMENT_STATUSES)
        raise _invalid(path, f"{where}.status", f"is {status_name!r}; use one of {names}")
    kind = table.get("proof")
    if not isinstance(kind, str) or kind not in PROOF_KEYS:
        raise _invalid(path, f"{where}.proof", f"is {kind!r}; use one of {', '.join(PROOF_KEYS)}")
    for key in table:
        if key in ("name", "status", "proof") or key in PROOF_KEYS[kind]:
            continue
        owner = next((other for other, keys in PROOF_KEYS.items() if key in keys), None)
        if owner is not None:
            raise _invalid(path, f"{where}.{key}", f'only goes with proof = "{owner}"')
        raise _invalid(path, f"{where}.{key}", "is not a known key")
    return Environment(name, Status(status_name), _proof(table, kind, path, where))


def _profile(name: str, raw: object, path: Path) -> Profile:
    where = f"board.profiles.{name}"
    table = _table(raw, path, where)
    _unknown(table, ("environments",), path, where)
    raw_environments = table.get("environments")
    if not isinstance(raw_environments, list) or not raw_environments:
        raise _invalid(path, f"{where}.environments", "must be a non-empty list of tables")
    environments = tuple(
        _environment(item, f"{where}.environments[{index}]", path)
        for index, item in enumerate(raw_environments)
    )
    for index, env in enumerate(environments):
        at = f"{where}.environments[{index}]"
        if any(env.name == other.name for other in environments[:index]):
            raise _invalid(path, f"{at}.name", f"{env.name!r} is repeated")
        if index and env.rung <= environments[index - 1].rung:
            raise _invalid(
                path,
                f"{at}.status",
                f"must rise along the list; {env.status.value} does not follow "
                f"{environments[index - 1].status.value}",
            )
    return Profile(name, environments)


def _profiles(table: dict, path: Path) -> dict[str, Profile]:
    raw = table.get("profiles")
    if not isinstance(raw, dict) or not raw:
        raise _invalid(path, "board.profiles", "must hold at least one profile table")
    return {name: _profile(name, value, path) for name, value in raw.items()}


def _repo(
    key: str, raw: object, profiles: dict[str, Profile], default: str, path: Path
) -> RepoSettings:
    where = f'board.repos."{key}"'
    table = _table(raw, path, where)
    for name in table:
        if name in FIRST_VERSION_REPO_KEYS:
            raise _invalid(path, f"{where}.{name}", FIRST_VERSION)
    _unknown(table, REPO_KEYS, path, where)
    ignore = table.get("ignore", False)
    if not isinstance(ignore, bool):
        raise _invalid(path, f"{where}.ignore", "must be true or false")
    if ignore and len(table) > 1:
        raise _invalid(path, where, "must hold ignore = true alone")
    profile = table.get("profile")
    if profile is not None and (not isinstance(profile, str) or profile not in profiles):
        raise _invalid(
            path, f"{where}.profile", f"is {profile!r}; use one of {', '.join(profiles)}"
        )
    inactive: tuple[str, ...] = ()
    if "inactive" in table:
        inactive = _strings(table["inactive"], path, f"{where}.inactive")
        used = profile or default
        known = [env.name for env in profiles[used].environments]
        unknown = [name for name in inactive if name not in known]
        if unknown:
            raise _invalid(
                path,
                f"{where}.inactive",
                f"names {unknown[0]!r}, not an environment of profile {used!r}; "
                f"use one of {', '.join(known)}",
            )
    base = table.get("base")
    if "base" in table and (not isinstance(base, str) or not _BASE.fullmatch(base)):
        raise _invalid(path, f"{where}.base", "must be a branch name")
    return RepoSettings(key, ignore, profile, inactive, base)


def _prefix_repos(table: dict, path: Path) -> dict[str, tuple[str, ...]]:
    raw = _table(table.get("prefix_repos", {}), path, "board.prefix_repos")
    out: dict[str, tuple[str, ...]] = {}
    for key, value in raw.items():
        where = f"board.prefix_repos.{key}"
        if not _PREFIX_KEY.fullmatch(key):
            raise _invalid(path, where, "must be a prefix without brackets or spaces")
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(name, str) and REPO_NAME.fullmatch(name) for name in value)
        ):
            raise _invalid(path, where, "must be a non-empty list of repo names")
        out[key] = tuple(value)
    return out


def _statuses(table: dict, profiles: dict[str, Profile], path: Path) -> dict[Status, str]:
    raw = _table(table.get("statuses", {}), path, "board.statuses")
    _unknown(raw, tuple(status.value for status in ENVIRONMENT_STATUSES), path, "board.statuses")
    used = {Status.IN_PROGRESS}
    used.update(env.status for profile in profiles.values() for env in profile.environments)
    statuses: dict[Status, str] = {}
    for status in ENVIRONMENT_STATUSES:
        if status not in used and status.value not in raw:
            continue
        name = raw.get(status.value)
        if not isinstance(name, str) or not name:
            raise _invalid(
                path,
                f"board.statuses.{status.value}",
                "must be a non-empty string (the tracker's status name)",
            )
        statuses[status] = name
    return statuses


def parse_board(table: dict, path: Path) -> BoardConfig:
    for key in table:
        if key in FIRST_VERSION_KEYS:
            raise _invalid(path, f"board.{key}", FIRST_VERSION)
    _unknown(table, BOARD_KEYS, path, "board")
    remote = _string(table.get("remote", DEFAULT_REMOTE), path, "board.remote")
    lookback = table.get("lookback_days", DEFAULT_LOOKBACK_DAYS)
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 1:
        raise _invalid(path, "board.lookback_days", "must be a positive integer")
    fetch = table.get("fetch", True)
    if not isinstance(fetch, bool):
        raise _invalid(path, "board.fetch", "must be true or false")
    profiles = _profiles(table, path)
    default = table.get("default_profile")
    if not isinstance(default, str) or default not in profiles:
        raise _invalid(
            path, "board.default_profile", f"is {default!r}; use one of {', '.join(profiles)}"
        )
    raw_repos = _table(table.get("repos", {}), path, "board.repos")
    repos = tuple(_repo(key, raw, profiles, default, path) for key, raw in raw_repos.items())
    return BoardConfig(
        remote,
        lookback,
        fetch,
        default,
        profiles,
        repos,
        _statuses(table, profiles, path),
        _prefix_repos(table, path),
    )


def unmapped_status(cfg: BoardConfig, overrides: dict[str, str]) -> str | None:
    """The first `[board.statuses]` name the tracker's mapping would read as another status.

    `validation` and `ready_deploy` have no tracker category of their own, so their names must be
    in the overrides; `in_progress` and `done` may rely on the category.
    """
    for status, name in cfg.statuses.items():
        mapped = overrides.get(name)
        if mapped == status.value or (mapped is None and status not in MAPPED_STATUSES):
            continue
        return (
            f'board.statuses.{status.value} "{name}" does not map back to {status.value} in '
            "[jira.status_overrides]; a card in it would be read wrong and could move backwards"
        )
    return None


def load_board() -> BoardConfig:
    table = userconfig.load_table("board")
    if not table:
        raise BoardMissing("config.toml has no [board] table")
    return parse_board(table, config_dir() / "config.toml")
