import json

from test_card import (
    approve,
    claude_settings,  # noqa: F401
    make_draft,
    pending_files,
    preview,
    problems,
    world,  # noqa: F401
)

from ws.identity import dev_id


def set_editmeta(world, key, allowed=("6",), parent=True):  # noqa: F811
    fields = {"issuetype": {"allowedValues": [{"id": item, "name": "x"} for item in allowed]}}
    if parent:
        fields["parent"] = {"required": False}
    world.fake.routes[("GET", f"/rest/api/3/issue/{key}/editmeta")] = (
        200,
        json.dumps({"fields": fields}),
    )


def test_edit_type_sends_the_id_and_shows_labels(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype={"id": "3", "name": "Tarefa"})
    set_editmeta(world, "TS-101")
    path = make_draft("t.md", "edit", key="TS-101", type="improvement")

    out, code = preview(path, capsys)
    assert "Tipo: Tarefa -> Melhoria" in out
    assert approve(path, code) == 0
    body = world.requests_to("PUT", "/rest/api/3/issue/TS-101")[-1]["body"]
    assert body["fields"]["issuetype"] == {"id": "6"}


def test_edit_type_not_allowed_by_the_screen_is_refused(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype={"id": "3", "name": "Tarefa"})
    set_editmeta(world, "TS-101", allowed=("4",))
    path = make_draft("t.md", "edit", key="TS-101", type="improvement")

    assert (
        "the card's edit screen does not allow type improvement: change it with the "
        "tracker's move, by hand" in problems(path, capsys)
    )


def test_edit_same_type_changes_nothing(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype={"id": "6", "name": "Melhoria"})
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
    assert "Responsável: Dev Example -> " in out
    assert "Relator: Outro Dev -> Dev Example" in out
    assert approve(path, code) == 0
    fields = world.requests_to("PUT", "/rest/api/3/issue/TS-101")[-1]["body"]["fields"]
    assert fields["assignee"] == {"accountId": "acc-ana"}
    assert fields["reporter"] == {"accountId": "acc-me"}


def test_edit_parent_of_an_epic_refused_when_editmeta_lacks_it(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype={"id": "8", "name": "Epic"})
    set_editmeta(world, "TS-101", parent=False)
    path = make_draft("t.md", "edit", key="TS-101", parent="TS-140")

    assert "the edit screen has no parent: link TS-101 to TS-140 by hand in the tracker" in (
        problems(path, capsys)
    )


def test_edit_parent_must_be_a_level_two_card(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype={"id": "8", "name": "Epic"})
    set_editmeta(world, "TS-101")
    path = make_draft("t.md", "edit", key="TS-101", parent="TS-100")

    assert "TS-100 is not an initiative" in problems(path, capsys)
