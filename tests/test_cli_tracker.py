import ast
import json
from pathlib import Path

import pytest
from test_card import claude_settings, create_draft, make_draft, pending_files, world  # noqa: F401
from test_jira import CARD, REST_ISSUE

import ws.cli
from ws import contracts, tracker
from ws.cli import main


def test_task_list_output_unchanged_through_the_facade(world, capsys):  # noqa: F811
    world.fake.pages = {None: {"issues": [REST_ISSUE], "isLast": True}}

    assert main(["task", "list", "--since", "2026-10-23"]) == 0

    expected = {"platform": "jira", "role": "mine", "cards": [CARD]}
    assert capsys.readouterr().out == json.dumps(expected, ensure_ascii=False, indent=2) + "\n"


def test_task_list_without_config_is_a_setup_problem(ws_config, capsys):
    assert main(["task", "list"]) == 2
    assert capsys.readouterr().err.startswith("ws task list: ")


def test_card_show_prints_a_valid_card_write(world, capsys):  # noqa: F811
    path = make_draft(
        "w.md", "worklog", "Revisão.\n", key="TS-101", time="1h 30m", day="2026-10-26"
    )

    assert main(["card", "show", str(path)]) == 0

    document = json.loads(capsys.readouterr().out)
    assert document["$schema"] == "card-write"
    assert contracts.validate(document, "card-write") == []
    assert world.fake.requests == []


def test_card_show_of_a_bad_draft_is_exit_1(world, capsys):  # noqa: F811
    path = make_draft("bad.md", "bogus")

    assert main(["card", "show", str(path)]) == 1
    assert capsys.readouterr().out == ""


def test_preview_json_prints_a_valid_card_plan(world, capsys):  # noqa: F811
    path = create_draft()

    assert main(["card", "preview", "--json", str(path)]) == 0

    plan = json.loads(capsys.readouterr().out)
    assert contracts.validate(plan, "card-plan") == []
    assert plan["summary"]
    [record] = pending_files()
    assert record.name == f"{plan['code']}.json"


def test_preview_json_writes_the_same_pending_record(world, capsys):  # noqa: F811
    path = create_draft()

    assert main(["card", "preview", str(path)]) == 0
    plain_code = capsys.readouterr().out.split()[-1]
    [plain] = pending_files()
    plain_record = json.loads(plain.read_text(encoding="utf-8"))
    plain.unlink()

    assert main(["card", "preview", "--json", str(path)]) == 0
    plan = json.loads(capsys.readouterr().out)

    [record] = pending_files()
    assert plan["code"] == plain_code
    saved = json.loads(record.read_text(encoding="utf-8"))
    assert {**saved, "sid": None} == {**plain_record, "sid": None}


def test_preview_json_keeps_the_exit_status_of_a_refused_draft(world, capsys):  # noqa: F811
    path = create_draft(priority="Urgent")

    plain = main(["card", "preview", str(path)])
    capsys.readouterr()
    as_json = main(["card", "preview", "--json", str(path)])

    assert plain != 0
    assert as_json == plain
    assert pending_files() == []


def test_cli_names_no_jira_module():
    tree = ast.parse(Path(ws.cli.__file__).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.alias):
            names.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)

    assert not [name for name in names if "jira" in name]


@pytest.fixture
def other_kind(world, ws_config):  # noqa: F811
    path = ws_config / "config.toml"
    path.write_text('[tracker]\nkind = "monday"\n' + path.read_text(encoding="utf-8"))


def _inputs(tmp_path):
    cards = tmp_path / "cards.json"
    cards.write_text(json.dumps({"cards": [CARD]}), encoding="utf-8")
    activity = tmp_path / "activity.json"
    activity.write_text(json.dumps({"repos": [], "warnings": []}), encoding="utf-8")
    return cards, activity


def test_task_list_refuses_an_unknown_kind(other_kind, capsys):
    assert main(["task", "list"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("ws task list: ") and "monday" in err and "Traceback" not in err


def test_task_status_refuses_an_unknown_kind(other_kind, tmp_path, capsys):
    cards, activity = _inputs(tmp_path)

    assert main(["task", "status", "--cards", str(cards), "--activity", str(activity)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("ws task status: ") and "monday" in err and "Traceback" not in err


def test_standup_report_refuses_an_unknown_kind(other_kind, tmp_path, capsys):
    cards, activity = _inputs(tmp_path)

    assert main(["standup", "report", "--cards", str(cards), "--activity", str(activity)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("ws standup report: ") and "monday" in err and "Traceback" not in err


def test_task_roles_are_defined_once_in_the_neutral_layer():
    from ws.tracker.jira import client

    assert set(client._ROLE_JQL) == set(tracker.ROLES)
    parser = ws.cli.build_parser()
    args = parser.parse_args(["task", "list", "--role", "following"])
    assert args.role in tracker.ROLES
