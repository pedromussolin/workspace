"""An epic and its initiative without premium (a link, not the parent field), and why epics and
initiatives stay out of sprints."""

import json
from pathlib import Path

import pytest
from test_card import (
    SPRINT_FIELD,
    _fields,
    approve,
    claude_settings,  # noqa: F401
    create_draft,
    make_draft,
    passing,
    pending_files,
    preview,
    problems,
    set_premium,
    world,  # noqa: F401
)

from ws import card
from ws.cli import main
from ws.config import data_dir
from ws.tracker import write
from ws.tracker.jira.settings import parse_settings
from ws.userconfig import ConfigInvalid

EPIC = {"id": "8", "name": "Epic", "hierarchyLevel": 1}
INITIATIVE = {"id": "9", "name": "Iniciativa", "hierarchyLevel": 2}
ISSUE_LINK = ("POST", "/rest/api/3/issueLink")
OUT_OF_SPRINTS = "an epic or an initiative stays out of sprints; put its cards in the sprint"
LINK_REQUEST = {
    "method": "POST",
    "path": "/rest/api/3/issueLink",
    "body": {
        "type": {"name": "Relates"},
        "inwardIssue": {"key": "TS-101"},
        "outwardIssue": {"key": "TS-140"},
    },
}


def epic_and_initiative(world, **epic):  # noqa: F811
    world.set_card("TS-101", issuetype=EPIC, parent=None, **epic)
    world.set_issue("TS-140", _fields("[FRONT] Iniciativa", level=2))


def parent_draft(name="p.md"):
    return make_draft(name, "edit", key="TS-101", parent="TS-140")


def epic_create(type_="epic", **front):
    return create_draft(
        title="[FRONT] Nível acima", body="## Contexto\nPor quê.\n", type=type_, epic=None, **front
    )


def test_parent_with_premium_sets_the_parent_field(world, capsys, ws_config):  # noqa: F811
    set_premium(ws_config)
    epic_and_initiative(world)
    path = parent_draft()

    out, code = preview(path, capsys)
    assert "\n  Pai: (nenhum) -> TS-140\n" in out
    assert "issueLink" not in out
    assert approve(path, code) == 0
    body = world.requests_to("PUT", "/rest/api/3/issue/TS-101")[-1]["body"]
    assert body == {"fields": {"parent": {"key": "TS-140"}}}
    assert world.requests_to(*ISSUE_LINK) == []


def test_parent_without_premium_plans_a_relates_link(world, capsys):  # noqa: F811
    epic_and_initiative(world)
    world.set_edit_screen("TS-101", without=("parent",))
    world.fake.routes[ISSUE_LINK] = (201, "")
    path = parent_draft()

    out, code = preview(path, capsys)
    [saved] = pending_files()
    record = json.loads(saved.read_text(encoding="utf-8"))

    assert "\n  Iniciativa: TS-140 (por link Relates)\n" in out
    assert "Requisição: POST /rest/api/3/issueLink" in out
    assert "Pai:" not in out and "PUT" not in out
    assert record["requests"] == [LINK_REQUEST]
    assert "  Iniciativa: TS-140 (por link Relates)" in record["summary"]
    assert code == card.approval_code(
        world.fake.site, record["requests"], record["before"], record["summary"]
    )
    same_as_a_link_draft = make_draft("l.md", "link", key="TS-101", relates=["TS-140"])
    assert passing(same_as_a_link_draft, capsys)["requests"] == [LINK_REQUEST]

    assert approve(path, code) == 0
    assert [r["body"] for r in world.requests_to(*ISSUE_LINK)] == [LINK_REQUEST["body"]]
    assert world.requests_to("PUT", "/rest/api/3/issue/TS-101") == []


def test_parent_without_premium_follows_the_configured_link_name(world, capsys, ws_config):  # noqa: F811
    epic_and_initiative(world)
    _, relates_code = preview(parent_draft(), capsys)
    config = ws_config / "config.toml"
    text = config.read_text(encoding="utf-8")
    config.write_text(text.replace('relates = "Relates"', 'relates = "Related"'), encoding="utf-8")

    out, related_code = preview(parent_draft(), capsys)

    assert "\n  Iniciativa: TS-140 (por link Related)\n" in out
    assert '"name": "Related"' in out
    assert related_code != relates_code


