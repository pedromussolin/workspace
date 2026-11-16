import json
import time
from datetime import UTC, date, datetime

import pytest

from ws.cli import main
from ws.config import config_dir
from ws.standupreport import build_report
from ws.taskmodel import Status, Task

TODAY = date(2026, 10, 27)
JIRA_CONFIG = (
    '[tracker]\nkind = "jira"\n\n[tracker.jira]\n'
    'site = "https://example.atlassian.net"\nemail = "dev@example.com"\n'
)


def make_task(key: str, status: Status, title: str = "Titulo de exemplo", updated=None) -> Task:
    return Task(
        ref=f"jira:{key}",
        key=key,
        title=title,
        url=f"https://example.atlassian.net/browse/{key}",
        status=status,
        epic_key=None,
        epic_title=None,
        requested_by_other=False,
        updated=updated or datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
    )


def make_commit(sha: str, day: str, subject: str, keys: list[str], repo: str = "app") -> dict:
    return {"repo": repo, "sha": sha, "date": day, "subject": subject, "keys": keys}


def make_pr(number: int, keys: list[str], updated_at: str, merged: bool = True) -> dict:
    return {
        "repo": "app",
        "number": number,
        "title": f"PR {number}",
        "state": "merged" if merged else "open",
        "merged_at": updated_at if merged else None,
        "updated_at": updated_at,
        "url": f"https://example.com/app/pull/{number}",
        "keys": keys,
    }


def make_activity(**overrides) -> dict:
    activity = {
        "window": {"since": "2026-10-26", "until": "2026-10-27"},
        "commits": [],
        "branches": [],
        "prs": [],
        "last_activity": {},
        "next_steps": [],
        "warnings": [],
    }
    activity.update(overrides)
    return activity


def test_key_with_commits_and_merged_pr_is_one_entry_without_suggestion():
    commits = [make_commit(f"s{n}", "2026-10-26", f"passo {n}", ["TS-101"]) for n in range(7)]
    commits[3] = make_commit("s3", "2026-10-27", "passo recente", ["TS-101"])
    activity = make_activity(commits=commits, prs=[make_pr(7, ["TS-101"], "2026-10-26T12:00:00Z")])
    report = build_report(activity, [make_task("TS-101", Status.IN_PROGRESS)], TODAY, 3)
    assert report["tracker"] is True
    assert len(report["yesterday"]) == 1
    entry = report["yesterday"][0]
    assert entry["key"] == "TS-101"
    assert entry["commits"] == 7
    assert len(entry["subjects"]) == 5
    assert entry["subjects"][0] == "passo recente"
    assert entry["prs"] == [{"ref": "app#7", "state": "merged", "title": "PR 7"}]
    assert entry["status"] == "in_progress"
    assert entry["url"] == "https://example.atlassian.net/browse/TS-101"
    assert entry["suggestion"] is None
    assert [(e["key"], e["suggestion"]) for e in report["today"]] == [("TS-101", None)]


def test_pr_updated_in_window_without_commit_is_listed_and_older_is_not():
    activity = make_activity(
        prs=[
            make_pr(7, ["TS-101"], "2026-10-26T08:00:00Z", merged=False),
            make_pr(8, ["TS-102"], "2026-10-25T23:00:00Z", merged=False),
        ]
    )
    report = build_report(activity, [], TODAY, 3)
    assert [entry["key"] for entry in report["yesterday"]] == ["TS-101"]
    assert report["yesterday"][0]["commits"] == 0


def test_yesterday_is_ordered_by_latest_activity():
    activity = make_activity(
        commits=[
            make_commit("a", "2026-10-26", "um", ["TS-101"]),
            make_commit("b", "2026-10-27", "dois", ["TS-102"]),
        ]
    )
    report = build_report(activity, [], TODAY, 3)
    assert [entry["key"] for entry in report["yesterday"]] == ["TS-102", "TS-101"]


def test_key_without_card_takes_the_pr_title_or_null():
    activity = make_activity(
        commits=[make_commit("a", "2026-10-26", "ajuste", ["TS-102"])],
        prs=[make_pr(7, ["TS-101"], "2026-10-26T08:00:00Z", merged=False)],
    )
    report = build_report(activity, None, TODAY, 3)
    by_key = {entry["key"]: entry for entry in report["yesterday"]}
    assert by_key["TS-101"]["title"] == "PR 7"
    assert by_key["TS-102"]["title"] is None
    assert by_key["TS-101"]["status"] is None
    assert by_key["TS-101"]["url"] is None


