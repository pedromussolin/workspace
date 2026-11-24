# ruff: noqa: F811
import ast
from datetime import date, datetime
from pathlib import Path

import pytest
from fake_tracker import FakeTracker, make_card
from time_helpers import (  # noqa: F401
    FLOOR,
    HOLIDAY,
    MONDAY,
    SATURDAY,
    SUNDAY,
    THURSDAY,
    TUESDAY,
    WEDNESDAY,
    activity,
    commit,
    day_of,
    git_run,
    item_text,
    mark,
    minutes,
    report,
    row,
    stamp,
    world,
    write_log,
    zone,
)

import ws
from ws import card, timereport
from ws.carddraft import parse_draft
from ws.contracts import validate
from ws.timelog import Interval
from ws.tracker.errors import TrackerError, TrackerSetup
from ws.tracker.port import Worklog

DAY = date(2026, 11, 24)


def at(clock: str, day: str = "2026-11-24") -> datetime:
    return datetime.fromisoformat(stamp(day, clock))


def span(card: str, begin: str, end: str, source: str = "marked") -> Interval:
    return Interval(card, at(begin), at(end), source)


def commit_at(*clocks: str) -> dict:
    return {"TS-1": [at(clock) for clock in clocks]}


def test_a_lone_marked_interval_is_all_its_card_minutes():
    found = timereport.split_day(DAY, [span("TS-1", "09:00", "11:00")], {})

    assert found == {"TS-1": {"marked": 120.0, "hook": 0.0}}


def test_an_overlap_is_split_by_the_commits_inside_it():
    intervals = [span("TS-1", "09:00", "11:00"), span("TS-2", "10:00", "12:00")]
    commits = {
        "TS-1": [at("10:15"), at("10:30"), at("10:45"), at("08:00")],
        "TS-2": [at("10:50"), at("11:30")],
    }

    found = timereport.split_day(DAY, intervals, commits)

    assert found["TS-1"]["marked"] == 60 + 45
    assert found["TS-2"]["marked"] == 60 + 15


def test_an_overlap_with_no_commits_is_split_equally():
    intervals = [span("TS-1", "09:00", "11:00"), span("TS-2", "10:00", "12:00")]

    found = timereport.split_day(DAY, intervals, {})

    assert found["TS-1"]["marked"] == 90
    assert found["TS-2"]["marked"] == 90


def test_an_overlap_of_three_cards_is_split_among_the_three():
    intervals = [span(ref, "09:00", "10:00") for ref in ("TS-1", "TS-2", "TS-3")]

    found = timereport.split_day(DAY, intervals, {})

    assert [found[ref]["marked"] for ref in ("TS-1", "TS-2", "TS-3")] == [20.0, 20.0, 20.0]


def test_an_interval_that_crosses_midnight_counts_in_both_days():
    crossing = Interval("TS-1", at("23:00", "2026-11-21"), at("01:00", "2026-11-22"), "marked")

    first = timereport.split_day(date(2026, 11, 21), [crossing], {})
    second = timereport.split_day(date(2026, 11, 22), [crossing], {})

    assert first["TS-1"]["marked"] == 60
    assert second["TS-1"]["marked"] == 60


def test_the_fill_goes_by_commit_share_and_closes_exactly_at_the_floor():
    rows, missing, fallback = timereport.close_day(
        {}, set(), {"TS-1": 3, "TS-2": 1}, {}, FLOOR, True
    )

    assert (rows["TS-1"]["filled"], rows["TS-2"]["filled"]) == (378, 150)
    assert missing == 0
    assert fallback is False


def test_every_card_with_commits_gets_a_step_when_the_budget_allows():
    rows, _, _ = timereport.close_day({}, set(), {"TS-1": 20, "TS-2": 1}, {}, 90, True)

    assert (rows["TS-1"]["filled"], rows["TS-2"]["filled"]) == (60, 30)


def test_a_budget_smaller_than_the_steps_goes_to_the_heaviest_cards():
    rows, _, _ = timereport.close_day({}, set(), {"TS-1": 3, "TS-2": 2, "TS-3": 1}, {}, 60, True)

    assert (rows["TS-1"]["filled"], rows["TS-2"]["filled"]) == (30, 30)
    assert rows["TS-3"]["filled"] == 0
    assert rows["TS-3"]["commits"] == 30


def test_a_day_already_at_the_floor_is_not_filled_and_a_commit_still_counts_thirty():
    base = {"TS-1": {"marked": 540.0, "hook": 0.0}}

    rows, missing, _ = timereport.close_day(base, set(), {"TS-2": 2}, {}, FLOOR, True)

    assert rows["TS-1"]["filled"] == 0
    assert rows["TS-2"] == {"marked": 0, "hook": 0, "commits": 30, "filled": 0}
    assert missing == 0


