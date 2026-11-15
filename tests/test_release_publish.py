import argparse
import itertools
import json
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fake_gh import fake_gh  # noqa: F401
from release_helpers import DAY, World  # noqa: F401

from ws import cli
from ws.release import build, gitops
from ws.release import plan as writeplan

pytest_plugins = ["release_helpers"]

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
CODE = f"release/{DAY}"
ONE, TWO, ONLY = "feature/TS-101-one", "feature/TS-102-two", "feature/TS-201-only"
HOOKS_COPY = "/srv/claude/hooks/workspace"
A_TITLE = f"release {DAY}: duas tarefas"
B_TITLE = "feat(TS-201): só isso"
A_BODY = "## O que traz\n\n{tasks}\n\n## Antes de subir\n\n## Ordem e efeitos\n\n## Como validei\n"
B_BODY = "## Tarefa\n\n{tasks}\n\n## Como validei\n\nok\n"
MERGED = "2026-11-10T00:00:00Z"
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ready(world, fake_gh, fixed_today, tmp_path, monkeypatch):  # noqa: F811
    settings = tmp_path / "claude-settings.json"
    command = f'python3 -I "{HOOKS_COPY}/approval_gate.py"'
    entry = {"matcher": "Bash|mcp__.*", "hooks": [{"type": "command", "command": command}]}
    gates = {
        "permissions": {"ask": ["Bash(ws release publish:*)", "Bash(ws release move:*)"]},
        "hooks": {"PreToolUse": [entry]},
    }
    settings.write_text(json.dumps(gates), encoding="utf-8")
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(settings))
    monkeypatch.setenv("WS_CLAUDE_HOOKS_DIR", HOOKS_COPY)
    monkeypatch.setattr(writeplan, "now", lambda: NOW)
    sessions = itertools.count(1000)
    monkeypatch.setattr(writeplan, "session_id", lambda: next(sessions))
    world.write_release({"repo-a": [ONE, TWO], "repo-b": [ONLY]})
    code = build.run_new(argparse.Namespace(project="demo", day=DAY, repos=[]))
    assert code == 0
    world.commit("repo-b", ONLY, "more.txt", "more\n", "feat(TS-201): ajuste local", push=False)
    world.git("repo-a", "checkout", "-q", "master")
    world.git("repo-b", "checkout", "-q", "master")
    return world


def drafts(world, *, a_body=A_BODY, sandbox=False, **front):
    world.write_pr("repo-a", A_TITLE, ["TS-101", "TS-102"], a_body, **front)
    world.write_pr("repo-b", B_TITLE, ["TS-201"], B_BODY)
    if sandbox:
        world.write_pr("repo-a-sandbox", A_TITLE + " (sdbx)", ["TS-101", "TS-102"], a_body)
        world.write_pr("repo-b-sandbox", B_TITLE + " (sdbx)", ["TS-201"], B_BODY)


def cli_run(capsys, *argv):
    code = cli.main(["release", *argv])
    captured = capsys.readouterr()
    return code, json.loads(captured.out) if captured.out.strip() else {}, captured.err


def preview(capsys, *extra):
    code, out, err = cli_run(capsys, "preview", "publish", DAY, "--project", "demo", *extra)
    assert code == 0, err
    return out


def publish_with(capsys, code, *extra):
    return cli_run(capsys, "publish", DAY, "--project", "demo", *extra, "--approve", code)


def run_all(capsys, *extra):
    out = preview(capsys, *extra)
    return out, publish_with(capsys, out["code"], *extra)


def all_refs(world):
    return {name: world.refs(name) for name in ("repo-a", "repo-b")}


def creates(gh):
    return [call[:-2] for call in gh.writes if call[:2] == ["pr", "create"]]