def test_today_has_in_progress_and_named_todo_and_trims_next_steps():
    activity = make_activity(
        last_activity={"TS-101": "2026-10-26"},
        next_steps=[
            {"project": "proj-a", "text": "continuar TS-102 amanhã"},
            {"project": "proj-b", "text": "revisar o desenho"},
        ],
    )
    tasks = [
        make_task("TS-101", Status.IN_PROGRESS),
        make_task("TS-102", Status.TODO),
        make_task("TS-103", Status.TODO),
    ]
    report = build_report(activity, tasks, TODAY, 3)
    assert [(e["key"], e["next_step"]) for e in report["today"]] == [
        ("TS-101", None),
        ("TS-102", "continuar TS-102 amanhã"),
    ]
    assert report["next_steps"] == [{"project": "proj-b", "text": "revisar o desenho"}]


def test_stuck_card_is_a_blocker_and_not_in_today():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    tasks = [make_task("TS-101", Status.IN_PROGRESS, updated=old)]
    report = build_report(make_activity(), tasks, TODAY, 3)
    assert report["blockers"] == [
        {
            "key": "TS-101",
            "title": "Titulo de exemplo",
            "url": "https://example.atlassian.net/browse/TS-101",
            "updated": "2026-10-20",
            "workdays": 3,
            "kind": "stuck",
        }
    ]
    assert report["today"] == []


def test_board_move_without_activity_adds_a_today_entry():
    board = make_board(moves=[make_move("TS-101", to="in_progress", environment=None)])
    report = build_report(
        make_activity(), [make_task("TS-101", Status.TODO)], TODAY, 3, board=board
    )
    assert report["yesterday"] == []
    assert len(report["today"]) == 1
    assert report["today"][0]["suggestion"]["rule"] == "board"


def test_keyless_counts_commits_and_sorted_unique_repos():
    activity = make_activity(
        commits=[
            make_commit("a", "2026-10-26", "x", [], repo="zeta"),
            make_commit("b", "2026-10-26", "y", [], repo="alfa"),
            make_commit("c", "2026-10-26", "z", [], repo="zeta"),
            make_commit("d", "2026-10-26", "w", ["TS-101"], repo="beta"),
        ]
    )
    report = build_report(activity, None, TODAY, 3)
    assert report["keyless"] == {"commits": 3, "repos": ["alfa", "zeta"]}


def write_files(tmp_path, activity, cards=None):
    activity_file = tmp_path / "activity.json"
    activity_file.write_text(json.dumps(activity))
    args = ["standup", "report", "--activity", str(activity_file), "--today", "2026-10-27"]
    if cards is not None:
        cards_file = tmp_path / "cards.json"
        cards_file.write_text(json.dumps({"platform": "jira", "cards": cards}))
        args += ["--cards", str(cards_file)]
    return args


def test_cli_without_cards_needs_no_config(ws_config, tmp_path, capsys):
    activity = make_activity(commits=[make_commit("a", "2026-10-26", "ajuste", ["TS-101"])])
    code = main(write_files(tmp_path, activity))
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["tracker"] is False
    assert payload["today"] == [] and payload["blockers"] == []
    assert [entry["key"] for entry in payload["yesterday"]] == ["TS-101"]
    assert ", " not in out and ": " not in out


def test_cli_with_cards_and_config(ws_config, tmp_path, capsys):
    (config_dir() / "config.toml").write_text(JIRA_CONFIG, encoding="utf-8")
    card = {
        "key": "TS-101",
        "title": "Titulo de exemplo",
        "status_name": "In Progress",
        "status_category": "indeterminate",
        "epic_key": None,
        "epic_title": None,
        "reporter_is_me": True,
        "updated": "2026-10-26T09:00:00+00:00",
    }
    activity = make_activity(last_activity={"TS-101": "2026-10-26"})
    code = main(write_files(tmp_path, activity, [card]))
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["tracker"] is True
    assert [entry["key"] for entry in payload["today"]] == ["TS-101"]


