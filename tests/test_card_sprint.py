"""`sprint` in a `ws card` draft: the active sprint, the next one, a named one or the backlog."""

import json

from test_card import (
    SPRINT_FIELD,
    approve,
    claude_settings,  # noqa: F401
    create_draft,
    make_draft,
    passing,
    preview,
    problems,
    world,  # noqa: F401
)
from test_jira import _client

from ws.tracker import write

SPRINTS = "/rest/agile/1.0/board/7/sprint"
ACTIVE = {
    "id": 55,
    "name": "Sprint 55",
    "state": "active",
    "startDate": "2026-10-27T15:00:00.000Z",
    "endDate": "2026-11-10T15:00:00.000Z",
}
LATER = {
    "id": 57,
    "name": "Sprint 57",
    "state": "future",
    "startDate": "2026-11-24T15:00:00.000Z",
    "endDate": "2026-12-08T15:00:00.000Z",
}
NEXT = {
    "id": 56,
    "name": "Sprint 56",
    "state": "future",
    "startDate": "2026-11-10T15:00:00.000Z",
    "endDate": "2026-11-24T15:00:00.000Z",
}
CLOSED = {"id": 54, "name": "Sprint 54", "state": "closed"}


def open_board(world, *sprints):  # noqa: F811
    """The board's open sprints; the later future sprint comes first, as order is not dates."""
    world.set_sprints(list(sprints or (ACTIVE, LATER, NEXT)))


def in_sprints(world, *entries):  # noqa: F811
    world.set_card("TS-101", fields={SPRINT_FIELD: list(entries) or None})


def edit(value, name="t.md"):
    return make_draft(name, "edit", key="TS-101", sprint=value)


def sent_fields(world):  # noqa: F811
    return world.requests_to("PUT", "/rest/api/3/issue/TS-101")[-1]["body"]["fields"]


def test_edit_moves_a_card_to_the_backlog(world, capsys):  # noqa: F811
    open_board(world)
    in_sprints(world, CLOSED, ACTIVE)
    path = edit("backlog")

    out, code = preview(path, capsys)

    assert "  Sprint: Sprint 55 -> backlog (nenhuma sprint)\n" in out
    assert approve(path, code) == 0
    assert sent_fields(world) == {SPRINT_FIELD: None}
    assert world.requests_to("GET", SPRINTS) == []


def test_edit_moves_a_card_to_the_next_sprint(world, capsys):  # noqa: F811
    open_board(world)
    in_sprints(world, CLOSED, ACTIVE)
    path = edit("next")

    out, code = preview(path, capsys)

    assert "  Sprint: Sprint 55 -> Sprint 56 (termina em 24/11)\n" in out
    assert approve(path, code) == 0
    assert sent_fields(world) == {SPRINT_FIELD: 56}
    assert world.requests_to("GET", SPRINTS)[0]["query"]["state"] == "active,future"


def test_next_without_start_dates_takes_the_lowest_id(world, capsys):  # noqa: F811
    undated = [{"id": number, "name": f"Sprint {number}", "state": "future"} for number in (60, 58)]
    open_board(world, ACTIVE, *undated)
    in_sprints(world)

    out, _ = preview(edit("next"), capsys)

    assert "  Sprint: (nenhuma) -> Sprint 58\n" in out


def test_next_prefers_a_dated_future_sprint(world, capsys):  # noqa: F811
    open_board(world, ACTIVE, {"id": 50, "name": "Sprint 50", "state": "future"}, LATER)
    in_sprints(world)

    out, _ = preview(edit("next"), capsys)

    assert "  Sprint: (nenhuma) -> Sprint 57 (termina em 08/12)\n" in out


def test_edit_moves_a_card_to_a_named_sprint(world, capsys):  # noqa: F811
    open_board(world)
    in_sprints(world, CLOSED, ACTIVE)
    path = edit("Sprint 57")

    out, code = preview(path, capsys)

    assert "  Sprint: Sprint 55 -> Sprint 57 (termina em 08/12)\n" in out
    assert approve(path, code) == 0
    assert sent_fields(world) == {SPRINT_FIELD: 57}


def test_naming_the_active_sprint_gives_the_active_line_and_its_warning(world, capsys):  # noqa: F811
    open_board(world, {**ACTIVE, "endDate": "2026-10-20T15:00:00.000Z"}, NEXT)
    in_sprints(world, CLOSED)

    out, _ = preview(edit("Sprint 55"), capsys)
    verdict = passing(edit("Sprint 55", "u.md"), capsys)

    assert "  Sprint: (nenhuma) -> Sprint 55\n" in out
    assert verdict["warnings"] == ["the sprint Sprint 55 ended on 2026-10-20 and is still active"]


def test_unknown_sprint_name_is_a_problem_naming_the_open_sprints(world, capsys):  # noqa: F811
    open_board(world)
    in_sprints(world, ACTIVE)

    found = problems(edit("Sprint 54"), capsys)

    assert found == (
        "no open sprint of the board is named 'Sprint 54'; "
        "open sprints: Sprint 55, Sprint 57, Sprint 56"
    )