def test_preview_publish_writes_nothing(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    before = all_refs(ready)
    out = preview(capsys)
    assert len(out["code"]) == 12
    assert fake_gh.writes == []
    assert all_refs(ready) == before
    path = writeplan.store() / f"{out['code']}.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert out["next"] == f"ws release publish {DAY} --project demo --approve {out['code']}"


def test_publish_with_the_right_code_runs_the_planned_calls_in_order(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready, sandbox=True)
    out = preview(capsys)
    a, b = "acme/repo-a", "acme/repo-b"
    assert out["calls"] == [
        f"repo-a: git push -u origin {CODE}",
        f"repo-a: gh pr create -R {a} --base master --head {CODE} --title {A_TITLE}",
        f"repo-a: gh pr create -R {a} --base sandbox --head {CODE} --title {A_TITLE} (sdbx)",
        f"repo-b: git push -u origin {ONLY}",
        f"repo-b: gh pr create -R {b} --base master --head {ONLY} --title {B_TITLE}",
        f"repo-b: gh pr create -R {b} --base sandbox --head {ONLY} --title {B_TITLE} (sdbx)",
    ]
    code, result, err = publish_with(capsys, out["code"])
    assert code == 0, err
    assert creates(fake_gh) == [
        ["pr", "create", "-R", a, "--base", "master", "--head", CODE, "--title", A_TITLE],
        ["pr", "create", "-R", a, "--base", "sandbox", "--head", CODE]
        + ["--title", A_TITLE + " (sdbx)"],
        ["pr", "create", "-R", b, "--base", "master", "--head", ONLY, "--title", B_TITLE],
        ["pr", "create", "-R", b, "--base", "sandbox", "--head", ONLY]
        + ["--title", B_TITLE + " (sdbx)"],
    ]
    assert f"refs/heads/{CODE}" in ready.refs("repo-a")
    assert f"refs/heads/{ONLY}" in ready.refs("repo-b")
    assert [row["code_pr"] for row in result["repos"]] == [1, 1]
    assert [row["sandbox_pr"] for row in result["repos"]] == [2, 2]
    assert len(result["gmud"]) == 4


def test_single_branch_prs_have_the_task_branch_as_head(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    _, (code, _, err) = run_all(capsys, "--repo", "repo-b")
    assert code == 0, err
    prs = fake_gh.prs("acme/repo-b")
    assert [pr["headRefName"] for pr in prs] == [ONLY, ONLY]
    assert all(pr["body"].startswith("Release: 20/11/2026\n\n") for pr in prs)
    assert fake_gh.prs("acme/repo-a") == []


def conflict_with_sandbox(world, capsys):
    world.commit("repo-a", "sandbox", "shared.txt", "sandbox\n", "chore: shared sandbox")
    world.commit("repo-a", ONE, "shared.txt", "one\n", "feat: shared one")
    world.git("repo-a", "checkout", "-q", "master")
    args = argparse.Namespace(project="demo", day=DAY, repos=[])
    assert build.run_new(args) == 3
    capsys.readouterr()
    sdbx = world.release_dir() / "repo-a-sdbx"
    (sdbx / "shared.txt").write_text("resolved\n")
    world.git("repo-a", "-C", str(sdbx), "add", "shared.txt")
    world.git("repo-a", "-C", str(sdbx), "commit", "-q", "--no-edit")
    assert build.run_new(args) == 0
    capsys.readouterr()
    world.git("repo-a", "checkout", "-q", "master")


def test_sandbox_pr_comes_from_the_sdbx_when_it_exists(ready, fake_gh, capsys):  # noqa: F811
    conflict_with_sandbox(ready, capsys)
    drafts(ready)
    out, (code, _, err) = run_all(capsys, "--repo", "repo-a")
    assert code == 0, err
    assert out["calls"][:2] == [
        f"repo-a: git push -u origin {CODE}",
        f"repo-a: git push -u origin {CODE}-sdbx",
    ]
    code_pr, sandbox_pr = fake_gh.prs("acme/repo-a")
    assert (code_pr["headRefName"], sandbox_pr["headRefName"]) == (CODE, f"{CODE}-sdbx")
    assert sandbox_pr["title"] == A_TITLE + " (sdbx)"
    paragraph = "Leva este código para a sandbox, para validar antes da master."
    assert paragraph in sandbox_pr["body"]
    assert (
        f"A {CODE}-sdbx tem a sandbox mesclada; difere do código só em: "
        "sandbox-only.txt, shared.txt." in sandbox_pr["body"]
    )
    assert sandbox_pr["body"].index(paragraph) < sandbox_pr["body"].index("## O que traz")
    assert f"refs/heads/{CODE}-sdbx" in ready.refs("repo-a")


def test_tasks_and_date_are_rendered(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready, a_body=A_BODY + "\nData: {release_date}\n")
    _, (code, _, err) = run_all(capsys, "--repo", "repo-a")
    assert code == 0, err
    body = fake_gh.prs("acme/repo-a")[0]["body"]
    assert "- TS-101: https://example.atlassian.net/browse/TS-101" in body
    assert "- TS-102: https://example.atlassian.net/browse/TS-102" in body
    assert "Data: 20/11/2026" in body
    assert "{" not in body


def test_publish_after_editing_a_draft_does_nothing(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    out = preview(capsys)
    before = all_refs(ready)
    draft = ready.release_dir() / "pr" / "repo-a.md"
    draft.write_text(draft.read_text() + "\nmais uma linha\n")
    code, _, err = publish_with(capsys, out["code"])
    assert code == 1 and "o estado mudou" in err
    assert fake_gh.writes == []
    assert all_refs(ready) == before


def test_repeated_publish_is_a_no_op(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    _, (code, _, err) = run_all(capsys)
    assert code == 0, err
    sent = len(fake_gh.writes)
    refs = all_refs(ready)
    out, (code, result, err) = run_all(capsys)
    assert code == 0, err
    assert out["calls"] == []
    assert len(fake_gh.writes) == sent == 4
    assert all_refs(ready) == refs
    assert [row["code_pr"] for row in result["repos"]] == [1, 1]
    assert len(result["gmud"]) == 4


def test_merged_code_pr_is_skipped(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    fake_gh.add_pr("acme/repo-b", 5, ONLY, "master", state="MERGED", merged_at=MERGED)
    out, (code, result, err) = run_all(capsys)
    assert code == 0, err
    assert not any(line.startswith("repo-b") for line in out["calls"])
    assert ready.refs("repo-b")[f"refs/heads/{ONLY}"] != ready.git("repo-b", "rev-parse", ONLY)
    assert [pr["number"] for pr in fake_gh.prs("acme/repo-b")] == [5]
    assert result["repos"][1] == {
        "repo": "repo-b",
        "code_pr": 5,
        "sandbox_pr": None,
        "skipped": True,
    }
    record = json.loads((ready.release_dir() / "published.json").read_text())
    assert record["repos"]["repo-b"]["code_pr"] == 5


def merge_into_origin_sandbox(world):
    world.git("repo-a", "checkout", "-q", "sandbox")
    world.git("repo-a", "merge", "-q", "--no-edit", CODE)
    world.git("repo-a", "push", "-q", "origin", "sandbox")
    world.git("repo-a", "checkout", "-q", "master")
    world.git("repo-a", "fetch", "-q", "origin")


def test_second_sandbox_pr_from_the_sandbox_2_draft(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready, sandbox=True)
    merge_into_origin_sandbox(ready)
    fake_gh.add_pr("acme/repo-a", 9, CODE, "sandbox", state="MERGED", merged_at=MERGED)
    out = preview(capsys, "--repo", "repo-a")
    assert [line for line in out["calls"] if "--base sandbox" in line] == []
    worktree = ready.release_dir() / "repo-a"
    (worktree / "more.txt").write_text("more\n")
    ready.git("repo-a", "-C", str(worktree), "add", "more.txt")
    ready.git("repo-a", "-C", str(worktree), "commit", "-q", "-m", "feat(TS-101): mais um")
    code, out, err = cli_run(
        capsys, "preview", "publish", DAY, "--project", "demo", "--repo", "repo-a"
    )
    assert code == 1 and "repo-a-sandbox-2.md" in json.dumps(out)
    ready.write_pr("repo-a-sandbox-2", A_TITLE + " 2 (sdbx)", ["TS-101", "TS-102"], A_BODY)
    _, (code, _, err) = run_all(capsys, "--repo", "repo-a")
    assert code == 0, err
    titles = [call[call.index("--title") + 1] for call in creates(fake_gh)]
    assert titles == [A_TITLE, A_TITLE + " 2 (sdbx)"]


def test_non_fast_forward_origin_is_a_problem(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    sandbox_tip = ready.git("repo-a", "rev-parse", "origin/sandbox")
    ready.git("repo-a", "push", "-q", "origin", f"{sandbox_tip}:refs/heads/{CODE}")
    before = all_refs(ready)
    code, out, err = cli_run(
        capsys, "preview", "publish", DAY, "--project", "demo", "--repo", "repo-a"
    )
    assert code == 1
    assert any("is not an ancestor" in problem for problem in out["problems"])
    assert fake_gh.writes == [] and all_refs(ready) == before


def test_fetch_runs_for_every_repo_of_the_release(ready, fake_gh, monkeypatch, capsys):  # noqa: F811
    drafts(ready)
    fetched = []
    monkeypatch.setattr(gitops, "fetch", lambda repo: fetched.append(repo.name))
    preview(capsys)
    assert sorted(fetched) == ["repo-a", "repo-b"]
    fetched.clear()
    preview(capsys, "--repo", "repo-b")
    assert fetched == ["repo-b"]


def test_fetch_failure_is_a_warning_in_every_json(ready, fake_gh, monkeypatch, capsys):  # noqa: F811
    drafts(ready)
    monkeypatch.setattr(gitops, "fetch", lambda repo: "boom")
    out = preview(capsys)
    assert "repo-a: fetch failed: boom" in out["warnings"]
    code, result, err = publish_with(capsys, out["code"])
    assert code == 0, err
    assert "repo-b: fetch failed: boom" in result["warnings"]
    ready.commit("repo-a", "master", "later.txt", "later\n", "chore: later")
    code, refused, _ = cli_run(capsys, "preview", "publish", DAY, "--project", "demo")
    assert code == 1 and "repo-a: fetch failed: boom" in refused["warnings"]


def test_repos_follow_the_config_order(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    ready.write_release({"repo-b": [ONLY], "repo-a": [ONE, TWO]})
    out = preview(capsys)
    assert out["calls"][0].startswith("repo-a:") and out["calls"][-1].startswith("repo-b:")


def test_a_repo_outside_the_release_is_refused(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    ready.write_release({"repo-b": [ONLY]})
    code, _, err = cli_run(
        capsys, "preview", "publish", DAY, "--project", "demo", "--repo", "repo-a"
    )
    assert code == 1 and "repo-a not in" in err


def test_bad_day_and_git_failure_exit_cleanly(ready, fake_gh, monkeypatch, capsys):  # noqa: F811
    drafts(ready)
    code, _, _ = cli_run(capsys, "preview", "publish", "20261399", "--project", "demo")
    assert code == 1
    code, _, _ = cli_run(capsys, "preview", "publish", "soon", "--project", "demo")
    assert code == 1

    def broken(*args, **kwargs):
        raise gitops.GitFailed("boom")

    monkeypatch.setattr(gitops, "count", broken)
    code, _, err = cli_run(capsys, "preview", "publish", DAY, "--project", "demo")
    assert code == 2 and "git: boom" in err


def test_a_bad_published_json_stops_the_preview(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    path = ready.release_dir() / "published.json"
    for bad in ("{not json", "[1]"):
        path.write_text(bad)
        code, _, err = cli_run(capsys, "preview", "publish", DAY, "--project", "demo")
        assert code == 2 and "published.json" in err
    assert fake_gh.writes == []


def test_a_head_outside_the_task_branch_pattern_is_a_problem(ready, fake_gh, capsys):  # noqa: F811
    odd = "feat/TS-301-odd"
    ready.branch("repo-b", odd, "origin/master")
    ready.commit("repo-b", odd, "odd.txt", "odd\n", "feat(TS-301): estranho")
    ready.git("repo-b", "checkout", "-q", "master")
    ready.write_release({"repo-b": [odd]})
    ready.write_pr("repo-b", "feat(TS-301): estranho", ["TS-301"], B_BODY)
    code, out, err = cli_run(capsys, "preview", "publish", DAY, "--project", "demo")
    assert code == 1 and "outside the allowed shapes" in err
    assert any("outside the allowed shapes" in problem for problem in out["problems"])
    assert not list(writeplan.store().glob("*.json"))


def test_forward_placeholders_resolved_by_the_second_pass(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready, a_body=A_BODY + "\nDepende de {pr:repo-b}.\n")
    out, (code, _, err) = run_all(capsys)
    assert code == 0, err
    assert any("segunda passada" in line for line in out["summary"])
    assert [call[:2] for call in fake_gh.writes].count(["pr", "edit"]) == 2
    for pr in fake_gh.prs("acme/repo-a"):
        assert "Depende de acme/repo-b#1." in pr["body"]


def test_a_rerun_completes_the_placeholders_left_on_open_prs(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready, a_body=A_BODY + "\nDepende de {pr:repo-b}.\n")
    fake_gh.fail("pr edit", "HTTP 422")
    out = preview(capsys)
    code, _, _ = publish_with(capsys, out["code"])
    assert code == 1
    assert "{pr:repo-b}" in fake_gh.prs("acme/repo-a")[0]["body"]
    state = fake_gh._read()
    state["failures"] = {}
    fake_gh._write(state)
    out, (code, _, err) = run_all(capsys)
    assert code == 0, err
    assert [line for line in out["summary"] if "segunda passada" in line]
    assert not any("pr create" in line for line in out["calls"])
    for pr in fake_gh.prs("acme/repo-a"):
        assert "Depende de acme/repo-b#1." in pr["body"]


def test_no_push_is_forced(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready, sandbox=True)
    behind = ready.git("repo-a", "rev-parse", f"{CODE}~1")
    ready.git("repo-a", "push", "-q", "origin", f"{behind}:refs/heads/{CODE}")
    before = all_refs(ready)
    out, (code, _, err) = run_all(capsys)
    assert code == 0, err
    for line in out["calls"]:
        words = line.split()
        assert "-f" not in words and not any(w.startswith("--force") for w in words)
        assert not any(w.startswith("+") for w in words)
    assert any(line.startswith("repo-a: git push") for line in out["calls"])
    for name, refs in before.items():
        after = all_refs(ready)[name]
        for ref, sha in refs.items():
            if after[ref] != sha:
                origin = ready.origin(name)
                done = subprocess.run(
                    ["git", "-C", str(origin), "merge-base", "--is-ancestor", sha, after[ref]]
                )
                assert done.returncode == 0, ref
    assert ready.refs("repo-a")[f"refs/heads/{CODE}"] == ready.git("repo-a", "rev-parse", CODE)


def test_publish_refuses_a_repo_that_is_not_ready(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready)
    out = preview(capsys)
    ready.commit("repo-a", "master", "later.txt", "later\n", "chore: later")
    before = all_refs(ready)
    code, _, err = publish_with(capsys, out["code"])
    assert code == 1 and "master moved" in err
    code, payload, err = cli_run(capsys, "preview", "publish", DAY, "--project", "demo")
    assert code == 1 and "master moved" in err
    assert any("master moved" in problem for problem in payload["problems"])
    assert fake_gh.writes == []
    assert all_refs(ready) == before


def test_publish_records_published_json(ready, fake_gh, capsys):  # noqa: F811
    drafts(ready, sandbox=True)
    path = ready.release_dir() / "published.json"
    path.write_text(json.dumps({"keep": 1, "repos": {"repo-a": {"note": "x"}}}))
    _, (code, _, err) = run_all(capsys)
    assert code == 0, err
    data = json.loads(path.read_text())
    assert data["keep"] == 1
    assert data["repos"]["repo-a"] == {
        "note": "x",
        "shape": "multi",
        "code_branch": CODE,
        "sandbox_branch": CODE,
        "code_pr": 1,
        "sandbox_pr": 2,
    }
    assert data["repos"]["repo-b"] == {
        "shape": "single",
        "code_branch": ONLY,
        "sandbox_branch": ONLY,
        "code_pr": 1,
        "sandbox_pr": 2,
    }
    assert build.read_published(ready.release_dir())["repo-b"]["shape"] == "single"


def test_release_fixtures_pass_check_secrets(ws_config, ready, tmp_path, monkeypatch, capsys):
    drafts(ready, sandbox=True)
    _, (code, result, err) = run_all(capsys)
    assert code == 0, err
    saved = tmp_path / "publish-output.json"
    saved.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    blocks = (ws_config / "names.toml").read_text(encoding="utf-8").split("[[names]]")
    others = "[[names]]".join(block for block in blocks if "Acme" not in block)
    names = tmp_path / "names-without-the-fixture-org"
    names.mkdir()
    (names / "names.toml").write_text(others, encoding="utf-8")
    monkeypatch.setenv("WS_CONFIG_DIR", str(names))
    monkeypatch.chdir(REPO_ROOT)
    paths = ["tests/release_helpers.py", "tests/fake_gh.py", str(saved)]
    assert cli.main(["check-secrets", *paths]) == 0
