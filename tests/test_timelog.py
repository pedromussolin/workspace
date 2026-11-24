# ruff: noqa: F811
import json
from datetime import datetime

import pytest
from time_helpers import (  # noqa: F401
    NOW,
    SATURDAY,
    activity,
    mark,
    run,
    world,
    write_log,
    zone,
)

from ws import timelog
from ws.config import data_dir

TODAY = "2026-11-27"


def lines():
    path = data_dir() / "timelog" / "2026-11.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def time_cmd(capsys, *argv):
    return run(capsys, "time", *argv)


def test_start_writes_a_private_event_line(world, capsys):
    code, document, _ = time_cmd(capsys, "start", "TS-1")

    assert code == 0
    assert document == {
        "version": 1,
        "action": "started",
        "card": "TS-1",
        "at": NOW.isoformat(),
    }
    assert lines() == [
        {"v": 1, "event": "start", "card": "TS-1", "at": NOW.isoformat(), "source": "manual"}
    ]
    folder = data_dir() / "timelog"
    assert folder.stat().st_mode & 0o777 == 0o700
    assert (folder / "2026-11.jsonl").stat().st_mode & 0o777 == 0o600


def test_start_at_a_clock_time_is_today_at_that_local_time(world, capsys):
    code, document, _ = time_cmd(capsys, "start", "TS-1", "--at", "09:30")

    assert code == 0
    assert document["at"] == f"{TODAY}T09:30:00-03:00"
    assert lines()[0]["at"] == f"{TODAY}T09:30:00-03:00"


def test_the_file_is_the_month_of_the_event_and_keeps_its_mode_when_it_exists(world, capsys):
    path = write_log(activity("TS-2", SATURDAY, "10:00"))
    path.chmod(0o644)

    time_cmd(capsys, "start", "TS-1")

    assert path.stat().st_mode & 0o777 == 0o600
    assert len(lines()) == 2


def test_starting_a_card_already_open_changes_nothing(world, capsys):
    time_cmd(capsys, "start", "TS-1", "--at", "09:00")

    code, document, _ = time_cmd(capsys, "start", "TS-1", "--at", "10:00")

    assert code == 0
    assert document["action"] == "none"
    assert "already open" in document["notes"][0]
    assert len(lines()) == 1


def test_several_cards_can_be_open_at_once(world, capsys):
    time_cmd(capsys, "start", "TS-1", "--at", "09:00")
    time_cmd(capsys, "start", "TS-2", "--at", "09:30")

    _, document, _ = time_cmd(capsys, "status")

    assert [item["card"] for item in document["open"]] == ["TS-1", "TS-2"]


def test_stop_closes_the_card_with_its_minutes(world, capsys):
    time_cmd(capsys, "start", "TS-1", "--at", "09:00")

    code, document, _ = time_cmd(capsys, "stop", "TS-1", "--at", "10:30")

    assert code == 0
    assert document["action"] == "stopped"
    assert document["stopped"] == [
        {"card": "TS-1", "start": f"{TODAY}T09:00:00-03:00", "minutes": 90}
    ]
    assert [item["event"] for item in lines()] == ["start", "stop"]


def test_stop_without_a_ref_closes_every_open_card(world, capsys):
    time_cmd(capsys, "start", "TS-1", "--at", "09:00")
    time_cmd(capsys, "start", "TS-2", "--at", "09:30")

    _, document, _ = time_cmd(capsys, "stop", "--at", "10:00")

    assert [item["card"] for item in document["stopped"]] == ["TS-1", "TS-2"]
    _, status, _ = time_cmd(capsys, "status")
    assert status["open"] == []


def test_a_stop_before_its_start_is_refused_and_writes_nothing(world, capsys):
    time_cmd(capsys, "start", "TS-1", "--at", "10:00")
    time_cmd(capsys, "start", "TS-2", "--at", "08:00")

    code, document, err = time_cmd(capsys, "stop", "--at", "09:00")

    assert (code, document) == (1, None)
    assert "before its start" in err
    assert [item["event"] for item in lines()] == ["start", "start"]


