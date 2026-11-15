import itertools
import json
import re
import stat
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fake_gh import fake_gh  # noqa: F401
from release_helpers import DAY

from ws import humans
from ws.config import data_dir
from ws.release import ReleaseRefused, ReleaseSetup, run
from ws.release import plan as writeplan
from ws.release.github import Gh
from ws.release.plan import Call, WritePlan
from ws.release.settings import load_release_config

pytest_plugins = ["release_helpers"]

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
BRANCH = f"release/{DAY}"
HOOKS_COPY = "/srv/claude/hooks/workspace"
NEXT = f"ws release publish {DAY} --project demo"


def write_settings(path, ask=("Bash(ws release publish:*)", "Bash(ws release move:*)")):
    command = f'python3 -I "{HOOKS_COPY}/approval_gate.py"'
    entry = {"matcher": "Bash|mcp__.*", "hooks": [{"type": "command", "command": command}]}
    gates = {"permissions": {"ask": list(ask)}, "hooks": {"PreToolUse": [entry]}}
    path.write_text(json.dumps(gates), encoding="utf-8")


@pytest.fixture
def ready(world, fake_gh, tmp_path, monkeypatch):  # noqa: F811
    settings = tmp_path / "claude-settings.json"
    write_settings(settings)
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(settings))
    monkeypatch.setenv("WS_CLAUDE_HOOKS_DIR", HOOKS_COPY)
    monkeypatch.setattr(writeplan, "now", lambda: NOW)
    sessions = itertools.count(1000)
    monkeypatch.setattr(writeplan, "session_id", lambda: next(sessions))
    world.branch("repo-a", BRANCH, "origin/master", push=False)
    world.settings = settings
    return world


def create(repo, head, ref, body, line):
    return Call(
        repo=repo,
        program="gh",
        args=("pr", "create", "-R", f"acme/{repo}", "--base", "master", "--head", head)
        + ("--title", f"Release {repo}"),
        line=line,
        body=body,
        answers=ref,
    )


def make_plan(world, tip="t1", body="corpo", action="publish", first_body=None):
    calls = [
        Call(
            repo="repo-a",
            program="git",
            args=("push", "-u", "origin", BRANCH),
            line="enviar a branch da release",
            cwd=str(world.clone("repo-a")),
        ),
        create("repo-a", BRANCH, "repo-a", first_body or body, "abrir a PR de repo-a"),
        create("repo-b", BRANCH, "repo-b", body, "abrir a PR de repo-b"),
    ]
    return WritePlan(
        action=action,
        slug="demo",
        days=(DAY,),
        tips={"repo-a": {BRANCH: tip}},
        calls=calls,
        drafts=[{"path": "pr/a.md", "sha256": "x"}],
        facts={"known": {}},
    )


def preview(world, **kwargs) -> str:
    payload, code = writeplan.show_preview(make_plan(world, **kwargs), NEXT)
    assert code == 0
    return payload["code"]


def approve(world, code, action="publish", build=None, local=None):
    build = build or (lambda: make_plan(world))
    return writeplan.approve(code, action, build, Gh(), load_release_config(), local)


def test_preview_stores_a_private_record(ready):
    payload, _ = writeplan.show_preview(make_plan(ready), NEXT)
    path = writeplan.store() / f"{payload['code']}.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert payload["next"] == f"{NEXT} --approve {payload['code']}"
    assert json.loads(path.read_text())["action"] == "publish"
    assert payload["summary"][0] == "enviar a branch da release"


def test_preview_with_problems_writes_nothing(ready):
    broken = make_plan(ready)
    broken.problems = ["falta o rascunho"]
    with pytest.raises(ReleaseRefused) as error:
        writeplan.show_preview(broken, NEXT)
    assert error.value.payload == {"problems": ["falta o rascunho"]}
    assert not list(data_dir().glob("release/pending/*.json"))


def test_code_changes_with_any_body_or_tip(ready):
    base = make_plan(ready).code
    assert make_plan(ready).code == base
    assert make_plan(ready, body="outro").code != base
    assert make_plan(ready, tip="t2").code != base


def test_approve_refuses_without_the_gate_settings(ready):
    code = preview(ready)
    write_settings(ready.settings, ask=())
    with pytest.raises(ReleaseSetup):
        approve(ready, code)


