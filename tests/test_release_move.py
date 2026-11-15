import argparse
import itertools
import json
import shutil
from datetime import UTC, datetime

import pytest
from fake_gh import fake_gh  # noqa: F401
from release_helpers import DAY, fixed_today, world  # noqa: F401, F811
from test_release_plan import HOOKS_COPY, write_settings

from ws.release import gitops, move
from ws.release import plan as writeplan
from ws.release.github import Gh
from ws.release.settings import load_release_config

pytest_plugins = ["release_helpers"]

NEW = "20261121"
REASON = "atraso na homologação"
NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
A, B = "acme/repo-a", "acme/repo-b"


@pytest.fixture
def ready(world, fake_gh, fixed_today, tmp_path, monkeypatch):  # noqa: F811
    settings = tmp_path / "claude-settings.json"
    write_settings(settings)
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(settings))
    monkeypatch.setenv("WS_CLAUDE_HOOKS_DIR", HOOKS_COPY)
    monkeypatch.setattr(writeplan, "now", lambda: NOW)
    sessions = itertools.count(1000)
    monkeypatch.setattr(writeplan, "session_id", lambda: next(sessions))
    world.gh = fake_gh
    return world


def publish_branches(ready, day=DAY, repos=("repo-a",), sdbx=True):
    for name in repos:
        ready.branch(name, f"release/{day}", "origin/master")
        ready.commit(name, f"release/{day}", "code.txt", "code\n", "feat: codigo")
        if sdbx:
            ready.branch(name, f"release/{day}-sdbx", "origin/sandbox")
            ready.commit(name, f"release/{day}-sdbx", "sdbx.txt", "sdbx\n", "feat: sdbx")
        ready.git(name, "checkout", "-q", "master")


def release_file(ready, day=DAY, b_multi=False):
    include = {
        "repo-a": ["feature/TS-101-one", "feature/TS-102-two"],
        "repo-b": ["feature/TS-201-only", "feature/TS-202-b"]
        if b_multi
        else ["feature/TS-201-only"],
    }
    ready.write_release(include, day=day)


def args(old=DAY, new=NEW, reason=REASON, approve=None, delete=False):
    return argparse.Namespace(
        project="demo",
        old=old,
        new=new,
        reason=reason,
        delete_old_branches=delete,
        approve=approve,
    )


def preview(capsys, **kwargs):
    code = move.run_preview(args(**kwargs))
    out = capsys.readouterr()
    return code, (json.loads(out.out) if out.out.strip() else {})


def run(capsys, **kwargs):
    code, payload = preview(capsys, **kwargs)
    assert code == 0, payload
    moved = move.run_move(args(approve=payload["code"], **kwargs))
    out = capsys.readouterr()
    return moved, (json.loads(out.out) if out.out.strip() else {})


def standard(ready, day=DAY):
    release_file(ready, day)
    publish_branches(ready, day)
    ready.gh.add_pr(
        A,
        70,
        f"release/{day}",
        "master",
        title=f"Release {day}",
        body="Depende de #73 e #730, veja acme/repo-a#73.\nRelease: 20/11/2026\n",
        labels=("release",),
        assignees=("dev1",),
    )
    ready.gh.add_pr(
        A, 73, f"release/{day}-sdbx", "sandbox", title=f"Sandbox {day}", body="sandbox\n"
    )


def new_prs(gh, slug):
    return [pr for pr in gh.prs(slug) if pr["headRefName"] == f"release/{NEW}"]


def creates(gh, slug):
    return [call for call in gh.writes if call[:2] == ["pr", "create"] and slug in call]


def test_move_copies_branches_with_the_same_commit(ready, capsys):
    standard(ready)
    code, _ = run(capsys)
    assert code == 0
    refs = ready.refs("repo-a")
    for suffix in ("", "-sdbx"):
        assert (
            refs[f"refs/heads/release/{NEW}{suffix}"] == refs[f"refs/heads/release/{DAY}{suffix}"]
        )


def test_move_replaces_with_word_boundaries(ready, capsys):
    standard(ready)
    run(capsys)
    created = [pr for pr in ready.gh.prs(A) if pr["headRefName"] == f"release/{NEW}"][0]
    assert created["title"] == f"Release {NEW}"
    assert "#730" in created["body"]
    assert "acme/repo-a#75" in created["body"]
    assert "#73 " not in created["body"] and "#73." not in created["body"]
    assert "Release: 21/11/2026" in created["body"]
    assert "Release: 20/11/2026" not in created["body"]


def test_move_copies_labels_and_assignees(ready, capsys):
    standard(ready)
    run(capsys)
    created = [pr for pr in ready.gh.prs(A) if pr["headRefName"] == f"release/{NEW}"][0]
    assert [item["name"] for item in created["labels"]] == ["release"]
    assert [item["login"] for item in created["assignees"]] == ["dev1"]


def test_move_closes_the_old_pr_after_the_new_exists(ready, capsys):
    standard(ready)
    run(capsys)
    writes = ready.gh.writes
    kinds = [
        call[:2] + [call[2]] for call in writes if call[:2] in (["pr", "create"], ["pr", "close"])
    ]
    create_at = next(i for i, call in enumerate(writes) if call[:2] == ["pr", "create"])
    close_at = next(i for i, call in enumerate(writes) if call[:3] == ["pr", "close", "70"])
    assert create_at < close_at, kinds
    comment = writes[close_at][writes[close_at].index("--comment") + 1]
    assert comment == (
        f"Substituído por https://github.com/{A}/pull/74: "
        f"a release passou a ser a de 21/11/2026, {REASON}."
    )
    states = {pr["number"]: pr["state"] for pr in ready.gh.prs(A)}
    assert states[70] == "CLOSED" and states[73] == "CLOSED"


