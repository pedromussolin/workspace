import json
from datetime import date

import pytest
from test_card import claude_settings, world  # noqa: F401
from test_jira import CARD, REST_ISSUE

import ws.tracker.jira
import ws.tracker.jira.adapter
import ws.tracker.jira_adapter
from ws.taskmodel import Status
from ws.tracker.errors import TrackerError
from ws.tracker.jira import JIRA_CAPABILITIES, open_tracker, task_from_listing
from ws.tracker.jira.adapter import JiraTracker
from ws.tracker.jira.client import JiraError, tasks_jql
from ws.userconfig import JiraConfig, load_config


def test_jira_error_is_a_tracker_error():
    error = JiraError("boom", status=503, uncertain=True)

    assert isinstance(error, TrackerError)
    assert (str(error), error.status, error.uncertain) == ("boom", 503, True)
    assert JiraError("plain").status is None
    assert JiraError("plain").uncertain is False


def test_open_tracker_returns_a_jira_tracker(world):  # noqa: F811
    tracker = open_tracker(load_config())

    assert isinstance(tracker, JiraTracker)
    assert tracker.kind == "jira"
    assert "worklog" in JIRA_CAPABILITIES


def test_list_tasks_is_the_task_list_json(world):  # noqa: F811
    world.fake.pages = {None: {"issues": [REST_ISSUE], "isLast": True}}

    listing = open_tracker(load_config()).list_tasks(date(2026, 10, 23), "mine")

    assert listing == {"platform": "jira", "role": "mine", "cards": [CARD]}
    assert world.fake.requests[-1]["query"]["jql"] == tasks_jql(date(2026, 10, 23), "mine")


def test_list_tasks_failure_is_a_tracker_error(world):  # noqa: F811
    world.fake.status = 500

    with pytest.raises(TrackerError):
        open_tracker(load_config()).list_tasks(date(2026, 10, 23), "mine")


def test_discover_toml_through_the_adapter(world):  # noqa: F811
    world.fake.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes")] = (
        200,
        json.dumps({"issueTypes": [{"id": "10002", "name": "Tarefa"}], "isLast": True}),
    )
    world.fake.routes[("GET", "/rest/api/3/issueLinkType")] = (
        200,
        json.dumps({"issueLinkTypes": [{"name": "Blocks"}]}),
    )

    text = open_tracker(load_config()).discover_toml()

    assert 'task = "10002"' in text
    assert 'blocks = "Blocks"' in text


def test_account_for_an_email(world):  # noqa: F811
    route = ("GET", "/rest/api/3/user/search")
    tracker = open_tracker(load_config())

    world.fake.routes[route] = (200, json.dumps([{"accountId": "acc-other"}]))
    assert tracker.account_for(" someone@example.com ") == "acc-other"
    assert world.fake.requests[-1]["query"] == {"query": "someone@example.com"}

    world.fake.routes[route] = (200, json.dumps([]))
    assert tracker.account_for("someone@example.com") is None

    world.fake.routes[route] = (
        200,
        json.dumps([{"accountId": "acc-me"}, {"accountId": "acc-other"}]),
    )
    assert tracker.account_for("someone@example.com") is None


def test_task_from_listing_needs_no_session():
    settings = JiraConfig(
        site="https://example.atlassian.net",
        email="me@example.com",
        status_overrides={"In Validation": "done"},
    )

    task = task_from_listing(CARD, settings)

    assert task.ref == "jira:TS-101"
    assert task.url == "https://example.atlassian.net/browse/TS-101"
    assert task.status is Status.DONE


def test_old_jira_adapter_path_is_the_adapter():
    assert ws.tracker.jira_adapter is ws.tracker.jira.adapter
