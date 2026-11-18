"""The `[release]` table of config.toml and the task link template the release texts use."""

import re
from dataclasses import dataclass
from pathlib import Path

from ws import tracker, userconfig
from ws.release import ReleaseSetup
from ws.tracker.errors import TrackerSetup

HINT = 'see "Release" in the README'
REPO_KEYS = {"slug", "path", "alembic"}
RELEASE_KEYS = {"base_branch", "sandbox_branch", "environments", "repos"}
ENV_KEYS = {"branch", "suffix", "default"}
ENV_NAME = re.compile(r"[a-z][a-z0-9-]*")
ENV_SUFFIX = re.compile(r"-[a-z0-9]+")
PRODUCTION = "production"
RESERVED = {PRODUCTION, "code"}


@dataclass(frozen=True)
class RepoEntry:
    name: str
    slug: str
    path: Path
    alembic: str | None

    @property
    def repo_name(self) -> str:
        return self.slug.split("/", 1)[1]


@dataclass(frozen=True)
class Environment:
    """A deploy target besides production: its branch, and the suffix of the copy of the code
    branch that carries its branch merged in."""

    name: str
    branch: str
    suffix: str
    default: bool

    @property
    def pr_suffix(self) -> str:
        return f" ({self.suffix[1:]})"


@dataclass(frozen=True)
class ReleaseConfig:
    base_branch: str
    environments: tuple[Environment, ...]
    repos: tuple[RepoEntry, ...]
    card_url_template: str

    def environment(self, name: str) -> Environment:
        for env in self.environments:
            if env.name == name:
                return env
        known = ", ".join([PRODUCTION, *(env.name for env in self.environments)])
        raise ReleaseSetup(f"unknown environment {name!r} (configured: {known}); {HINT}")

    def defaults(self) -> tuple[Environment, ...]:
        return tuple(env for env in self.environments if env.default)

    def select(self, names: list[str] | None) -> tuple[Environment, ...]:
        """The environments named, in config order; without names, the defaults. `production`
        is a valid name that selects no environment (the callers read it themselves)."""
        if not names:
            return self.defaults()
        chosen = {env.name for env in map(self.environment, (n for n in names if n != PRODUCTION))}
        return tuple(env for env in self.environments if env.name in chosen)

    @property
    def protected(self) -> set[str]:
        return {self.base_branch, *(env.branch for env in self.environments)}

    def entry(self, name: str) -> RepoEntry:
        for repo in self.repos:
            if repo.name == name:
                return repo
        known = ", ".join(repo.name for repo in self.repos)
        raise ReleaseSetup(f"unknown repo {name!r} (configured: {known}); {HINT}")


def _fail(message: str) -> ReleaseSetup:
    return ReleaseSetup(f"{message}; {HINT}")


def _text(table: dict, key: str, where: str, default: str | None = None) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or not value:
        raise _fail(f"{where}.{key} must be a non-empty string")
    return value


def _repo(name: str, table: object) -> RepoEntry:
    where = f"release.repos.{name}"
    if not isinstance(table, dict):
        raise _fail(f"{where} must be a table")
    unknown = sorted(set(table) - REPO_KEYS)
    if unknown:
        raise _fail(f"{where}: unknown key {', '.join(unknown)}")
    slug = _text(table, "slug", where)
    owner, _, repo = slug.partition("/")
    if not owner or not repo or "/" in repo:
        raise _fail(f"{where}.slug must be owner/name")
    alembic = _text(table, "alembic", where) if "alembic" in table else None
    return RepoEntry(
        name=name,
        slug=slug,
        path=Path(_text(table, "path", where)).expanduser(),
        alembic=alembic,
    )


def _environment(name: str, table: object) -> Environment:
    where = f"release.environments.{name}"
    if not ENV_NAME.fullmatch(name) or name in RESERVED:
        raise _fail(
            f"{where}: the name must match [a-z][a-z0-9-]* and not be "
            f"{' or '.join(map(repr, sorted(RESERVED)))} (reserved)"
        )
    if not isinstance(table, dict):
        raise _fail(f"{where} must be a table")
    unknown = sorted(set(table) - ENV_KEYS)
    if unknown:
        raise _fail(f"{where}: unknown key {', '.join(unknown)}")
    suffix = _text(table, "suffix", where)
    if not ENV_SUFFIX.fullmatch(suffix):
        raise _fail(f"{where}.suffix must look like -abc (a dash and letters or digits)")
    default = table.get("default", False)
    if not isinstance(default, bool):
        raise _fail(f"{where}.default must be true or false")
    return Environment(name, _text(table, "branch", where), suffix, default)


def _environments(release: dict, base_branch: str) -> tuple[Environment, ...]:
    tables = release.get("environments")
    if tables is None:
        branch = _text(release, "sandbox_branch", "release", "sandbox")
        return (Environment("sandbox", branch, "-sdbx", True),)
    if "sandbox_branch" in release:
        raise _fail("release.sandbox_branch and release.environments together: use one")
    if not isinstance(tables, dict) or not tables:
        raise _fail("release.environments must list at least one environment")
    found = tuple(_environment(name, table) for name, table in tables.items())
    for label, values in (
        ("suffix", [env.suffix for env in found]),
        ("branch", [env.branch for env in found]),
    ):
        if len(set(values)) != len(values):
            raise _fail(f"release.environments: two environments share a {label}")
    clash = [env.name for env in found if env.branch == base_branch]
    if clash:
        raise _fail(f"release.environments.{clash[0]}.branch is the base branch")
    return found


def load_release_config() -> ReleaseConfig:
    try:
        release = userconfig.load_table("release")
        template = tracker.card_url_template()
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid, TrackerSetup) as error:
        raise _fail(str(error)) from error
    unknown = sorted(set(release) - RELEASE_KEYS)
    if unknown:
        raise _fail(f"release: unknown key {', '.join(unknown)}")
    repos = release.get("repos")
    if not isinstance(repos, dict) or not repos:
        raise _fail("release.repos must list at least one repo")
    base_branch = _text(release, "base_branch", "release", "master")
    return ReleaseConfig(
        base_branch=base_branch,
        environments=_environments(release, base_branch),
        repos=tuple(_repo(name, table) for name, table in repos.items()),
        card_url_template=template,
    )
