import json

from test_card import (
    SPRINT_FIELD,
    _fields,
    approve,
    claude_settings,  # noqa: F401
    make_draft,
    passing,
    pending_files,
    preview,
    problems,
    world,  # noqa: F401
)

from ws.identity import dev_id

TASK = {"id": "3", "name": "Tarefa", "hierarchyLevel": 0}
EPIC = {"id": "8", "name": "Epic", "hierarchyLevel": 1}


def set_editmeta(world, key, allowed=("6",), parent=True):  # noqa: F811
    fields = {"issuetype": {"allowedValues": [{"id": item, "name": "x"} for item in allowed]}}
    if parent:
        fields["parent"] = {"required": False}
    world.fake.routes[("GET", f"/rest/api/3/issue/{key}/editmeta")] = (
        200,
        json.dumps({"fields": fields}),
    )


def test_edit_type_sends_the_id_and_shows_labels(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype=TASK)
    set_editmeta(world, "TS-101")
    path = make_draft("t.md", "edit", key="TS-101", type="improvement")

    out, code = preview(path, capsys)
    assert "Tipo: Tarefa -> Melhoria" in out
    assert approve(path, code) == 0
    body = world.requests_to("PUT", "/rest/api/3/issue/TS-101")[-1]["body"]
    assert body["fields"]["issuetype"] == {"id": "6"}


def test_edit_type_not_allowed_by_the_screen_is_refused(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype=TASK)
    set_editmeta(world, "TS-101", allowed=("4",))
    path = make_draft("t.md", "edit", key="TS-101", type="improvement")

    assert (
        "the card's edit screen does not allow type improvement: change it with the "
        "tracker's move, by hand" in problems(path, capsys)
    )


def test_edit_same_type_changes_nothing(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype={"id": "6", "name": "Melhoria", "hierarchyLevel": 0})
    set_editmeta(world, "TS-101")
    path = make_draft("t.md", "edit", key="TS-101", type="improvement")

    assert "the draft changes nothing on the card" in problems(path, capsys)


def test_edit_assignee_and_reporter(world, capsys):  # noqa: F811
    world.set_card(
        "TS-101",
        reporter={"accountId": "acc-other", "displayName": "Outro Dev"},
    )
    path = make_draft(
        "t.md", "edit", key="TS-101", assignee=dev_id("ana@example.com"), reporter="me"
    )

    out, code = preview(path, capsys)
    record = json.loads(pending_files()[0].read_text(encoding="utf-8"))
    assert record["before"] == [{"assignee": "acc-me", "reporter": "acc-other"}]
    assert "\n  Responsável: Dev Example -> acc-ana\n" in out
    assert "\n  Relator: Outro Dev -> Dev Example\n" in out
    assert approve(path, code) == 0
    fields = world.requests_to("PUT", "/rest/api/3/issue/TS-101")[-1]["body"]["fields"]
    assert fields["assignee"] == {"accountId": "acc-ana"}
    assert fields["reporter"] == {"accountId": "acc-me"}


def test_edit_parent_of_an_epic_refused_when_editmeta_lacks_it(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype=EPIC)
    set_editmeta(world, "TS-101", parent=False)
    path = make_draft("t.md", "edit", key="TS-101", parent="TS-140")

    assert "the edit screen has no parent: link TS-101 to TS-140 by hand in the tracker" in (
        problems(path, capsys)
    )


def test_edit_parent_must_be_a_level_two_card(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype=EPIC)
    set_editmeta(world, "TS-101")
    path = make_draft("t.md", "edit", key="TS-101", parent="TS-100")

    assert "TS-100 is not an initiative" in problems(path, capsys)


def test_edit_parent_of_an_epic_sends_it_and_shows_it(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype=EPIC, parent=None)
    world.set_issue("TS-140", _fields("[FRONT] Iniciativa", level=2))
    set_editmeta(world, "TS-101")
    path = make_draft("t.md", "edit", key="TS-101", parent="TS-140")

    out, code = preview(path, capsys)
    record = json.loads(pending_files()[0].read_text(encoding="utf-8"))
    assert record["before"] == [{"parent": None}]
    assert "\n  Pai: (nenhum) -> TS-140\n" in out
    assert approve(path, code) == 0
    body = world.requests_to("PUT", "/rest/api/3/issue/TS-101")[-1]["body"]
    assert body == {"fields": {"parent": {"key": "TS-140"}}}


def test_edit_parent_must_not_be_a_done_initiative(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype=EPIC, parent=None)
    world.set_issue("TS-140", _fields("[FRONT] Iniciativa", level=2, category="done"))
    set_editmeta(world, "TS-101")
    path = make_draft("t.md", "edit", key="TS-101", parent="TS-140")

    assert "initiative TS-140 is done" in problems(path, capsys)


def test_edit_parent_on_a_card_is_refused(world, capsys):  # noqa: F811
    world.set_issue("TS-140", _fields("[FRONT] Iniciativa", level=2))
    path = make_draft("t.md", "edit", key="TS-101", parent="TS-140")

    assert "parent is only for an epic; a card uses epic" in problems(path, capsys)
    assert world.writes() == []