def test_approve_refuses_a_wrong_code(ready):
    code = preview(ready)
    forged = "f" * 12
    (writeplan.store() / f"{code}.json").rename(writeplan.store() / f"{forged}.json")
    with pytest.raises(ReleaseRefused, match="was changed"):
        approve(ready, forged)
    with pytest.raises(ReleaseRefused, match="not an approval code"):
        approve(ready, "../x")


def test_approve_refuses_without_a_record(ready, fake_gh):  # noqa: F811
    with pytest.raises(ReleaseRefused, match="no pending"):
        approve(ready, "a" * 12)
    assert fake_gh.writes == []


def test_approve_refuses_after_30_minutes(ready, monkeypatch, fake_gh):  # noqa: F811
    code = preview(ready)
    monkeypatch.setattr(writeplan, "now", lambda: NOW + timedelta(minutes=31))
    with pytest.raises(ReleaseRefused, match="expired"):
        approve(ready, code)
    assert fake_gh.writes == []
    assert not (writeplan.store() / f"{code}.json").exists()


def test_approve_refuses_in_the_same_session(ready, monkeypatch, fake_gh):  # noqa: F811
    monkeypatch.setattr(writeplan, "session_id", lambda: 7)
    code = preview(ready)
    with pytest.raises(ReleaseRefused, match="separate steps"):
        approve(ready, code)
    assert fake_gh.writes == []


def test_approve_refuses_a_move_code_for_publish(ready, fake_gh):  # noqa: F811
    code = preview(ready, action="move")

    def build():
        raise AssertionError("must not rebuild")

    with pytest.raises(ReleaseRefused, match="move preview"):
        approve(ready, code, build=build)
    assert fake_gh.writes == []


def test_approve_refuses_when_the_state_changed(ready, fake_gh):  # noqa: F811
    code = preview(ready)
    with pytest.raises(ReleaseRefused, match="o estado mudou desde a prévia"):
        approve(ready, code, build=lambda: make_plan(ready, tip="t2"))
    assert fake_gh.writes == []


def test_approve_sends_and_pushes_to_the_origin(ready, fake_gh):  # noqa: F811
    code = preview(ready)
    payload, exit_code = approve(ready, code)
    assert exit_code == 0
    assert payload["failed"] is None and len(payload["done"]) == 3
    assert BRANCH in "".join(ready.refs("repo-a"))
    assert payload["prs"] == {
        "repo-a": "https://github.com/acme/repo-a/pull/1",
        "repo-b": "https://github.com/acme/repo-b/pull/1",
    }
    assert len(fake_gh.writes) == 2


def test_approve_deletes_the_record_before_sending(ready, fake_gh):  # noqa: F811
    path_holder = {}

    def first_send():
        assert not path_holder["path"].exists()
        raise RuntimeError("stop here")

    def build():
        plan = make_plan(ready)
        plan.calls.insert(0, Call(repo="repo-a", program="local", args=("first",), line="primeiro"))
        return plan

    code = build().code
    writeplan.show_preview(build(), NEXT)
    path_holder["path"] = writeplan.store() / f"{code}.json"
    assert path_holder["path"].exists()
    payload, exit_code = approve(ready, code, build=build, local={"first": first_send})
    assert exit_code == 1 and payload["failed"] == "primeiro"
    assert fake_gh.writes == []
    with pytest.raises(ReleaseRefused, match="no pending"):
        approve(ready, code, build=build)


def test_approve_refuses_an_edited_summary(ready, fake_gh):  # noqa: F811
    code = preview(ready)
    path = writeplan.store() / f"{code}.json"
    record = json.loads(path.read_text())
    record["summary"] = ["inofensivo"]
    path.write_text(json.dumps(record))
    with pytest.raises(ReleaseRefused, match="was changed"):
        approve(ready, code)
    assert fake_gh.writes == []


def test_approve_refuses_what_guard_refuses(ready, fake_gh):  # noqa: F811
    bad = make_plan(ready)
    bad.calls.append(gh_call("pr", "merge", "5"))
    writeplan.show_preview(bad, NEXT)
    with pytest.raises(ReleaseRefused, match="outside the allowed shapes: gh pr merge 5"):
        approve(ready, bad.code, build=lambda: bad)
    assert fake_gh.writes == []
    assert BRANCH not in "".join(ready.refs("repo-a"))


