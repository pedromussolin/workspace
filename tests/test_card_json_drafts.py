import json
from pathlib import Path

import pytest
from test_card import (
    approve,
    claude_settings,  # noqa: F401
    create_draft,
    make_draft,
    pending_files,
    preview,
    world,  # noqa: F401
)

from ws import card
from ws.cli import main
from ws.config import data_dir
from ws.tracker import write


def json_twin(md_path, name, **changes):
    document = {**card.show(str(md_path)), **changes}
    path = md_path.parent / name
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def record_without_sources(path):
    """The pending record minus the sources, code, summary and session."""
    record = json.loads(path.read_text(encoding="utf-8"))
    for name in ("drafts", "code", "summary", "sid"):
        record.pop(name)
    return record


def summary_of(path):
    return json.loads(path.read_text(encoding="utf-8"))["summary"]


def test_json_draft_previews_like_its_markdown_twin(world, capsys):  # noqa: F811
    md = create_draft("twin.md")
    js = json_twin(md, "twin.json")

    md_out, md_code = preview(md, capsys)
    [md_record] = pending_files()
    md_record_data = record_without_sources(md_record)
    md_sources = json.loads(md_record.read_text(encoding="utf-8"))["drafts"]
    md_summary = summary_of(md_record)
    md_record.unlink()
    js_out, js_code = preview(js, capsys)
    [js_record] = pending_files()
    js_sources = json.loads(js_record.read_text(encoding="utf-8"))["drafts"]

    # The code covers the summary, whose header names the file, so only the extension differs.
    assert md_code != js_code
    assert [line.replace("twin.md", "twin.json") for line in md_summary] == summary_of(js_record)
    assert md_out.replace("twin.md", "twin.json").replace(md_code, js_code) == js_out
    assert md_record_data == record_without_sources(js_record)
    assert md_sources[0]["sha256"] != js_sources[0]["sha256"]
    assert js_sources[0]["path"] == str(js)


def test_json_draft_applies_after_its_preview(world, capsys):  # noqa: F811
    js = json_twin(create_draft("go.md"), "go.json")
    _, code = preview(js, capsys)

    assert approve(js, code) == 0
    assert world.writes()


def test_json_draft_with_an_unknown_key_is_refused(world, capsys):  # noqa: F811
    js = json_twin(create_draft("odd.md"), "odd.json", surprise="x")

    assert main(["card", "check", str(js)]) == 1
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["ok"] is False
    assert any("surprise" in line for line in verdict["problems"])


def test_a_malformed_json_draft_is_refused(world, capsys):  # noqa: F811
    path = make_draft("bad.md", "move", key="TS-1", to="x").with_name("bad.json")
    path.write_text("{not json", encoding="utf-8")

    assert main(["card", "check", str(path)]) == 1
    assert "JSON" in capsys.readouterr().out


