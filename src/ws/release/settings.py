"""The `[release]` table of config.toml and the task link template the release texts use."""

from dataclasses import dataclass
from pathlib import Path

from ws import tracker, userconfig
from ws.release import ReleaseSetup
from ws.tracker.errors import TrackerSetup

HINT = 'see "Release" in the README'
REPO_KEYS = {"slug", "path", "alembic"}
RELEASE_KEYS = {"base_branch", "sandbox_branch", "repos"}


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
class ReleaseConfig:
    base_branch: str
    sandbox_branch: str
    repos: tuple[RepoEntry, ...]
    card_url_template: str

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


def load_release_config() -> ReleaseConfig:
    try:
        release = userconfig.load_table("release")
        template = tracker.card_url_template(userconfig.load_config())
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid, TrackerSetup) as error:
        raise _fail(str(error)) from error
    unknown = sorted(set(release) - RELEASE_KEYS)
    if unknown:
        raise _fail(f"release: unknown key {', '.join(unknown)}")
    repos = release.get("repos")
    if not isinstance(repos, dict) or not repos:
        raise _fail("release.repos must list at least one repo")
    return ReleaseConfig(
        base_branch=_text(release, "base_branch", "release", "master"),
        sandbox_branch=_text(release, "sandbox_branch", "release", "sandbox"),
        repos=tuple(_repo(name, table) for name, table in repos.items()),
        card_url_template=template,
    )