ALONE = "without premium the initiative is a link: put `parent` in its own draft"
WITH_ANOTHER_CHANGE = [
    pytest.param({"priority": "High"}, "", id="priority"),
    pytest.param({"title": "[FRONT] Épico renomeado"}, "", id="title"),
    pytest.param({}, "## Contexto\nNovo texto.\n", id="description"),
]


@pytest.mark.parametrize(("front", "body"), WITH_ANOTHER_CHANGE)
def test_parent_without_premium_with_another_change_is_refused(world, capsys, front, body):  # noqa: F811
    epic_and_initiative(world)
    path = make_draft("p.md", "edit", body, key="TS-101", parent="TS-140", **front)

    assert problems(path, capsys) == ALONE
    assert world.writes() == []


@pytest.mark.parametrize(("front", "body"), WITH_ANOTHER_CHANGE)
def test_parent_without_premium_with_another_change_is_refused_json(world, capsys, front, body):  # noqa: F811
    epic_and_initiative(world)
    md = make_draft("p.md", "edit", body, key="TS-101", parent="TS-140", **front)
    js = card.write_draft("p.json", json.dumps(card.show(str(md)), ensure_ascii=False))

    assert problems(js, capsys) == ALONE
    assert world.writes() == []


def test_parent_without_premium_with_another_draft_goes_in_one_batch(world, capsys):  # noqa: F811
    epic_and_initiative(world)
    world.fake.routes[ISSUE_LINK] = (201, "")
    folder = data_dir() / "cards" / "drafts" / "batch"
    folder.mkdir(parents=True)
    make_draft("batch/1-priority.md", "edit", key="TS-101", priority="High")
    make_draft("batch/2-parent.md", "edit", key="TS-101", parent="TS-140")

    out, code = preview(folder, capsys)
    [saved] = pending_files()
    requests = json.loads(saved.read_text(encoding="utf-8"))["requests"]

    assert out.count("Código de aprovação:") == 1
    assert [(r["method"], r["path"]) for r in requests] == [
        ("PUT", "/rest/api/3/issue/TS-101"),
        ISSUE_LINK,
    ]
    assert approve(folder, code) == 0
    put = world.requests_to("PUT", "/rest/api/3/issue/TS-101")
    assert [r["body"] for r in put] == [{"fields": {"priority": {"name": "High"}}}]
    assert [r["body"] for r in world.requests_to(*ISSUE_LINK)] == [LINK_REQUEST["body"]]


@pytest.mark.parametrize("side", ["outwardIssue", "inwardIssue"])
def test_parent_without_premium_already_linked_changes_nothing(world, capsys, side):  # noqa: F811
    epic_and_initiative(world, issuelinks=[{"type": {"name": "Relates"}, side: {"key": "TS-140"}}])
    path = parent_draft()

    assert problems(path, capsys) == "the draft changes nothing on the card"
    [step] = card.preview_plan(str(path))["steps"]
    assert step["preview"][-1] == "Iniciativa: TS-140 (por link Relates): já existe"
    assert (step["problems"], step["native"]) == (["the draft changes nothing on the card"], [])
    assert pending_files() == []
    assert world.writes() == []


def test_parent_without_premium_another_link_type_does_not_count(world, capsys):  # noqa: F811
    blocks = {"type": {"name": "Blocks"}, "outwardIssue": {"key": "TS-140"}}
    epic_and_initiative(world, issuelinks=[blocks])

    assert passing(parent_draft(), capsys)["requests"] == [LINK_REQUEST]


def test_parent_without_premium_must_be_an_initiative(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuetype=EPIC, parent=None)

    assert "TS-100 is not an initiative" in problems(
        make_draft("p.md", "edit", key="TS-101", parent="TS-100"), capsys
    )


def test_parent_without_premium_needs_a_writable_epic(world, capsys):  # noqa: F811
    epic_and_initiative(world)
    world.set_card("TS-102", assignee="acc-other", issuetype=EPIC, parent=None)
    path = make_draft("p.md", "edit", key="TS-102", parent="TS-140")

    assert "card TS-102 is not yours" in problems(path, capsys)
    assert world.writes() == []