def test_the_fill_ignores_intruders_and_their_time_does_not_count_for_the_floor():
    base = {"TS-9": {"marked": 120.0, "hook": 0.0}}

    rows, _, _ = timereport.close_day(base, {"TS-9"}, {"TS-1": 1, "TS-9": 5}, {}, FLOOR, True)

    assert rows["TS-1"]["filled"] == FLOOR
    assert rows["TS-9"]["filled"] == 0


def test_without_commits_the_workspace_item_commits_fill_the_day():
    rows, _, fallback = timereport.close_day({}, set(), {}, {"TS-4": 2, "TS-5": 1}, FLOOR, True)

    assert (rows["TS-4"]["filled"], rows["TS-5"]["filled"]) == (348, 180)
    assert fallback is True


def test_without_commits_or_items_the_touched_cards_share_equally():
    base = {"TS-1": {"marked": 10.0, "hook": 0.0}, "TS-2": {"marked": 0.0, "hook": 0.0}}

    rows, missing, fallback = timereport.close_day(base, set(), {}, {}, FLOOR, True)

    assert rows["TS-1"]["filled"] + rows["TS-2"]["filled"] == FLOOR - 10
    assert missing == 0
    assert fallback is True


def test_a_day_with_nothing_leaves_the_whole_floor_as_no_evidence():
    rows, missing, _ = timereport.close_day({}, set(), {}, {}, FLOOR, True)

    assert rows == {}
    assert missing == FLOOR


def test_a_day_still_open_is_not_filled():
    rows, missing, _ = timereport.close_day({}, set(), {"TS-1": 1}, {}, FLOOR, False)

    assert rows["TS-1"] == {"marked": 0, "hook": 0, "commits": 30, "filled": 0}
    assert missing == 0


def test_the_fill_is_exact_whatever_the_weights():
    for floor in (30, 31, 59, 60, 61, 528, 600):
        for weights in ({"TS-1": 1}, {"TS-1": 1, "TS-2": 1}, {"TS-1": 7, "TS-2": 3, "TS-3": 1}):
            rows, missing, _ = timereport.close_day({}, set(), weights, {}, floor, True)
            assert sum(item["filled"] for item in rows.values()) == floor
            assert missing == 0


def test_the_report_by_commit_share_follows_the_contract(world, capsys):
    world.tracker()
    for clock in ("10:00", "11:00", "12:00"):
        commit(world.api, "feat(TS-1): passo", stamp(TUESDAY, clock))
    commit(world.api, "fix(TS-2): outro", stamp(TUESDAY, "15:00"))

    code, document, err = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert code == 0, err
    assert validate(document, "time-report") == []
    found = day_of(document, TUESDAY)
    assert minutes(document, TUESDAY) == {"TS-1": 378, "TS-2": 150}
    assert row(document, TUESDAY, "TS-1")["sources"] == {
        "marked": 0,
        "hook": 0,
        "commits": 0,
        "filled": 378,
    }
    assert (found["workday"], found["floor_minutes"], found["planned_minutes"]) == (True, 528, 528)
    assert (found["below_floor"], found["no_evidence_minutes"], found["intruder_minutes"]) == (
        False,
        0,
        0,
    )
    assert {item["ref"]: item["total_minutes"] for item in document["cards"]} == {
        "TS-1": 378,
        "TS-2": 150,
    }


def test_marked_and_hook_time_come_first_and_the_fill_goes_to_the_committer(world, capsys):
    world.tracker()
    write_log(
        mark("start", "TS-1", TUESDAY, "09:00"),
        mark("stop", "TS-1", TUESDAY, "11:00"),
        activity("TS-2", TUESDAY, "13:00"),
        activity("TS-2", TUESDAY, "13:20"),
        activity("TS-2", TUESDAY, "13:45"),
    )
    commit(world.api, "feat(TS-2): passo", stamp(TUESDAY, "14:00"))

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert row(document, TUESDAY, "TS-1")["sources"]["marked"] == 120
    assert row(document, TUESDAY, "TS-1")["minutes"] == 120
    assert row(document, TUESDAY, "TS-2")["sources"] == {
        "marked": 0,
        "hook": 75,
        "commits": 0,
        "filled": FLOOR - 195,
    }
    assert day_of(document, TUESDAY)["planned_minutes"] == FLOOR


def test_hook_time_of_a_card_inside_its_own_mark_is_not_counted_twice(world, capsys):
    world.tracker()
    write_log(
        mark("start", "TS-1", SATURDAY, "09:00"),
        mark("stop", "TS-1", SATURDAY, "11:00"),
        activity("TS-1", SATURDAY, "09:30"),
        activity("TS-1", SATURDAY, "10:00"),
        activity("TS-3", SATURDAY, "12:30"),
        activity("TS-3", SATURDAY, "13:00"),
    )

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert minutes(document, SATURDAY) == {"TS-1": 120, "TS-3": 60}
    assert row(document, SATURDAY, "TS-1")["sources"] == {
        "marked": 120,
        "hook": 0,
        "commits": 0,
        "filled": 0,
    }
    assert row(document, SATURDAY, "TS-3")["sources"]["hook"] == 60


