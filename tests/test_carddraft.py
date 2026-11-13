import pytest

from ws.carddraft import DraftError, parse_draft


def draft(front, body="# T\n\nx\n"):
    return parse_draft(f"+++\n{front}\n+++\n{body}".encode())


def create(extra="", kind="task"):
    return draft(f'op = "create"\ntype = "{kind}"\npriority = "High"\n{extra}')


def link(extra, body=""):
    return draft(f'op = "link"\nkey = "TS-1"\n{extra}', body)


def test_draft_create_needs_a_type():
    with pytest.raises(DraftError, match="missing key 'type' for op create"):
        draft('op = "create"\npriority = "High"\nepic = "TS-1"')


def test_draft_create_type_must_be_neutral():
    message = "type must be one of task, bug, hotfix, improvement, feature, epic, initiative"

    with pytest.raises(DraftError, match=message):
        create('epic = "TS-1"', kind="Melhoria")


def test_draft_create_card_type_needs_an_epic():
    with pytest.raises(DraftError, match="a task needs an epic"):
        create()


def test_draft_create_card_type_refuses_parent():
    with pytest.raises(DraftError, match="parent is only for an epic; a card uses epic"):
        create('epic = "TS-1"\nparent = "TS-2"')


def test_draft_create_epic_refuses_an_epic_key():
    message = "an epic has no epic; use parent for its initiative"

    with pytest.raises(DraftError, match=message):
        create('epic = "TS-1"', kind="epic")


def test_draft_create_epic_accepts_parent_and_no_due():
    values = create('parent = "TS-2"', kind="epic").values

    assert values["parent"] == "TS-2"
    assert "due" not in values


def test_draft_create_initiative_refuses_parent():
    with pytest.raises(DraftError, match="an initiative has no parent"):
        create('parent = "TS-2"', kind="initiative")


def test_draft_create_accepts_people_and_sprint():
    values = create(
        'epic = "TS-1"\nassignee = "ana@example.com"\nreporter = "bia@example.com"\n'
        'sprint = "active"'
    ).values

    assert values["assignee"] == "ana@example.com"
    assert values["reporter"] == "bia@example.com"
    assert values["sprint"] == "active"


def test_draft_sprint_accepts_only_active():
    with pytest.raises(DraftError, match='sprint must be "active"'):
        create('epic = "TS-1"\nsprint = "Sprint 9"')


def test_draft_edit_accepts_type_people_and_parent():
    values = draft(
        'op = "edit"\nkey = "TS-1"\ntype = "bug"\nassignee = "a"\nreporter = "b"\nparent = "TS-9"',
        "",
    ).values

    assert values["type"] == "bug"
    assert values["parent"] == "TS-9"


def test_draft_edit_type_must_be_neutral():
    with pytest.raises(DraftError, match="type must be one of"):
        draft('op = "edit"\nkey = "TS-1"\ntype = "Bug"', "")


def test_draft_edit_refuses_an_upper_type():
    with pytest.raises(DraftError, match="type initiative is not a card type"):
        draft('op = "edit"\nkey = "TS-1"\ntype = "initiative"', "")


def test_draft_edit_refuses_epic_and_parent_together():
    with pytest.raises(DraftError, match="use epic for a card or parent for an epic, not both"):
        draft('op = "edit"\nkey = "TS-1"\nepic = "TS-2"\nparent = "TS-3"', "")


def test_draft_link_lists():
    parsed = link('blocks = ["TS-2"]')

    assert parsed.op == "link"
    assert parsed.values == {"key": "TS-1", "blocks": ["TS-2"]}


def test_draft_link_strips_card_keys():
    assert link('relates = [" TS-2 ", "TS-3"]').values["relates"] == ["TS-2", "TS-3"]


def test_draft_link_needs_one_list():
    with pytest.raises(DraftError, match="a link needs blocks, blocked_by or relates"):
        link("")


def test_draft_link_refuses_its_own_key():
    with pytest.raises(DraftError, match="a card cannot link to itself"):
        link('blocks = ["TS-1"]')


def test_draft_link_refuses_the_same_card_twice():
    with pytest.raises(DraftError, match="TS-2 appears in more than one list"):
        link('blocks = ["TS-2"]\nblocked_by = ["TS-2"]')


def test_draft_link_refuses_a_duplicate_inside_one_list():
    with pytest.raises(DraftError, match="blocks lists TS-2 twice"):
        link('blocks = ["TS-2", "TS-2"]')


@pytest.mark.parametrize("value", ['"TS-2"', '["TS-2", ""]', "[1]", '["  "]'])
def test_draft_link_lists_hold_card_keys(value):
    with pytest.raises(DraftError, match="blocks must be a list of card keys"):
        link(f"blocks = {value}")


def test_draft_link_has_no_body():
    with pytest.raises(DraftError, match="a link draft has no body"):
        link('blocks = ["TS-2"]', "texto\n")


def test_draft_link_refuses_unknown_keys():
    with pytest.raises(DraftError, match="unknown key 'to' for op link"):
        link('blocks = ["TS-2"]\nto = "X"')
