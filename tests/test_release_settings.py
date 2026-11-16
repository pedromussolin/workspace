from pathlib import Path

import pytest

from ws.release import ReleaseSetup
from ws.release.settings import load_release_config

JIRA = '[tracker]\nkind = "jira"\n[tracker.jira]\nsite = "https://example.atlassian.net/"\n'
README = 'see "Release" in the README'


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "ws-config"
    folder.mkdir()
    monkeypatch.setenv("WS_CONFIG_DIR", str(folder))
    return folder


def _write(config_dir: Path, text: str) -> None:
    (config_dir / "config.toml").write_text(text, encoding="utf-8")


def test_release_config_reads_repos_in_file_order(config_dir):
    _write(
        config_dir,
        JIRA
        + '[release]\nbase_branch = "main"\nsandbox_branch = "sbx"\n'
        + '[release.repos.repo-b]\nslug = "acme/repo-b"\npath = "~/x"\n'
        + '[release.repos.repo-a]\nslug = "acme/repo-a"\npath = "/srv/a"\n'
        + 'alembic = "migrations/versions"\n',
    )

    config = load_release_config()

    assert config.base_branch == "main"
    assert config.sandbox_branch == "sbx"
    assert config.card_url_template == "https://example.atlassian.net/browse/{key}"
    assert tuple(entry.name for entry in config.repos) == ("repo-b", "repo-a")
    first, second = config.repos
    assert first.path == Path.home() / "x"
    assert first.alembic is None
    assert second.alembic == "migrations/versions"
    assert second.repo_name == "repo-a"
    assert config.entry("repo-a") is second


def test_release_config_reads_the_old_jira_table_without_email(config_dir, capsys):
    _write(
        config_dir,
        '[jira]\nsite = "https://example.atlassian.net"\n'
        '[release.repos.repo-a]\nslug = "acme/repo-a"\npath = "/srv/a"\n',
    )

    config = load_release_config()

    assert config.card_url_template == "https://example.atlassian.net/browse/{key}"
    assert capsys.readouterr().err.count("deprecated") == 1


def test_release_config_ignores_the_other_sections(config_dir):
    _write(
        config_dir,
        JIRA + "[standup]\nstale_workdays = 'x'\n[tracker.jira.types]\nbogus = 'y'\n"
        '[release.repos.repo-a]\nslug = "acme/repo-a"\npath = "/srv/a"\n',
    )

    assert load_release_config().card_url_template.endswith("/browse/{key}")


def test_card_url_template_facade_for_both_config_shapes(config_dir):
    from ws import tracker
    from ws.tracker.errors import TrackerSetup

    _write(config_dir, JIRA)
    assert tracker.card_url_template() == "https://example.atlassian.net/browse/{key}"
    _write(config_dir, '[jira]\nsite = "https://example.atlassian.net"\n')
    assert tracker.card_url_template() == "https://example.atlassian.net/browse/{key}"
    _write(config_dir, '[tracker]\nkind = "jira"\n[tracker.jira]\nsite = "ftp://x"\n')
    with pytest.raises(TrackerSetup, match="site"):
        tracker.card_url_template()


def test_release_config_defaults_the_branches(config_dir):
    _write(
        config_dir,
        JIRA + '[release.repos.repo-a]\nslug = "acme/repo-a"\npath = "/srv/a"\n',
    )

    config = load_release_config()

    assert (config.base_branch, config.sandbox_branch) == ("master", "sandbox")


def test_release_config_names_missing_keys(config_dir):
    _write(config_dir, JIRA + '[release.repos.repo-a]\npath = "/srv/a"\n')

    with pytest.raises(ReleaseSetup) as error:
        load_release_config()

    assert "release.repos.repo-a.slug" in str(error.value)
    assert str(error.value).endswith(README)


def test_release_config_refuses_unknown_keys(config_dir):
    _write(
        config_dir,
        JIRA + '[release.repos.repo-a]\nslug = "acme/repo-a"\npath = "/s"\nbranch = "x"\n',
    )

    with pytest.raises(ReleaseSetup, match="branch") as error:
        load_release_config()

    assert str(error.value).endswith(README)


def test_release_config_without_tracker_fails(config_dir):
    _write(config_dir, '[release.repos.repo-a]\nslug = "acme/repo-a"\npath = "/s"\n')

    with pytest.raises(ReleaseSetup, match=r"\[tracker\] kind") as error:
        load_release_config()

    assert str(error.value).endswith(README)


def test_release_config_without_a_release_table(config_dir):
    _write(config_dir, JIRA)

    with pytest.raises(ReleaseSetup, match="release.repos") as error:
        load_release_config()

    assert str(error.value).endswith(README)


def test_release_config_without_a_config_file(config_dir):
    with pytest.raises(ReleaseSetup) as error:
        load_release_config()

    assert str(error.value).endswith(README)