def test_hook_time_of_the_run_ends_at_the_next_mark_of_its_own_card(world, capsys):
    world.tracker()
    write_log(
        activity("TS-1", SATURDAY, "09:50"),
        mark("start", "TS-1", SATURDAY, "10:00"),
        mark("stop", "TS-1", SATURDAY, "11:00"),
    )

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert row(document, SATURDAY, "TS-1")["sources"]["hook"] == 10
    assert minutes(document, SATURDAY) == {"TS-1": 70}


def test_a_mark_of_one_card_does_not_hide_the_hook_activity_of_another(world, capsys):
    world.tracker()
    write_log(
        mark("start", "TS-1", SATURDAY, "09:00"),
        mark("stop", "TS-1", SATURDAY, "11:00"),
        activity("TS-2", SATURDAY, "09:30"),
        activity("TS-2", SATURDAY, "10:00"),
    )

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    # TS-2's run is 09:30 to 10:30; the hour inside TS-1's mark is split equally.
    assert row(document, SATURDAY, "TS-1")["sources"] == {
        "marked": 90,
        "hook": 0,
        "commits": 0,
        "filled": 0,
    }
    assert row(document, SATURDAY, "TS-2")["sources"]["hook"] == 30
    assert day_of(document, SATURDAY)["planned_minutes"] == 120


def test_a_mark_and_hook_activity_of_two_cards_split_the_overlap_by_commits(world, capsys):
    world.tracker()
    write_log(
        mark("start", "TS-1", SATURDAY, "09:00"),
        mark("stop", "TS-1", SATURDAY, "11:00"),
        activity("TS-2", SATURDAY, "09:30"),
        activity("TS-2", SATURDAY, "10:00"),
    )
    commit(world.api, "feat(TS-2): x", stamp(SATURDAY, "10:00"))

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert row(document, SATURDAY, "TS-1")["sources"]["marked"] == 60
    assert row(document, SATURDAY, "TS-2")["sources"]["hook"] == 60


def test_two_cards_with_overlapping_hook_activity_split_the_overlap(world, capsys):
    world.tracker()
    write_log(
        activity("TS-1", SATURDAY, "10:00"),
        activity("TS-1", SATURDAY, "10:20"),
        activity("TS-2", SATURDAY, "10:10"),
        activity("TS-2", SATURDAY, "10:40"),
    )
    commit(world.api, "feat(TS-1): x", stamp(SATURDAY, "10:15"))
    commit(world.api, "feat(TS-1): y", stamp(SATURDAY, "10:25"))
    commit(world.api, "feat(TS-2): z", stamp(SATURDAY, "10:35"))

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    # TS-1 runs 10:00-10:50 and TS-2 10:10-11:10; they overlap from 10:10 to 10:50 (40 minutes),
    # where TS-1 has two commits and TS-2 one.
    assert row(document, SATURDAY, "TS-1")["sources"]["hook"] == round(10 + 40 * 2 / 3)
    assert row(document, SATURDAY, "TS-2")["sources"]["hook"] == round(20 + 40 / 3)


def test_a_gap_over_the_idle_limit_ends_the_hook_interval(world, capsys):
    world.tracker()
    write_log(
        activity("TS-1", SATURDAY, "10:00"),
        activity("TS-1", SATURDAY, "10:25"),
        activity("TS-1", SATURDAY, "11:10"),
    )

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert minutes(document, SATURDAY) == {"TS-1": 85}


def test_the_idle_limit_comes_from_the_config(world, capsys):
    world.tracker()
    world.set_time("idle_minutes = 60")
    write_log(
        activity("TS-1", SATURDAY, "10:00"),
        activity("TS-1", SATURDAY, "10:25"),
        activity("TS-1", SATURDAY, "11:10"),
    )

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert minutes(document, SATURDAY) == {"TS-1": 130}


def test_overlapping_marks_of_two_cards_split_by_commits_in_the_report(world, capsys):
    world.tracker()
    write_log(
        mark("start", "TS-1", SATURDAY, "09:00"),
        mark("start", "TS-2", SATURDAY, "10:00"),
        mark("stop", "TS-1", SATURDAY, "11:00"),
        mark("stop", "TS-2", SATURDAY, "12:00"),
    )
    for clock in ("10:15", "10:30", "10:45"):
        commit(world.api, "feat(TS-1): x", stamp(SATURDAY, clock))
    commit(world.api, "feat(TS-2): y", stamp(SATURDAY, "10:50"))

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert minutes(document, SATURDAY) == {"TS-1": 105, "TS-2": 75}


