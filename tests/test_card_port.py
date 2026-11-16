import json
from datetime import date
from pathlib import Path

import pytest
from test_card import (
    NOW,
    approve,
    claude_settings,  # noqa: F401
    create_draft,
    make_draft,
    pending_files,
    preview,
    world,  # noqa: F401
)
from test_card_golden import DRAFTS, prepare

from ws import card, contracts
from ws.carddraft import DraftError, parse_draft
from ws.cli import main
from ws.tracker import port, write

CARD_TEST_DRAFTS = {
    **DRAFTS,
    "create-people": lambda name: create_draft(
        name, assignee="me", reporter="me", item="projects/demo/tasks/01-a.md"
    ),
    "create-epic-parent": lambda name: create_draft(
        name, type="epic", epic=None, sprint=None, parent="TS-140"
    ),
    "create-bug": lambda name: create_draft(name, type="bug", sprint=None),
    "edit-title": lambda name: make_draft(name, "edit", key="TS-101", title="[FRONT] Novo título"),
    "edit-start": lambda name: make_draft(name, "edit", key="TS-101", start=date(2026, 11, 5)),
    "edit-people": lambda name: make_draft(
        name, "edit", key="TS-101", assignee="me", reporter="me"
    ),
    "edit-epic": lambda name: make_draft(name, "edit", key="TS-101", epic="TS-111"),
    "edit-parent": lambda name: make_draft(name, "edit", key="TS-101", parent="TS-100"),
    "edit-type": lambda name: make_draft(name, "edit", key="TS-101", type="improvement"),
    "edit-sprint": lambda name: make_draft(name, "edit", key="TS-101", sprint="active"),
    "edit-body": lambda name: make_draft(name, "edit", "## Contexto\nsó isso\n", key="TS-101"),
    "worklog-plain": lambda name: make_draft(name, "worklog", key="TS-101", time="1h"),
    "link-blocked-by": lambda name: make_draft(name, "link", key="TS-101", blocked_by=["TS-102"]),
}


def _envelope(steps: list[dict]) -> dict:
    return {"$schema": "card-result", "version": 1, "steps": steps}


@pytest.mark.parametrize("name", list(CARD_TEST_DRAFTS))
def test_every_accepted_draft_validates_as_card_write(name):
    path = CARD_TEST_DRAFTS[name](f"{name}.md")
    draft = parse_draft(path.read_bytes())

    item = card.load(path)

    assert item.draft == draft
    assert item.problems == []
    assert item.entry == {
        "source": {"path": str(path), "sha256": draft.sha256},
        "write": write.to_document(draft),
        "problems": [],
    }
    assert write.check_document(item.entry["write"]) == []