def test_move_merged_sandbox_pr_is_commented_not_recreated(ready, capsys):
    release_file(ready)
    publish_branches(ready, sdbx=False)
    ready.branch("repo-a", f"release/{DAY}-sdbx", "origin/sandbox")
    ready.git("repo-a", "checkout", "-q", "master")
    ready.gh.add_pr(
        A,
        80,
        f"release/{DAY}-sdbx",
        "sandbox",
        state="MERGED",
        merged_at="2026-11-12T10:00:00Z",
    )
    code, _ = run(capsys)
    assert code == 0
    assert [call for call in ready.gh.writes if call[:2] == ["pr", "create"]] == []
    comment = [call for call in ready.gh.writes if call[:3] == ["pr", "comment", "80"]]
    assert comment[0][-1] == f"A release passou a ser a de 21/11/2026, {REASON}."


def test_move_merged_sandbox_pr_is_recreated_when_the_branch_grew(ready, capsys):
    release_file(ready)
    publish_branches(ready)
    ready.gh.add_pr(
        A,
        80,
        f"release/{DAY}-sdbx",
        "sandbox",
        state="MERGED",
        merged_at="2026-11-12T10:00:00Z",
        title=f"Sandbox {DAY}",
    )
    code, _ = run(capsys)
    assert code == 0
    new = [pr for pr in ready.gh.prs(A) if pr["headRefName"] == f"release/{NEW}-sdbx"]
    assert len(new) == 1 and new[0]["baseRefName"] == "sandbox"
    assert new[0]["title"] == f"Sandbox {NEW}"
    assert any(call[:3] == ["pr", "comment", "80"] for call in ready.gh.writes)


def test_move_single_branch_only_edits_the_release_line(ready, capsys):
    release_file(ready)
    publish_branches(ready)
    ready.gh.add_pr(
        B,
        5,
        "feature/TS-201-only",
        "master",
        title="Release 20261120",
        body="Release: 20/11/2026\n\ntexto 20/11/2026\n",
    )
    before = ready.refs("repo-b")
    code, _ = run(capsys)
    assert code == 0
    assert ready.refs("repo-b") == before
    assert creates(ready.gh, B) == []
    edits = [call for call in ready.gh.writes if call[:2] == ["pr", "edit"] and B in call]
    assert len(edits) == 1
    assert ready.gh.bodies[5] == "Release: 21/11/2026\n\ntexto 20/11/2026\n"
    assert ready.gh.prs(B)[0]["title"] == "Release 20261120"


def test_move_lists_residual_dates(ready, capsys):
    standard(ready)
    ready.gh.add_pr(
        B, 5, "feature/TS-201-only", "master", body="Release: 20/11/2026\n\nrevisão de 20/11\n"
    )
    code, payload = preview(capsys)
    assert code == 0
    assert all(
        item["text"] != "Release: 20/11/2026"
        for item in payload["residual_dates"]
        if item["repo"] == "repo-a"
    )
    assert {"repo": "repo-b", "pr": 5, "text": "revisão de 20/11"} in payload["residual_dates"]


def test_move_refuses_when_new_is_taken_in_one_repo(ready, fake_gh, capsys):  # noqa: F811
    release_file(ready, b_multi=True)
    publish_branches(ready, repos=("repo-a", "repo-b"))
    ready.branch("repo-b", f"release/{NEW}", "origin/master")
    ready.git("repo-b", "checkout", "-q", "master")
    before = ready.refs("repo-a")
    code, _ = preview(capsys)
    assert code == 1
    assert fake_gh.writes == []
    assert ready.refs("repo-a") == before
    assert list(writeplan.store().glob("*.json")) == []


@pytest.mark.parametrize("day", ["20261112", DAY])
def test_move_refuses_a_past_new_or_the_same_day(ready, day, capsys):
    standard(ready)
    code, _ = preview(capsys, new=day)
    assert code == 1
    assert ready.gh.writes == []


def test_move_refuses_a_missing_release_folder(ready, capsys):
    code, _ = preview(capsys, old="20261125", new="20261126")
    assert code == 2


def test_move_failure_in_the_second_repo_then_rerun_finishes(ready, capsys):
    release_file(ready, b_multi=True)
    publish_branches(ready, repos=("repo-a", "repo-b"))
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", title=f"R {DAY}")
    ready.gh.add_pr(B, 30, f"release/{DAY}", "master", title=f"R {DAY}")
    ready.gh.fail("pr create", "HTTP 422", repo=B)
    code, payload = run(capsys)
    assert code == 1 and payload["failed"]
    assert len(new_prs(ready.gh, A)) == 1 and new_prs(ready.gh, B) == []
    assert f"refs/heads/release/{NEW}" in ready.refs("repo-b")
    ready.gh.clear_failures()
    before = len(ready.gh.writes)
    code, payload = run(capsys)
    assert code == 0
    assert len(new_prs(ready.gh, A)) == 1 and len(new_prs(ready.gh, B)) == 1
    later = ready.gh.writes[before:]
    assert all(call[:2] != ["pr", "create"] or B in call for call in later)
    assert {pr["number"]: pr["state"] for pr in ready.gh.prs(B)}[30] == "CLOSED"


def test_move_gate_cases(ready, monkeypatch, capsys):
    standard(ready)
    code, payload = preview(capsys)
    assert code == 0
    wrong = "0" * 12
    assert move.run_move(args(approve=wrong)) == 1
    capsys.readouterr()
    assert ready.gh.writes == []
    monkeypatch.setattr(writeplan, "session_id", lambda: 7)
    code, payload = preview(capsys)
    assert code == 0
    assert move.run_move(args(approve=payload["code"])) == 1
    assert capsys.readouterr().err
    assert ready.gh.writes == []


def test_move_from_a_past_date_is_allowed(ready, capsys):
    standard(ready, day="20261110")
    code, _ = run(capsys, old="20261110")
    assert code == 0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("veja #73", "veja {pr:r-73}"),
        ("veja #730", "veja #730"),
        ("acme/repo-a#73.", "{pr:r-73}."),
        ("acme/repo-b#73", "acme/repo-b#73"),
        ("a#73", "a#73"),
    ],
)
def test_replace_numbers(text, expected):
    assert move.replace_numbers(text, {(A, 73): "r-73"}, A) == expected