def test_a_mark_across_midnight_counts_on_each_day(world, capsys):
    world.tracker()
    write_log(
        mark("start", "TS-1", SATURDAY, "23:00"),
        mark("stop", "TS-1", SUNDAY, "01:00"),
    )

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SUNDAY)

    assert minutes(document, SATURDAY) == {"TS-1": 60}
    assert minutes(document, SUNDAY) == {"TS-1": 60}


def test_an_open_mark_of_a_past_day_ends_at_the_cards_last_activity(world, capsys):
    world.tracker()
    write_log(
        mark("start", "TS-1", SATURDAY, "14:00"),
        activity("TS-1", SATURDAY, "15:30"),
        mark("start", "TS-2", SATURDAY, "16:00"),
    )

    code, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert code == 0
    assert minutes(document, SATURDAY) == {"TS-1": 120}
    assert row(document, SATURDAY, "TS-1")["sources"]["marked"] == 90
    assert row(document, SATURDAY, "TS-1")["sources"]["hook"] == 30
    assert any("TS-2" in warning and "no stop" in warning for warning in document["warnings"])


def test_a_holiday_and_a_weekend_have_no_floor(world, capsys):
    world.tracker()
    commit(world.api, "feat(TS-1): x", stamp(HOLIDAY, "10:00"))
    commit(world.api, "feat(TS-1): y", stamp(SATURDAY, "10:00"))

    _, document, _ = report(capsys, "--from", HOLIDAY, "--to", SATURDAY)

    for day in (HOLIDAY, SATURDAY):
        found = day_of(document, day)
        assert (found["workday"], found["floor_minutes"], found["below_floor"]) == (False, 0, False)
        assert minutes(document, day) == {"TS-1": 30}
        assert row(document, day, "TS-1")["sources"]["commits"] == 30
    assert [item["date"] for item in document["days"]] == [HOLIDAY, SATURDAY]


def test_the_extra_holidays_of_the_config_have_no_floor_either(world, capsys):
    world.tracker()
    world.config.write_text(
        world.config.read_text(encoding="utf-8") + '\n[workdays]\nholidays = ["2026-11-24"]\n'
    )
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert day_of(document, TUESDAY)["workday"] is False
    assert minutes(document, TUESDAY) == {"TS-1": 30}


def test_the_floor_comes_from_the_config(world, capsys):
    world.tracker()
    world.set_time('day_floor = "6h"')
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert day_of(document, TUESDAY)["floor_minutes"] == 360
    assert minutes(document, TUESDAY) == {"TS-1": 360}


def test_an_intruder_is_counted_apart_and_never_fills_the_floor(world, capsys):
    world.tracker()
    write_log(mark("start", "TS-9", TUESDAY, "14:00"), mark("stop", "TS-9", TUESDAY, "15:00"))
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))
    commit(world.api, "fix(TS-9): y", stamp(TUESDAY, "14:30"))

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    found = day_of(document, TUESDAY)
    assert (found["planned_minutes"], found["intruder_minutes"]) == (FLOOR, 60)
    assert minutes(document, TUESDAY) == {"TS-1": FLOOR, "TS-9": 60}
    assert row(document, TUESDAY, "TS-9")["unplanned"] is True
    assert row(document, TUESDAY, "TS-1")["unplanned"] is False


def test_an_intruder_with_only_a_commit_counts_thirty_and_still_no_fill(world, capsys):
    world.tracker()
    commit(world.api, "fix(TS-9): y", stamp(TUESDAY, "14:30"))

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    found = day_of(document, TUESDAY)
    assert minutes(document, TUESDAY) == {"TS-9": 30}
    assert (found["planned_minutes"], found["intruder_minutes"]) == (0, 30)
    assert (found["below_floor"], found["no_evidence_minutes"]) == (True, FLOOR)


def test_a_day_with_no_evidence_at_all_is_listed_for_the_user(world, capsys):
    world.tracker()

    _, document, _ = report(capsys, "--from", MONDAY, "--to", MONDAY)

    found = day_of(document, MONDAY)
    assert found["cards"] == []
    assert (found["no_evidence_minutes"], found["below_floor"]) == (FLOOR, True)
    assert any("status history" in warning for warning in document["warnings"])


