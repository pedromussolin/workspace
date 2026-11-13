import json
from pathlib import Path

import pytest
from fake_tracker import FakeTracker, make_card
from item_helpers import ANA, ME, write_item
from item_helpers import item_repo as item_repo  # noqa: F401
from test_card import (
    claude_settings,  # noqa: F401
    world,  # noqa: F401
)

from ws import itemrecord
from ws.carddraft import DraftError, parse_draft
from ws.cli import main
from ws.config import data_dir
from ws.taskmodel import Status
from ws.tracker.port import Link

FRONT = f'card = "TS-5"\ntype = "task"\nepic = "TS-100"\nassignee = "{ME}"\nreporter = "{ME}"'
CARDLESS = f'type = "task"\nepic = "TS-100"\nassignee = "{ME}"\nreporter = "{ME}"'
REL = "projects/demo/tasks/01-a.md"


@pytest.fixture
def tracker(monkeypatch):
    def install(*cards, **options):
        fake = FakeTracker(cards, **options)
        monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: fake)
        return fake

    return install


def run(capsys, *argv):
    code = main(["item", *argv])
    out = capsys.readouterr()
    return code, json.loads(out.out) if out.out.strip() else None, out.err


def check(capsys):
    return run(capsys, "check", "--tracker")


def draft_files():
    folder = data_dir() / "cards" / "drafts"
    return sorted(folder.rglob("*.md")) if folder.exists() else []


def test_check_tracker_reports_each_drift_kind(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT)
    tracker(
        make_card("TS-5", type="bug", parent="TS-111", assignee="acc-ana", reporter="acc-other"),
        names={"acc-me": "Dev Example", "acc-ana": "Ana X"},
    )

    code, report, _ = check(capsys)

    assert code == 0
    fields = {d["field"]: d for d in report["drift"]}
    assert set(fields) == {"type", "epic", "assignee", "reporter"}
    assert fields["type"] == {
        "path": REL,
        "card": "TS-5",
        "field": "type",
        "item": "task",
        "tracker": "bug",
    }
    assert fields["epic"]["item"] == "TS-100" and fields["epic"]["tracker"] == "TS-111"
    assert fields["assignee"]["item"] == ME and fields["assignee"]["tracker"] == ANA
    assert fields["assignee"]["names"] == {"item": "Dev Example", "tracker": "Ana X"}
    assert fields["reporter"]["tracker"] == "acc-other"


def test_check_tracker_missing_card_is_a_problem(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT)
    tracker()

    code, report, _ = check(capsys)

    assert code == 1
    assert report["problems"] == [
        {"path": REL, "problem": "card TS-5 was not found in the tracker's project"}
    ]


def test_check_tracker_level_other_than_zero_is_a_problem(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT)
    tracker(make_card("TS-5", level=1))

    code, report, _ = check(capsys)

    assert code == 1
    assert report["problems"][0]["problem"] == "TS-5 is not a card (level 1)"


def test_check_tracker_pending_creates_and_links(item_repo, tracker, capsys):  # noqa: F811
    write_item(
        item_repo, "01-a.md", FRONT + '\nblocks = ["TS-7", "tasks/02-b.md"]\nrelates = ["TS-8"]'
    )
    write_item(item_repo, "02-b.md", CARDLESS)
    tracker(make_card("TS-5"), make_card("TS-7"), make_card("TS-8", parent="TS-100"))

    code, report, _ = check(capsys)

    assert code == 0
    assert report["pending"] == [
        {"path": REL, "card": "TS-5", "op": "link", "kind": "blocks", "to": "TS-7", "waits": False},
        {
            "path": REL,
            "card": "TS-5",
            "op": "link",
            "kind": "blocks",
            "to": "tasks/02-b.md",
            "waits": True,
        },
        {
            "path": REL,
            "card": "TS-5",
            "op": "link",
            "kind": "relates",
            "to": "TS-8",
            "waits": False,
        },
        {"path": "projects/demo/tasks/02-b.md", "card": None, "op": "create"},
    ]


def test_check_tracker_link_to_a_ref_the_tracker_lacks_is_a_problem(
    item_repo,  # noqa: F811
    tracker,
    capsys,
):
    write_item(item_repo, "01-a.md", FRONT + '\nblocks = ["TS-9"]')
    tracker(make_card("TS-5"))

    code, report, _ = check(capsys)

    assert code == 1
    assert "TS-9 was not found" in report["problems"][0]["problem"]


