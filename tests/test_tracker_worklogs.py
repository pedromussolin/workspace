# ruff: noqa: F811
import json
from datetime import date

import pytest
from test_card import (
    claude_settings,  # noqa: F401
    world,  # noqa: F401
)

from ws.tracker.errors import TrackerError
from ws.tracker.port import Worklog, open_tracker

PATH = "/rest/api/3/issue/TS-101/worklog"


def page(items, total=None):
    return (200, json.dumps({"worklogs": items, "total": len(items) if total is None else total}))


def entry(day, seconds, account):
    return {
        "started": f"{day}T09:00:00.000-0300",
        "timeSpentSeconds": seconds,
        "author": {"accountId": account},
    }


def test_the_jira_adapter_reads_every_worklog_as_day_minutes_and_author(world):
    world.fake.routes[("GET", PATH)] = page(
        [entry("2026-11-24", 7200, "acc-me"), entry("2026-11-25", 1800, "acc-ana")]
    )

    found = open_tracker().worklogs("TS-101")

    assert found == [
        Worklog(date(2026, 11, 24), 120, "acc-me"),
        Worklog(date(2026, 11, 25), 30, "acc-ana"),
    ]


def test_the_jira_adapter_reads_every_page_of_worklogs(world):
    world.fake.routes[("GET", PATH, "0")] = page([entry("2026-11-24", 60, "acc-me")] * 100, 101)
    world.fake.routes[("GET", PATH, "100")] = page([entry("2026-11-25", 120, "acc-me")], 101)

    found = open_tracker().worklogs("TS-101")

    assert len(found) == 101
    assert found[-1] == Worklog(date(2026, 11, 25), 2, "acc-me")


def test_a_card_that_is_absent_has_no_worklogs(world):
    world.fake.routes[("GET", "/rest/api/3/issue/TS-404/worklog")] = (404, "{}")

    assert open_tracker().worklogs("TS-404") == []


def test_a_worklog_read_that_fails_is_a_tracker_error(world):
    world.fake.routes[("GET", PATH)] = (500, "{}")

    with pytest.raises(TrackerError):
        open_tracker().worklogs("TS-101")


def test_an_unexpected_worklog_shape_is_a_tracker_error(world):
    world.fake.routes[("GET", PATH)] = page([{"started": 1}])

    with pytest.raises(TrackerError, match="unexpected worklog"):
        open_tracker().worklogs("TS-101")
