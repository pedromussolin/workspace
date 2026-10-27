import stat
import sys
from pathlib import Path

import pytest

from ws.cli import main
from ws.userconfig import (
    ConfigInvalid,
    ConfigMissing,
    load_config,
    load_jira_token,
    save_jira_token,
)

CONFIG = """\
[jira]
site = "https://example.atlassian.net"
email = "dev@example.com"

[jira.status_overrides]
"In Validation" = "validation"
"Cancelled Late" = "cancelled"

[standup]
repos = ["~/repos/sample", "/srv/other"]
author_emails = ["dev@example.com"]
"""


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "ws-config"
    folder.mkdir()
    monkeypatch.setenv("WS_CONFIG_DIR", str(folder))
    return folder


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_load_config_reads_every_field(config_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (config_dir / "config.toml").write_text(CONFIG, encoding="utf-8")

    config = load_config()

    assert config.jira.site == "https://example.atlassian.net"
    assert config.jira.email == "dev@example.com"
    assert config.jira.status_overrides == {
        "In Validation": "validation",
        "Cancelled Late": "cancelled",
    }
    assert config.standup.repos == (tmp_path / "repos" / "sample", Path("/srv/other"))
    assert config.standup.author_emails == ("dev@example.com",)
    assert config.standup.stale_workdays == 3


def test_missing_config_raises_config_missing_with_path(config_dir):
    with pytest.raises(ConfigMissing) as error:
        load_config()

    assert error.value.path == config_dir / "config.toml"


def test_override_to_unknown_status_is_invalid(config_dir):
    text = CONFIG.replace('"Cancelled Late" = "cancelled"', '"X" = "doing"')
    (config_dir / "config.toml").write_text(text, encoding="utf-8")

    with pytest.raises(ConfigInvalid, match="doing"):
        load_config()


def test_wrong_type_is_invalid(config_dir):
    text = CONFIG.replace("[standup]", '[standup]\nstale_workdays = "3"')
    (config_dir / "config.toml").write_text(text, encoding="utf-8")

    with pytest.raises(ConfigInvalid, match="stale_workdays"):
        load_config()


def test_malformed_toml_is_invalid(config_dir):
    (config_dir / "config.toml").write_text("[jira\n", encoding="utf-8")

    with pytest.raises(ConfigInvalid, match="config.toml"):
        load_config()


def test_save_token_writes_600_in_700_folder_and_load_reads_it(tmp_path, monkeypatch):
    folder = tmp_path / "fresh" / "workspace"
    monkeypatch.setenv("WS_CONFIG_DIR", str(folder))

    path = save_jira_token('tok"en\\1')

    assert path == folder / "credentials"
    assert _mode(path) == 0o600
    assert _mode(folder) == 0o700
    assert load_jira_token() == 'tok"en\\1'


def test_load_token_missing_file_or_key_raises_config_missing(config_dir):
    with pytest.raises(ConfigMissing) as error:
        load_jira_token()
    assert error.value.path == config_dir / "credentials"

    (config_dir / "credentials").write_text('[other]\nkey = "v"\n', encoding="utf-8")
    with pytest.raises(ConfigMissing):
        load_jira_token()


def test_save_token_refuses_to_overwrite_another_table(config_dir):
    credentials = config_dir / "credentials"
    credentials.write_text('[other]\nkey = "v"\n', encoding="utf-8")

    with pytest.raises(ConfigInvalid, match="credentials"):
        save_jira_token("secret")

    assert credentials.read_text(encoding="utf-8") == '[other]\nkey = "v"\n'


def test_save_token_replaces_an_existing_jira_token(config_dir):
    save_jira_token("old")
    save_jira_token("new")

    assert load_jira_token() == "new"


def test_cli_token_refuses_without_tty(config_dir, monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    code = main(["config", "token", "jira"])

    assert code == 2
    assert "run this in your own terminal: ws config token jira" in capsys.readouterr().err
    assert not (config_dir / "credentials").exists()


def test_cli_token_saves_what_getpass_reads(config_dir, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "typed-token")

    assert main(["config", "token", "jira"]) == 0
    assert load_jira_token() == "typed-token"
