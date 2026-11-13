import re
from pathlib import Path

import pytest
from adopt_items.maprows import Link, Row
from adopt_items.plan import PlanError, build_plan, render_plan

PEOPLE = {"ana": "dev-aaaaaaaaaa", "bia": "dev-bbbbbbbbbb"}


def row(**kw) -> Row:
    base = dict(
        source="a.tsv", line=2, project="p", file=None, origin_project=None, card="TS-1",
        action="manter", type_="task", epic=None, assignee="ana", reporter="bia", links=(),
        status="a fazer", scope="", heading="H", done_when="",
    )  # fmt: skip
    base.update(kw)
    return Row(**base)


def make_repo(tmp_path: Path, **projects: list[str]) -> Path:
    for project, names in projects.items():
        tasks = tmp_path / "projects" / project / "tasks"
        tasks.mkdir(parents=True)
        for name in names:
            (tasks / name).write_text("# body\n")
    return tmp_path


def test_single_row_file_becomes_an_item_of_that_card(tmp_path):
    repo = make_repo(tmp_path, p=["01-a.md"])
    rows = [row(file="tasks/01-a.md", epic="TS-9")]
    plan = build_plan(rows, repo, PEOPLE, [])
    (item,) = plan.items
    assert (item.origin, item.path, item.project, item.slug) == (
        "file",
        "projects/p/tasks/01-a.md",
        "p",
        None,
    )
    assert item.fields == {
        "card": "TS-1", "type": "task", "epic": "TS-9",
        "assignee": "dev-aaaaaaaaaa", "reporter": "dev-bbbbbbbbbb",
    }  # fmt: skip
    assert plan.project_tomls["p"]["epics"] == ["TS-9"]


