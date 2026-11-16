"""Local, per-user config of ws: `config.toml` (no secrets) and the tokens of `credentials`."""

import importlib
import os
import re
import stat
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ws.config import config_dir
from ws.identity import DEV_ID
from ws.tracker import ADAPTERS, KNOWN_KINDS

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
class StandupConfig:
    repo_roots: tuple[Path, ...]
    stale_workdays: int = DEFAULT_STALE_WORKDAYS


@dataclass(frozen=True)
class Person:
    dev_id: str
    ids: dict[str, str]
    label: str | None = None


@dataclass(frozen=True, init=False)
class UserConfig:
    """`tracker_kind` and `tracker_settings` are None when config.toml names no tracker (or the
    kind has no adapter): the file still loads, and what needs the tracker refuses."""

    standup: StandupConfig
    identity: str | None
    tracker_kind: str | None
    people: dict[str, Person]
    tracker_settings: object

    def __init__(
        self,
        *,
        standup: StandupConfig,
        identity_email: str | None = None,
        identity: str | None = None,
        tracker_kind: str | None = "jira",
        people: dict[str, Person] | None = None,
        tracker_settings: object = None,
        jira: object = None,
    ):
        values = {
            "standup": standup,
            "identity": identity_email or identity,
            "tracker_kind": tracker_kind,
            "people": {} if people is None else people,
            "tracker_settings": tracker_settings if jira is None else jira,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)

    @property
    def identity_email(self) -> str:
        if not self.identity:
            raise ConfigInvalid(
                "config.toml: identity.email is not set; set it or the tracker e-mail"
            )
        return self.identity

    @property
    def jira(self):
        """The settings of the `jira` kind; callers move to `tracker_settings` (Task 15)."""
        if self.tracker_settings is None or self.tracker_kind != "jira":
            raise ConfigInvalid(NO_TRACKER if not self.tracker_kind else NOT_JIRA)
        return self.tracker_settings


NO_TRACKER = 'config.toml: [tracker] kind is not set; add [tracker] kind = "jira"'
NOT_JIRA = "config.toml: the tracker settings are not Jira's"
OLD_TABLE_NOTICE = "config.toml: [jira] is deprecated; move it under [tracker.jira]"
_deprecation_shown = False


def __getattr__(name):
    if name == "JiraConfig":
        from ws.tracker.jira.settings import JiraConfig

        return JiraConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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


def _people(data: dict, path: Path) -> dict[str, Person]:
    people = _table(data, "people", path)
    result = {}
    for key, entry in people.items():
        if not DEV_ID.fullmatch(key):
            raise ConfigInvalid(f"{path}: people.{key} is not a dev id (dev- and 10 hex digits)")
        if not isinstance(entry, dict):
            raise ConfigInvalid(f"{path}: people.{key} must be a table")
        for name in entry:
            if name != "label" and name not in KNOWN_KINDS:
                raise ConfigInvalid(
                    f"{path}: people.{key}.{name} is not a tracker kind "
                    f"({', '.join(KNOWN_KINDS)}) or label"
                )
        ids = {
            kind: _string(entry, kind, path, f"people.{key}")
            for kind in KNOWN_KINDS
            if kind in entry
        }
        result[key] = Person(key, ids, _optional_string(entry, "label", path, f"people.{key}"))
    return result


def _standup_config(data: dict, path: Path) -> StandupConfig:
    standup = _table(data, "standup", path)
    stale = standup.get("stale_workdays", DEFAULT_STALE_WORKDAYS)
    if isinstance(stale, bool) or not isinstance(stale, int) or stale < 1:
        raise ConfigInvalid(f"{path}: standup.stale_workdays must be a positive integer")
    roots = _string_list(standup, "repo_roots", path, "standup")
    return StandupConfig(
        repo_roots=(
            (Path.home() / "repos",)
            if roots is None
            else tuple(Path(item).expanduser() for item in roots)
        ),
        stale_workdays=stale,
    )


def load_standup() -> StandupConfig:
    """The `[standup]` settings alone, so a command that needs only them works without `[jira]`."""
    path = config_dir() / "config.toml"
    return _standup_config(_read_toml(path), path)


def load_table(name: str) -> dict:
    """The raw `[name]` table of config.toml, `{}` when the file has no such table.

    Each command validates its own keys. A missing file raises `ConfigMissing`; malformed TOML or
    a `name` that is not a table raises `ConfigInvalid`.
    """
    path = config_dir() / "config.toml"
    return _table(_read_toml(path), name, path)


def _tracker_settings(data: dict, tracker: dict, kind: str | None, path: Path) -> object:
    old, new = "jira" in data, "jira" in tracker
    if old and new:
        raise ConfigInvalid(
            f"{path}: both [jira] and [tracker.jira] are set; keep only [tracker.jira]"
        )
    if old:
        return _old_jira_settings(data, kind, path)
    if kind not in ADAPTERS:
        return None
    table = tracker.get(kind, {})
    if not isinstance(table, dict):
        raise ConfigInvalid(f"{path}: [tracker.{kind}] must be a table")
    return importlib.import_module(ADAPTERS[kind]).parse_settings(table, path)


def _old_jira_settings(data: dict, kind: str | None, path: Path) -> object:
    """Compatibility with the `[jira]` table, removed in Task 18."""
    global _deprecation_shown
    if not _deprecation_shown:
        _deprecation_shown = True
        print(OLD_TABLE_NOTICE, file=sys.stderr)
    if kind not in (None, "jira"):
        return None
    from ws.tracker.jira.settings import parse_settings

    return parse_settings(_table(data, "jira", path), path, "jira")


def load_config() -> UserConfig:
    path = config_dir() / "config.toml"
    data = _read_toml(path)
    standup = _standup_config(data, path)
    tracker = _table(data, "tracker", path)
    identity = _table(data, "identity", path)
    kind = _optional_string(tracker, "kind", path, "tracker")
    settings = _tracker_settings(data, tracker, kind, path)
    if kind is None and "jira" in data:
        kind = "jira"
    return UserConfig(
        standup=standup,
        identity_email=_optional_string(identity, "email", path, "identity")
        or getattr(settings, "email", None),
        tracker_kind=kind,
        people=_people(data, path),
        tracker_settings=settings,
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


def toml_string(value: str) -> str:
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
            lines.append(f"{key} = {toml_string(value)}")
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