def test_check_validates_a_card_plan_document(world, capsys):  # noqa: F811
    md = create_draft("plan.md")
    preview(md, capsys)
    plan = card.preview_plan(str(md))
    good = md.parent / "plan.json"
    good.write_text(json.dumps(plan), encoding="utf-8")
    assert main(["card", "check", str(good)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    plan["steps"] = "nope"
    bad = md.parent / "bad-plan.json"
    bad.write_text(json.dumps(plan), encoding="utf-8")
    assert main(["card", "check", str(bad)]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_a_folder_mixes_md_and_json_drafts(world, capsys):  # noqa: F811
    folder = data_dir() / "cards" / "drafts" / "mix"
    folder.mkdir(parents=True)
    md = make_draft("mix/one.md", "move", key="TS-101", to="Em Andamento")
    json_twin(md, "two.json", to="Em Validação")

    assert [p.name for p in card.collect(str(folder))] == ["one.md", "two.json"]
    out, _ = preview(folder, capsys)
    assert "(one.md)" in out and "(two.json)" in out


def test_write_and_remove_accept_json_names(world):  # noqa: F811
    path = card.write_draft("made.json", "{}")

    assert path.name == "made.json"
    assert card.remove_draft("made.json") is True


SCHEMA_HAS_STATUS = "status" in json.dumps(
    json.loads((Path(card.__file__).parent / "data/contracts/card-write.schema.json").read_text())
)


@pytest.mark.skipif(not SCHEMA_HAS_STATUS, reason="card-write schema has no `status` yet")
def test_json_move_takes_a_neutral_status(world, capsys):  # noqa: F811
    md = make_draft("m.md", "move", key="TS-101", to="Em Andamento")
    document = {"$schema": "card-write", "version": 1, "op": "move", "key": "TS-101"}
    path = md.with_name("m.json")
    path.write_text(json.dumps({**document, "status": "in_progress"}), encoding="utf-8")

    assert main(["card", "check", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


MOVE = {"$schema": "card-write", "version": 1, "op": "move", "key": "TS-101"}


def test_move_with_neither_to_nor_status_is_refused():
    assert write.check_document(MOVE) == ["missing key 'to' for op move"]


@pytest.mark.skipif(not SCHEMA_HAS_STATUS, reason="card-write schema has no `status` yet")
def test_move_with_both_to_and_status_is_refused():
    both = write.check_document({**MOVE, "to": "x", "status": "done"})

    assert both == ["a move needs exactly one of to or status, not both"]


def twins(folder, front, body, document):
    """The Markdown draft and its `card-write` twin, loaded as `ws card` loads them."""
    md = folder / "twin.md"
    md.write_text(f"+++\n{front}\n+++\n{body}", encoding="utf-8")
    js = folder / "twin.json"
    js.write_text(
        json.dumps({"$schema": "card-write", "version": 1, **document}, ensure_ascii=False),
        encoding="utf-8",
    )
    return card.load(md), card.load(js)


CREATE = 'op = "create"\npriority = "High"\n'
CREATE_JSON = {"op": "create", "priority": "High", "title": "T", "body": "x\n"}
EDIT = 'op = "edit"\nkey = "TS-1"\n'
EDIT_JSON = {"op": "edit", "key": "TS-1"}
LINK = 'op = "link"\nkey = "TS-1"\n'
LINK_JSON = {"op": "link", "key": "TS-1"}
ITEM = "projects/demo/tasks/01-tela.md"

RULE_TWINS = [
    pytest.param(
        CREATE + 'type = "task"',
        "# T\n\nx\n",
        {**CREATE_JSON, "type": "task"},
        ["a task needs an epic"],
        id="card-without-epic",
    ),
    pytest.param(
        CREATE + 'type = "task"\nepic = "TS-1"\nparent = "TS-2"',
        "# T\n\nx\n",
        {**CREATE_JSON, "type": "task", "epic": "TS-1", "parent": "TS-2"},
        ["parent is only for an epic; a card uses epic"],
        id="card-with-parent",
    ),
    pytest.param(
        CREATE + 'type = "epic"\nepic = "TS-1"',
        "# T\n\nx\n",
        {**CREATE_JSON, "type": "epic", "epic": "TS-1"},
        ["an epic has no epic; use parent for its initiative"],
        id="epic-with-epic",
    ),
    pytest.param(
        CREATE + 'type = "initiative"\nparent = "TS-2"',
        "# T\n\nx\n",
        {**CREATE_JSON, "type": "initiative", "parent": "TS-2"},
        ["an initiative has no parent"],
        id="initiative-with-parent",
    ),
    pytest.param(
        CREATE + 'type = "epic"\nsprint = "active"',
        "# T\n\nx\n",
        {**CREATE_JSON, "type": "epic", "sprint": "active"},
        ["an epic or an initiative stays out of sprints; put its cards in the sprint"],
        id="epic-in-a-sprint",
    ),
    pytest.param(
        CREATE + 'type = "task"\nepic = "TS-1"\nitem = "notes/tela.md"',
        "# T\n\nx\n",
        {**CREATE_JSON, "type": "task", "epic": "TS-1", "item": "notes/tela.md"},
        ["item must be a path like projects/<slug>/tasks/NN-name.md"],
        id="item-outside-a-project",
    ),
    pytest.param(
        CREATE + f'type = "epic"\nitem = "{ITEM}"',
        "# T\n\nx\n",
        {**CREATE_JSON, "type": "epic", "item": ITEM},
        ["item is only for a card; an epic or an initiative has no item"],
        id="item-on-an-epic",
    ),
    pytest.param(
        EDIT + 'type = "initiative"',
        "",
        {**EDIT_JSON, "type": "initiative"},
        [
            "type initiative is not a card type: changing a card's level is done by hand in the "
            "tracker"
        ],
        id="edit-to-an-upper-type",
    ),
    pytest.param(
        EDIT + 'epic = "TS-2"\nparent = "TS-3"',
        "",
        {**EDIT_JSON, "epic": "TS-2", "parent": "TS-3"},
        ["use epic for a card or parent for an epic, not both"],
        id="edit-epic-and-parent",
    ),
    pytest.param(
        EDIT + 'title = "  "',
        "",
        {**EDIT_JSON, "title": "  "},
        ["title must be a non-empty string"],
        id="blank-title",
    ),
    pytest.param(
        'op = "move"\nkey = ""\nto = "X"',
        "",
        {"op": "move", "key": "", "to": "X"},
        ["key must be a non-empty string"],
        id="blank-key",
    ),
    pytest.param(
        LINK + 'blocks = ["TS-1"]',
        "",
        {**LINK_JSON, "blocks": ["TS-1"]},
        ["a card cannot link to itself"],
        id="link-to-itself",
    ),
    pytest.param(
        LINK + 'blocks = [" TS-1 "]',
        "",
        {**LINK_JSON, "blocks": [" TS-1 "]},
        ["a card cannot link to itself"],
        id="link-to-itself-with-spaces",
    ),
    pytest.param(
        LINK + 'blocks = ["TS-2"]\nrelates = ["TS-2"]',
        "",
        {**LINK_JSON, "blocks": ["TS-2"], "relates": ["TS-2"]},
        ["TS-2 appears in more than one list"],
        id="card-in-two-lists",
    ),
    pytest.param(
        LINK + 'blocks = ["TS-2", "TS-2"]',
        "",
        {**LINK_JSON, "blocks": ["TS-2", "TS-2"]},
        ["blocks lists TS-2 twice"],
        id="card-twice-in-a-list",
    ),
    pytest.param(
        LINK + 'blocks = ["TS-2", ""]',
        "",
        {**LINK_JSON, "blocks": ["TS-2", ""]},
        ["blocks must be a list of card keys"],
        id="blank-card-in-a-list",
    ),
    pytest.param(
        LINK + 'blocks = ["  "]',
        "",
        {**LINK_JSON, "blocks": ["  "]},
        ["blocks must be a list of card keys"],
        id="spaces-in-a-list",
    ),
    pytest.param(
        EDIT + 'add_labels = ["a", "b"]\nremove_labels = ["b"]',
        "",
        {**EDIT_JSON, "add_labels": ["a", "b"], "remove_labels": ["b"]},
        ["b is in add_labels and in remove_labels"],
        id="label-added-and-removed",
    ),
    pytest.param(
        EDIT + 'add_labels = ["a", ""]',
        "",
        {**EDIT_JSON, "add_labels": ["a", ""]},
        ["add_labels must be a list of labels"],
        id="blank-label",
    ),
    pytest.param(
        EDIT + 'remove_labels = ["a", "a"]',
        "",
        {**EDIT_JSON, "remove_labels": ["a", "a"]},
        ["remove_labels lists a twice"],
        id="repeated-label",
    ),
    pytest.param(
        LINK + 'causes = ["TS-2"]\ncaused_by = ["TS-2"]',
        "",
        {**LINK_JSON, "causes": ["TS-2"], "caused_by": ["TS-2"]},
        ["TS-2 appears in more than one list"],
        id="cause-and-effect-of-the-same-card",
    ),
    pytest.param(
        'op = "move"\nkey = "TS-1"\nto = "X"\nstatus = "done"',
        "",
        {"op": "move", "key": "TS-1", "to": "X", "status": "done"},
        ["a move needs exactly one of to or status, not both"],
        id="move-to-and-status",
    ),
    pytest.param(
        'op = "move"\nkey = "TS-1"',
        "",
        {"op": "move", "key": "TS-1"},
        ["missing key 'to' for op move"],
        id="move-without-target",
    ),
]


@pytest.mark.parametrize(("front", "body", "document", "expected"), RULE_TWINS)
def test_a_json_twin_is_refused_with_the_markdown_text(tmp_path, front, body, document, expected):
    md, js = twins(tmp_path, front, body, document)

    assert (md.draft, md.problems) == (None, expected)
    assert (js.draft, js.problems) == (None, expected)


SHAPE_TWINS = [
    pytest.param(
        'op = "create"\npriority = "High"\nepic = "TS-1"',
        "# T\n\nx\n",
        {**CREATE_JSON, "epic": "TS-1"},
        ["missing key 'type' for op create"],
        ["$: missing required key type for op create"],
        id="missing-key",
    ),
    pytest.param(
        LINK + 'blocks = ["TS-2"]\nto = "X"',
        "",
        {**LINK_JSON, "blocks": ["TS-2"], "to": "X"},
        ["unknown key 'to' for op link"],
        ["$.to: not a key of op link"],
        id="unknown-key",
    ),
    pytest.param(
        EDIT + 'type = "Bug"',
        "",
        {**EDIT_JSON, "type": "Bug"},
        ["type must be one of task, bug, hotfix, improvement, feature, epic, initiative"],
        ["$.type: expected one of task, bug, hotfix, improvement, feature, epic, initiative"],
        id="type-not-neutral",
    ),
    pytest.param(
        'op = "move"\nkey = "TS-1"\nstatus = "feito"',
        "",
        {"op": "move", "key": "TS-1", "status": "feito"},
        [
            "status must be one of todo, in_progress, review, validation, ready_deploy, "
            "blocked, done, cancelled"
        ],
        [
            "$.status: expected one of todo, in_progress, review, validation, ready_deploy, "
            "blocked, done, cancelled"
        ],
        id="status-not-neutral",
    ),
    pytest.param(
        CREATE + 'type = "task"\nepic = "TS-1"\nsprint = ""',
        "# T\n\nx\n",
        {**CREATE_JSON, "type": "task", "epic": "TS-1", "sprint": ""},
        ["sprint must be a non-empty string"],
        ["$.sprint: expected a non-empty string"],
        id="blank-sprint",
    ),
    pytest.param(
        LINK.rstrip(),
        "",
        LINK_JSON,
        ["a link needs blocks, blocked_by, relates, causes or caused_by"],
        ["$: a link needs blocks, blocked_by, relates, causes or caused_by"],
        id="link-without-lists",
    ),
    pytest.param(
        LINK + 'blocks = "TS-2"',
        "",
        {**LINK_JSON, "blocks": "TS-2"},
        ["blocks must be a list of card keys"],
        ["$.blocks: expected array, got string"],
        id="list-not-a-list",
    ),
    pytest.param(
        LINK + 'blocks = ["TS-2"]',
        "texto\n",
        {**LINK_JSON, "blocks": ["TS-2"], "body": "texto\n"},
        ["a link draft has no body"],
        ["$.body: not a key of op link"],
        id="link-with-a-body",
    ),
    pytest.param(
        'op = "worklog"\nkey = "TS-1"\ntime = "1h"\nday = "ontem"',
        "",
        {"op": "worklog", "key": "TS-1", "time": "1h", "day": "ontem"},
        ["day must be a date (YYYY-MM-DD)"],
        ["$.day: expected a date YYYY-MM-DD"],
        id="malformed-date",
    ),
]


@pytest.mark.parametrize(("front", "body", "document", "md_text", "json_text"), SHAPE_TWINS)
def test_a_json_twin_of_a_shape_refusal_keeps_the_contract_words(
    tmp_path, front, body, document, md_text, json_text
):
    """Where the `card-write` contract itself refuses the shape, each form keeps its own words."""
    md, js = twins(tmp_path, front, body, document)

    assert (md.draft, md.problems) == (None, md_text)
    assert (js.draft, js.problems) == (None, json_text)


@pytest.mark.parametrize(
    ("front", "body", "document"),
    [
        (
            CREATE + 'type = "task"\nepic = "TS-1"\nlabels = ["a", "b"]\nestimate = "2h 30m"',
            "# T\n\nx\n",
            {
                **CREATE_JSON,
                "type": "task",
                "epic": "TS-1",
                "labels": ["a", "b"],
                "estimate": "2h 30m",
            },
        ),
        (
            EDIT + 'add_labels = ["a"]\nremove_labels = ["b"]\nestimate = "45m"',
            "",
            {**EDIT_JSON, "add_labels": ["a"], "remove_labels": ["b"], "estimate": "45m"},
        ),
        (
            LINK + 'causes = ["TS-2"]\ncaused_by = ["TS-3"]',
            "",
            {**LINK_JSON, "causes": ["TS-2"], "caused_by": ["TS-3"]},
        ),
    ],
    ids=["create", "edit", "link"],
)
def test_the_label_estimate_and_cause_keys_are_the_same_in_both_forms(
    tmp_path, front, body, document
):
    md, js = twins(tmp_path, front, body, document)

    assert md.problems == js.problems == []
    assert md.draft.values == js.draft.values
    assert md.draft.title == js.draft.title


def test_labels_are_not_a_key_of_an_edit_in_either_form(tmp_path):
    md, js = twins(tmp_path, EDIT + 'labels = ["a"]', "", {**EDIT_JSON, "labels": ["a"]})

    assert md.problems == ["unknown key 'labels' for op edit"]
    assert js.problems == ["$.labels: not a key of op edit"]


def test_json_values_are_trimmed_like_the_markdown_twin(tmp_path):
    md, js = twins(
        tmp_path,
        LINK.replace('"TS-1"', '" TS-1 "') + 'relates = [" TS-2 ", "TS-3"]',
        "",
        {**LINK_JSON, "key": " TS-1 ", "relates": [" TS-2 ", "TS-3"]},
    )

    assert md.draft.values == js.draft.values == {"key": "TS-1", "relates": ["TS-2", "TS-3"]}
    assert write.to_document(md.draft) == write.to_document(js.draft)


def test_check_refuses_a_json_card_create_without_an_epic(world, capsys):  # noqa: F811
    document = card.show(str(create_draft("no-epic.md")))
    del document["epic"]
    js = card.write_draft("no-epic.json", json.dumps(document, ensure_ascii=False))

    assert main(["card", "check", str(js)]) == 1
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["problems"] == ["a task needs an epic"]
    assert world.fake.requests == []
