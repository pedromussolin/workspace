import json

import pytest
from test_card import claude_settings, world  # noqa: F401

from ws.cli import main
from ws.tracker.jira.client import JiraClient


def _issue(key, summary, type_id, parent=None):
    fields = {
        "summary": summary,
        "status": {"name": "To Do", "statusCategory": {"key": "new"}},
        "issuetype": {"id": type_id},
    }
    if parent:
        fields["parent"] = {"key": parent}
    return {"key": key, "fields": fields}


@pytest.fixture
def searches(monkeypatch):
    seen: list[str] = []
    answers = {
        "assignee = currentUser() AND": [],
        "issuetype in (8, 9)": [
            _issue("TS-140", "[FRONT] Iniciativa", "9"),
            _issue("TS-142", "[BACK] Épico meu", "8", parent="TS-150"),
        ],
        "parent in (TS-140)": [_issue("TS-141", "[FRONT] Épico filho", "8", parent="TS-140")],
    }

    def search(self, jql, fields):
        seen.append(jql)
        for start, issues in answers.items():
            if jql.startswith(start) or start in jql:
                return issues
        return []

    monkeypatch.setattr(JiraClient, "search", search)
    return seen, answers


@pytest.mark.usefixtures("world")
def test_epics_lists_owned_epics_and_initiatives(capsys, searches):
    seen, answers = searches
    answers["assignee = currentUser() AND"] = [
        {"key": "TS-1", "fields": {"parent": _epic_of_open_card()}}
    ]

    assert main(["card", "epics"]) == 0

    entries = {e["key"]: e for e in json.loads(capsys.readouterr().out)["epics"]}
    assert list(entries) == ["TS-100", "TS-140", "TS-142", "TS-141"]
    assert (entries["TS-140"]["level"], entries["TS-140"]["parent"]) == (2, None)
    assert (entries["TS-141"]["level"], entries["TS-141"]["parent"]) == (1, "TS-140")
    assert (entries["TS-142"]["level"], entries["TS-142"]["parent"]) == (1, "TS-150")
    assert (entries["TS-100"]["level"], entries["TS-100"]["parent"]) == (1, None)
    assert seen[1] == (
        "issuetype in (8, 9) AND (assignee = currentUser() OR reporter = currentUser()) "
        'AND statusCategory != Done AND project = "TS"'
    )
    assert seen[2] == "parent in (TS-140) AND statusCategory != Done"


@pytest.mark.usefixtures("world")
def test_epics_do_not_duplicate_an_epic_of_an_open_card(capsys, searches):
    _, answers = searches
    answers["assignee = currentUser() AND"] = [
        {"key": "TS-1", "fields": {"parent": _epic_of_open_card("TS-141")}}
    ]

    assert main(["card", "epics"]) == 0

    keys = [e["key"] for e in json.loads(capsys.readouterr().out)["epics"]]
    assert keys.count("TS-141") == 1


@pytest.mark.usefixtures("world")
def test_epics_without_epic_and_initiative_types_keep_the_old_behavior(
    capsys,
    searches,
    ws_config,
):
    seen, answers = searches
    config = ws_config / "config.toml"
    text = config.read_text(encoding="utf-8")
    config.write_text(text.replace('epic = "8"\n', "").replace('initiative = "9"\n', ""))
    answers["assignee = currentUser() AND"] = [
        {"key": "TS-1", "fields": {"parent": _epic_of_open_card()}}
    ]

    assert main(["card", "epics"]) == 0

    keys = [e["key"] for e in json.loads(capsys.readouterr().out)["epics"]]
    assert keys == ["TS-100"]
    assert len(seen) == 1


def _epic_of_open_card(key="TS-100"):
    return {
        "key": key,
        "fields": {
            "summary": "[FRONT] Épico de exemplo",
            "status": {"name": "In Progress", "statusCategory": {"key": "indeterminate"}},
            "issuetype": {"hierarchyLevel": 1},
        },
    }
