"""Local, per-user config of ws: `config.toml` (no secrets) and the tokens of `credentials`."""

import os
import re
import stat
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ws.config import config_dir
from ws.jira import SiteRefused, check_site
from ws.taskmodel import Status

DEFAULT_STALE_WORKDAYS = 3
TOKEN_SERVICES = {"jira": "Jira", "github": "GitHub"}
STORED_FIELD = "token"
BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


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


def _site(jira: dict, path: Path) -> str:
    site = _string(jira, "site", path, "jira")
    try:
        return check_site(site)
    except SiteRefused as error:
        raise ConfigInvalid(f"{path}: jira.site: {error}") from None


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
            site=_site(jira, path),
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


def _refuse_foreign_credentials(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode):
        raise ConfigInvalid(f"{path} is a symlink; the API key is only read from a real file")
    if info.st_uid != os.getuid():
        raise ConfigInvalid(f"{path} is not owned by you; the API key is not read from it")


def load_token(service: str, folder: Path | None = None) -> str:
    path = _credentials_path() if folder is None else folder / "credentials"
    _refuse_foreign_credentials(path)
    data = _read_toml(path)
    stored = _table(data, service, path).get(STORED_FIELD)
    if not isinstance(stored, str) or not stored:
        raise ConfigMissing(path, f"{TOKEN_SERVICES[service]} token in")
    return stored


def load_jira_token() -> str:
    return load_token("jira")


TOML_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _toml_string(value: str) -> str:
    """A TOML basic string; `json.dumps` is not one (DEL stays raw, astral characters split)."""
    out = []
    for char in value:
        if char in TOML_ESCAPES:
            out.append(TOML_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def _credentials_text(tables: dict, path: Path) -> str:
    """Every table back as TOML; only tables of plain strings can be rewritten without loss."""
    chunks = []
    for name, table in tables.items():
        if not isinstance(table, dict) or not BARE_KEY.fullmatch(name):
            raise ConfigInvalid(f"{path} holds content ws cannot rewrite; add the token by hand")
        lines = [f"[{name}]"]
        for key, value in table.items():
            if not isinstance(value, str) or not BARE_KEY.fullmatch(key):
                raise ConfigInvalid(
                    f"{path} holds content ws cannot rewrite; add the token by hand"
                )
            lines.append(f"{key} = {_toml_string(value)}")
        chunks.append("\n".join(lines) + "\n")
    return "\n".join(chunks)


def save_token(service: str, value: str) -> Path:
    path = _credentials_path()
    _refuse_foreign_credentials(path)
    try:
        tables = _read_toml(path)
    except ConfigMissing:
        tables = {}
    text = _credentials_text(
        {**tables, service: {**_table(tables, service, path), STORED_FIELD: value}}, path
    )
    folder = path.parent
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    _replace_atomically(path, text)
    return path


def _replace_atomically(path: Path, text: str) -> None:
    """Write beside the file and rename over it: a failure never leaves a truncated credentials."""
    try:
        data = text.encode("utf-8")
        tomllib.loads(text)
    except (UnicodeEncodeError, tomllib.TOMLDecodeError):
        raise ConfigInvalid("the token cannot be stored as TOML; nothing was written") from None
    descriptor, name = tempfile.mkstemp(prefix=".credentials-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def save_jira_token(value: str) -> Path:
    return save_token("jira", value)