def test_check_tracker_link_declared_on_the_other_side_is_not_drift(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT + '\nblocks = ["TS-6"]')
    write_item(item_repo, "02-b.md", FRONT.replace("TS-5", "TS-6") + '\nblocked_by = ["TS-5"]\n')
    tracker(
        make_card("TS-5", links=(Link("blocks", "TS-6"),)),
        make_card("TS-6", links=(Link("blocked_by", "TS-5"),)),
    )

    code, report, _ = check(capsys)

    assert (code, report["drift"], report["pending"]) == (0, [], [])


def test_check_tracker_link_declared_only_by_the_other_item_is_not_drift(
    item_repo, tracker, capsys
):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT)
    write_item(item_repo, "02-b.md", FRONT.replace("TS-5", "TS-6") + '\nblocks = ["TS-5"]')
    tracker(
        make_card("TS-5", links=(Link("blocked_by", "TS-6"),)),
        make_card("TS-6", links=(Link("blocks", "TS-5"),)),
    )

    code, report, _ = check(capsys)

    assert (code, report["drift"], report["pending"]) == (0, [], [])


def test_check_tracker_undeclared_tracker_link_is_drift(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT)
    tracker(make_card("TS-5", links=(Link("relates", "TS-9"),)))

    code, report, _ = check(capsys)

    assert code == 0
    assert report["drift"] == [
        {"path": REL, "card": "TS-5", "field": "relates", "item": [], "tracker": ["TS-9"]}
    ]


def test_check_tracker_orphans(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT)
    tracker(
        make_card("TS-5"),
        make_card("TS-20", title="Loose"),
        make_card("TS-21", status=Status.DONE),
        make_card("TS-22", assignee="acc-other", reporter="acc-other"),
    )

    _, report, _ = check(capsys)

    assert report["orphans"] == [{"card": "TS-20", "title": "Loose", "epic": "TS-100"}]


def test_check_tracker_cardless_item_without_epic_is_pending_with_needs_epic(
    item_repo,  # noqa: F811
    tracker,
    capsys,
):
    write_item(item_repo, "01-a.md", f'type = "task"\nassignee = "{ME}"\nreporter = "{ME}"')
    tracker()

    code, report, _ = check(capsys)

    assert code == 0
    assert report["pending"] == [{"path": REL, "card": None, "op": "create", "needs": "epic"}]


def test_check_tracker_does_not_compare_an_untracked_item(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", 'type = "task"\ntracker = false\nstatus = "todo"')
    tracker()

    code, report, _ = check(capsys)

    assert (code, report["pending"], report["drift"]) == (0, [], [])


def drafts_setup(item_repo, tracker):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT + '\nblocks = ["TS-7"]')
    write_item(item_repo, "02-b.md", CARDLESS)
    return tracker(make_card("TS-5", type="bug"), make_card("TS-7"))


def test_drafts_writes_edit_link_and_create(item_repo, tracker, capsys):  # noqa: F811
    drafts_setup(item_repo, tracker)

    code, result, _ = run(capsys, "drafts")

    assert code == 0
    assert result["count"] == 3
    names = sorted(p.name for p in Path(result["folder"]).iterdir())
    assert names == ["create-demo-02-b.md", "edit-TS-5.md", "link-TS-5.md"]
    folder = Path(result["folder"])
    edit = parse_draft((folder / "edit-TS-5.md").read_bytes())
    assert edit.op == "edit" and edit.values == {"key": "TS-5", "type": "task"}
    link = parse_draft((folder / "link-TS-5.md").read_bytes())
    assert link.values == {"key": "TS-5", "blocks": ["TS-7"]}
    create = folder / "create-demo-02-b.md"
    with pytest.raises(DraftError):
        parse_draft(create.read_bytes())
    assert result["need_text"] == [str(create)]
    text = create.read_text(encoding="utf-8")
    assert 'item = "projects/demo/tasks/02-b.md"' in text
    assert 'priority = "Medium"' in text and "## Contexto" in text and "## Pronto quando" in text
    assert result["waiting"] == [] and result["by_hand"] == []


