import json

from ws.cli import main
from ws.identity import dev_id
from ws.userconfig import save_jira_token

SEARCH = ("GET", "/rest/api/3/user/search")


def setup(ws_config, fake_jira):
    (ws_config / "config.toml").write_text(
        f'[jira]\nsite = "{fake_jira.site}"\nemail = "dev@example.com"\nproject = "TS"\n',
        encoding="utf-8",
    )
    save_jira_token("sample-value")


def test_people_me_prints_the_users_dev_id(ws_config, fake_jira, capsys):
    setup(ws_config, fake_jira)
    assert main(["people", "me"]) == 0
    assert capsys.readouterr().out.strip() == dev_id("dev@example.com")
    assert fake_jira.requests == []


def test_people_add_finds_the_account_by_email(ws_config, fake_jira, capsys):
    setup(ws_config, fake_jira)
    fake_jira.routes[SEARCH] = (200, json.dumps([{"accountId": "acc-ana"}]))
    assert main(["people", "add", "ana@example.com"]) == 0
    out = capsys.readouterr().out
    assert f'[people."{dev_id("ana@example.com")}"]' in out
    assert 'jira = "acc-ana"' in out
    assert "ana@example.com" not in out


def test_people_add_with_account_skips_the_search(ws_config, fake_jira, capsys):
    setup(ws_config, fake_jira)
    assert main(["people", "add", "ana@example.com", "--account", "acc-ana"]) == 0
    assert 'jira = "acc-ana"' in capsys.readouterr().out
    assert not [r for r in fake_jira.requests if r["path"] == SEARCH[1]]


def test_people_add_refuses_zero_or_several_matches(ws_config, fake_jira, capsys):
    setup(ws_config, fake_jira)
    for found in ([], [{"accountId": "a"}, {"accountId": "b"}]):
        fake_jira.routes[SEARCH] = (200, json.dumps(found))
        assert main(["people", "add", "ana@example.com"]) == 1
        err = capsys.readouterr().err
        assert "--account" in err
        assert "ana@example.com" not in err
