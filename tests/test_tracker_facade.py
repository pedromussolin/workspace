import json
from dataclasses import replace
from datetime import date

import pytest
from test_card import claude_settings, world  # noqa: F401
from test_jira import CARD, REST_ISSUE

from ws import tracker
from ws.taskmodel import Status
from ws.tracker.errors import TrackerSetup
from ws.userconfig import JiraConfig, StandupConfig, UserConfig


def _config(kind="jira", overrides=None):
    return UserConfig(
        jira=JiraConfig(
            site="https://example.atlassian.net",
            email="dev@example.com",
            status_overrides=overrides or {},
        ),
        standup=StandupConfig(repo_roots=()),
        identity_email="dev@example.com",
        tracker_kind=kind,
    )


def test_facade_dispatches_list_tasks(world):  # noqa: F811
    world.fake.pages = {None: {"issues": [REST_ISSUE], "isLast": True}}

    listing = tracker.list_tasks(date(2026, 10, 23), "mine")

    assert listing == {"platform": "jira", "role": "mine", "cards": [CARD]}

    world.fake.routes[("GET", "/rest/api/3/user/search")] = (
        200,
        json.dumps([{"accountId": "acc-other"}]),
    )
    assert tracker.account_for("someone@example.com") == "acc-other"


def test_facade_task_from_listing_is_offline():
    config = _config(overrides={"In Validation": "validation"})
    card = {**CARD, "status_name": "In Validation"}

    task = tracker.task_from_listing(card, config)

    assert task.key == CARD["key"]
    assert task.status == Status.VALIDATION
    assert tracker.status_overrides(config) == {"In Validation": "validation"}


def test_facade_unknown_kind_is_a_setup_problem():
    config = replace(_config(), tracker_kind="monday")

    with pytest.raises(TrackerSetup, match="monday"):
        tracker.task_from_listing(CARD, config)
    with pytest.raises(TrackerSetup, match="monday"):
        tracker.status_overrides(config)
