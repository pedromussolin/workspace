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
DEFAULT_DAY_FLOOR_MINUTES = 8 * 60 + 48
DEFAULT_IDLE_MINUTES = 30
MAX_DAY_FLOOR_MINUTES = 24 * 60
DURATION = re.compile(r"(?:(\d+)h(?: ?([0-5]?\d)m?)?|(\d+)m)")
TOKEN_SERVICES = {"jira": "Jira", "github": "GitHub"}
STORED_FIELD = "token"
BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
POLICY_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")


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
class TimeConfig:
    """`[time]`: the least a working day closes at, and the gap of silence that ends an interval
    of session activity."""

    day_floor_minutes: int = DEFAULT_DAY_FLOOR_MINUTES
    idle_minutes: int = DEFAULT_IDLE_MINUTES


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
    card_policy: str | None
    time: TimeConfig

    def __init__(
        self,
        *,
        standup: StandupConfig,
        identity_email: str | None = None,
        identity: str | None = None,
        tracker_kind: str | None = None,
        people: dict[str, Person] | None = None,
        tracker_settings: object = None,
        card_policy: str | None = None,
        time: TimeConfig | None = None,
    ):
        values = {
            "standup": standup,
            "identity": identity_email or identity,
            "tracker_kind": tracker_kind,
            "people": {} if people is None else people,
            "tracker_settings": tracker_settings,
            "card_policy": card_policy,
            "time": time or TimeConfig(),
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)

    @property
    def identity_email(self) -> str | None:
        return self.identity or None

    def require_identity_email(self) -> str:
        """Your e-mail; raises when neither `[identity]` nor the tracker settings have one."""
        if not self.identity:
            raise ConfigInvalid(
                "config.toml: identity.email is not set; set it or the tracker e-mail"
            )
        return self.identity


OLD_TABLE_NOTICE = "config.toml: [jira] is deprecated; move it under [tracker.jira]"
_deprecation_shown = False


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
    """The `[standup]` settings alone, so a command that needs only them works without the
    tracker table."""
    path = config_dir() / "config.toml"
    return _standup_config(_read_toml(path), path)


def load_time() -> TimeConfig:
    """The `[time]` settings alone; the defaults when config.toml does not exist, so marking time
    needs no setup."""
    path = config_dir() / "config.toml"
    try:
        return _time_config(_read_toml(path), path)
    except ConfigMissing:
        return TimeConfig()


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


def _notice_old_table() -> None:
    global _deprecation_shown
    if not _deprecation_shown:
        _deprecation_shown = True
        print(OLD_TABLE_NOTICE, file=sys.stderr)


def load_tracker_table() -> tuple[str | None, dict, Path, str]:
    """The tracker kind, its raw table, the file and the table's name for messages, with no
    other section validated.

    The table is `[tracker.<kind>]`, or the old `[jira]` when the kind is absent or `jira`.
    """
    path = config_dir() / "config.toml"
    data = _read_toml(path)
    tracker = _table(data, "tracker", path)
    kind = _optional_string(tracker, "kind", path, "tracker")
    old, new = "jira" in data, "jira" in tracker
    if old and new:
        raise ConfigInvalid(
            f"{path}: both [jira] and [tracker.jira] are set; keep only [tracker.jira]"
        )
    section = f"tracker.{kind}" if kind else "tracker"
    if old:
        _notice_old_table()
        if kind in (None, "jira"):
            return "jira", _table(data, "jira", path), path, "jira"
        return kind, {}, path, section
    table = tracker.get(kind, {}) if kind else {}
    if not isinstance(table, dict):
        raise ConfigInvalid(f"{path}: [{section}] must be a table")
    return kind, table, path, section


def _old_jira_settings(data: dict, kind: str | None, path: Path) -> object:
    """The old `[jira]` table still loads, with one deprecation line, through the adapter of
    the `jira` kind; its messages name `[jira]`."""
    _notice_old_table()
    if kind not in (None, "jira"):
        return None
    adapter = importlib.import_module(ADAPTERS["jira"])
    return adapter.parse_settings(_table(data, "jira", path), path, "jira")


def _card_policy(data: dict, path: Path) -> str | None:
    """`[card] policy`: the name of the company card policy file, None when it is not set."""
    name = _optional_string(_table(data, "card", path), "policy", path, "card")
    if name is not None and not POLICY_NAME.fullmatch(name):
        raise ConfigInvalid(
            f"{path}: card.policy must be a file name of lowercase letters, digits, - and _"
        )
    return name


def _duration_minutes(text: str) -> int | None:
    """`8h48`, `8h 48m`, `8h` or `528m` as minutes; None for any other text."""
    found = DURATION.fullmatch(text.strip())
    if not found:
        return None
    if found.group(3) is not None:
        return int(found.group(3))
    return int(found.group(1)) * 60 + int(found.group(2) or 0)


def _time_config(data: dict, path: Path) -> TimeConfig:
    """`[time] day_floor` (default 8h48) and `idle_minutes` (default 30)."""
    table = _table(data, "time", path)
    floor = DEFAULT_DAY_FLOOR_MINUTES
    if "day_floor" in table:
        text = _string(table, "day_floor", path, "time")
        minutes = _duration_minutes(text)
        if minutes is None or not 0 < minutes <= MAX_DAY_FLOOR_MINUTES:
            raise ConfigInvalid(
                f"{path}: time.day_floor must be hours and minutes like 8h48, up to 24h"
            )
        floor = minutes
    idle = _optional_positive_int(table, "idle_minutes", path, "time") or DEFAULT_IDLE_MINUTES
    return TimeConfig(day_floor_minutes=floor, idle_minutes=idle)


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
        card_policy=_card_policy(data, path),
        time=_time_config(data, path),
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