def test_a_day_without_commits_takes_its_cards_from_the_workspace_items(world, capsys):
    world.tracker()
    files = {"projects/demo/tasks/01-a.md": item_text("TS-4")}
    commit(world.workspace, "docs: a", stamp(WEDNESDAY, "09:00"), files=files)
    files = {"projects/demo/tasks/01-a.md": item_text("TS-4") + "mais\n"}
    commit(world.workspace, "docs: b", stamp(WEDNESDAY, "10:00"), files=files)
    files = {"projects/demo/tasks/02-b.md": item_text("TS-5")}
    commit(world.workspace, "docs: c", stamp(WEDNESDAY, "11:00"), files=files)
    files = {"projects/demo/tasks/03-c.md": item_text(None)}
    commit(world.workspace, "docs: d", stamp(WEDNESDAY, "12:00"), files=files)
    commit(world.workspace, "docs: e", stamp(WEDNESDAY, "13:00"), files={"README.md": "x\n"})

    _, document, _ = report(capsys, "--from", WEDNESDAY, "--to", WEDNESDAY)

    assert minutes(document, WEDNESDAY) == {"TS-4": 348, "TS-5": 180}
    assert row(document, WEDNESDAY, "TS-4")["sources"]["filled"] == 348


def test_workspace_commits_of_another_author_do_not_count(world, capsys):
    world.tracker()
    other = world.workspace
    commit(
        other,
        "docs: a",
        stamp(WEDNESDAY, "09:00"),
        files={"projects/d/tasks/a.md": item_text("TS-4")},
    )
    other_email = "someone@example.com"
    git_run(other, "config", "user.email", other_email)
    commit(
        other,
        "docs: b",
        stamp(WEDNESDAY, "10:00"),
        files={"projects/d/tasks/b.md": item_text("TS-5")},
    )

    _, document, _ = report(capsys, "--from", WEDNESDAY, "--to", WEDNESDAY)

    assert minutes(document, WEDNESDAY) == {"TS-5": FLOOR}


def test_a_commit_counts_for_the_card_of_its_branch_when_the_message_names_none(world, capsys):
    world.tracker()
    commit(world.api, "ajusta o filtro", stamp(TUESDAY, "10:00"), branch="feature/TS-3-filtro")

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert minutes(document, TUESDAY) == {"TS-3": FLOOR}


def test_a_commit_of_another_author_does_not_count(world, capsys):
    world.tracker()
    commit(world.api, "feat(TS-1): mine", stamp(TUESDAY, "10:00"))
    git_run(world.api, "config", "user.email", "someone@example.com")
    commit(world.api, "feat(TS-2): not mine", stamp(TUESDAY, "11:00"))
    git_run(world.api, "config", "user.email", "dev@example.com")

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert minutes(document, TUESDAY) == {"TS-1": FLOOR}


def test_refs_that_are_not_cards_of_the_project_are_left_out_with_a_note(world, capsys):
    world.tracker()
    commit(world.api, "chore(UTF-8): codificacao", stamp(TUESDAY, "10:00"))
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "11:00"))
    commit(world.api, "sem referencia", stamp(TUESDAY, "12:00"))

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert minutes(document, TUESDAY) == {"TS-1": FLOOR}
    assert any("UTF-8" in warning for warning in document["warnings"])
    assert any("name no card" in warning for warning in document["warnings"])


def test_today_is_not_filled_before_it_is_over(world, capsys):
    world.tracker()
    commit(world.api, "feat(TS-1): x", stamp("2026-11-27", "10:00"))

    _, document, _ = report(capsys, "--from", "2026-11-27", "--to", "2026-11-27")

    found = day_of(document, "2026-11-27")
    assert found["closed"] is False
    assert minutes(document, "2026-11-27") == {"TS-1": 30}
    assert (found["below_floor"], found["no_evidence_minutes"]) == (False, 0)


def test_days_after_today_are_left_out_with_a_note(world, capsys):
    world.tracker()

    _, document, _ = report(capsys, "--from", "2026-11-27", "--to", "2026-12-04")

    assert [item["date"] for item in document["days"]] == []
    assert any("after today" in warning for warning in document["warnings"])


def test_a_week_is_monday_to_sunday(world, capsys):
    world.tracker()
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))

    code, document, _ = report(capsys, "--week", "2026-W48")

    assert code == 0
    assert [item["date"] for item in document["days"]] == [
        "2026-11-23",
        "2026-11-24",
        "2026-11-25",
        "2026-11-26",
    ]
    assert {item["ref"]: item["total_minutes"] for item in document["cards"]} == {"TS-1": FLOOR}


def test_hours_the_user_already_logged_are_subtracted_per_card_and_day(world, capsys):
    world.tracker(
        worklogs={
            "TS-1": [
                Worklog(date(2026, 11, 24), 100, "acc-me"),
                Worklog(date(2026, 11, 24), 20, "acc-me"),
                Worklog(date(2026, 11, 24), 600, "acc-ana"),
                Worklog(date(2026, 11, 25), 999, "acc-me"),
            ]
        }
    )
    for clock in ("10:00", "11:00", "12:00"):
        commit(world.api, "feat(TS-1): x", stamp(TUESDAY, clock))
    commit(world.api, "fix(TS-2): y", stamp(TUESDAY, "15:00"))

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert row(document, TUESDAY, "TS-1")["logged_minutes"] == 120
    assert row(document, TUESDAY, "TS-1")["to_log_minutes"] == 258
    assert row(document, TUESDAY, "TS-2")["to_log_minutes"] == 150
    by_card = {item["ref"]: item for item in document["cards"]}
    assert (by_card["TS-1"]["total_minutes"], by_card["TS-1"]["logged_minutes"]) == (378, 120)
    assert by_card["TS-1"]["to_log_minutes"] == 258