def test_residual_dates_forms():
    text = "Release: 20/11/2026\nem 20/11\nem 20/11/2025\n21/11\n"
    assert move.residual_dates(text, "20261120") == ["Release: 20/11/2026", "em 20/11"]


def new_of(gh, slug, head):
    return [pr for pr in gh.prs(slug) if pr["headRefName"] == head and pr["state"] == "OPEN"][0]


def two_repos(ready, a_body="a\n", b_body="b\n"):
    release_file(ready, b_multi=True)
    publish_branches(ready, repos=("repo-a", "repo-b"))
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", title=f"R {DAY}", body=a_body)
    ready.gh.add_pr(B, 30, f"release/{DAY}", "master", title=f"R {DAY}", body=b_body)


def test_rerun_fixes_a_backward_reference(ready, capsys):
    two_repos(ready, b_body="Depende de acme/repo-a#70\n")
    ready.gh.fail("pr create", "HTTP 422", repo=B)
    assert run(capsys)[0] == 1
    ready.gh.clear_failures()
    assert run(capsys)[0] == 0
    number = new_of(ready.gh, A, f"release/{NEW}")["number"]
    assert new_of(ready.gh, B, f"release/{NEW}")["body"] == f"Depende de acme/repo-a#{number}\n"


def test_rerun_fixes_a_forward_reference(ready, capsys):
    two_repos(ready, a_body="Depende de acme/repo-b#30\n")
    ready.gh.fail("pr create", "HTTP 422", repo=B)
    assert run(capsys)[0] == 1
    assert "{pr:" in new_of(ready.gh, A, f"release/{NEW}")["body"]
    ready.gh.clear_failures()
    assert run(capsys)[0] == 0
    number = new_of(ready.gh, B, f"release/{NEW}")["number"]
    assert new_of(ready.gh, A, f"release/{NEW}")["body"] == f"Depende de acme/repo-b#{number}\n"


def test_rerun_after_a_failed_close_fixes_the_reference_in_the_repo(ready, capsys):
    standard(ready)
    ready.gh.fail("pr close", "HTTP 422", repo=A)
    assert run(capsys)[0] == 1
    ready.gh.clear_failures()
    assert run(capsys)[0] == 0
    body = new_of(ready.gh, A, f"release/{NEW}")["body"]
    assert "{pr:" not in body
    assert f"acme/repo-a#{new_of(ready.gh, A, f'release/{NEW}-sdbx')['number']}" in body
    assert {pr["number"]: pr["state"] for pr in ready.gh.prs(A)}[70] == "CLOSED"


def test_move_back_creates_new_prs_instead_of_reusing_closed_ones(ready, capsys):
    standard(ready)
    assert run(capsys)[0] == 0
    assert run(capsys, old=NEW, new=DAY)[0] == 0
    states = {pr["number"]: pr["state"] for pr in ready.gh.prs(A)}
    assert states[74] == states[75] == "CLOSED"
    assert new_of(ready.gh, A, f"release/{DAY}")["number"] > 75
    assert new_of(ready.gh, A, f"release/{DAY}-sdbx")["number"] > 75


def test_calls_follow_the_config_order_not_the_release_file(ready, capsys):
    ready.write_release(
        {
            "repo-b": ["feature/TS-201-only", "feature/TS-202-b"],
            "repo-a": ["feature/TS-101-one", "feature/TS-102-two"],
        }
    )
    publish_branches(ready, repos=("repo-a", "repo-b"))
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", title=f"R {DAY}")
    ready.gh.add_pr(B, 30, f"release/{DAY}", "master", title=f"R {DAY}")
    code, payload = preview(capsys)
    assert code == 0
    assert payload["calls"][0].startswith("repo-a:")


def comments_of(gh, slug, number):
    return [
        c["body"] for pr in gh.prs(slug) if pr["number"] == number for c in pr.get("comments", [])
    ]


def test_merged_comment_survives_a_failure_and_is_not_repeated(ready, capsys):
    two_repos(ready)
    merged = {"state": "MERGED", "merged_at": "2026-11-12T10:00:00Z"}
    ready.gh.add_pr(A, 80, f"release/{DAY}-sdbx", "sandbox", **merged)
    ready.gh.add_pr(B, 81, f"release/{DAY}-sdbx", "sandbox", **merged)
    ready.gh.fail("pr create", "HTTP 422", repo=B)
    assert run(capsys)[0] == 1
    text = f"A release passou a ser a de 21/11/2026, {REASON}."
    assert comments_of(ready.gh, A, 80) == [text]
    assert comments_of(ready.gh, B, 81) == []
    ready.gh.clear_failures()
    assert run(capsys)[0] == 0
    assert comments_of(ready.gh, A, 80) == [text]
    assert comments_of(ready.gh, B, 81) == [text]


def test_merged_pr_with_a_deleted_head_still_gets_the_comment(ready, capsys):
    release_file(ready)
    publish_branches(ready, sdbx=False)
    ready.gh.add_pr(
        A, 80, f"release/{DAY}-sdbx", "sandbox", state="MERGED", merged_at="2026-11-12T10:00:00Z"
    )
    assert run(capsys)[0] == 0
    assert comments_of(ready.gh, A, 80) == [f"A release passou a ser a de 21/11/2026, {REASON}."]


def test_fetch_runs_first_and_a_failure_is_a_warning(ready, capsys):
    release_file(ready)
    publish_branches(ready, sdbx=False)
    ready.git("repo-a", "update-ref", "-d", f"refs/remotes/origin/release/{DAY}")
    code, payload = preview(capsys)
    assert code == 0 and payload["warnings"] == []
    assert any(f"release/{DAY}:refs/heads/release/{NEW}" in call for call in payload["calls"])
    ready.git("repo-a", "remote", "set-url", "origin", "/nonexistent/origin.git")
    code, payload = preview(capsys)
    assert code == 0
    assert any(w.startswith("repo-a: fetch failed") for w in payload["warnings"])


