"""What every `Writer` must do, checked on the Jira writer (through the fake Jira server) and on
the in-memory tracker, so the port is shown to be neutral."""

import fake_tracker
import pytest
from fake_tracker import FakeTracker, make_card
from test_card import (
    SPRINT_FIELD,
    claude_settings,  # noqa: F401
    folder_with_three,
    make_draft,
    pending_files,
    world,  # noqa: F401
)

from ws import card, contracts
from ws.cli import main
from ws.config import data_dir
from ws.tracker import ADAPTERS, port, write
from ws.tracker.errors import TrackerError


@pytest.fixture(params=["jira", "memory"])
def opened(request, world):  # noqa: F811
    """`opened(paths)` is the writer of the tracker under test, set up for those drafts."""
    if request.param == "jira":
        return lambda paths: port.open_writer([card.load(path).entry for path in paths])
    cards = [make_card("TS-101"), make_card("TS-102", assignee="acc-other")]
    return lambda paths: FakeTracker(cards, kind="memory")


def _entries(paths):
    return [card.load(path).entry for path in paths]


def _planned(opened, paths):
    writer = opened(paths)
    plan = writer.plan(_entries(paths))
    plan["summary"] = []
    return writer, plan


def _three():
    return sorted(folder_with_three().glob("*.md"))


def test_plan_is_a_valid_card_plan(opened):
    writer, plan = _planned(opened, _three())

    assert contracts.validate(plan, "card-plan") == []
    assert plan["tracker"] and plan["target"] == writer.target.rstrip("/")
    assert [step["problems"] for step in plan["steps"]] == [[], [], []]
    assert all(step["native"] for step in plan["steps"])
    assert [step["card"] for step in plan["steps"]] == ["TS-101"] * 3


def test_same_entries_give_the_same_code(opened):
    paths = _three()
    _, first = _planned(opened, paths)
    _, second = _planned(opened, paths)

    assert write.plan_code(first) == write.plan_code(second)
    assert write.calls(first) == write.calls(second)


def test_unknown_card_is_a_problem_not_a_call(opened):
    path = make_draft("1-comment.md", "comment", "Oi.\n", key="TS-999")

    _, plan = _planned(opened, [path])

    [step] = plan["steps"]
    assert step["problems"]
    assert step["native"] == []
    assert contracts.validate(plan, "card-plan") == []


def test_apply_yields_valid_card_result_steps(opened):
    paths = _three()
    writer, plan = _planned(opened, paths)

    steps = list(writer.apply(plan))

    assert (
        contracts.validate({"$schema": "card-result", "version": 1, "steps": steps}, "card-result")
        == []
    )
    assert [step["status"] for step in steps] == ["applied"] * 3
    assert [step["draft"] for step in steps] == [step["draft"] for step in plan["steps"]]
    assert [call for step in steps for call in step["sent"]] == write.calls(plan)
    assert all(step["url"] and "TS-101" in step["url"] for step in steps)


def test_apply_stops_at_the_first_failure(opened):
    writer, plan = _planned(opened, _three())
    seen = []

    def send(call):
        seen.append(call)
        if len(seen) == 2:
            raise TrackerError("refused")
        return writer.send(call)

    steps = list(writer.apply(plan, send))

    assert [step["status"] for step in steps] == ["applied", "failed"]
    assert steps[1]["error"] == "refused" and steps[1]["sent"] == []
    assert len(seen) == 2


@pytest.mark.parametrize(
    "error",
    [TrackerError("unsure", uncertain=True), RuntimeError("boom")],
    ids=["tracker", "plain"],
)
def test_apply_yields_uncertain_and_stops(opened, error):
    writer, plan = _planned(opened, _three())
    seen = []

    def send(call):
        seen.append(call)
        raise error

    steps = list(writer.apply(plan, send))

    assert [step["status"] for step in steps] == ["uncertain"]
    assert steps[0]["sent"] == [] and steps[0]["error"]
    assert len(seen) == 1


def test_guard_refuses_a_call_outside_the_plan(opened):
    writer, plan = _planned(opened, _three())
    own = write.calls(plan)
    stray = {**own[0], "path": "/admin/elsewhere"}

    assert writer.guard(own) is None
    assert writer.guard([*own, stray]) is not None


@pytest.mark.parametrize("markdown", ["texto simples\n", "## Contexto\n- um\n- dois\n", "a\x00b\n"])
def test_render_body_refuses_with_a_line_or_passes(opened, markdown):
    writer = opened([])

    try:
        rendered = writer.render_body(markdown)
    except ValueError as error:
        assert isinstance(error.line, int) and error.line >= 1
    else:
        assert rendered is not None


