import json
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
    load_standup,
    load_table,
    load_token,
    save_jira_token,
    save_token,
)

CONFIG = """\
[jira]
site = "https://example.atlassian.net"
email = "dev@example.com"

[jira.status_overrides]
"In Validation" = "validation"
"Cancelled Late" = "cancelled"

[standup]
repo_roots = ["~/projects", "/srv/other"]
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
    assert config.standup.repo_roots == (tmp_path / "projects", Path("/srv/other"))
    assert config.standup.stale_workdays == 3


def test_repo_roots_default_to_home_repos_without_standup_table(config_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    only_jira = CONFIG.split("[standup]")[0]
    (config_dir / "config.toml").write_text(only_jira, encoding="utf-8")

    config = load_config()

    assert config.standup.repo_roots == (tmp_path / "repos",)
    assert config.standup.stale_workdays == 3


def test_repo_roots_must_be_a_list_of_strings(config_dir):
    text = CONFIG.replace('repo_roots = ["~/projects", "/srv/other"]', 'repo_roots = "~/x"')
    (config_dir / "config.toml").write_text(text, encoding="utf-8")

    with pytest.raises(ConfigInvalid, match="repo_roots"):
        load_config()


def test_missing_config_raises_config_missing_with_path(config_dir):
    with pytest.raises(ConfigMissing) as error:
        load_config()

    assert error.value.path == config_dir / "config.toml"


def test_override_to_the_workflow_stages_is_valid(config_dir):
    text = CONFIG.replace(
        '"Cancelled Late" = "cancelled"',
        '"Ready Deploy" = "ready_deploy"\n"Code Review" = "review"\n"Block" = "blocked"',
    )
    (config_dir / "config.toml").write_text(text, encoding="utf-8")

    overrides = load_config().jira.status_overrides

    assert overrides["Ready Deploy"] == "ready_deploy"
    assert overrides["Code Review"] == "review"
    assert overrides["Block"] == "blocked"


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


def test_save_token_keeps_the_other_sections(config_dir):
    credentials = config_dir / "credentials"
    credentials.write_text('[other]\nkey = "v"\n', encoding="utf-8")

    save_token("github", "gh-secret")

    assert load_token("github") == "gh-secret"
    assert 'key = "v"' in credentials.read_text(encoding="utf-8")
    save_jira_token("jira-secret")
    assert load_token("github") == "gh-secret"
    assert load_jira_token() == "jira-secret"
    assert 'key = "v"' in credentials.read_text(encoding="utf-8")
    assert _mode(credentials) == 0o600


def test_save_token_refuses_content_it_cannot_rewrite(config_dir):
    credentials = config_dir / "credentials"
    original = '[other]\nlist = ["a", "b"]\n'
    credentials.write_text(original, encoding="utf-8")

    with pytest.raises(ConfigInvalid, match="cannot rewrite"):
        save_token("github", "secret")

    assert credentials.read_text(encoding="utf-8") == original


def test_load_token_of_a_service_without_it_names_the_service(config_dir):
    save_jira_token("jira-secret")

    with pytest.raises(ConfigMissing, match="GitHub token"):
        load_token("github")


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


def test_cli_token_github_saves_what_getpass_reads_and_keeps_jira(config_dir, monkeypatch, capsys):
    save_jira_token("jira-secret")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "gh-typed")

    assert main(["config", "token", "github"]) == 0

    assert load_token("github") == "gh-typed"
    assert load_jira_token() == "jira-secret"
    assert "saved the GitHub token" in capsys.readouterr().out


def test_cli_token_github_refuses_without_tty_and_on_empty_input(config_dir, monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert main(["config", "token", "github"]) == 2
    assert "run this in your own terminal: ws config token github" in capsys.readouterr().err

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "  ")
    assert main(["config", "token", "github"]) == 2
    assert not (config_dir / "credentials").exists()


def test_mcp_headers_prints_only_the_authorization_header(config_dir, monkeypatch, capsys):
    save_token("github", "gh-secret")
    monkeypatch.setenv("CLAUDE_CODE_MCP_SERVER_NAME", "github")

    assert main(["mcp-headers", "github"]) == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"Authorization": "Bearer gh-secret"}
    assert captured.out.count("\n") == 1
    assert captured.err == ""


@pytest.mark.parametrize("value", [None, ""])
def test_mcp_headers_refuses_outside_claude_code(config_dir, monkeypatch, capsys, value):
    save_token("github", "gh-secret")
    if value is None:
        monkeypatch.delenv("CLAUDE_CODE_MCP_SERVER_NAME", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_CODE_MCP_SERVER_NAME", value)

    assert main(["mcp-headers", "github"]) == 2

    captured = capsys.readouterr()
    assert "headersHelper" in captured.err
    assert "gh-secret" not in captured.out + captured.err


def test_mcp_headers_without_a_token_exits_2_on_stderr(config_dir, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_MCP_SERVER_NAME", "github")

    assert main(["mcp-headers", "github"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "credentials" in captured.err


def test_mcp_headers_help_says_the_gate_asks(capsys):
    with pytest.raises(SystemExit):
        main(["mcp-headers", "--help"])

    assert "approval gate asks" in capsys.readouterr().out


CARD_KEYS = """\
project = "TS"
board_id = 12
issue_type = "Task"
start_date_field = "customfield_1"
sprint_field = "customfield_2"
"""


def test_card_keys_are_read(config_dir):
    text = CONFIG.replace('email = "dev@example.com"\n', 'email = "dev@example.com"\n' + CARD_KEYS)
    (config_dir / "config.toml").write_text(text, encoding="utf-8")

    jira = load_config().jira

    assert jira.project == "TS"
    assert jira.board_id == 12
    assert jira.issue_type == "Task"
    assert jira.start_date_field == "customfield_1"
    assert jira.sprint_field == "customfield_2"


def test_card_keys_are_none_when_absent(config_dir):
    (config_dir / "config.toml").write_text(CONFIG, encoding="utf-8")

    jira = load_config().jira

    assert jira.project is None
    assert jira.board_id is None
    assert jira.issue_type is None
    assert jira.start_date_field is None
    assert jira.sprint_field is None


@pytest.mark.parametrize(
    ("line", "key"),
    [
        ("project = 5", "project"),
        ('project = ""', "project"),
        ('board_id = "12"', "board_id"),
        ("board_id = true", "board_id"),
        ("board_id = 0", "board_id"),
        ("issue_type = 3", "issue_type"),
        ("start_date_field = 3", "start_date_field"),
        ("sprint_field = []", "sprint_field"),
    ],
)
def test_card_keys_of_the_wrong_type_are_invalid(config_dir, line, key):
    text = CONFIG.replace('email = "dev@example.com"\n', f'email = "dev@example.com"\n{line}\n')
    (config_dir / "config.toml").write_text(text, encoding="utf-8")

    with pytest.raises(ConfigInvalid, match=f"jira.{key}"):
        load_config()


@pytest.mark.parametrize(
    "site",
    [
        "http://example.atlassian.net",
        "https://evil.example",
        "https://example.atlassian.net.x.example",
    ],
)
def test_load_config_refuses_a_site_that_is_not_https_atlassian_cloud(config_dir, site):
    (config_dir / "config.toml").write_text(
        CONFIG.replace("https://example.atlassian.net", site), encoding="utf-8"
    )

    with pytest.raises(ConfigInvalid, match="atlassian.net"):
        load_config()


def test_load_token_refuses_a_credentials_symlink(config_dir, tmp_path):
    real = tmp_path / "elsewhere"
    real.write_text('[jira]\ntoken = "stolen"\n', encoding="utf-8")
    real.chmod(0o600)
    (config_dir / "credentials").symlink_to(real)

    with pytest.raises(ConfigInvalid, match="symlink"):
        load_jira_token()


def test_load_token_refuses_a_credentials_file_of_another_owner(config_dir, monkeypatch):
    save_jira_token("secret")
    mine = (config_dir / "credentials").stat().st_uid
    monkeypatch.setattr("os.getuid", lambda: mine + 1)

    with pytest.raises(ConfigInvalid, match="owned"):
        load_jira_token()


def test_save_token_refuses_to_write_through_a_symlink(config_dir, tmp_path):
    victim = tmp_path / "victim.toml"
    victim.write_text("keep me\n", encoding="utf-8")
    (config_dir / "credentials").symlink_to(victim)

    with pytest.raises(ConfigInvalid, match="symlink"):
        save_jira_token("secret")

    assert victim.read_text(encoding="utf-8") == "keep me\n"


def test_save_token_refuses_a_dangling_symlink(config_dir, tmp_path):
    target = tmp_path / "not-yet"
    (config_dir / "credentials").symlink_to(target)

    with pytest.raises(ConfigInvalid, match="symlink"):
        save_jira_token("secret")

    assert not target.exists()


def test_save_token_refuses_a_file_of_another_owner(config_dir, monkeypatch):
    save_jira_token("first")
    mine = (config_dir / "credentials").stat().st_uid
    monkeypatch.setattr("os.getuid", lambda: mine + 1)

    with pytest.raises(ConfigInvalid, match="owned"):
        save_jira_token("second")


@pytest.mark.parametrize("token", ["a\x7fb", "emoji-\U0001f600-end", "tab\tnl\nbell\x07", "á ç"])
def test_save_token_stores_what_json_would_break(config_dir, token):
    save_token("github", token)

    assert load_token("github") == token


def test_save_token_failing_to_replace_keeps_the_old_file_and_leaves_no_temporary(
    config_dir, monkeypatch
):
    save_jira_token("old")
    credentials = config_dir / "credentials"
    before = credentials.read_text(encoding="utf-8")

    def broken(source, target):
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", broken)

    with pytest.raises(OSError, match="disk full"):
        save_jira_token("new")

    assert credentials.read_text(encoding="utf-8") == before
    assert [path.name for path in config_dir.iterdir()] == ["credentials"]


def test_save_token_that_is_not_encodable_leaves_the_file_untouched(config_dir):
    save_jira_token("old")
    credentials = config_dir / "credentials"
    before = credentials.read_text(encoding="utf-8")

    with pytest.raises(ConfigInvalid, match="nothing was written"):
        save_jira_token("lone-\ud800-surrogate")

    assert credentials.read_text(encoding="utf-8") == before
    assert _mode(credentials) == 0o600


def test_load_table_returns_the_raw_table(config_dir):
    text = CONFIG + '\n[env_check]\nsource = "aws"\n\n[env_check.repos.api]\npath = "~/x"\n'
    (config_dir / "config.toml").write_text(text, encoding="utf-8")

    table = load_table("env_check")

    assert table == {"source": "aws", "repos": {"api": {"path": "~/x"}}}


def test_load_table_absent_is_empty(config_dir):
    (config_dir / "config.toml").write_text(CONFIG, encoding="utf-8")

    assert load_table("deploy_check") == {}


def test_load_table_needs_no_jira_table(config_dir):
    (config_dir / "config.toml").write_text("[handoff]\nmax_listed = 3\n", encoding="utf-8")

    assert load_table("handoff") == {"max_listed": 3}


def test_load_table_that_is_not_a_table_is_invalid(config_dir):
    (config_dir / "config.toml").write_text('handoff = "x"\n', encoding="utf-8")

    with pytest.raises(ConfigInvalid, match=r"\[handoff\] must be a table"):
        load_table("handoff")


def test_load_table_missing_file_raises_config_missing(config_dir):
    with pytest.raises(ConfigMissing):
        load_table("handoff")


def test_load_standup_needs_no_jira_table(config_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (config_dir / "config.toml").write_text(
        '[standup]\nrepo_roots = ["~/projects"]\nstale_workdays = 5\n', encoding="utf-8"
    )

    standup = load_standup()

    assert standup.repo_roots == (tmp_path / "projects",)
    assert standup.stale_workdays == 5


def test_load_standup_defaults_and_rejects_a_bad_value(config_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (config_dir / "config.toml").write_text("", encoding="utf-8")
    assert load_standup().repo_roots == (tmp_path / "repos",)

    (config_dir / "config.toml").write_text("[standup]\nstale_workdays = 0\n", encoding="utf-8")
    with pytest.raises(ConfigInvalid, match="stale_workdays"):
        load_standup()