def test_move_refuses_when_the_new_folder_exists(ready, capsys):
    standard(ready)
    ready.release_dir(NEW).mkdir(parents=True)
    (ready.release_dir(NEW) / "anotacoes.txt").write_text("de outra pessoa\n")
    code, _ = preview(capsys)
    assert code == 1 and ready.gh.writes == []


def test_move_refuses_a_foreign_open_pr_from_the_new_branch(ready, capsys):
    release_file(ready)
    publish_branches(ready, sdbx=False)
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master")
    ready.gh.add_pr(A, 90, f"release/{NEW}", "sandbox")
    code, _ = preview(capsys)
    assert code == 1 and ready.gh.writes == []


def test_move_refuses_a_local_new_branch_alone(ready, capsys):
    standard(ready)
    ready.git("repo-a", "branch", f"release/{NEW}", "origin/master")
    code, _ = preview(capsys)
    assert code == 1 and ready.gh.writes == []
    assert f"refs/heads/release/{NEW}" not in ready.refs("repo-a")


def test_single_branch_pr_without_a_release_line_is_reported(ready, capsys):
    standard(ready)
    ready.gh.add_pr(B, 5, "feature/TS-201-only", "master", body="sem linha\n")
    code, payload = preview(capsys)
    assert code == 0
    assert any("repo-b: PR #5 has no Release: line" in w for w in payload["warnings"])
    assert not any("pr edit 5" in call for call in payload["calls"])


def test_residual_dates_scan_the_recreated_merged_sandbox_pr(ready, capsys):
    release_file(ready)
    publish_branches(ready)
    ready.gh.add_pr(
        A,
        80,
        f"release/{DAY}-sdbx",
        "sandbox",
        state="MERGED",
        merged_at="2026-11-12T10:00:00Z",
        body="revisão de 20/11\n",
    )
    code, payload = preview(capsys)
    assert code == 0
    assert {"repo": "repo-a", "pr": 80, "text": "revisão de 20/11"} in payload["residual_dates"]


def edit_pr(gh, slug, number, **fields):
    data = gh._read()
    for item in data["prs"][slug]:
        if item["number"] == number:
            item.update(fields)
    gh._write(data)


def test_abandoned_closed_pr_on_the_same_head_is_not_a_replacement(ready, capsys):
    two_repos(ready)
    ready.gh.add_pr(A, 60, f"release/{DAY}", "master", state="CLOSED", body="corpo abandonado\n")
    ready.gh.fail("pr create", "HTTP 422", repo=B)
    assert run(capsys)[0] == 1
    ready.gh.clear_failures()
    assert run(capsys)[0] == 0
    assert new_of(ready.gh, A, f"release/{NEW}")["body"] == "a\n"


def test_a_completed_move_plans_nothing_on_the_next_preview(ready, capsys):
    standard(ready)
    ready.gh.add_pr(A, 60, f"release/{DAY}", "master", state="CLOSED", body="corpo abandonado\n")
    assert run(capsys)[0] == 0
    code, payload = preview(capsys)
    assert code == 0 and payload["nothing_to_send"] is True


def test_a_hand_edit_on_the_new_pr_survives_the_rerun(ready, capsys):
    two_repos(ready)
    ready.gh.fail("pr create", "HTTP 422", repo=B)
    assert run(capsys)[0] == 1
    number = new_of(ready.gh, A, f"release/{NEW}")["number"]
    edit_pr(ready.gh, A, number, body="a\neditado à mão: revisão de 21/11\n")
    ready.gh.clear_failures()
    assert run(capsys)[0] == 0
    assert "editado à mão" in new_of(ready.gh, A, f"release/{NEW}")["body"]


def test_rerun_when_the_create_of_the_second_pr_failed_in_the_repo(ready, capsys):
    standard(ready)
    for suffix in ("", "-sdbx"):
        source = f"refs/remotes/origin/release/{DAY}{suffix}"
        ready.git("repo-a", "push", "-q", "origin", f"{source}:refs/heads/release/{NEW}{suffix}")
    ready.gh.add_pr(
        A,
        74,
        f"release/{NEW}",
        "master",
        title=f"Release {NEW}",
        body="Depende de {pr:repo-a-73} e #730, veja {pr:repo-a-73}.\nRelease: 21/11/2026\n",
    )
    edit_pr(
        ready.gh,
        A,
        70,
        state="CLOSED",
        comments=[{"body": f"Substituído por https://github.com/{A}/pull/74: x"}],
    )
    assert run(capsys)[0] == 0
    body = new_of(ready.gh, A, f"release/{NEW}")["body"]
    sdbx = new_of(ready.gh, A, f"release/{NEW}-sdbx")["number"]
    assert "{pr:" not in body and f"acme/repo-a#{sdbx}" in body


def test_merged_and_open_sandbox_prs_on_one_head_make_a_single_create(ready, capsys):
    release_file(ready)
    publish_branches(ready)
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", title=f"R {DAY}")
    ready.gh.add_pr(
        A, 73, f"release/{DAY}-sdbx", "sandbox", state="MERGED", merged_at="2026-11-12T10:00:00Z"
    )
    ready.gh.add_pr(A, 76, f"release/{DAY}-sdbx", "sandbox", title=f"S2 {DAY}")
    code, payload = preview(capsys)
    assert code == 0
    sdbx = [c for c in payload["calls"] if " pr create " in c and f"release/{NEW}-sdbx" in c]
    assert len(sdbx) == 1
    assert any(" pr comment 73 " in c for c in payload["calls"])


def test_a_title_citing_a_pr_created_later_is_a_problem(ready, capsys):
    release_file(ready)
    publish_branches(ready)
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", title="Depende da #73")
    ready.gh.add_pr(A, 73, f"release/{DAY}-sdbx", "sandbox", title="s")
    code, _ = preview(capsys)
    assert code == 1 and ready.gh.writes == []