def test_two_rows_on_one_file_make_a_document_and_two_new_items(tmp_path):
    repo = make_repo(tmp_path, p=["41-x.md"])
    rows = [
        row(file="tasks/41-x.md", card="TS-5464"),
        row(file="tasks/41-x.md", card="TS-5465", line=3),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    assert [i.origin for i in plan.items] == ["new", "new"]
    assert [i.docs for i in plan.items] == [["41-x.md"], ["41-x.md"]]
    assert plan.documents == {"p": ["41-x.md"]}
    assert plan.unattached == []


def test_sem_card_with_file_is_tracker_false_with_status(tmp_path):
    repo = make_repo(tmp_path, p=["01-a.md"])
    rows = [row(file="tasks/01-a.md", card="-", action="sem-card", status="concluída (2/2)")]
    (item,) = build_plan(rows, repo, PEOPLE, []).items
    assert item.fields == {"tracker": False, "status": "done"}


def test_sem_card_without_file_makes_no_item_but_keeps_the_project(tmp_path):
    repo = make_repo(tmp_path, q=[])
    rows = [row(project="q", card="-", action="sem-card", type_=None, assignee=None)]
    plan = build_plan(rows, repo, PEOPLE, [])
    assert plan.items == []
    assert plan.project_tomls["q"]["epics"] == []


def test_open_existing_card_without_file_gets_an_item_and_closed_one_does_not(tmp_path):
    repo = make_repo(tmp_path, p=[])
    rows = [
        row(card="TS-7", status="Em andamento"),
        row(card="TS-8", status="Concluído", line=3),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    (item,) = plan.items
    assert (item.origin, item.fields["card"]) == ("new", "TS-7")
    assert [(r.card, why) for r, why in plan.skipped] == [("TS-8", "closed card, no file")]


def test_epico_and_epic_rows_are_not_items(tmp_path):
    repo = make_repo(tmp_path, p=[])
    rows = [
        row(project="epico", card="TS-50", type_="epic"),
        row(card="TS-51", type_="epic", line=3),
        row(card="TS-52", type_="initiative", line=4),
        row(card="novo-e-5", type_="epic", line=5),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    assert plan.items == []
    assert plan.project_tomls == {"p": {"epics": ["TS-51"], "initiative": "TS-52"}}


def test_pending_epic_has_no_epic_field(tmp_path):
    repo = make_repo(tmp_path, p=[])
    rows = [
        row(card="novo-a-2", epic="novo-E3", action="criar"),
        row(card="novo-a-3", epic="VM TELAS", action="criar", line=3),
        row(card="novo-a-4", epic="TS-5357", action="criar", line=4),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    assert ["epic" in i.fields for i in plan.items] == [False, False, True]
    assert [(i.row.card, e) for i, e in plan.pending_epics] == [
        ("novo-a-2", "novo-E3"), ("novo-a-3", "novo-E1"),
    ]  # fmt: skip
    assert plan.project_tomls["p"]["epics"] == ["TS-5357"]


def test_move_goes_to_the_row_project_and_takes_attached_docs(tmp_path):
    repo = make_repo(tmp_path, **{"vm-migration": [], "artemis-v2": ["13-m.md", "13-m-notes.md"]})
    rows = [row(project="vm-migration", file="tasks/13-m.md", origin_project="artemis-v2")]
    plan = build_plan(rows, repo, PEOPLE, [("artemis-v2", "13-m-notes.md", "TS-1")])
    assert sorted(plan.moves) == [
        ("projects/artemis-v2/tasks/13-m-notes.md", "projects/vm-migration/tasks/13-m-notes.md"),
        ("projects/artemis-v2/tasks/13-m.md", "projects/vm-migration/tasks/13-m.md"),
    ]
    (item,) = plan.items
    assert (item.project, item.path, item.docs) == (
        "vm-migration",
        "projects/vm-migration/tasks/13-m.md",
        ["13-m-notes.md"],
    )
    assert plan.documents == {"vm-migration": ["13-m-notes.md"]}


def test_move_refuses_a_name_that_exists_in_the_destination(tmp_path):
    repo = make_repo(tmp_path, **{"vm-migration": ["13-m.md"], "artemis-v2": ["13-m.md"]})
    rows = [row(project="vm-migration", file="tasks/13-m.md", origin_project="artemis-v2")]
    with pytest.raises(PlanError) as err:
        build_plan(rows, repo, PEOPLE, [])
    text = str(err.value)
    assert "projects/artemis-v2/tasks/13-m.md" in text
    assert "projects/vm-migration/tasks/13-m.md" in text


def test_documents_attach_by_ts_number_then_by_unique_prefix_else_unattached(tmp_path):
    names = ["01-a.md", "02-b.md", "01-a-extra.md", "ts-2-plan.md", "02-b-more.md", "99-z.md"]
    repo = make_repo(tmp_path, p=names)
    rows = [
        row(file="tasks/01-a.md", card="TS-1"),
        row(file="tasks/02-b.md", card="TS-2", line=3),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    docs = {i.row.card: i.docs for i in plan.items}
    assert docs == {"TS-1": ["01-a-extra.md"], "TS-2": ["02-b-more.md", "ts-2-plan.md"]}
    assert plan.unattached == ["p/99-z.md"]
    assert plan.documents["p"] == sorted(
        ["01-a-extra.md", "02-b-more.md", "99-z.md", "ts-2-plan.md"]
    )


def test_novo_links_become_item_paths(tmp_path):
    repo = make_repo(tmp_path, p=["03-a.md", "07-b.md"], vm=["05-c.md"])
    rows = [
        row(card="TS-1", file="tasks/03-a.md", links=(Link("blocks", "novo-a-5"),
                                                      Link("relates", "TS-99"))),
        row(card="novo-a-5", action="criar", line=5, heading="new one"),
        row(card="novo-a-6", action="criar", line=6, heading="other", project="vm",
            links=(Link("blocked_by", "TS-1"),)),
        row(card="TS-3", file="tasks/07-b.md", line=7, links=(Link("blocks", "novo-a-6"),)),
    ]  # fmt: skip
    plan = build_plan(rows, repo, PEOPLE, [])
    by_card = {i.row.card: i for i in plan.items}
    assert by_card["TS-1"].fields["blocks"] == ["tasks/08-new-a-5.md"]
    assert by_card["TS-1"].fields["relates"] == ["TS-99"]
    assert by_card["TS-1"].link_rows == [("blocks", "novo-a-5")]
    assert by_card["TS-3"].fields["blocks"] == ["../vm/tasks/06-new-a-6.md"]
    assert by_card["novo-a-6"].fields["blocked_by"] == ["TS-1"]


def test_link_to_a_skipped_row_or_a_tracker_false_item_refuses(tmp_path):
    repo = make_repo(tmp_path, p=["01-a.md"])
    rows = [
        row(card="TS-1", file="tasks/01-a.md", links=(Link("blocks", "novo-a-3"),
                                                      Link("blocks", "novo-a-4"))),
        row(card="novo-a-3", file="tasks/01-a.md", action="sem-card", line=3),
        row(card="novo-a-4", action="criar", status="documento de apoio", line=4),
    ]  # fmt: skip
    with pytest.raises(PlanError) as err:
        build_plan(rows, repo, PEOPLE, [])
    assert str(err.value).count("novo-a-") >= 2


def test_new_item_slugs_follow_ruling_11(tmp_path):
    repo = make_repo(tmp_path, p=["41-x.md"])
    rows = [
        row(card="TS-5465", file="tasks/41-x.md"),
        row(card="TS-5466", file="tasks/41-x.md", line=3),
        row(card="TS-5570", line=4),
        row(card="novo-others-3", action="criar", line=5),
        row(card="novo-others-6", action="criar", line=6, file="tasks/41-x.md"),
        row(card="novo-others-7", action="criar", line=7, file="tasks/41-x.md"),
    ]
    items = build_plan(rows, repo, PEOPLE, []).items
    assert [i.slug for i in items] == [
        "ts-5465-x", "ts-5466-x", "ts-5570", "new-others-3", "x", "x-2",
    ]  # fmt: skip
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i.slug) for i in items)


def test_status_documento_de_apoio_is_a_document_not_an_item(tmp_path):
    repo = make_repo(tmp_path, p=["01-a.md", "02-s.md"])
    rows = [
        row(file="tasks/01-a.md"),
        row(file="tasks/02-s.md", card="TS-2", status="documento de apoio", line=3),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    assert [i.path for i in plan.items] == ["projects/p/tasks/01-a.md"]
    assert "02-s.md" in plan.documents["p"]


def test_rename_is_planned_when_the_old_folder_exists(tmp_path):
    repo = make_repo(tmp_path, **{"operations-screens-migration": ["01-a.md"]})
    rows = [row(project="operations-screens-migration", file="tasks/01-a.md")]
    plan = build_plan(rows, repo, PEOPLE, [])
    assert plan.rename == ("projects/operations-screens-migration", "projects/vm-migration")
    assert plan.items[0].project == "vm-migration"
    assert "vm-migration" in plan.project_tomls


def test_no_rename_without_the_old_folder_and_whitelabel_maps_to_its_folder(tmp_path):
    repo = make_repo(tmp_path, **{"whitelabel-restructure": ["01-a.md"]})
    plan = build_plan([row(project="whitelabel", file="tasks/01-a.md")], repo, PEOPLE, [])
    assert plan.rename is None
    assert plan.items[0].project == "whitelabel-restructure"


def test_every_problem_is_listed_in_one_error(tmp_path):
    repo = make_repo(tmp_path, p=[])
    rows = [
        row(file="tasks/nope.md", assignee="zed"),
        row(action="perguntar", line=3, card="TS-3"),
    ]
    with pytest.raises(PlanError) as err:
        build_plan(rows, repo, PEOPLE, [])
    text = str(err.value)
    assert "zed" in text and "perguntar" in text and "nope.md" in text


def test_render_plan_mentions_every_move_item_and_skip(tmp_path):
    repo = make_repo(tmp_path, **{"vm-migration": [], "artemis-v2": ["13-m.md"]})
    rows = [
        row(project="vm-migration", file="tasks/13-m.md", origin_project="artemis-v2"),
        row(card="TS-8", status="Concluído", line=3),
        row(card="TS-9", status="Em andamento", line=4),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    text = render_plan(plan)
    assert "projects/artemis-v2/tasks/13-m.md" in text
    assert "projects/vm-migration/tasks/13-m.md" in text
    assert "tasks/13-m.md" in text and "TS-9" in text
    item_lines = [ln for ln in text.splitlines() if ln.startswith("item ") and "vm-migration" in ln]
    assert item_lines
    for ln in item_lines:
        assert ln.count("projects/vm-migration/tasks/") == 1
        assert "vm-migration/projects/" not in ln
    assert "TS-8" in text and "closed card, no file" in text
    assert text.rstrip().splitlines()[-1].startswith("total")


def test_new_items_get_consecutive_predicted_paths_in_plan_order(tmp_path):
    repo = make_repo(tmp_path, p=["04-a.md", "09-b.md"])
    rows = [
        row(card="novo-a-2", action="criar"),
        row(card="TS-5", line=3),
        row(card="novo-a-4", action="criar", line=4),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    assert [i.path for i in plan.items] == [
        "projects/p/tasks/10-new-a-2.md",
        "projects/p/tasks/11-ts-5.md",
        "projects/p/tasks/12-new-a-4.md",
    ]


def test_the_same_move_registered_twice_is_not_a_clash(tmp_path):
    repo = make_repo(tmp_path, **{"vm-migration": [], "artemis-v2": ["13-m.md"]})
    rows = [
        row(project="vm-migration", file="tasks/13-m.md", origin_project="artemis-v2"),
        row(project="vm-migration", file="tasks/13-m.md", origin_project="artemis-v2",
            status="documento de apoio", line=3),
    ]  # fmt: skip
    plan = build_plan(rows, repo, PEOPLE, [])
    assert len(plan.moves) == 1


def test_sem_card_row_of_a_multi_row_file_is_skipped_with_a_reason(tmp_path):
    repo = make_repo(tmp_path, p=["41-x.md"])
    rows = [
        row(file="tasks/41-x.md", card="TS-1"),
        row(file="tasks/41-x.md", card="TS-2", line=3),
        row(file="tasks/41-x.md", card="-", action="sem-card", line=4),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    assert len(plan.items) == 2
    assert [why for _, why in plan.skipped] == ["sem-card row of a file that became a document"]