def test_parent_without_premium_needs_the_link_type_in_the_config(world, capsys, ws_config):  # noqa: F811
    epic_and_initiative(world)
    config = ws_config / "config.toml"
    text = config.read_text(encoding="utf-8")
    config.write_text(text.replace('relates = "Relates"\n', ""), encoding="utf-8")

    assert "link kind 'relates' has no link type: add it to [tracker.jira.links]" in problems(
        parent_draft(), capsys
    )


def test_create_epic_with_parent_without_premium_is_refused(world, capsys):  # noqa: F811
    world.set_issue("TS-140", _fields("[FRONT] Iniciativa", level=2))

    assert (
        "without premium the initiative is a link: create the epic first, then edit it with "
        "`parent`" in problems(epic_create(parent="TS-140", sprint=None), capsys)
    )
    assert world.writes() == []


def table(**keys):
    return {"site": "https://example.atlassian.net", "email": "dev@example.com", **keys}


def test_premium_and_initiative_link_defaults():
    settings = parse_settings(table(), Path("config.toml"))

    assert (settings.premium, settings.initiative_link) == (False, "relates")


def test_initiative_link_names_a_key_of_the_links_table():
    links = {"blocks": "Blocks", "relates": "Relates"}
    settings = parse_settings(
        table(premium=True, initiative_link="blocks", links=links), Path("config.toml")
    )

    assert (settings.premium, settings.initiative_link) == (True, "blocks")


@pytest.mark.parametrize("name", ["parent", "relates"])
def test_unknown_initiative_link_is_a_config_error(name):
    with pytest.raises(ConfigInvalid, match=r"\[tracker\.jira\.links\]"):
        parse_settings(table(initiative_link=name, links={"blocks": "Blocks"}), Path("config.toml"))


def test_premium_must_be_true_or_false():
    with pytest.raises(ConfigInvalid, match=r"tracker\.jira\.premium"):
        parse_settings(table(premium="sim"), Path("config.toml"))


@pytest.mark.parametrize("type_", ["epic", "initiative"])
def test_epic_create_with_sprint_is_refused(world, capsys, type_):  # noqa: F811
    code = main(["card", "check", str(epic_create(type_, sprint="active"))])
    verdict = json.loads(capsys.readouterr().out)

    assert (code, verdict["problems"]) == (1, [OUT_OF_SPRINTS])
    assert world.fake.requests == []


@pytest.mark.parametrize("type_", ["epic", "initiative"])
def test_epic_create_with_sprint_is_refused_json(world, capsys, type_):  # noqa: F811
    document = card.show(str(epic_create(type_, sprint=None)))
    document["sprint"] = "next"
    path = card.write_draft("upper.json", json.dumps(document, ensure_ascii=False))

    assert write.check_document(document) == [OUT_OF_SPRINTS]
    assert main(["card", "check", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["problems"] == [OUT_OF_SPRINTS]
    assert world.fake.requests == []


@pytest.mark.parametrize("issuetype", [EPIC, INITIATIVE], ids=["epic", "initiative"])
@pytest.mark.parametrize("sprint", ["active", "next", "Sprint 55"])
def test_initiative_edit_into_a_sprint_is_refused(world, capsys, issuetype, sprint):  # noqa: F811
    world.set_card("TS-101", issuetype=issuetype, parent=None)

    assert problems(make_draft("s.md", "edit", key="TS-101", sprint=sprint), capsys) == (
        OUT_OF_SPRINTS
    )
    assert not [r for r in world.fake.requests if "/sprint" in r["path"]]


@pytest.mark.parametrize("issuetype", [EPIC, INITIATIVE], ids=["epic", "initiative"])
def test_epic_to_backlog_is_allowed(world, capsys, issuetype):  # noqa: F811
    held = [{"id": 55, "name": "Sprint 55", "state": "active"}]
    world.set_card("TS-101", issuetype=issuetype, parent=None, fields={SPRINT_FIELD: held})
    path = make_draft("b.md", "edit", key="TS-101", sprint="backlog")

    out, code = preview(path, capsys)
    assert "\n  Sprint: Sprint 55 -> backlog (nenhuma sprint)\n" in out
    assert approve(path, code) == 0
    body = world.requests_to("PUT", "/rest/api/3/issue/TS-101")[-1]["body"]
    assert body == {"fields": {SPRINT_FIELD: None}}