def test_cli_with_cards_and_no_config_exits_2(ws_config, tmp_path, capsys):
    code = main(write_files(tmp_path, make_activity(), []))
    assert code == 2
    assert "config.toml" in capsys.readouterr().err


def test_cli_malformed_activity_exits_2_without_traceback(ws_config, tmp_path, capsys):
    activity_file = tmp_path / "activity.json"
    activity_file.write_text("{not json")
    assert main(["standup", "report", "--activity", str(activity_file)]) == 2
    assert "invalid input" in capsys.readouterr().err
    activity_file.write_text(json.dumps({"window": {"since": "2026-10-26"}}))
    assert main(["standup", "report", "--activity", str(activity_file)]) == 2
    err = capsys.readouterr().err
    assert "invalid input" in err and "Traceback" not in err
    assert main(["standup", "report", "--activity", str(tmp_path / "missing.json")]) == 2


def test_cli_malformed_card_exits_2(ws_config, tmp_path, capsys):
    (config_dir() / "config.toml").write_text(JIRA_CONFIG, encoding="utf-8")
    code = main(write_files(tmp_path, make_activity(), [{"key": "TS-101"}]))
    assert code == 2
    assert "card is missing" in capsys.readouterr().err


@pytest.fixture
def sao_paulo(monkeypatch):
    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_pr_window_starts_at_local_midnight_of_since(sao_paulo):
    activity = make_activity(
        prs=[
            make_pr(7, ["TS-101"], "2026-10-26T02:59:00Z", merged=False),
            make_pr(8, ["TS-102"], "2026-10-26T03:00:00Z", merged=False),
            make_pr(9, ["TS-103"], "2026-10-25T23:30:00-03:00", merged=False),
        ]
    )
    report = build_report(activity, None, TODAY, 3)
    assert [entry["key"] for entry in report["yesterday"]] == ["TS-102"]


def test_yesterday_orders_by_local_day_then_by_first_appearance(sao_paulo):
    activity = make_activity(
        commits=[
            make_commit("a", "2026-10-26", "um", ["TS-101"]),
            make_commit("b", "2026-10-27", "dois", ["TS-102"]),
        ],
        prs=[
            make_pr(7, ["TS-103"], "2026-10-26T12:00:00Z", merged=False),
            make_pr(8, ["TS-101"], "2026-10-26T12:00:00Z", merged=False),
            make_pr(9, ["TS-104"], "2026-10-27T01:00:00-03:00", merged=False),
            make_pr(10, ["TS-105"], "2026-10-27T01:00:00Z", merged=False),
        ],
    )
    report = build_report(activity, None, TODAY, 3)
    assert [entry["key"] for entry in report["yesterday"]] == [
        "TS-102",
        "TS-104",
        "TS-101",
        "TS-103",
        "TS-105",
    ]


def test_card_with_board_move_and_stale_update_gets_the_suggestion_and_no_blocker():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    tasks = [make_task("TS-101", Status.IN_PROGRESS, updated=old)]
    board = make_board(moves=[make_move("TS-101")])
    report = build_report(make_activity(), tasks, TODAY, 3, board=board)
    assert report["blockers"] == []
    assert [(e["key"], e["suggestion"]["rule"]) for e in report["today"]] == [("TS-101", "board")]


def test_card_key_repeated_in_tasks_gives_one_today_entry():
    task = make_task("TS-101", Status.IN_PROGRESS)
    report = build_report(make_activity(), [task, task], TODAY, 3)
    assert [entry["key"] for entry in report["today"]] == ["TS-101"]


def four_yesterday_activity():
    commits = [make_commit(f"s{n}", "2026-10-26", f"passo {n}", [f"TS-10{n}"]) for n in range(1, 5)]
    prs = [make_pr(9, ["TS-104"], "2026-10-26T12:00:00Z")]
    return make_activity(commits=commits, prs=prs)


def test_report_without_top_keeps_whole_lists_and_zero_more():
    tasks = [make_task("TS-104", Status.IN_PROGRESS)]
    board = make_board(moves=[make_move("TS-104")])
    report = build_report(four_yesterday_activity(), tasks, TODAY, 3, board=board)
    assert len(report["yesterday"]) == 4
    assert report["more"] == {"yesterday": 0, "today": 0}
    assert [move["key"] for move in report["moves"]] == ["TS-104"]