def test_edit_epic_on_an_epic_is_refused(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype=EPIC, parent=None)
    path = make_draft("t.md", "edit", key="TS-101", epic="TS-111")

    assert "an epic has no epic; use parent for its initiative" in problems(path, capsys)


def test_edit_type_of_an_epic_is_refused(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype=EPIC, parent=None)
    path = make_draft("t.md", "edit", key="TS-101", type="task")

    message = "TS-101 is an epic: changing a card's level is done by hand in the tracker"
    assert message in problems(path, capsys)


def test_edit_type_to_an_upper_type_is_refused(world, capsys):  # noqa: F811
    path = make_draft("t.md", "edit", key="TS-101", type="epic")

    assert (
        "type epic is not a card type: changing a card's level is done by hand in the tracker"
        in problems(path, capsys)
    )


def test_edit_person_missing_from_the_edit_screen_is_refused(world, capsys):  # noqa: F811
    world.set_card("TS-101", reporter={"accountId": "acc-other", "displayName": "Outro Dev"})
    world.set_edit_screen("TS-101", without=("reporter",))
    path = make_draft("t.md", "edit", key="TS-101", reporter="me")

    assert "the edit screen of TS-101 has no reporter" in problems(path, capsys)
    assert world.writes() == []


def test_edit_due_missing_from_the_edit_screen_is_refused(world, capsys):  # noqa: F811
    world.set_edit_screen("TS-101", without=("duedate",))
    path = make_draft("t.md", "edit", key="TS-101", due="2026-11-20")

    assert "the edit screen of TS-101 has no duedate" in problems(path, capsys)


def test_edit_priority_of_a_card_without_a_type_id_reads_no_screen(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype={"name": "Tarefa", "hierarchyLevel": 0})
    path = make_draft("t.md", "edit", key="TS-101", priority="High")

    passing(path, capsys)
    assert not [r for r in world.fake.requests if "createmeta" in r["path"]]


def test_edit_title_of_an_epic_needs_its_own_prefix_not_the_initiatives(world, capsys):  # noqa: F811
    initiative = {"key": "TS-140", "fields": {"summary": "[DESLIGA] Iniciativa"}}
    world.set_card("TS-101", issuetype=EPIC, parent=initiative)

    passing(make_draft("t.md", "edit", key="TS-101", title="[BACK] Épico renomeado"), capsys)
    assert "an epic title starts with [PREFIX]" in problems(
        make_draft("u.md", "edit", key="TS-101", title="Sem prefixo"), capsys
    )


def test_edit_sprint_active_sends_the_id_and_shows_the_change(world, capsys):  # noqa: F811
    world.set_card("TS-101", fields={SPRINT_FIELD: [{"id": 50, "name": "Sprint 50"}]})
    path = make_draft("t.md", "edit", key="TS-101", sprint="active")

    out, code = preview(path, capsys)
    assert "Sprint: Sprint 50 -> Sprint 55" in out
    assert approve(path, code) == 0
    body = world.requests_to("PUT", "/rest/api/3/issue/TS-101")[-1]["body"]
    assert body["fields"] == {SPRINT_FIELD: 55}


def test_edit_sprint_of_a_card_without_one_shows_none(world, capsys):  # noqa: F811
    world.set_card("TS-101")
    out, _ = preview(make_draft("t.md", "edit", key="TS-101", sprint="active"), capsys)
    assert "Sprint: (nenhuma) -> Sprint 55" in out


def test_edit_sprint_already_in_the_active_sprint_changes_nothing(world, capsys):  # noqa: F811
    world.set_card("TS-101", fields={SPRINT_FIELD: [{"id": 55, "name": "Sprint 55"}]})
    path = make_draft("t.md", "edit", key="TS-101", sprint="active")

    assert "the draft changes nothing on the card" in problems(path, capsys)


def test_edit_sprint_needs_exactly_one_active_sprint(world, capsys):  # noqa: F811
    world.set_card("TS-101")
    path = make_draft("t.md", "edit", key="TS-101", sprint="active")
    world.set_sprints([])
    assert "exactly one active sprint, found 0" in problems(path, capsys)
    world.set_sprints([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
    assert "exactly one active sprint, found 2" in problems(path, capsys)


def test_edit_sprint_other_than_active_is_refused(world, capsys):  # noqa: F811
    path = make_draft("t.md", "edit", key="TS-101", sprint="Sprint 55")
    assert 'sprint must be "active"' in problems(path, capsys)


def test_edit_sprint_missing_from_the_edit_screen_is_refused(world, capsys):  # noqa: F811
    world.set_card("TS-101")
    world.set_edit_screen("TS-101", without=(SPRINT_FIELD,))
    path = make_draft("t.md", "edit", key="TS-101", sprint="active")

    assert f"the edit screen of TS-101 has no {SPRINT_FIELD}" in problems(path, capsys)