def test_more_logged_than_worked_leaves_nothing_to_log(world, capsys):
    world.tracker(worklogs={"TS-1": [Worklog(date(2026, 11, 24), 1000, "acc-me")]})
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert row(document, TUESDAY, "TS-1")["to_log_minutes"] == 0


def test_a_tracker_without_worklog_reads_says_nothing_was_subtracted(world, capsys):
    world.tracker(capabilities=())
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))

    _, document, _ = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert any("nothing was subtracted" in warning for warning in document["warnings"])


def test_the_report_never_writes_to_the_tracker(world, capsys):
    fake = world.tracker()
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))

    report(capsys, "--from", TUESDAY, "--to", TUESDAY)
    report(capsys, "--card", "TS-1", "--drafts", str(world.drafts / "t"))

    assert fake.sent == []
    assert fake.records == {}


def ast_names(source: str) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.split(".")[-1])
    return names


WRITE_PATHS = {"open_writer", "apply", "send", "plan", "Writer", "apply_steps"}


def test_the_scan_for_write_paths_flags_a_module_that_reaches_the_writer():
    broken = "from ws.tracker import port\nwriter = port.open_writer([])\nwriter.send(call)\n"

    assert ast_names(broken) & WRITE_PATHS == {"open_writer", "send"}
    assert ast_names("from ws.tracker import port\nport.open_tracker()\n") & WRITE_PATHS == set()


@pytest.mark.parametrize("name", ["timereport.py", "timelog.py", "time_cli.py"])
def test_the_time_modules_never_reach_a_write_path_of_the_tracker(name):
    source = (Path(ws.__file__).parent / name).read_text(encoding="utf-8")

    assert ast_names(source) & WRITE_PATHS == set()


def drafts_folder(world, name="time-ts-1"):
    return world.drafts / name


def three_days(world):
    for clock in ("10:00", "11:00", "12:00"):
        commit(world.api, "feat(TS-1): x", stamp(TUESDAY, clock))
    commit(world.api, "fix(TS-2): y", stamp(TUESDAY, "15:00"))
    commit(world.api, "feat(TS-1): z", stamp(THURSDAY, "10:00"))


def test_card_mode_covers_the_days_the_card_was_worked_and_lists_only_that_card(world, capsys):
    world.tracker()
    three_days(world)

    code, document, _ = report(capsys, "--card", "TS-1")

    assert code == 0
    assert [item["date"] for item in document["days"]] == [TUESDAY, WEDNESDAY, THURSDAY]
    assert minutes(document, TUESDAY) == {"TS-1": 378}
    assert minutes(document, WEDNESDAY) == {}
    assert minutes(document, THURSDAY) == {"TS-1": FLOOR}
    assert day_of(document, TUESDAY)["planned_minutes"] == FLOOR
    assert [item["ref"] for item in document["cards"]] == ["TS-1"]
    assert document["cards"][0]["total_minutes"] == 378 + FLOOR


def test_drafts_hold_one_worklog_per_day_with_the_time_to_log(world, capsys):
    world.tracker(worklogs={"TS-1": [Worklog(date(2026, 11, 24), 120, "acc-me")]})
    three_days(world)
    folder = drafts_folder(world)

    code, document, err = report(capsys, "--card", "TS-1", "--drafts", str(folder))

    assert code == 0, err
    assert document["drafts"] == {
        "folder": str(folder),
        "count": 2,
        "files": ["TS-1-worklog-2026-11-24.md", "TS-1-worklog-2026-11-26.md"],
    }
    assert validate(document, "time-report") == []
    first = parse_draft((folder / "TS-1-worklog-2026-11-24.md").read_bytes())
    second = parse_draft((folder / "TS-1-worklog-2026-11-26.md").read_bytes())
    assert (first.op, first.values["key"], first.values["time"]) == ("worklog", "TS-1", "4h 18m")
    assert first.values["day"] == date(2026, 11, 24)
    assert (second.values["time"], second.values["day"]) == ("8h 48m", date(2026, 11, 26))
    assert sorted(path.name for path in folder.iterdir()) == document["drafts"]["files"]
    assert [card.load(path).problems for path in sorted(folder.iterdir())] == [[], []]
    assert (folder / "TS-1-worklog-2026-11-24.md").stat().st_mode & 0o777 == 0o600