def test_report_top_cuts_yesterday_but_moves_keep_the_cut_suggestion():
    tasks = [make_task("TS-104", Status.IN_PROGRESS)]
    board = make_board(moves=[make_move("TS-104")])
    report = build_report(four_yesterday_activity(), tasks, TODAY, 3, top=2, board=board)
    assert [entry["key"] for entry in report["yesterday"]] == ["TS-101", "TS-102"]
    assert report["more"] == {"yesterday": 2, "today": 0}
    assert len(report["moves"]) == 1
    move = report["moves"][0]
    assert set(move) == {"key", "from", "to"}
    assert move["key"] == "TS-104"


def test_report_top_cuts_today_and_never_next_steps_or_blockers():
    tasks = [make_task(f"TS-20{n}", Status.IN_PROGRESS) for n in range(1, 4)]
    steps = [{"repo": "app", "text": "TS-299 revisar"}]
    report = build_report(make_activity(next_steps=steps), tasks, TODAY, 3, top=1)
    assert len(report["today"]) == 1
    assert report["more"] == {"yesterday": 0, "today": 2}
    assert report["next_steps"] == steps


def test_report_moves_is_empty_without_suggestions():
    report = build_report(make_activity(), None, TODAY, 3)
    assert report["moves"] == []


def test_cli_top_flag_and_invalid_values(ws_config, tmp_path, capsys):
    args = write_files(tmp_path, four_yesterday_activity())
    assert main([*args, "--top", "2"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["yesterday"]) == 2
    assert payload["more"] == {"yesterday": 2, "today": 0}
    for bad in ("0", "-1"):
        with pytest.raises(SystemExit) as error:
            main([*args, "--top", bad])
        assert error.value.code == 2


def test_blocked_card_is_a_confirmed_blocker_with_no_suggestion_and_not_in_today():
    activity = make_activity(
        commits=[make_commit("abc1234" * 5 + "abcde", "2026-10-26", "ajuste", ["TS-101"])],
        last_activity={"TS-101": "2026-10-26"},
    )
    tasks = [make_task("TS-101", Status.BLOCKED)]
    report = build_report(activity, tasks, TODAY, 3)
    assert report["blockers"] == [
        {
            "key": "TS-101",
            "title": "Titulo de exemplo",
            "url": "https://example.atlassian.net/browse/TS-101",
            "updated": "2026-10-26",
            "workdays": None,
            "kind": "blocked",
        }
    ]
    assert report["today"] == []
    assert report["moves"] == []


def test_review_and_ready_deploy_cards_are_in_today_without_suggestion():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    activity = make_activity(prs=[make_pr(7, ["TS-102"], "2026-10-24T12:00:00Z")])
    tasks = [
        make_task("TS-101", Status.REVIEW, updated=datetime(2026, 10, 26, 9, 0, tzinfo=UTC)),
        make_task("TS-102", Status.READY_DEPLOY, updated=old),
    ]
    report = build_report(activity, tasks, TODAY, 3)
    assert [(e["key"], e["status"], e["suggestion"]) for e in report["today"]] == [
        ("TS-101", "review", None),
        ("TS-102", "ready_deploy", None),
    ]
    assert report["blockers"] == []
    assert report["moves"] == []


def test_blockers_list_blocked_first_then_stuck_each_in_card_order():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    tasks = [
        make_task("TS-101", Status.IN_PROGRESS, updated=old),
        make_task("TS-102", Status.BLOCKED),
        make_task("TS-103", Status.REVIEW, updated=old),
        make_task("TS-104", Status.BLOCKED),
    ]
    report = build_report(make_activity(), tasks, TODAY, 3)
    assert [(b["key"], b["kind"]) for b in report["blockers"]] == [
        ("TS-102", "blocked"),
        ("TS-104", "blocked"),
        ("TS-101", "stuck"),
        ("TS-103", "stuck"),
    ]
    assert report["today"] == []


def make_board(**overrides) -> dict:
    board = {"moves": [], "held": [], "limited": [], "to_confirm": [], "warnings": []}
    board.update(overrides)
    return board


def make_move(key: str, to: str = "validation", environment: str | None = "dev") -> dict:
    return {
        "key": key,
        "title": "Titulo de exemplo",
        "from": "in_progress",
        "to": to,
        "to_name": "Validation",
        "environment": environment,
        "stale": False,
    }


def test_board_move_becomes_the_suggestion_with_its_environment_as_evidence():
    commits = [make_commit("abc1234", "2026-10-26", "ajuste", ["TS-101"])]
    board = make_board(moves=[make_move("TS-101")])
    report = build_report(
        make_activity(commits=commits),
        [make_task("TS-101", Status.IN_PROGRESS)],
        TODAY,
        3,
        board=board,
    )
    assert report["yesterday"][0]["suggestion"] == {
        "from": "in_progress",
        "to": "validation",
        "rule": "board",
        "evidence": "dev",
    }
    assert report["moves"] == [{"key": "TS-101", "from": "in_progress", "to": "validation"}]


def test_board_move_without_environment_has_commit_as_evidence():
    board = make_board(moves=[make_move("TS-101", to="in_progress", environment=None)])
    report = build_report(
        make_activity(), [make_task("TS-101", Status.TODO)], TODAY, 3, board=board
    )
    assert report["today"][0]["suggestion"]["evidence"] == "commit"


def test_board_wins_over_the_activity_rules():
    activity = make_activity(prs=[make_pr(7, ["TS-101"], "2026-10-26T12:00:00Z")])
    board = make_board(moves=[make_move("TS-101", to="ready_deploy", environment="prod")])
    report = build_report(
        activity, [make_task("TS-101", Status.IN_PROGRESS)], TODAY, 3, board=board
    )
    assert report["yesterday"][0]["suggestion"]["rule"] == "board"
    assert report["yesterday"][0]["suggestion"]["to"] == "ready_deploy"


def test_board_with_no_moves_drops_the_activity_suggestions():
    activity = make_activity(prs=[make_pr(7, ["TS-101"], "2026-10-26T12:00:00Z")])
    report = build_report(
        activity, [make_task("TS-101", Status.IN_PROGRESS)], TODAY, 3, board=make_board()
    )
    assert report["yesterday"][0]["suggestion"] is None
    assert report["moves"] == []


def test_board_moves_list_every_move_even_cut_by_top_or_not_shown():
    moves = [make_move(f"TS-10{n}") for n in range(1, 4)] + [make_move("TS-999")]
    commits = [make_commit(f"s{n}", "2026-10-26", "x", [f"TS-10{n}"]) for n in range(1, 4)]
    tasks = [make_task(f"TS-10{n}", Status.IN_PROGRESS) for n in range(1, 4)]
    report = build_report(
        make_activity(commits=commits), tasks, TODAY, 3, top=1, board=make_board(moves=moves)
    )
    assert len(report["yesterday"]) == 1
    assert [move["key"] for move in report["moves"]] == ["TS-101", "TS-102", "TS-103", "TS-999"]


def test_board_to_confirm_passes_through_and_warnings_follow_the_activity_ones():
    confirm = [{"key": "TS-105", "title": "Titulo de exemplo", "since": "2026-10-20"}]
    board = make_board(to_confirm=confirm, warnings=["fetch demo-api: boom"])
    report = build_report(make_activity(warnings=["a"]), None, TODAY, 3, board=board)
    assert report["to_confirm"] == confirm
    assert report["warnings"] == ["a", "fetch demo-api: boom"]


def test_report_without_board_has_empty_to_confirm():
    assert build_report(make_activity(), None, TODAY, 3)["to_confirm"] == []


def test_cli_board_flag_reads_the_file_and_rejects_bad_ones(ws_config, tmp_path, capsys):
    args = write_files(tmp_path, make_activity())
    board_file = tmp_path / "board.json"
    board_file.write_text(json.dumps(make_board(warnings=["w"])))
    assert main([*args, "--board", str(board_file)]) == 0
    assert json.loads(capsys.readouterr().out)["warnings"] == ["w"]
    board_file.write_text("{}")
    assert main([*args, "--board", str(board_file)]) == 2
    assert "invalid input" in capsys.readouterr().err
    board_file.write_text("not json")
    assert main([*args, "--board", str(board_file)]) == 2
    assert "invalid input" in capsys.readouterr().err