def test_git_timeout_is_uncertain(ready, monkeypatch, capsys):
    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(writeplan, "run_git", slow)
    payload, exit_code = writeplan.execute(make_plan(ready), Gh())
    assert exit_code == 1 and payload["uncertain"] is True
    assert payload["failed"] == "enviar a branch da release"
    assert "resultado incerto" in capsys.readouterr().err


def test_git_rejected_push_is_a_plain_failure(ready):
    plan = make_plan(ready)
    plan.calls[0] = git_call_in(ready, "push", "-u", "origin", "release/20261199")
    payload, exit_code = writeplan.execute(plan, Gh())
    assert exit_code == 1 and payload["uncertain"] is False and payload["done"] == []


def test_git_push_never_waits_for_a_password(ready, monkeypatch):
    seen = {}
    real = writeplan.run_git

    def spy(repo, *args, **kwargs):
        seen.update(kwargs)
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(writeplan, "run_git", spy)
    writeplan.execute(make_plan(ready), Gh())
    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0" and seen["timeout"] > 0


def test_a_non_json_plan_is_refused_clearly(ready):
    plan = make_plan(ready)
    plan.facts = {"renumber": {("repo-a", 1): "x"}}
    with pytest.raises(ReleaseRefused, match="not JSON-safe"):
        writeplan.show_preview(plan, NEXT)


def test_execute_stops_at_the_first_failure(ready, fake_gh):  # noqa: F811
    fake_gh.fail("pr create", "HTTP 422")
    payload, exit_code = writeplan.execute(make_plan(ready), Gh())
    assert exit_code == 1
    assert payload["done"] == ["enviar a branch da release"]
    assert payload["failed"] == "abrir a PR de repo-a"
    assert payload["not_sent"] == ["abrir a PR de repo-b"]
    assert payload["uncertain"] is False


def test_execute_uncertain_is_not_retried(ready, fake_gh, capsys):  # noqa: F811
    fake_gh.fail("pr create", "HTTP 502")
    payload, exit_code = writeplan.execute(make_plan(ready), Gh())
    assert exit_code == 1
    assert payload["uncertain"] is True
    assert [call[:2] for call in fake_gh.writes] == [["pr", "create"]]
    assert "resultado incerto: confira no GitHub" in capsys.readouterr().err


def test_execute_second_pass_resolves_forward_refs(ready, fake_gh):  # noqa: F811
    plan = make_plan(ready, first_body="veja {pr:repo-b}")
    plan.calls += writeplan.second_pass(plan.calls)
    assert plan.calls[-1].line.startswith("segunda passada: ")
    payload, exit_code = writeplan.execute(plan, Gh())
    assert exit_code == 0
    assert "acme/repo-b#1" in fake_gh.prs("acme/repo-a")[0]["body"]
    assert [call[:2] for call in fake_gh.writes] == [["pr", "create"]] * 2 + [["pr", "edit"]]


def test_second_pass_skips_bodies_without_later_refs(ready):
    plan = make_plan(ready, first_body="veja {pr:repo-a}")
    assert writeplan.second_pass(plan.calls) == []


def gh_call(*args):
    return Call(repo="repo-a", program="gh", args=args, line="x", cwd=None)


def git_call_in(world, *args):
    return Call(
        repo="repo-a", program="git", args=args, line="enviar", cwd=str(world.clone("repo-a"))
    )


def git_call(*args):
    return Call(repo="repo-a", program="git", args=args, line="x", cwd="/somewhere")


REFUSED = [
    gh_call("pr", "merge", "5"),
    git_call("push", "-f", "origin", BRANCH),
    git_call("push", "-u", "origin", "master"),
    git_call("push", "-u", "origin", "sandbox"),
    git_call("push", "origin", f"+{BRANCH}"),
    git_call(
        "push", "origin", f"refs/remotes/origin/{BRANCH}-sdbx:refs/heads/{BRANCH[:-8]}20261121"
    ),
    git_call("worktree", "move", f"/w/x/../../etc/release-{DAY}x", f"/w/release-{DAY}"),
    git_call("worktree", "move", f"release-{DAY}/repo-a", "../release-20261121"),
    gh_call(
        "pr", "create", "-R", "other/repo", "--base", "master", "--head", BRANCH, "--title", "t"
    ),
    gh_call(
        "pr", "create", "-R", "acme/repo-a", "--base", "feature/x", "--head", BRANCH, "--title", "t"
    ),
    gh_call(
        "pr", "create", "-R", "acme/repo-a", "--base", "master", "--head", "master", "--title", "t"
    ),
    gh_call("pr", "edit", "5", "-R", "acme/repo-a", "--base", "master"),
    git_call("push", "origin", "--delete", "master"),
    Call(repo="repo-a", program="git", args=("push", "-u", "origin", BRANCH), line="x"),
    Call(repo="repo-a", program="local", args=("unknown",), line="x"),
    Call(repo="repo-a", program="sh", args=("-c", "true"), line="x"),
]