def test_drafts_only_selects_refs_and_paths(item_repo, tracker, capsys):  # noqa: F811
    drafts_setup(item_repo, tracker)

    code, result, _ = run(capsys, "drafts", "--only", "TS-5,projects/demo/tasks/02-b.md")
    assert code == 0 and result["count"] == 3

    code, result, _ = run(capsys, "drafts", "--only", "projects/demo/tasks/02-b.md")
    assert code == 0 and result["count"] == 1
    assert [p.name for p in Path(result["folder"]).iterdir()] == ["create-demo-02-b.md"]

    code, _, err = run(capsys, "drafts", "--only", "TS-99")
    assert code == 1 and "TS-99" in err


def test_drafts_link_to_an_item_without_card_waits(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT + '\nblocks = ["tasks/02-b.md"]')
    write_item(item_repo, "02-b.md", CARDLESS)
    tracker(make_card("TS-5"))

    _, result, _ = run(capsys, "drafts")

    assert result["count"] == 1
    assert [w["to"] for w in result["waiting"]] == ["tasks/02-b.md"]


def test_drafts_do_not_redraft_links_the_tracker_has(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT + '\nblocks = ["TS-7"]')
    tracker(make_card("TS-5", links=(Link("blocks", "TS-7"),)), make_card("TS-7"))

    _, result, _ = run(capsys, "drafts")

    assert result == {"folder": None, "count": 0, "need_text": [], "waiting": [], "by_hand": []}
    assert draft_files() == []


def test_drafts_one_link_declared_on_both_sides_is_drafted_once(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT + '\nblocks = ["TS-6"]')
    write_item(item_repo, "02-b.md", FRONT.replace("TS-5", "TS-6") + '\nblocked_by = ["TS-5"]')
    tracker(make_card("TS-5"), make_card("TS-6"))

    _, result, _ = run(capsys, "drafts")

    assert result["count"] == 1


def test_drafts_cardless_item_without_epic_is_not_drafted(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", f'type = "task"\nassignee = "{ME}"\nreporter = "{ME}"')
    tracker()

    code, result, _ = run(capsys, "drafts")

    assert code == 0 and result["count"] == 0 and result["folder"] is None
    assert result["by_hand"] == [
        f"item {REL} has no epic: set it in the item, then run ws item drafts again"
    ]

    write_item(item_repo, "01-a.md", CARDLESS)
    code, result, _ = run(capsys, "drafts")
    assert code == 0 and result["count"] == 1


def test_drafts_refuses_an_item_recorded_uncertain(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", CARDLESS)
    tracker()
    itemrecord.record(REL, "?")

    code, _, err = run(capsys, "drafts")

    assert code == 1
    assert "uncertain create" in err and "ws item set-card" in err
    assert draft_files() == []


def test_drafts_refuses_when_check_has_problems(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT)
    tracker()

    code, _, err = run(capsys, "drafts")

    assert code == 1 and "problem" in err
    assert draft_files() == []


def test_drafts_missing_capability_goes_to_by_hand(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT + '\nblocks = ["TS-7"]')
    tracker(
        make_card("TS-5", type="bug"),
        make_card("TS-7"),
        capabilities={"worklog"},
    )

    code, result, _ = run(capsys, "drafts")

    assert code == 0 and result["count"] == 0
    assert result["by_hand"] == [
        "change the type of TS-5 by hand in the tracker",
        "create the link TS-5 blocks TS-7 by hand in the tracker",
    ]


def test_drafts_undeclared_tracker_link_goes_to_by_hand(item_repo, tracker, capsys):  # noqa: F811
    write_item(item_repo, "01-a.md", FRONT)
    tracker(make_card("TS-5", links=(Link("blocks", "TS-7"),)))

    code, result, _ = run(capsys, "drafts")

    assert code == 0 and result["count"] == 0
    assert result["by_hand"] == [
        f"remove the link TS-5 blocks TS-7 by hand, or ws item pull {REL} --fields blocks"
    ]


def test_check_tracker_through_the_jira_adapter(world, item_repo, capsys):  # noqa: F811
    world.set_card(
        "TS-101",
        issuetype={"id": "3", "hierarchyLevel": 0},
        reporter={"accountId": "acc-me"},
    )
    world.fake.pages = {None: {"issues": [], "isLast": True}}
    write_item(item_repo, "01-a.md", FRONT.replace("TS-5", "TS-101"))

    code, report, _ = check(capsys)

    assert code == 0
    assert report == {"problems": [], "drift": [], "pending": [], "orphans": []}