def test_stopping_a_card_that_is_not_open_is_a_note_not_a_failure(world, capsys):
    code, document, _ = time_cmd(capsys, "stop", "TS-1")

    assert code == 0
    assert document["action"] == "none"
    assert document["notes"] == ["TS-1 is not open"]
    assert not (data_dir() / "timelog").exists()


def test_stopping_with_nothing_open_is_a_note(world, capsys):
    code, document, _ = time_cmd(capsys, "stop")

    assert code == 0
    assert document["notes"] == ["no interval is open"]


@pytest.mark.parametrize("clock", ["18:01", "23:59"])
def test_a_time_in_the_future_is_refused(world, capsys, clock):
    code, _, err = time_cmd(capsys, "start", "TS-1", "--at", clock)

    assert code == 1
    assert "future" in err
    assert not (data_dir() / "timelog").exists()


@pytest.mark.parametrize("clock", ["9", "25:00", "09:60", "nine", ""])
def test_a_malformed_time_is_refused(world, capsys, clock):
    code, _, err = time_cmd(capsys, "start", "TS-1", "--at", clock)

    assert code == 1
    assert "HH:MM" in err


@pytest.mark.parametrize("ref", ["ts-1", "1", "TS-", "TS 1"])
def test_a_bad_card_ref_is_refused(world, capsys, ref):
    code, _, err = time_cmd(capsys, "start", ref)

    assert code == 1
    assert "card ref" in err


def test_status_gives_todays_minutes_per_card_and_the_open_ones(world, capsys):
    write_log(
        mark("start", "TS-1", TODAY, "09:00"),
        mark("stop", "TS-1", TODAY, "10:00"),
        mark("start", "TS-2", TODAY, "16:00"),
        activity("TS-3", TODAY, "11:00"),
        activity("TS-3", TODAY, "11:20"),
        activity("TS-5", TODAY, "17:50"),
        mark("start", "TS-4", "2026-11-26", "09:00"),
        mark("stop", "TS-4", "2026-11-26", "10:00"),
    )

    code, document, _ = time_cmd(capsys, "status")

    assert code == 0
    assert document["date"] == TODAY
    assert document["open"] == [{"card": "TS-2", "since": f"{TODAY}T16:00:00-03:00"}]
    assert document["today"] == [
        {"card": "TS-1", "minutes": 60, "marked": 60, "hook": 0},
        {"card": "TS-2", "minutes": 120, "marked": 120, "hook": 0},
        {"card": "TS-3", "minutes": 50, "marked": 0, "hook": 50},
        {"card": "TS-5", "minutes": 10, "marked": 0, "hook": 10},
    ]


def test_status_works_without_a_config_and_reads_the_idle_limit_from_it(world, capsys):
    world.config.unlink()

    code, document, _ = time_cmd(capsys, "status")

    assert code == 0
    assert document["open"] == [] and document["today"] == []


def test_status_with_a_bad_time_table_is_a_setup_problem(world, capsys):
    world.set_time("idle_minutes = 0")

    code, _, err = time_cmd(capsys, "status")

    assert code == 2
    assert "time.idle_minutes" in err


def test_the_reader_accepts_what_the_hook_writes(world):
    write_log(
        {
            "v": 1,
            "event": "activity",
            "card": "TS-1",
            "at": "2026-11-24T15:12:09-03:00",
            "source": "hook",
            "repo": "acme-api",
            "branch": "feature/TS-1-x",
        },
        {
            "v": 1,
            "event": "activity",
            "card": None,
            "at": "2026-11-24T15:13:09-03:00",
            "source": "hook",
            "repo": "acme-api",
            "branch": "main",
        },
    )

    events, skipped = timelog.read(datetime(2026, 11, 24).date(), datetime(2026, 11, 24).date())

    assert skipped == 0
    assert [(item.card, item.repo, item.branch) for item in events] == [
        ("TS-1", "acme-api", "feature/TS-1-x"),
        (None, "acme-api", "main"),
    ]