@pytest.mark.parametrize("call", REFUSED, ids=lambda call: " ".join(call.args))
def test_guard_refuses(ready, call):
    plan = make_plan(ready)
    plan.calls = [call]
    refused = writeplan.guard(plan, load_release_config())
    assert refused == f"{call.program} {' '.join(call.args)}"


def test_guard_allows_the_known_shapes(ready):
    plan = make_plan(ready)
    plan.calls += [
        git_call("push", "origin", f"refs/remotes/origin/{BRANCH}:refs/heads/release/20261121"),
        git_call(
            "push", "origin", f"refs/remotes/origin/{BRANCH}-sdbx:refs/heads/release/20261121-sdbx"
        ),
        git_call("worktree", "move", f"release-{DAY}/repo-a", "release-20261121/repo-a"),
        git_call(
            "worktree",
            "move",
            f"/d/projects/demo/release-{DAY}",
            "/d/projects/demo/release-20261121",
        ),
        git_call("push", "origin", "--delete", BRANCH),
        git_call("branch", "-m", BRANCH, f"{BRANCH}-sdbx"),
        git_call("branch", "-u", f"origin/{BRANCH}", BRANCH),
        git_call("worktree", "move", f"/w/release-{DAY}", f"/w/release-{DAY}-sdbx"),
        gh_call("pr", "edit", "{num:repo-a}", "-R", "acme/repo-a"),
        gh_call("pr", "close", "5", "-R", "acme/repo-a", "--comment", "fechada"),
        gh_call("pr", "comment", "5", "-R", "acme/repo-a", "--body", "oi"),
        gh_call(
            "pr",
            "create",
            "-R",
            "acme/repo-a",
            "--base",
            "sandbox",
            "--head",
            "feature/TS-1-x",
            "--title",
            "t",
            "--label",
            "release",
            "--assignee",
            "me",
        ),
        Call(repo="repo-a", program="local", args=("mark", "x"), line="x"),
    ]
    assert writeplan.guard(plan, load_release_config(), ("mark",)) is None


def test_release_code_never_merges_a_pr_or_forces():
    folder = Path(writeplan.__file__).parent
    forbidden = re.compile(r"""["']pr["'],\s*["']merge["']|--force|["']-f["']|["']\+""")
    assert list(folder.glob("*.py"))
    for path in folder.glob("*.py"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path.name


def test_by_hand_asks_s_n(ready, monkeypatch, fake_gh):  # noqa: F811
    code = preview(ready)
    monkeypatch.setattr(humans, "by_hand", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    with pytest.raises(ReleaseRefused, match="nothing was sent"):
        approve(ready, code)
    assert fake_gh.writes == []
    monkeypatch.setattr("builtins.input", lambda prompt="": "s")
    payload, exit_code = approve(ready, code)
    assert exit_code == 0 and len(fake_gh.writes) == 2


def test_local_handlers_run_when_named(ready):
    seen = []
    plan = make_plan(ready)
    plan.calls = [Call(repo="repo-a", program="local", args=("mark", "x"), line="marcar")]
    code = plan.code
    writeplan.show_preview(plan, NEXT)
    payload, exit_code = approve(
        ready, code, build=lambda: plan, local={"mark": lambda *args: seen.append(args)}
    )
    assert exit_code == 0 and seen == [("x",)]


def test_run_prints_the_failed_json(ready, fake_gh, capsys):  # noqa: F811
    code = preview(ready)
    fake_gh.fail("pr create", "HTTP 422")
    assert run("publish", lambda: approve(ready, code)) == 1
    assert json.loads(capsys.readouterr().out)["failed"] == "abrir a PR de repo-a"