def test_card_url_contains_the_key(opened):
    assert "TS-101" in opened([]).card_url("TS-101")


def test_capabilities_are_known_names(opened):
    writer = opened([])

    assert writer.capabilities <= set(port.CAPABILITIES)
    assert isinstance(writer, port.Writer)


def test_the_memory_tracker_refuses_what_it_lacks_as_a_problem():
    path = make_draft("1-worklog.md", "worklog", key="TS-101", time="1h")
    tracker = FakeTracker([make_card("TS-101")], kind="memory", capabilities={"description"})

    [step] = tracker.plan(_entries([path]))["steps"]

    assert step["native"] == [] and "worklog" in step["problems"][0]


def test_preview_and_apply_run_on_the_memory_tracker(
    world,  # noqa: F811
    ws_config,
    monkeypatch,
    capsys,
):
    tracker = FakeTracker([make_card("TS-101")], kind="memory")
    monkeypatch.setitem(ADAPTERS, "memory", "fake_tracker")
    monkeypatch.setattr(fake_tracker, "INSTALLED", [tracker])
    settings = ws_config / "config.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8").replace('kind = "jira"', 'kind = "memory"'),
        encoding="utf-8",
    )
    drafts = folder_with_three()

    assert main(["card", "preview", str(drafts)]) == 0
    out = capsys.readouterr().out
    code = out.split("Código de aprovação: ")[1].split()[0]
    assert "nada foi enviado ao Memória" in out
    assert tracker.sent == [] and len(pending_files()) == 1

    assert main(["card", "apply", str(drafts), "--approve", code]) == 0

    assert [call["method"] for call in tracker.sent] == ["POST", "SET", "POST"]
    assert tracker.records["TS-101"]["priority"] == "High"
    assert world.writes() == []
    assert sorted(path.name for path in (data_dir() / "cards" / "done").glob("*.md")) == [
        "1-comment.md",
        "2-edit.md",
        "3-worklog.md",
    ]
    assert pending_files() == []


BOARD_SPRINTS = [
    {"id": 55, "name": "Sprint 55", "state": "active", "endDate": "2026-11-10T15:00:00.000Z"},
    {"id": 57, "name": "Sprint 57", "state": "future", "startDate": "2026-11-24T15:00:00.000Z"},
    {"id": 56, "name": "Sprint 56", "state": "future", "startDate": "2026-11-10T15:00:00.000Z"},
]


@pytest.fixture(params=["jira", "memory"])
def sprinted(request, world):  # noqa: F811
    """`opened`, with TS-101 in the active "Sprint 55" and "Sprint 56" and "Sprint 57" to come."""
    if request.param == "jira":
        world.set_sprints(BOARD_SPRINTS)
        closed = {"id": 54, "name": "Sprint 54", "state": "closed"}
        world.set_card("TS-101", fields={SPRINT_FIELD: [closed, BOARD_SPRINTS[0]]})
        return lambda paths: port.open_writer(_entries(paths))
    return lambda paths: FakeTracker([make_card("TS-101", sprint="Sprint 55")], kind="memory")


@pytest.mark.parametrize(
    "value, shown", [("backlog", "backlog"), ("next", "Sprint 56"), ("Sprint 57", "Sprint 57")]
)
def test_a_sprint_move_is_one_call_that_applies(sprinted, value, shown):
    path = make_draft("1-edit.md", "edit", key="TS-101", sprint=value)
    writer, plan = _planned(sprinted, [path])

    [step] = plan["steps"]
    assert contracts.validate(plan, "card-plan") == []
    assert step["problems"] == [] and len(step["native"]) == 1
    assert shown in " ".join(step["preview"])
    assert [result["status"] for result in writer.apply(plan)] == ["applied"]


def test_an_unknown_sprint_is_a_problem_naming_the_open_sprints(sprinted):
    path = make_draft("1-edit.md", "edit", key="TS-101", sprint="Sprint 54")
    _, plan = _planned(sprinted, [path])

    [step] = plan["steps"]
    assert step["native"] == []
    named = " ".join(step["problems"])
    assert "Sprint 54" in named
    assert all(name in named for name in ("Sprint 55", "Sprint 56", "Sprint 57"))


def test_the_backlog_for_a_card_in_no_sprint_is_a_problem(opened):
    path = make_draft("1-edit.md", "edit", key="TS-101", sprint="backlog")
    _, plan = _planned(opened, [path])

    [step] = plan["steps"]
    assert step["problems"] and step["native"] == []