def test_crlf_and_the_trailing_newline_do_not_plan_an_edit(ready, capsys):
    standard(ready)
    assert run(capsys)[0] == 0
    number = new_of(ready.gh, A, f"release/{NEW}")["number"]
    body = new_of(ready.gh, A, f"release/{NEW}")["body"]
    edit_pr(ready.gh, A, number, body=body.replace("\n", "\r\n").rstrip("\r\n"))
    code, payload = preview(capsys)
    assert code == 0 and payload["nothing_to_send"] is True


def test_a_url_prefix_does_not_make_pr_7_the_replacement_of_pr_74(ready):
    release_file(ready)
    publish_branches(ready, sdbx=False)
    source = f"refs/remotes/origin/release/{DAY}"
    ready.git("repo-a", "push", "-q", "origin", f"{source}:refs/heads/release/{NEW}")
    ready.gh.add_pr(A, 7, f"release/{NEW}", "master", body="x\n")
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", state="CLOSED")
    edit_pr(
        ready.gh, A, 70, comments=[{"body": f"Substituído por https://github.com/{A}/pull/74: x"}]
    )
    plan = move.build_plan(load_release_config(), "demo", DAY, NEW, REASON, False, Gh())
    assert "repo-a-70" not in plan.facts["known"]


def test_rerun_keeps_a_merged_pr_comment_only_once_a_later_pr_is_closed(ready, capsys):
    release_file(ready, b_multi=True)
    publish_branches(ready, repos=("repo-a", "repo-b"))
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", title=f"R {DAY}", body="cita #73\n")
    merged = {"state": "MERGED", "merged_at": "2026-11-12T10:00:00Z"}
    ready.gh.add_pr(A, 73, f"release/{DAY}-sdbx", "sandbox", **merged)
    ready.gh.add_pr(
        A, 76, f"release/{DAY}-sdbx", "sandbox", title=f"S2 {DAY}", body="ver acme/repo-b#30\n"
    )
    ready.gh.add_pr(B, 30, f"release/{DAY}", "master", title=f"R {DAY}", body="b\n")
    ready.gh.fail("pr create", "HTTP 422", repo=B)
    assert run(capsys)[0] == 1
    ready.gh.clear_failures()
    before = len(ready.gh.writes)
    assert run(capsys)[0] == 0
    edits = [call[2] for call in ready.gh.writes[before:] if call[:2] == ["pr", "edit"]]
    assert len(edits) == len(set(edits))
    assert new_of(ready.gh, A, f"release/{NEW}")["body"] == "cita #73\n"
    sdbx = new_of(ready.gh, A, f"release/{NEW}-sdbx")
    assert f"acme/repo-b#{new_of(ready.gh, B, f'release/{NEW}')['number']}" in sdbx["body"]


def add_worktrees(ready, day=DAY):
    for suffix in ("", "-sdbx"):
        ready.git(
            "repo-a",
            "worktree",
            "add",
            "-q",
            str(ready.release_dir(day) / f"repo-a{suffix}"),
            f"release/{day}{suffix}",
        )
        ready.git(
            "repo-a",
            "branch",
            "-u",
            f"origin/release/{day}{suffix}",
            f"release/{day}{suffix}",
        )


def upstream(ready, branch):
    return ready.git("repo-a", "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}")


def local_branches(ready):
    return set(ready.git("repo-a", "branch", "--format=%(refname:short)").split())


def worktree_paths(ready):
    out = ready.git("repo-a", "worktree", "list", "--porcelain")
    return {line.split(" ", 1)[1] for line in out.splitlines() if line.startswith("worktree ")}


def test_old_branches_stay_without_the_flag(ready, capsys):
    standard(ready)
    assert run(capsys)[0] == 0
    refs = ready.refs("repo-a")
    for suffix in ("", "-sdbx"):
        assert f"refs/heads/release/{DAY}{suffix}" in refs
        assert f"refs/heads/release/{NEW}{suffix}" in refs


def test_old_branches_deleted_with_the_flag_when_every_pr_is_closed(ready, capsys):
    standard(ready)
    ready.gh.add_pr(A, 60, f"release/{DAY}", "master", state="CLOSED", body="antiga\n")
    code, payload = run(capsys, delete=True)
    assert code == 0
    refs = ready.refs("repo-a")
    for suffix in ("", "-sdbx"):
        assert f"refs/heads/release/{DAY}{suffix}" not in refs
        assert f"refs/heads/release/{NEW}{suffix}" in refs
    assert any("apagar release/" in line for line in payload["done"])


def test_delete_refused_while_a_pr_from_the_head_stays_open(ready, capsys):
    standard(ready)

    class Racing(Gh):
        def prs(self, slug, *, head=None, base=None, state="all"):
            found = super().prs(slug, head=head, base=base, state=state)
            if slug == A and head == f"release/{DAY}" and state == "open":
                ready.gh.add_pr(A, 99, f"release/{DAY}", "master", title="Aberta depois")
                found = super().prs(slug, head=head, base=base, state=state)
            return found

    plan = move.build_plan(load_release_config(), "demo", DAY, NEW, REASON, True, Racing())
    assert any(
        f"release/{DAY} stays: PR #99 from it is still open" in problem for problem in plan.problems
    )
    deleted = [
        call.args[3] for call in plan.calls if call.args[:3] == ("push", "origin", "--delete")
    ]
    assert f"release/{DAY}" not in deleted


def test_delete_refused_when_it_is_a_base(ready, capsys):
    standard(ready)
    ready.gh.add_pr(A, 80, "feature/TS-101-one", f"release/{DAY}", title="Empilhada")
    code, payload = preview(capsys, delete=True)
    assert code == 1 and ready.gh.writes == []
    assert any(
        f"release/{DAY} stays: it is the base of PR #80" in problem
        for problem in payload["problems"]
    )
    code, _ = preview(capsys)
    assert code == 0


