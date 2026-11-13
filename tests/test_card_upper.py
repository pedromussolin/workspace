import json

from test_card import (
    _fields,
    claude_settings,  # noqa: F401
    create_draft,
    passing,
    preview,
    problems,
    world,  # noqa: F401
)

SCREEN = "/rest/api/3/issue/createmeta/TS/issuetypes/{}"
PRIORITY = {"fieldId": "priority", "allowedValues": [{"name": "High"}]}


def screen(world, type_id, *, parent):  # noqa: F811
    fields = [PRIORITY] + ([{"fieldId": "parent"}] if parent else [])
    world.fake.routes[("GET", SCREEN.format(type_id))] = (200, json.dumps({"fields": fields}))


def upper_draft(type_="epic", title="[FRONT] Épico novo", **front):
    return create_draft(title=title, body="## Contexto\nPor quê.\n", type=type_, epic=None, **front)


def sent_fields(path, capsys):
    return passing(path, capsys)["requests"][0]["body"]["fields"]


def test_create_epic_without_parent(world, capsys):  # noqa: F811
    screen(world, "8", parent=False)

    fields = sent_fields(upper_draft(), capsys)

    assert fields["issuetype"] == {"id": "8"}
    assert "parent" not in fields


def test_create_epic_title_needs_a_prefix(world, capsys):  # noqa: F811
    screen(world, "8", parent=False)

    assert "an epic title starts with [PREFIX]" in problems(
        upper_draft(title="Sem prefixo"), capsys
    )


def test_create_epic_with_parent_when_the_screen_has_it(world, capsys):  # noqa: F811
    screen(world, "8", parent=True)
    world.set_issue("TS-140", _fields("[FRONT] Iniciativa", level=2))

    fields = sent_fields(upper_draft(parent="TS-140"), capsys)

    assert fields["parent"] == {"key": "TS-140"}


def test_create_epic_with_parent_refused_when_the_screen_lacks_it(world, capsys):  # noqa: F811
    screen(world, "8", parent=False)
    world.set_issue("TS-140", _fields("[FRONT] Iniciativa", level=2))

    assert (
        "the epic create screen has no parent: create it without parent and link it to TS-140 "
        "by hand in the tracker" in problems(upper_draft(parent="TS-140"), capsys)
    )
    assert world.writes() == []


def test_create_epic_parent_must_be_an_initiative(world, capsys):  # noqa: F811
    screen(world, "8", parent=True)
    world.set_issue("TS-140", _fields("[FRONT] Outro épico", level=1))

    assert "TS-140 is not an initiative" in problems(upper_draft(parent="TS-140"), capsys)


def test_create_epic_parent_must_not_be_done(world, capsys):  # noqa: F811
    screen(world, "8", parent=True)
    world.set_issue("TS-140", _fields("[FRONT] Iniciativa", level=2, category="done"))

    assert "initiative TS-140 is done" in problems(upper_draft(parent="TS-140"), capsys)


def test_create_initiative(world, capsys):  # noqa: F811
    screen(world, "9", parent=False)

    fields = sent_fields(upper_draft("initiative", "[FRONT] Iniciativa nova"), capsys)

    assert fields["issuetype"] == {"id": "9"}
    assert "parent" not in fields


def test_create_initiative_title_needs_a_prefix(world, capsys):  # noqa: F811
    screen(world, "9", parent=False)

    assert "an initiative title starts with [PREFIX]" in problems(
        upper_draft("initiative", "Sem prefixo"), capsys
    )


def test_create_epic_preview_in_portuguese(world, capsys):  # noqa: F811
    screen(world, "8", parent=True)
    world.set_issue("TS-140", _fields("[FRONT] Iniciativa", level=2))
    path = upper_draft(parent="TS-140")

    out, _ = preview(path, capsys)

    assert "Criar épico no projeto TS" in out
    assert "Tipo: Épico" in out
    assert "Iniciativa: TS-140 [FRONT] Iniciativa" in out


def test_epic_still_needs_only_the_context_section(world, capsys):  # noqa: F811
    screen(world, "8", parent=False)

    passing(upper_draft(), capsys)
