import argparse
import itertools
import json
from datetime import UTC, datetime

import pytest
from fake_gh import fake_gh  # noqa: F401
from release_helpers import DAY, fixed_today, world  # noqa: F401, F811
from test_release_plan import HOOKS_COPY, write_settings

from ws.release import move
from ws.release import plan as writeplan

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
    assert "Release: 20/11/2026" in created["body"]


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
    assert {"repo": "repo-a", "pr": 70, "text": "Release: 20/11/2026"} in payload["residual_dates"]
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
    assert code == 1


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