def test_local_rename_and_worktree_move(ready, capsys):
    standard(ready)
    add_worktrees(ready)
    old_tree = ready.release_dir(DAY) / "repo-a"
    assert run(capsys)[0] == 0
    new_tree = ready.release_dir(NEW) / "repo-a"
    assert local_branches(ready) >= {f"release/{NEW}", f"release/{NEW}-sdbx"}
    assert not local_branches(ready) & {f"release/{DAY}", f"release/{DAY}-sdbx"}
    assert upstream(ready, f"release/{NEW}") == f"origin/release/{NEW}"
    assert upstream(ready, f"release/{NEW}-sdbx") == f"origin/release/{NEW}-sdbx"
    assert str(new_tree.resolve()) in worktree_paths(ready)
    assert str((ready.release_dir(NEW) / "repo-a-sdbx").resolve()) in worktree_paths(ready)
    assert not old_tree.exists() and not ready.release_dir(DAY).exists()
    assert (ready.release_dir(NEW) / "release.toml").is_file()
    assert ready.git("repo-a", "-C", str(new_tree), "symbolic-ref", "--short", "HEAD") == (
        f"release/{NEW}"
    )


def test_drafts_move_with_the_new_date(ready, capsys):
    standard(ready)
    ready.write_pr("repo-a", f"release {DAY}: entrega", ["TS-101"], f"corpo {DAY}\n")
    (ready.release_dir(DAY) / "published.json").write_text("{}\n")
    assert run(capsys)[0] == 0
    draft = (ready.release_dir(NEW) / "pr" / "repo-a.md").read_text()
    assert f'title = "release {NEW}: entrega"' in draft and f"corpo {NEW}\n" in draft
    assert DAY not in draft
    assert (ready.release_dir(NEW) / "published.json").is_file()


def fail_git_once(monkeypatch, predicate):
    real = writeplan._git
    state = {"done": False}

    def fake(call, args):
        if not state["done"] and predicate(args):
            state["done"] = True
            raise gitops.GitFailed("injected")
        return real(call, args)

    monkeypatch.setattr(writeplan, "_git", fake)
    return state


def fail_folder_once(monkeypatch, mode):
    real = move.move_folder
    state = {"done": False}

    def fake(*given):
        if not state["done"] and given[-1] == mode:
            state["done"] = True
            raise OSError("injected")
        return real(*given)

    monkeypatch.setattr(move, "move_folder", fake)
    return state


def run_once(capsys, **kwargs):
    code, payload = preview(capsys, **kwargs)
    if code != 0 or payload.get("nothing_to_send"):
        return code, payload
    moved = move.run_move(args(approve=payload["code"], **kwargs))
    out = capsys.readouterr()
    return moved, (json.loads(out.out) if out.out.strip() else {})


def finished_state(ready):
    refs = ready.refs("repo-a")
    for suffix in ("", "-sdbx"):
        assert f"refs/heads/release/{DAY}{suffix}" not in refs
        assert f"refs/heads/release/{NEW}{suffix}" in refs
        assert upstream(ready, f"release/{NEW}{suffix}") == f"origin/release/{NEW}{suffix}"
        tree = (ready.release_dir(NEW) / f"repo-a{suffix}").resolve()
        assert str(tree) in worktree_paths(ready)
    assert not local_branches(ready) & {f"release/{DAY}", f"release/{DAY}-sdbx"}
    assert not ready.release_dir(DAY).exists()
    assert (ready.release_dir(NEW) / "release.toml").is_file()


STEPS = {
    "delete": lambda a: a[:3] == ("push", "origin", "--delete") and not a[3].endswith("sdbx"),
    "delete-sdbx": lambda a: a[:3] == ("push", "origin", "--delete") and a[3].endswith("sdbx"),
    "branch-m": lambda a: a[:2] == ("branch", "-m") and not a[2].endswith("sdbx"),
    "branch-m-sdbx": lambda a: a[:2] == ("branch", "-m") and a[2].endswith("sdbx"),
    "branch-u": lambda a: a[:2] == ("branch", "-u") and not a[3].endswith("sdbx"),
    "branch-u-sdbx": lambda a: a[:2] == ("branch", "-u") and a[3].endswith("sdbx"),
    "worktree": lambda a: a[:2] == ("worktree", "move") and not a[2].endswith("sdbx"),
    "worktree-sdbx": lambda a: a[:2] == ("worktree", "move") and a[2].endswith("sdbx"),
}


@pytest.mark.parametrize("step", list(STEPS))
def test_rerun_finishes_after_a_failure_at_each_git_step(ready, capsys, monkeypatch, step):
    standard(ready)
    add_worktrees(ready)
    state = fail_git_once(monkeypatch, STEPS[step])
    code, payload = run_once(capsys, delete=True)
    assert state["done"] and code == 1 and payload["failed"]
    code, payload = run_once(capsys, delete=True)
    assert code == 0, payload
    finished_state(ready)
    code, payload = preview(capsys, delete=True)
    assert code == 0 and payload["nothing_to_send"] is True


@pytest.mark.parametrize("mode", ["files", "finish"])
def test_rerun_finishes_after_a_failure_at_each_folder_phase(ready, capsys, monkeypatch, mode):
    standard(ready)
    add_worktrees(ready)
    state = fail_folder_once(monkeypatch, mode)
    code, payload = run_once(capsys, delete=True)
    assert state["done"] and code == 1 and payload["failed"]
    code, payload = run_once(capsys, delete=True)
    assert code == 0, payload
    finished_state(ready)
    code, payload = preview(capsys, delete=True)
    assert code == 0 and payload["nothing_to_send"] is True


@pytest.mark.parametrize("ahead", [False, True])
def test_rerun_finishes_when_the_local_branch_differs_from_origin(
    ready, capsys, monkeypatch, ahead
):
    standard(ready)
    branch = f"release/{DAY}"
    ready.git("repo-a", "checkout", "-q", branch)
    sha = ready.git("repo-a", "rev-parse", "HEAD")
    if ahead:
        ready.commit("repo-a", branch, "late.txt", "late\n", "feat: tarde", push=False)
    else:
        ready.commit("repo-a", branch, "late.txt", "late\n", "feat: tarde")
        ready.git("repo-a", "reset", "-q", "--hard", sha)
    ready.git("repo-a", "checkout", "-q", "master")
    add_worktrees(ready)
    state = fail_git_once(monkeypatch, STEPS["worktree"])
    code, payload = run_once(capsys)
    assert state["done"] and code == 1 and payload["failed"]
    assert run_once(capsys)[0] == 0
    assert f"release/{NEW}" in local_branches(ready)
    assert not ready.release_dir(DAY).exists()