@pytest.mark.parametrize(
    "op, body, front, message",
    [
        ("comment", "\n\n", {"key": "TS-101"}, "the comment is empty"),
        ("move", "texto\n", {"key": "TS-101", "to": "Em Validação"}, "a move has no body"),
    ],
)
def test_a_draft_the_contract_refuses_keeps_the_rules_message(
    world,  # noqa: F811
    capsys,
    op,
    body,
    front,
    message,
):
    path = make_draft("d.md", op, body, **front)

    item = card.load(path)

    assert item.draft is not None
    assert item.problems == write.check_document(write.to_document(item.draft)) != []
    assert main(["card", "check", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["problems"] == [message]


def test_load_runs_the_card_write_validator(world, capsys, monkeypatch):  # noqa: F811
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    monkeypatch.setattr(write, "check_document", lambda document: ["$.key: refused here"])

    assert main(["card", "preview", str(path)]) == 1

    out = capsys.readouterr().out
    assert out == "Nada foi enviado. Problemas encontrados:\n  c.md: $.key: refused here\n"
    assert pending_files() == []
    assert world.writes() == []


def test_preview_plan_validates_as_card_plan(world):  # noqa: F811
    drafts = prepare(world, list(DRAFTS))

    plan = card.preview_plan(str(drafts))

    assert contracts.validate(plan, "card-plan") == []
    assert write.check_document(plan) == []
    assert plan["tracker"] == "jira"
    assert plan["target"] == world.fake.site
    assert plan["today"] == "2026-10-27"
    assert [step["draft"]["path"] for step in plan["steps"]] == [
        str(drafts / f"{number}-{op}.md") for number, op in enumerate(DRAFTS, 1)
    ]
    assert plan["summary"][0] == "[1/7] Criar card (1-create.md)"
    assert all(step["problems"] == [] for step in plan["steps"])
    assert world.writes() == []


def test_preview_plan_code_is_the_pending_code(world, capsys):  # noqa: F811
    drafts = prepare(world, list(DRAFTS))

    plan = card.preview_plan(str(drafts))

    [record] = pending_files()
    saved = json.loads(record.read_text(encoding="utf-8"))
    assert record.name == f"{plan['code']}.json"
    assert saved["code"] == plan["code"] == write.plan_code(plan)
    expected = write.pending_record(plan, created_at=NOW.isoformat(), sid=saved["sid"])
    assert saved == expected
    _, printed = preview(drafts, capsys)
    assert printed == plan["code"]


def test_preview_plan_of_a_refused_draft_has_problems_and_no_code(world):  # noqa: F811
    path = create_draft(priority="Urgent")

    plan = card.preview_plan(str(path))

    assert contracts.validate(plan, "card-plan") == []
    assert "code" not in plan
    [step] = plan["steps"]
    assert step["problems"] and step["native"] == []
    assert pending_files() == []


def test_show_prints_the_card_write_of_a_draft(world):  # noqa: F811
    path = make_draft(
        "w.md", "worklog", "Revisão.\n", key="TS-101", time="1h 30m", day=date(2026, 10, 26)
    )

    document = card.show(str(path))

    assert document == {
        "$schema": "card-write",
        "version": 1,
        "op": "worklog",
        "day": "2026-10-26",
        "key": "TS-101",
        "time": "1h 30m",
        "body": "Revisão.",
    }
    assert write.check_document(document) == []
    assert world.fake.requests == []


def test_show_reads_only_drafts(world, tmp_path):  # noqa: F811
    outside = tmp_path / "x.md"
    outside.write_text('+++\nop = "move"\nkey = "TS-1"\nto = "X"\n+++\n', encoding="utf-8")
    broken = make_draft("b.md", "move", key="TS-101")

    with pytest.raises(DraftError, match="not a real file or folder inside"):
        card.show(str(outside))
    with pytest.raises(DraftError, match="missing key 'to'"):
        card.show(str(broken))


def test_apply_result_validates_as_card_result(world, capsys, monkeypatch):  # noqa: F811
    from ws.tracker.jira.adapter import JiraTracker

    drafts = prepare(world, list(DRAFTS))
    _, code = preview(drafts, capsys)
    seen: list[dict] = []
    real = JiraTracker.apply

    def recording(self, plan, send=None):
        for step in real(self, plan, send):
            seen.append(step)
            yield step

    monkeypatch.setattr(JiraTracker, "apply", recording)

    assert approve(drafts, code) == 0

    assert contracts.validate(_envelope(seen), "card-result") == []
    assert [step["status"] for step in seen] == ["applied"] * len(DRAFTS)
    assert [step["created"] for step in seen[:2]] == ["TS-200", "TS-200"]
    assert seen[2]["url"] == f"{world.fake.site}/browse/TS-101"
    assert sum(len(step["sent"]) for step in seen) == len(world.writes())


def test_apply_result_of_a_refused_write_validates_as_card_result(world, capsys, monkeypatch):  # noqa: F811
    from ws.tracker.jira.adapter import JiraTracker

    world.fake.routes[("PUT", "/rest/api/3/issue/TS-101")] = (400, '{"errors": {"x": "no"}}')
    path = make_draft("e.md", "edit", key="TS-101", priority="High")
    _, code = preview(path, capsys)
    seen: list[dict] = []
    real = JiraTracker.apply

    def recording(self, plan, send=None):
        for step in real(self, plan, send):
            seen.append(step)
            yield step

    monkeypatch.setattr(JiraTracker, "apply", recording)

    assert approve(path, code) == 3

    assert contracts.validate(_envelope(seen), "card-result") == []
    [step] = seen
    assert (step["status"], step["sent"], step["created"], step["url"]) == (
        "failed",
        [],
        None,
        None,
    )
    assert "o Jira recusou" in capsys.readouterr().out


def test_the_writer_of_the_jira_config_is_the_jira_tracker(world):  # noqa: F811
    writer = port.open_writer([])

    assert isinstance(writer, port.Writer)
    assert (writer.name, writer.target) == ("Jira", world.fake.site.rstrip("/"))
    assert writer.card_url("TS-1") == f"{world.fake.site}/browse/TS-1"


def test_open_writer_asks_only_the_config_the_drafts_need(world, ws_config):  # noqa: F811
    config = ws_config / "config.toml"
    config.write_text(config.read_text().replace("board_id = 7\n", ""), encoding="utf-8")
    move = card.load(make_draft("m.md", "move", key="TS-101", to="Em Andamento"))
    create = card.load(create_draft())

    assert port.open_writer([move.entry]).name == "Jira"
    with pytest.raises(port.TrackerSetup, match="board_id"):
        port.open_writer([move.entry, create.entry])


def test_card_core_builds_no_jira_request():
    source = Path(card.__file__).read_text(encoding="utf-8")

    assert "/rest/api" not in source
    assert "/browse/" not in source
    assert "cardrules" not in source