def test_a_day_fully_logged_gets_no_draft(world, capsys):
    world.tracker(worklogs={"TS-1": [Worklog(date(2026, 11, 24), 378, "acc-me")]})
    three_days(world)
    folder = drafts_folder(world)

    _, document, _ = report(capsys, "--card", "TS-1", "--drafts", str(folder))

    assert document["drafts"]["files"] == ["TS-1-worklog-2026-11-26.md"]


def test_a_planned_card_gets_no_estimate_draft_unless_asked(world, capsys):
    world.tracker()
    three_days(world)
    plain = drafts_folder(world, "plain")
    asked = drafts_folder(world, "asked")

    _, unflagged, _ = report(capsys, "--card", "TS-1", "--drafts", str(plain))
    assert unflagged["cards"][0]["unplanned"] is False
    _, document, _ = report(capsys, "--card", "TS-1", "--drafts", str(asked), "--unplanned")

    assert not (plain / "TS-1-estimate.md").exists()
    estimate = parse_draft((asked / "TS-1-estimate.md").read_bytes())
    assert (estimate.op, estimate.values["key"], estimate.values["estimate"]) == (
        "edit",
        "TS-1",
        "15h 6m",
    )
    assert "TS-1-estimate.md" in document["drafts"]["files"]
    assert document["cards"][0]["unplanned"] is True
    assert {r["unplanned"] for day in document["days"] for r in day["cards"]} == {True}
    assert card.load(asked / "TS-1-estimate.md").problems == []


def test_a_card_with_an_unplanned_label_gets_the_estimate_draft_by_itself(world, capsys):
    world.tracker()
    write_log(mark("start", "TS-9", TUESDAY, "14:00"), mark("stop", "TS-9", TUESDAY, "14:50"))
    folder = drafts_folder(world, "intruder")

    code, document, _ = report(capsys, "--card", "TS-9", "--drafts", str(folder))

    assert code == 0
    assert document["cards"][0]["unplanned"] is True
    estimate = parse_draft((folder / "TS-9-estimate.md").read_bytes())
    assert estimate.values["estimate"] == "50m"
    worklog = parse_draft((folder / "TS-9-worklog-2026-11-24.md").read_bytes())
    assert worklog.values["time"] == "50m"


def test_drafts_go_into_a_folder_that_already_holds_other_drafts(world, capsys):
    world.tracker()
    three_days(world)
    folder = drafts_folder(world)
    folder.mkdir(parents=True)
    (folder / "TS-1-move.md").write_text("+++\nop = 'move'\n+++\n", encoding="utf-8")

    code, document, err = report(capsys, "--card", "TS-1", "--drafts", str(folder))

    assert code == 0, err
    assert document["drafts"]["files"] == [
        "TS-1-worklog-2026-11-24.md",
        "TS-1-worklog-2026-11-26.md",
    ]
    assert sorted(path.name for path in folder.iterdir()) == [
        "TS-1-move.md",
        "TS-1-worklog-2026-11-24.md",
        "TS-1-worklog-2026-11-26.md",
    ]
    assert (folder / "TS-1-move.md").read_text(encoding="utf-8") == "+++\nop = 'move'\n+++\n"


def test_drafts_refuse_a_name_clash_listing_the_names_and_overwrite_nothing(world, capsys):
    world.tracker()
    three_days(world)
    folder = drafts_folder(world)
    folder.mkdir(parents=True)
    (folder / "TS-1-worklog-2026-11-24.md").write_text("mine", encoding="utf-8")
    (folder / "TS-1-worklog-2026-11-26.md").write_text("mine too", encoding="utf-8")

    code, document, err = report(capsys, "--card", "TS-1", "--drafts", str(folder))

    assert (code, document) == (1, None)
    assert "TS-1-worklog-2026-11-24.md, TS-1-worklog-2026-11-26.md" in err
    assert sorted(path.read_text(encoding="utf-8") for path in folder.iterdir()) == [
        "mine",
        "mine too",
    ]


def test_a_clash_on_one_name_writes_none_of_the_other_drafts(world, capsys):
    world.tracker()
    three_days(world)
    folder = drafts_folder(world)
    folder.mkdir(parents=True)
    (folder / "TS-1-worklog-2026-11-26.md").write_text("mine", encoding="utf-8")

    code, _, _ = report(capsys, "--card", "TS-1", "--drafts", str(folder))

    assert code == 1
    assert [path.name for path in folder.iterdir()] == ["TS-1-worklog-2026-11-26.md"]