def test_a_stray_folder_in_the_new_folder_is_refused_at_preview(ready, capsys):
    standard(ready)
    add_worktrees(ready)
    (ready.release_dir(NEW) / "repo-a").mkdir(parents=True)
    code, _ = preview(capsys)
    assert code == 1 and ready.gh.writes == []


def test_the_delete_check_does_not_mix_pr_numbers_across_repos(ready):
    release_file(ready, b_multi=True)
    publish_branches(ready, repos=("repo-a", "repo-b"), sdbx=False)
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", body="Release: 20/11/2026\n")
    ready.gh.add_pr(B, 99, f"release/{DAY}", "master", body="Release: 20/11/2026\n")

    class Racing(Gh):
        def prs(self, slug, *, head=None, base=None, state="all"):
            found = super().prs(slug, head=head, base=base, state=state)
            if slug == A and head == f"release/{DAY}" and state == "open":
                if not any(pr.number == 99 for pr in found):
                    ready.gh.add_pr(A, 99, f"release/{DAY}", "master", title="Aberta depois")
                found = super().prs(slug, head=head, base=base, state=state)
            return found

    plan = move.build_plan(load_release_config(), "demo", DAY, NEW, REASON, True, Racing())
    assert any(f"{A.split('/')[1]}: release/{DAY} stays: PR #99" in p for p in plan.problems)


def test_a_single_branch_repo_worktree_moves_too(ready, capsys):
    standard(ready)
    ready.git(
        "repo-b",
        "worktree",
        "add",
        "-q",
        str(ready.release_dir(DAY) / "repo-b"),
        "feature/TS-201-only",
    )
    assert run_once(capsys)[0] == 0
    assert str((ready.release_dir(NEW) / "repo-b").resolve()) in worktree_paths_of(ready, "repo-b")
    assert "feature/TS-201-only" in ready.git("repo-b", "branch", "--format=%(refname:short)")
    assert not ready.release_dir(DAY).exists()
    code, payload = preview(capsys)
    assert code == 0 and payload["nothing_to_send"] is True


def worktree_paths_of(ready, name):
    out = ready.git(name, "worktree", "list", "--porcelain")
    return {line.split(" ", 1)[1] for line in out.splitlines() if line.startswith("worktree ")}


def test_a_registered_worktree_with_its_folder_gone_is_a_problem(ready, capsys):
    standard(ready)
    add_worktrees(ready)
    shutil.rmtree(ready.release_dir(DAY) / "repo-a")
    code, payload = preview(capsys)
    assert code == 1 and ready.gh.writes == []
    assert any("git worktree prune" in problem for problem in payload["problems"])


def test_old_folder_stays_when_it_still_holds_files(ready, capsys):
    standard(ready)
    (ready.release_dir(DAY) / "anotacoes.txt").write_text("minhas notas\n")
    code, _ = run(capsys)
    assert code == 0
    assert (ready.release_dir(DAY) / "anotacoes.txt").read_text() == "minhas notas\n"
    assert not (ready.release_dir(DAY) / "release.toml").exists()
    assert (ready.release_dir(NEW) / "release.toml").is_file()


def test_leftovers_are_reported_and_the_folder_is_not_planned_again(ready, capsys):
    standard(ready)
    ready.write_pr("repo-a", f"release {DAY}: entrega", ["TS-101"], "corpo\n")
    (ready.release_dir(DAY) / "anotacoes.txt").write_text("notas\n")
    code, payload = run_once(capsys)
    assert code == 0 and payload["left_in_old"] == ["anotacoes.txt"]
    draft = ready.release_dir(NEW) / "pr" / "repo-a.md"
    draft.write_text(draft.read_text() + f"\ndata {DAY} de proposito\n")
    code, payload = preview(capsys)
    assert code == 0 and payload["nothing_to_send"] is True
    assert payload["left_in_old"] == ["anotacoes.txt"]
    assert run_once(capsys)[0] == 0
    assert f"data {DAY} de proposito" in draft.read_text()


def test_an_empty_new_folder_is_free(ready, capsys):
    standard(ready)
    ready.release_dir(NEW).mkdir(parents=True)
    assert run_once(capsys)[0] == 0
    assert (ready.release_dir(NEW) / "release.toml").is_file()


def test_a_failed_draft_swap_leaves_the_rerun_to_finish_it(ready, capsys, monkeypatch):
    standard(ready)
    ready.write_pr("repo-a", f"release {DAY}: entrega", ["TS-101"], "corpo\n")
    real, state = move._swap, {"done": False}

    def flaky(value, old, new):
        if not state["done"] and value.startswith("+++"):
            state["done"] = True
            raise OSError("injected")
        return real(value, old, new)

    monkeypatch.setattr(move, "_swap", flaky)
    code, payload = run_once(capsys)
    assert state["done"] and code == 1 and payload["failed"]
    assert "left_in_old" not in payload and "pr" in payload["not_moved_yet"]
    assert run_once(capsys)[0] == 0
    draft = (ready.release_dir(NEW) / "pr" / "repo-a.md").read_text()
    assert f"release {NEW}: entrega" in draft and DAY not in draft


def test_a_stale_local_new_branch_without_the_old_one_is_refused(ready, capsys):
    standard(ready)
    ready.git("repo-a", "branch", "-D", f"release/{DAY}")
    ready.git("repo-a", "branch", f"release/{NEW}", "origin/master")
    code, payload = preview(capsys)
    assert code == 1 and ready.gh.writes == []
    assert any(f"the local branch release/{NEW} exists" in p for p in payload["problems"])


