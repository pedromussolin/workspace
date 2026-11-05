import tomllib
from datetime import date, datetime
from pathlib import Path

from ws.boardconfig import parse_board
from ws.boardrules import plan_moves
from ws.codeposition import Holding, Position
from ws.taskmodel import Status, Task

CFG = parse_board(
    tomllib.loads(
        """
[board]
[[board.environments]]
name = "sandbox"
branches = ["sandbox"]
status = "validation"

[[board.environments]]
name = "master"
branches = ["master"]
status = "ready_deploy"

[[board.environments]]
name = "production"
status = "done"
deploy_repo = "{repo}-argocd"
deploy_branch = "master"
image_tag = 'prod-([0-9a-f]{7,40})'

[board.statuses]
in_progress = "Em andamento"
validation = "In Validation"
ready_deploy = "Ready Deploy"
done = "Concluído"
"""
    )["board"],
    Path("config.toml"),
)
TODAY = date(2026, 11, 5)


def task(key, status, **kw):
    return Task(
        ref=key,
        key=key,
        title=f"title {key}",
        url=f"https://example.com/{key}",
        status=status,
        epic_key=kw.pop("epic_key", None),
        epic_title=None,
        requested_by_other=False,
        updated=kw.pop("updated", datetime(2026, 11, 1, 10, 0)),
        **kw,
    )


def pos(rung, environment=None, holding=None, stale=False, limited=False):
    return Position(rung, environment, holding, ("demo-api",), stale, limited)


def plan(tasks, positions):
    return plan_moves(tasks, positions, CFG, TODAY)


def test_todo_with_code_in_progress_moves():
    out = plan([task("TS-101", Status.TODO)], {"TS-101": pos(1)})
    assert out["moves"] == [
        {
            "key": "TS-101",
            "title": "title TS-101",
            "from": "todo",
            "to": "in_progress",
            "to_name": "Em andamento",
            "environment": None,
            "stale": False,
        }
    ]


def test_in_progress_with_production_moves_to_done():
    out = plan([task("TS-101", Status.IN_PROGRESS)], {"TS-101": pos(4, "production")})
    assert out["moves"][0]["to"] == "done"
    assert out["moves"][0]["to_name"] == "Concluído"
    assert out["moves"][0]["environment"] == "production"


def test_review_with_sandbox_moves_to_validation():
    out = plan([task("TS-101", Status.REVIEW)], {"TS-101": pos(2, "sandbox")})
    assert out["moves"][0]["from"] == "review"
    assert out["moves"][0]["to"] == "validation"


def test_same_rung_does_not_move():
    out = plan([task("TS-101", Status.VALIDATION)], {"TS-101": pos(2, "sandbox")})
    assert out["moves"] == []


def test_never_goes_back():
    out = plan([task("TS-101", Status.READY_DEPLOY)], {"TS-101": pos(2, "sandbox")})
    assert out["moves"] == []


def test_blocked_cancelled_done_and_epic_are_skipped():
    tasks = [
        task("TS-101", Status.BLOCKED),
        task("TS-102", Status.CANCELLED),
        task("TS-103", Status.DONE),
        task("TS-104", Status.TODO, is_epic=True),
    ]
    positions = {t.key: pos(4, "production", limited=True) for t in tasks}
    out = plan(tasks, positions)
    assert out == {"moves": [], "held": [], "limited": [], "to_confirm": []}


def test_key_that_is_epic_of_another_task_is_skipped():
    tasks = [task("TS-100", Status.TODO), task("TS-101", Status.TODO, epic_key="TS-100")]
    out = plan(tasks, {"TS-100": pos(4, "production"), "TS-101": pos(1)})
    assert [m["key"] for m in out["moves"]] == ["TS-101"]


def test_key_without_position_does_not_move():
    assert plan([task("TS-101", Status.TODO)], {})["moves"] == []


def test_moves_follow_task_order_and_copy_stale():
    tasks = [task("TS-102", Status.TODO), task("TS-101", Status.TODO)]
    out = plan(tasks, {"TS-101": pos(1, stale=True), "TS-102": pos(1)})
    assert [(m["key"], m["stale"]) for m in out["moves"]] == [("TS-102", False), ("TS-101", True)]


def test_held_lists_card_kept_by_a_commit_outside_environments():
    holding = Holding("demo-api", "abc1234", "TS-101 wip", None, "feature/x", tag="v1")
    out = plan([task("TS-101", Status.IN_PROGRESS)], {"TS-101": pos(1, holding=holding)})
    assert out["moves"] == []
    assert out["held"] == [
        {
            "key": "TS-101",
            "title": "title TS-101",
            "status": "in_progress",
            "holding": {
                "repo": "demo-api",
                "commit": "abc1234",
                "subject": "TS-101 wip",
                "reached": None,
                "branch": "feature/x",
                "tag": None,
            },
        }
    ]


def test_held_keeps_tag_when_commit_reached_an_environment():
    holding = Holding("demo-api", "abc1234", "TS-101 x", "sandbox", "sandbox", tag="v1")
    out = plan([task("TS-101", Status.IN_PROGRESS)], {"TS-101": pos(1, holding=holding)})
    assert out["held"][0]["holding"]["tag"] == "v1"


def test_moved_card_is_not_held():
    holding = Holding("demo-api", "abc1234", "TS-101 x", None, "feature/x")
    out = plan([task("TS-101", Status.TODO)], {"TS-101": pos(1, holding=holding)})
    assert len(out["moves"]) == 1
    assert out["held"] == []


def test_limited_position_lists_card_with_what_it_proves():
    out = plan([task("TS-101", Status.IN_PROGRESS)], {"TS-101": pos(3, "master", limited=True)})
    assert out["moves"][0]["to"] == "ready_deploy"
    assert out["limited"] == [
        {
            "key": "TS-101",
            "title": "title TS-101",
            "status": "in_progress",
            "proves": "ready_deploy",
            "repos": ["demo-api"],
        }
    ]


def test_to_confirm_lists_validation_card_updated_on_previous_workday():
    yesterday = task("TS-101", Status.VALIDATION, updated=datetime(2026, 11, 4, 9, 0))
    today = task("TS-102", Status.VALIDATION, updated=datetime(2026, 11, 5, 9, 0))
    out = plan([yesterday, today], {})
    assert out["to_confirm"] == [{"key": "TS-101", "title": "title TS-101", "since": "2026-11-04"}]


def test_to_confirm_ignores_other_statuses_and_epics():
    old = datetime(2026, 10, 1)
    tasks = [
        task("TS-101", Status.IN_PROGRESS, updated=old),
        task("TS-102", Status.VALIDATION, updated=old, is_epic=True),
        task("TS-103", Status.VALIDATION, updated=old),
    ]
    out = plan(tasks, {})
    assert [c["key"] for c in out["to_confirm"]] == ["TS-103"]
