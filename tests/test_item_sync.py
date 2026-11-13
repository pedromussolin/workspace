import json
from datetime import date

import pytest
from fake_tracker import FakeTracker, make_card
from item_helpers import ANA, ME, write_item
from item_helpers import item_repo as item_repo

from ws import itemrecord
from ws.cli import main
from ws.taskmodel import Status
from ws.tracker import port
from ws.tracker.port import Link

REL = "projects/demo/tasks/01-a.md"
FRONT = (
    f'card = "TS-5"\n# keep me\ntype = "task"\nepic = "TS-100"\nassignee = "{ME}"\n'
    f'reporter = "{ME}"'
)


def run(capsys, *argv):
    code = main(["item", *argv])
    out = capsys.readouterr()
    return code, json.loads(out.out) if out.out.strip() else None, out.err


@pytest.fixture
def serve(monkeypatch):
    def install(*cards):
        tracker = FakeTracker(cards)
        monkeypatch.setattr(port, "open_tracker", lambda: tracker)
        return tracker

    return install


def test_pull_copies_the_tracker_values(item_repo, serve, capsys):
    path = write_item(item_repo, "01-a.md", FRONT)
    before = path.read_text(encoding="utf-8")
    serve(make_card("TS-5", type="bug", assignee="acc-ana"))

    code, report, _ = run(capsys, "pull", REL, "--fields", "type,assignee")

    assert code == 0
    assert report == {
        "path": REL,
        "changed": {
            "type": {"item": "task", "tracker": "bug"},
            "assignee": {"item": ME, "tracker": ANA},
        },
    }
    assert path.read_text(encoding="utf-8") == before.replace(
        'type = "task"', 'type = "bug"'
    ).replace(f'assignee = "{ME}"', f'assignee = "{ANA}"')


def test_pull_links_come_sorted(item_repo, serve, capsys):
    path = write_item(item_repo, "01-a.md", FRONT)
    links = (Link("blocks", "TS-9"), Link("blocks", "TS-8"))
    serve(make_card("TS-5", links=links))

    assert run(capsys, "pull", REL, "--fields", "blocks")[0] == 0
    assert 'blocks = ["TS-8", "TS-9"]' in path.read_text(encoding="utf-8")


def test_pull_refuses_an_account_without_dev_id(item_repo, serve, capsys):
    path = write_item(item_repo, "01-a.md", FRONT)
    before = path.read_text(encoding="utf-8")
    serve(make_card("TS-5", assignee="acc-x"))

    code, _, err = run(capsys, "pull", REL, "--fields", "assignee")

    assert code == 1
    assert "the tracker's assignee acc-x has no dev id: run ws people add <e-mail>" in err
    assert path.read_text(encoding="utf-8") == before


def test_pull_refuses_an_unknown_field(item_repo, serve, capsys):
    write_item(item_repo, "01-a.md", FRONT)
    serve(make_card("TS-5"))

    code, _, err = run(capsys, "pull", REL, "--fields", "card")

    assert code == 1
    assert "'card' cannot be pulled" in err


def test_pull_refuses_cardless_untracked_and_missing_card(item_repo, serve, capsys):
    write_item(item_repo, "01-a.md", FRONT.replace('card = "TS-5"\n', ""))
    write_item(item_repo, "02-b.md", 'tracker = false\nstatus = "todo"')
    write_item(item_repo, "03-c.md", FRONT.replace("TS-5", "TS-6"))
    serve(make_card("TS-5"))
    for name in ("01-a", "02-b", "03-c"):
        rel = f"projects/demo/tasks/{name}.md"
        assert run(capsys, "pull", rel, "--fields", "type")[0] == 1


def test_sync_rewrites_only_the_tracker_table(item_repo, serve, capsys):
    path = write_item(item_repo, "01-a.md", FRONT, body="# 01 — Algo\n\nTexto.\n")
    before = path.read_text(encoding="utf-8")
    serve(make_card("TS-5", status=Status.IN_PROGRESS, due=date(2026, 12, 1), sprint="S1"))

    code, report, _ = run(capsys, "sync")

    assert code == 0
    assert report == {"updated": [REL], "problems": []}
    text = path.read_text(encoding="utf-8")
    today = date.today().isoformat()
    table = (
        '[tracker]\nstatus = "in_progress"\npriority = "Medium"\ndue = 2026-12-01\n'
        f'sprint = "S1"\nsynced = {today}\n'
    )
    assert text == before.replace("\n+++\n# 01", f"\n\n{table}+++\n# 01", 1)


def test_sync_skips_untracked_and_cardless_items(item_repo, serve, capsys):
    cardless = write_item(item_repo, "01-a.md", FRONT.replace('card = "TS-5"\n', ""))
    untracked = write_item(item_repo, "02-b.md", 'tracker = false\nstatus = "todo"')
    before = (cardless.read_text(encoding="utf-8"), untracked.read_text(encoding="utf-8"))
    tracker = serve(make_card("TS-5"))

    code, report, _ = run(capsys, "sync")

    assert (code, report) == (0, {"updated": [], "problems": []})
    assert (cardless.read_text(encoding="utf-8"), untracked.read_text(encoding="utf-8")) == before
    assert tracker.reads == []


def test_sync_missing_card_is_a_problem_and_leaves_the_item(item_repo, serve, capsys):
    path = write_item(item_repo, "01-a.md", FRONT)
    before = path.read_text(encoding="utf-8")
    serve()

    code, report, _ = run(capsys, "sync", "demo")

    assert code == 1
    assert report["updated"] == []
    assert report["problems"][0]["path"] == REL
    assert path.read_text(encoding="utf-8") == before


