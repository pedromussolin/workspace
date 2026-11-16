"""The Jira settings of config.toml (`[tracker.jira]`), parsed by the adapter.

`userconfig` loads this module inside `load_config`, so the helpers it shares are imported from
there without an import cycle.
"""

from dataclasses import dataclass, field
from pathlib import Path

from ws.taskmodel import Status
from ws.tracker import vocab
from ws.tracker.jira.client import SiteRefused, check_site
from ws.userconfig import (
    ConfigInvalid,
    _optional_positive_int,
    _optional_string,
    _string,
)

SECTION = "tracker.jira"


@dataclass(frozen=True)
class JiraConfig:
    site: str
    email: str
    status_overrides: dict[str, str]
    project: str | None = None
    board_id: int | None = None
    start_date_field: str | None = None
    sprint_field: str | None = None
    types: dict[str, str] = field(default_factory=dict)
    links: dict[str, str] = field(default_factory=dict)


def _status_overrides(table: dict, path: Path, section: str) -> dict[str, str]:
    overrides = table.get("status_overrides", {})
    if not isinstance(overrides, dict):
        raise ConfigInvalid(f"{path}: {section}.status_overrides must be a table")
    valid = {status.value for status in Status}
    for name, value in overrides.items():
        if value not in valid:
            raise ConfigInvalid(
                f"{path}: {section}.status_overrides.{name!r} is {value!r}; "
                f"use one of {', '.join(sorted(valid))}"
            )
    return dict(overrides)


def _site(table: dict, path: Path, section: str) -> str:
    site = _string(table, "site", path, section)
    try:
        return check_site(site)
    except SiteRefused as error:
        raise ConfigInvalid(f"{path}: {section}.site: {error}") from None


def _name_map(
    table: dict, key: str, allowed: tuple[str, ...], path: Path, section: str
) -> dict[str, str]:
    names = table.get(key, {})
    if not isinstance(names, dict):
        raise ConfigInvalid(f"{path}: {section}.{key} must be a table")
    for name in names:
        if name not in allowed:
            raise ConfigInvalid(
                f"{path}: {section}.{key}.{name} is not a neutral name; "
                f"use one of {', '.join(allowed)}"
            )
        _string(names, name, path, f"{section}.{key}")
    return dict(names)


def card_url_template(table: dict, path: Path, section: str = SECTION) -> str:
    """The card link from the raw table, checking only `site`."""
    return f"{_site(table, path, section).rstrip('/')}/browse/{{key}}"


def parse_settings(table: dict, path: Path, section: str = SECTION) -> JiraConfig:
    """`section` names the table in the messages: the old `[jira]` still loads through here."""
    if "issue_type" in table:
        raise ConfigInvalid(
            f"{path}: [{section}] issue_type was replaced by [{section}.types]; delete the "
            f"issue_type line from [{section}], then run `ws tracker discover` and paste its "
            "output into config.toml"
        )
    return JiraConfig(
        site=_site(table, path, section),
        email=_string(table, "email", path, section),
        status_overrides=_status_overrides(table, path, section),
        project=_optional_string(table, "project", path, section),
        board_id=_optional_positive_int(table, "board_id", path, section),
        start_date_field=_optional_string(table, "start_date_field", path, section),
        sprint_field=_optional_string(table, "sprint_field", path, section),
        types=_name_map(table, "types", vocab.CARD_TYPES + vocab.UPPER_TYPES, path, section),
        links=_name_map(table, "links", vocab.LINK_NAMES, path, section),
    )