@pytest.mark.parametrize(
    "line",
    [
        "not json",
        "[]",
        '{"v": 2, "event": "start", "card": "TS-1", "at": "2026-11-24T10:00:00-03:00"}',
        '{"v": 1, "event": "pause", "card": "TS-1", "at": "2026-11-24T10:00:00-03:00"}',
        '{"v": 1, "event": "start", "card": null, "at": "2026-11-24T10:00:00-03:00"}',
        '{"v": 1, "event": "start", "card": "x", "at": "2026-11-24T10:00:00-03:00"}',
        '{"v": 1, "event": "start", "card": "TS-1", "at": "yesterday"}',
        '{"v": 1, "event": "start", "card": "TS-1", "at": "2026-11-24T10:00:00-03:00", "repo": 5}',
    ],
)
def test_the_reader_skips_a_line_it_cannot_use(world, line):
    write_log(line, activity("TS-1", "2026-11-24", "10:00"))

    events, skipped = timelog.read(datetime(2026, 11, 24).date(), datetime(2026, 11, 24).date())

    assert (len(events), skipped) == (1, 1)


def test_the_scan_for_unusable_lines_counts_a_broken_sample():
    # The reader's own check, run on a sample that breaks it, must flag it.
    assert timelog._event({"v": 1, "event": "start", "card": "nope", "at": "x"}) is None
    assert timelog._event(json.loads(json.dumps(activity("TS-1", TODAY, "10:00")))) is not None


def test_the_reader_looks_a_month_back_for_an_interval_opened_earlier(world):
    write_log(mark("start", "TS-1", "2026-10-30", "23:00"), month="2026-10")
    write_log(mark("stop", "TS-1", "2026-11-02", "01:00"))

    events, _ = timelog.read(datetime(2026, 11, 2).date(), datetime(2026, 11, 2).date())
    closed, opened = timelog.replay(events)

    assert opened == {}
    assert [(item.card, item.minutes) for item in closed] == [("TS-1", 50 * 60)]


def test_events_out_of_order_are_replayed_by_time(world):
    write_log(
        mark("stop", "TS-1", TODAY, "11:00"),
        mark("start", "TS-1", TODAY, "09:00"),
    )

    events, _ = timelog.read(datetime(2026, 11, 27).date(), datetime(2026, 11, 27).date())

    assert [item.minutes for item in timelog.replay(events)[0]] == [120]


def test_an_open_mark_of_today_runs_to_now(world, capsys):
    write_log(mark("start", "TS-1", TODAY, "16:00"))

    _, document, _ = time_cmd(capsys, "status")

    assert document["today"] == [{"card": "TS-1", "minutes": 120, "marked": 120, "hook": 0}]


def test_the_reader_accepts_null_fields_and_a_session_and_counts_no_card_time_for_them(world):
    write_log(
        {
            "v": 1,
            "event": "activity",
            "card": None,
            "at": "2026-11-24T15:12:09-03:00",
            "source": "hook",
            "repo": None,
            "branch": None,
            "session": None,
        },
        {
            "v": 1,
            "event": "activity",
            "card": "TS-1",
            "at": "2026-11-24T15:13:09-03:00",
            "source": "hook",
            "repo": None,
            "branch": None,
            "session": "abc-123",
        },
    )
    day = datetime(2026, 11, 24).date()

    events, skipped = timelog.read(day, day)

    assert (len(events), skipped) == (2, 0)
    found = timelog.hook_intervals(events, 30, NOW)
    assert [item.card for item in found] == ["TS-1"]
    assert [item.minutes for item in found] == [30]


def test_the_log_folder_follows_the_data_dir_override(world, tmp_path, monkeypatch):
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path / "elsewhere"))

    assert timelog.timelog_dir() == tmp_path / "elsewhere" / "timelog"