def mixed(ready, b_body):
    release_file(ready)
    publish_branches(ready)
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", title=f"release {DAY}: a", body="a\n")
    ready.gh.add_pr(B, 5, "feature/TS-201-only", "master", title="feat(TS-201): b", body=b_body)


def test_a_mixed_shape_move_points_the_single_branch_pr_at_the_new_pr(ready, capsys):
    mixed(ready, "Release: 20/11/2026\n\nDepende de acme/repo-a#70\n")
    code, payload = preview(capsys)
    assert code == 0
    create = next(
        i for i, call in enumerate(payload["calls"]) if "pr create -R acme/repo-a" in call
    )
    edit = next(i for i, call in enumerate(payload["calls"]) if "pr edit 5 -R acme/repo-b" in call)
    assert create < edit
    assert run(capsys)[0] == 0
    number = new_of(ready.gh, A, f"release/{NEW}")["number"]
    assert ready.gh.bodies[5] == f"Release: 21/11/2026\n\nDepende de acme/repo-a#{number}\n"


def test_a_mixed_shape_rerun_fills_the_single_branch_pr_from_the_known_pr(ready, capsys):
    mixed(ready, "Release: 20/11/2026\n\nDepende de acme/repo-a#70, revisão de 20/11\n")
    ready.gh.fail("pr edit", "HTTP 422", repo=B)
    assert run(capsys)[0] == 1
    ready.gh.clear_failures()
    number = new_of(ready.gh, A, f"release/{NEW}")["number"]
    code, payload = preview(capsys)
    assert code == 0
    text = f"Depende de acme/repo-a#{number}, revisão de 20/11"
    assert {"repo": "repo-b", "pr": 5, "text": text} in payload["residual_dates"]
    assert run(capsys)[0] == 0
    assert f"acme/repo-a#{number}, revisão de 20/11" in ready.gh.bodies[5]
    assert "{pr:" not in ready.gh.bodies[5]


def test_an_old_pr_into_another_base_is_not_recreated(ready, capsys):
    standard(ready)
    ready.gh.add_pr(A, 50, f"release/{DAY}", "staging", title=f"release {DAY}: stg", body="x\n")
    code, payload = preview(capsys)
    assert code == 0
    assert not any("--base staging" in call for call in payload["calls"])
    assert not any("pr close 50" in call for call in payload["calls"])
    code, payload = preview(capsys, delete=True)
    assert code == 1 and ready.gh.writes == []
    assert f"repo-a: release/{DAY} stays: PR #50 from it is still open" in payload["problems"]


def write_published(ready, rows):
    path = ready.release_dir(DAY) / "published.json"
    path.write_text(json.dumps({"repos": rows}), encoding="utf-8")


def test_published_json_follows_the_move(ready, capsys):
    standard(ready)
    code_branch, sandbox_branch = f"release/{DAY}", f"release/{DAY}-sdbx"
    a_row = {"shape": "multi", "code_branch": code_branch, "sandbox_branch": sandbox_branch}
    write_published(ready, {"repo-a": {**a_row, "code_pr": 70, "sandbox_pr": 73}})
    assert run(capsys)[0] == 0
    record = json.loads((ready.release_dir(NEW) / "published.json").read_text())
    row = record["repos"]["repo-a"]
    assert row["code_branch"] == f"release/{NEW}" and row["sandbox_branch"] == f"release/{NEW}-sdbx"
    assert row["code_pr"] == new_of(ready.gh, A, f"release/{NEW}")["number"]
    assert row["sandbox_pr"] == new_of(ready.gh, A, f"release/{NEW}-sdbx")["number"]


def test_a_failed_published_json_write_is_a_warning(ready, capsys, monkeypatch):
    standard(ready)
    write_published(ready, {"repo-a": {"shape": "multi", "code_branch": f"release/{DAY}"}})

    def refuse(folder, data):
        raise PermissionError("read-only")

    monkeypatch.setattr(writeplan, "write_published", refuse)
    code, payload = run(capsys)
    assert code == 0 and payload["failed"] is None
    assert any("published.json was not updated: read-only" in w for w in payload["warnings"])


def test_the_recorded_shape_wins_over_the_include_count(ready, capsys):
    release_file(ready, b_multi=True)
    publish_branches(ready)
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", title=f"release {DAY}: a", body="a\n")
    ready.gh.add_pr(B, 5, "feature/TS-201-only", "master", body="Release: 20/11/2026\n")
    single = {"shape": "single", "code_branch": "feature/TS-201-only", "code_pr": 5}
    write_published(ready, {"repo-b": single})
    assert run(capsys)[0] == 0
    assert ready.gh.bodies[5] == "Release: 21/11/2026\n"
    assert creates(ready.gh, B) == []


def test_move_fetches_only_the_release_repos(ready, capsys, monkeypatch):
    ready.write_release({"repo-a": ["feature/TS-101-one", "feature/TS-102-two"]})
    publish_branches(ready)
    ready.gh.add_pr(A, 70, f"release/{DAY}", "master", title=f"release {DAY}: a", body="a\n")
    fetched = []
    monkeypatch.setattr(gitops, "fetch", lambda repo: fetched.append(repo.name))
    code, _ = preview(capsys)
    assert code == 0 and fetched == ["repo-a"]


def test_preview_move_names_itself_and_a_refusal_keeps_the_warnings(ready, capsys, monkeypatch):
    assert move.run_preview(args(old="20261125", new="20261126")) == 2
    assert capsys.readouterr().err.startswith("ws release preview move: ")
    standard(ready)
    monkeypatch.setattr(gitops, "fetch", lambda repo: "boom")
    ready.git("repo-a", "branch", f"release/{NEW}", "origin/master")
    code, payload = preview(capsys)
    assert code == 1 and "repo-a: fetch failed: boom" in payload["warnings"]


def test_a_malformed_day_cannot_be_evaluated(ready, capsys):
    standard(ready)
    assert preview(capsys, new="2026-1-21")[0] == 2