def test_two_sprints_with_the_same_name_is_a_problem(world, capsys):  # noqa: F811
    open_board(world, ACTIVE, NEXT, {**LATER, "name": "Sprint 56"})
    in_sprints(world, ACTIVE)

    found = problems(edit("Sprint 56"), capsys)

    assert found == (
        "2 open sprints of the board are named 'Sprint 56'; "
        "open sprints: Sprint 55, Sprint 56, Sprint 56"
    )


def test_backlog_on_create_is_refused(world, capsys):  # noqa: F811
    found = problems(create_draft(sprint="backlog"), capsys)

    assert "a create without `sprint` already goes to the backlog" in found
    assert world.writes() == []


def test_the_document_check_refuses_backlog_on_create_and_a_blank_sprint():
    created = {
        "$schema": "card-write",
        "version": 1,
        "op": "create",
        "type": "task",
        "epic": "TS-100",
        "priority": "High",
        "title": "[FRONT] T",
    }
    edited = {"$schema": "card-write", "version": 1, "op": "edit", "key": "TS-101"}

    assert write.check_document({**created, "sprint": "backlog"}) == [
        "$.sprint: a create without `sprint` already goes to the backlog"
    ]
    assert write.check_document({**edited, "sprint": " "}) == [
        "$.sprint: expected a non-empty string"
    ]
    for value in ("active", "next", "backlog", "Sprint 56"):
        assert write.check_document({**edited, "sprint": value}) == []
    assert write.check_document({**created, "sprint": "Sprint 56"}) == []


def test_next_without_a_future_sprint_is_a_problem(world, capsys):  # noqa: F811
    open_board(world, ACTIVE)
    in_sprints(world, ACTIVE)

    assert problems(edit("next"), capsys) == 'the board has no future sprint for sprint = "next"'


def test_create_into_next_needs_due(world, capsys):  # noqa: F811
    open_board(world)
    assert 'due is required with sprint = "next"' in problems(
        create_draft(sprint="next", due=None), capsys
    )

    path = create_draft("b.md", sprint="next")
    out, code = preview(path, capsys)

    assert "  Sprint: Sprint 56 (termina em 24/11)\n" in out
    assert approve(path, code) == 0
    [created] = world.requests_to("POST", "/rest/api/3/issue")
    assert created["body"]["fields"][SPRINT_FIELD] == 56


def test_create_into_a_named_sprint_needs_due(world, capsys):  # noqa: F811
    open_board(world)

    assert 'due is required with sprint = "Sprint 57"' in problems(
        create_draft(sprint="Sprint 57", due=None), capsys
    )


def test_backlog_for_a_card_in_no_open_sprint_changes_nothing(world, capsys):  # noqa: F811
    open_board(world)
    in_sprints(world, CLOSED)
    assert problems(edit("backlog"), capsys) == "the draft changes nothing on the card"

    in_sprints(world)
    assert problems(edit("backlog"), capsys) == "the draft changes nothing on the card"


def test_a_card_already_in_the_named_sprint_changes_nothing(world, capsys):  # noqa: F811
    open_board(world)
    in_sprints(world, CLOSED, NEXT)

    assert problems(edit("next"), capsys) == "the draft changes nothing on the card"
    assert problems(edit("Sprint 56"), capsys) == "the draft changes nothing on the card"


def test_active_sprint_preview_line_is_unchanged(world, capsys):  # noqa: F811
    in_sprints(world, {"id": 50, "name": "Sprint 50"})

    edited, _ = preview(edit("active"), capsys)
    created, _ = preview(create_draft(), capsys)

    assert "  Sprint: Sprint 50 -> Sprint 55\n" in edited
    assert "  Sprint: Sprint 55 (termina em 2026-11-10)\n" in created
    queries = [request["query"] for request in world.requests_to("GET", SPRINTS)]
    assert queries == [{"state": "active"}, {"state": "active"}]


def test_open_sprints_reads_every_page_of_active_and_future_sprints(fake_jira):
    path = "/rest/agile/1.0/board/12/sprint"
    first = {"startAt": 0, "isLast": False, "values": [ACTIVE, LATER]}
    fake_jira.routes[("GET", path, "0")] = (200, json.dumps(first))
    fake_jira.routes[("GET", path, "2")] = (200, json.dumps({"isLast": True, "values": [NEXT]}))

    assert _client(fake_jira).open_sprints(12) == [ACTIVE, LATER, NEXT]

    assert [request["query"]["state"] for request in fake_jira.requests] == ["active,future"] * 2
    assert [request["query"]["startAt"] for request in fake_jira.requests] == ["0", "2"]


def test_open_sprints_tolerates_an_empty_answer(fake_jira):
    fake_jira.routes[("GET", "/rest/agile/1.0/board/1/sprint")] = (200, "")

    assert _client(fake_jira).open_sprints(1) == []