def test_drafts_refuse_a_folder_outside_the_drafts_area(world, capsys, tmp_path):
    world.tracker()
    three_days(world)

    code, _, err = report(capsys, "--card", "TS-1", "--drafts", str(tmp_path / "elsewhere"))

    assert code == 1
    assert "is not a folder inside" in err
    assert not (tmp_path / "elsewhere").exists()


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--card", "TS-1", "--week", "2026-W48"],
        ["--card", "TS-1", "--from", "2026-11-24"],
        ["--from", "2026-11-24"],
        ["--to", "2026-11-24"],
        ["--from", "2026-11-25", "--to", "2026-11-24"],
        ["--from", "24/11", "--to", "2026-11-24"],
        ["--week", "2026-48"],
        ["--week", "2026-W60"],
        ["--card", "ts-1"],
        ["--from", "2026-11-24", "--to", "2026-11-24", "--drafts", "x"],
        ["--from", "2026-11-24", "--to", "2026-11-24", "--unplanned"],
    ],
)
def test_bad_arguments_are_a_rule_failure_and_touch_nothing(world, capsys, argv):
    fake = world.tracker()

    code, document, err = report(capsys, *argv)

    assert (code, document) == (1, None)
    assert err.startswith("ws time report:")
    assert fake.reads == []


def test_a_card_that_is_not_in_the_project_is_refused(world, capsys):
    world.tracker()

    code, _, err = report(capsys, "--card", "TS-404")

    assert code == 1
    assert "not in the configured project" in err


def test_a_card_with_no_evidence_is_refused(world, capsys):
    world.tracker()

    code, _, err = report(capsys, "--card", "TS-1")

    assert code == 1
    assert "no evidence" in err


def test_a_card_with_no_start_or_creation_date_needs_a_period(world, capsys):
    world.tracker([make_card("TS-1")])

    code, _, err = report(capsys, "--card", "TS-1")

    assert code == 1
    assert "--from and --to" in err


def test_the_creation_date_stands_in_for_a_missing_start(world, capsys):
    world.tracker([make_card("TS-1", created=date(2026, 11, 24))])
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))

    code, document, _ = report(capsys, "--card", "TS-1")

    assert code == 0
    assert minutes(document, TUESDAY) == {"TS-1": FLOOR}


def test_a_missing_config_is_a_setup_problem(world, capsys):
    world.config.unlink()

    code, _, err = report(capsys, "--week", "2026-W48")

    assert code == 2
    assert "config.toml" in err


def test_a_bad_time_table_is_a_setup_problem(world, capsys):
    world.tracker()
    world.set_time('day_floor = "soon"')

    code, _, err = report(capsys, "--week", "2026-W48")

    assert code == 2
    assert "time.day_floor" in err


def test_a_tracker_that_cannot_be_set_up_is_exit_two(world, capsys, monkeypatch):
    def refuse():
        raise TrackerSetup("tracker token is missing")

    monkeypatch.setattr("ws.tracker.port.open_tracker", refuse)

    code, _, err = report(capsys, "--week", "2026-W48")

    assert code == 2
    assert "token" in err


def test_a_tracker_that_fails_is_exit_three(world, capsys, monkeypatch):
    class Down(FakeTracker):
        def card(self, ref):
            raise TrackerError("tracker is unreachable")

    fake = Down([make_card("TS-1")])
    monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: fake)
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))

    code, document, err = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert (code, document) == (3, None)
    assert "unreachable" in err


def test_a_worklog_read_that_fails_is_exit_three(world, capsys, monkeypatch):
    class NoWorklogs(FakeTracker):
        def worklogs(self, ref):
            raise TrackerError("worklog read refused")

    fake = NoWorklogs([make_card("TS-1")])
    monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: fake)
    commit(world.api, "feat(TS-1): x", stamp(TUESDAY, "10:00"))

    code, _, err = report(capsys, "--from", TUESDAY, "--to", TUESDAY)

    assert code == 3
    assert "refused" in err


def test_an_unreadable_line_of_the_log_is_skipped_with_a_note(world, capsys):
    world.tracker()
    write_log(
        "not json",
        '{"v": 2, "event": "activity"}',
        activity("TS-1", SATURDAY, "10:00"),
        activity("TS-1", SATURDAY, "10:10"),
    )

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert minutes(document, SATURDAY) == {"TS-1": 40}
    assert any("2 unreadable" in warning for warning in document["warnings"])


def test_activity_outside_a_card_branch_is_not_counted(world, capsys):
    world.tracker()
    write_log(activity(None, SATURDAY, "10:00"), activity(None, SATURDAY, "10:10"))

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert document["days"] == []
    assert document["warnings"] == []


def test_a_company_policy_that_lists_no_unplanned_label_makes_every_card_planned(world, capsys):
    world.tracker()
    (Path(world.config.parent) / "card-policies" / "acme-like.toml").write_text(
        "version = 1\n", encoding="utf-8"
    )
    write_log(mark("start", "TS-9", SATURDAY, "10:00"), mark("stop", "TS-9", SATURDAY, "11:00"))

    _, document, _ = report(capsys, "--from", SATURDAY, "--to", SATURDAY)

    assert row(document, SATURDAY, "TS-9")["unplanned"] is False
    assert day_of(document, SATURDAY)["planned_minutes"] == 60
