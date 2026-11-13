import json
import tomllib

from ws.cli import main
from ws.tracker.jira_discover import discover_toml
from ws.userconfig import save_jira_token

TYPES = [
    {"id": "10002", "name": "Tarefa"},
    {"id": "10010", "name": "Melhoria"},
    {"id": "10136", "name": "Iniciativa"},
    {"id": "10001", "name": "História"},
]
LINKS = [{"name": "Blocks"}, {"name": "Relates"}, {"name": "Duplicate"}]


def test_discover_maps_known_names():
    text = discover_toml(TYPES, LINKS)
    assert 'task = "10002"' in text
    assert 'improvement = "10010"' in text
    assert 'initiative = "10136"' in text
    assert '# "História" = "10001"' in text
    assert 'blocks = "Blocks"' in text
    assert 'relates = "Relates"' in text
    assert '# "Duplicate"' in text
    parsed = tomllib.loads(text)
    assert parsed["jira"]["types"]["task"] == "10002"
    assert parsed["jira"]["links"] == {"blocks": "Blocks", "relates": "Relates"}


def test_discover_cli_reads_the_project(ws_config, fake_jira, capsys):
    (ws_config / "config.toml").write_text(
        f'[jira]\nsite = "{fake_jira.site}"\nemail = "dev@example.com"\nproject = "TS"\n',
        encoding="utf-8",
    )
    save_jira_token("sample-value")
    fake_jira.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes")] = (
        200,
        json.dumps({"issueTypes": TYPES, "total": 4}),
    )
    fake_jira.routes[("GET", "/rest/api/3/issueLinkType")] = (
        200,
        json.dumps({"issueLinkTypes": LINKS}),
    )
    assert main(["tracker", "discover"]) == 0
    assert capsys.readouterr().out.startswith("[jira.types]")
