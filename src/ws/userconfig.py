"""Local, per-user config of ws: `config.toml` (no secrets) and the Jira token in `credentials`."""

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ws.config import config_dir
from ws.taskmodel import Status

DEFAULT_STALE_WORKDAYS = 3


class ConfigMissing(Exception):
    def __init__(self, path: Path, what: str = "file"):
        super().__init__(f"{what} {path} is missing")
        self.path = path


class ConfigInvalid(ValueError):
    pass


@dataclass(frozen=True)
class JiraConfig:
    site: str
    email: str
    status_overrides: dict[str, str]
    project: str | None = None
    board_id: int | None = None
    issue_type: str | None = None
    start_date_field: str | None = None
    sprint_field: str | None = None


@dataclass(frozen=True)
class StandupConfig:
    repo_roots: tuple[Path, ...]
    stale_workdays: int = DEFAULT_STALE_WORKDAYS


@dataclass(frozen=True)
class UserConfig:
    jira: JiraConfig
    standup: StandupConfig


def _read_toml(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigMissing(path) from None
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigInvalid(f"{path}: {error}") from None


def _table(data: dict, key: str, path: Path) -> dict:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConfigInvalid(f"{path}: [{key}] must be a table")
    return value


def _string(table: dict, key: str, path: Path, section: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigInvalid(f"{path}: {section}.{key} must be a non-empty string")
    return value


def _optional_string(table: dict, key: str, path: Path, section: str) -> str | None:
    if key not in table:
        return None
    return _string(table, key, path, section)


def _optional_positive_int(table: dict, key: str, path: Path, section: str) -> int | None:
    if key not in table:
        return None
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigInvalid(f"{path}: {section}.{key} must be a positive integer")
    return value


def _string_list(table: dict, key: str, path: Path, section: str) -> list[str] | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigInvalid(f"{path}: {section}.{key} must be a list of strings")
    return value


def _status_overrides(jira: dict, path: Path) -> dict[str, str]:
    overrides = jira.get("status_overrides", {})
    if not isinstance(overrides, dict):
        raise ConfigInvalid(f"{path}: jira.status_overrides must be a table")
    valid = {status.value for status in Status}
    for name, value in overrides.items():
        if value not in valid:
            raise ConfigInvalid(
                f"{path}: jira.status_overrides.{name!r} is {value!r}; "
                f"use one of {', '.join(sorted(valid))}"
            )
    return dict(overrides)


def load_config() -> UserConfig:
    path = config_dir() / "config.toml"
    data = _read_toml(path)
    jira = _table(data, "jira", path)
    standup = _table(data, "standup", path)
    stale = standup.get("stale_workdays", DEFAULT_STALE_WORKDAYS)
    if isinstance(stale, bool) or not isinstance(stale, int) or stale < 1:
        raise ConfigInvalid(f"{path}: standup.stale_workdays must be a positive integer")
    roots = _string_list(standup, "repo_roots", path, "standup")
    return UserConfig(
        jira=JiraConfig(
            site=_string(jira, "site", path, "jira"),
            email=_string(jira, "email", path, "jira"),
            status_overrides=_status_overrides(jira, path),
            project=_optional_string(jira, "project", path, "jira"),
            board_id=_optional_positive_int(jira, "board_id", path, "jira"),
            issue_type=_optional_string(jira, "issue_type", path, "jira"),
            start_date_field=_optional_string(jira, "start_date_field", path, "jira"),
            sprint_field=_optional_string(jira, "sprint_field", path, "jira"),
        ),
        standup=StandupConfig(
            repo_roots=(
                (Path.home() / "repos",)
                if roots is None
                else tuple(Path(item).expanduser() for item in roots)
            ),
            stale_workdays=stale,
        ),
    )


def _credentials_path() -> Path:
    return config_dir() / "credentials"


def load_jira_token() -> str:
    path = _credentials_path()
    data = _read_toml(path)
    stored = _table(data, "jira", path).get("token")
    if not isinstance(stored, str) or not stored:
        raise ConfigMissing(path, "Jira token in")
    return stored


def save_jira_token(value: str) -> Path:
    path = _credentials_path()
    try:
        existing = _read_toml(path)
    except ConfigMissing:
        existing = {}
    if set(existing) - {"jira"}:
        raise ConfigInvalid(f"{path} holds other tables; add the Jira token by hand")
    folder = path.parent
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"[jira]\ntoken = {json.dumps(value)}\n")
    path.chmod(0o600)
    return path