def test_set_card_writes_and_clears_the_record(item_repo, capsys):
    path = write_item(item_repo, "01-a.md", FRONT.replace('card = "TS-5"\n', ""))
    itemrecord.record(REL, "TS-200")

    code, _, _ = run(capsys, "set-card", str(path), "TS-200")

    assert code == 0
    assert 'card = "TS-200"' in path.read_text(encoding="utf-8")
    assert itemrecord.recorded(REL) is None


def test_set_card_refuses_another_card(item_repo, capsys):
    path = write_item(item_repo, "01-a.md", FRONT)
    before = path.read_text(encoding="utf-8")

    code, _, err = run(capsys, "set-card", REL, "TS-200")

    assert code == 1
    assert "already has card" in err
    assert path.read_text(encoding="utf-8") == before


def test_set_card_none_clears_only_a_recorded_item(item_repo, capsys):
    write_item(item_repo, "01-a.md", FRONT.replace('card = "TS-5"\n', ""))
    assert run(capsys, "set-card", REL, "--none")[0] == 1
    itemrecord.record(REL, "?")

    assert run(capsys, "set-card", REL, "--none")[0] == 0
    assert itemrecord.recorded(REL) is None


def test_sync_a_failing_fetch_is_a_problem_and_the_rest_goes_on(item_repo, monkeypatch, capsys):
    from ws.tracker.port import TrackerError

    first = write_item(item_repo, "01-a.md", FRONT)
    second = write_item(item_repo, "02-b.md", FRONT.replace("TS-5", "TS-6"))
    before = first.read_text(encoding="utf-8")
    tracker = FakeTracker([make_card("TS-6")])
    real = tracker.card

    def card(ref):
        if ref == "TS-5":
            raise TrackerError("boom")
        return real(ref)

    tracker.card = card
    monkeypatch.setattr(port, "open_tracker", lambda: tracker)

    code, report, _ = run(capsys, "sync")

    assert code == 1
    assert report["updated"] == ["projects/demo/tasks/02-b.md"]
    assert [p["path"] for p in report["problems"]] == [REL]
    assert first.read_text(encoding="utf-8") == before
    assert "[tracker]" in second.read_text(encoding="utf-8")


def test_sync_reports_an_item_that_failed_to_parse(item_repo, serve, capsys):
    write_item(item_repo, "01-a.md", "card = ")
    serve()

    code, report, _ = run(capsys, "sync")

    assert code == 1
    assert [p["path"] for p in report["problems"]] == [REL]


def test_pull_an_empty_link_list_writes_nothing(item_repo, serve, capsys):
    path = write_item(item_repo, "01-a.md", FRONT)
    before = path.read_text(encoding="utf-8")
    serve(make_card("TS-5"))

    code, report, _ = run(capsys, "pull", REL, "--fields", "blocks")

    assert (code, report["changed"]) == (0, {})
    assert path.read_text(encoding="utf-8") == before


def test_pull_links_keep_waiting_entries_and_the_item_spelling(item_repo, serve, capsys):
    listed = '["TS-2", "tasks/02-b.md", "tasks/03-c.md"]'
    path = write_item(item_repo, "01-a.md", FRONT + f"\nblocks = {listed}")
    write_item(item_repo, "02-b.md", FRONT.replace('card = "TS-5"\n', ""))
    write_item(item_repo, "03-c.md", FRONT.replace("TS-5", "TS-3"))
    before = path.read_text(encoding="utf-8")
    links = (Link("blocks", "TS-4"), Link("blocks", "TS-3"), Link("relates", "TS-9"))
    serve(make_card("TS-5", links=links))

    code, report, _ = run(capsys, "pull", REL, "--fields", "blocks")

    assert code == 0
    pulled = ["tasks/02-b.md", "tasks/03-c.md", "TS-4"]
    assert report["changed"] == {
        "blocks": {"item": ["TS-2", "tasks/02-b.md", "tasks/03-c.md"], "tracker": pulled}
    }
    assert path.read_text(encoding="utf-8") == before.replace(
        f"blocks = {listed}", 'blocks = ["tasks/02-b.md", "tasks/03-c.md", "TS-4"]'
    )


def test_pull_links_unchanged_when_only_a_waiting_entry_is_extra(item_repo, serve, capsys):
    path = write_item(item_repo, "01-a.md", FRONT + '\nrelates = ["tasks/02-b.md", "TS-9"]')
    write_item(item_repo, "02-b.md", FRONT.replace('card = "TS-5"\n', ""))
    before = path.read_text(encoding="utf-8")
    serve(make_card("TS-5", links=(Link("relates", "TS-9"),)))

    code, report, _ = run(capsys, "pull", REL, "--fields", "relates")

    assert (code, report["changed"]) == (0, {})
    assert path.read_text(encoding="utf-8") == before


def test_pull_links_refuses_an_entry_that_does_not_resolve(item_repo, serve, capsys):
    path = write_item(item_repo, "01-a.md", FRONT + '\nblocks = ["tasks/09-none.md"]')
    before = path.read_text(encoding="utf-8")
    serve(make_card("TS-5", links=(Link("blocks", "TS-4"),)))

    code, _, err = run(capsys, "pull", REL, "--fields", "blocks")

    assert code == 1
    assert "tasks/09-none.md" in err and "fix the item first" in err
    assert path.read_text(encoding="utf-8") == before
