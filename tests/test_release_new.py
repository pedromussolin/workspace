import argparse
import json
import subprocess
from pathlib import Path

from fake_gh import fake_gh  # noqa: F401
from release_helpers import DAY, REV_BASE, World

from ws.release import build

pytest_plugins = ["release_helpers"]

CODE = f"release/{DAY}"
ONE, TWO, ONLY = "feature/TS-101-one", "feature/TS-102-two", "feature/TS-201-only"
BASE = "origin/master"


def _new(capsys, day: str = DAY, repos: list[str] | None = None) -> tuple[int, dict, str]:
    args = argparse.Namespace(project="demo", day=day, repos=repos or [])
    code = build.run_new(args)
    captured = capsys.readouterr()
    out = captured.out
    return code, json.loads(out) if out.strip() else {}, captured.err


def _setup(world: World, *, a=(ONE, TWO), b=(ONLY,)) -> None:
    include = {"repo-a": list(a)}
    if b:
        include["repo-b"] = list(b)
    world.write_release(include)


def _repo(payload: dict, name: str) -> dict:
    return next(r for r in payload["repos"] if r["repo"] == name)


def _first_parent(world: World, repo: str, ref: str) -> list[str]:
    out = world.git(repo, "log", "--first-parent", "--merges", "--format=%s", ref)
    return list(reversed(out.splitlines()))


def _stack(world: World) -> None:
    world.git("repo-a", "push", "-q", "origin", "--delete", TWO)
    world.git("repo-a", "branch", "-q", "-D", TWO)
    world.branch("repo-a", TWO, ONE)
    world.commit("repo-a", TWO, "two.txt", "two\n", "feat: two")
    world.git("repo-a", "checkout", "-q", "master")


def _conflict_with_sandbox(world: World) -> None:
    world.commit("repo-a", "sandbox", "shared.txt", "sandbox\n", "chore: shared sandbox")
    world.commit("repo-a", ONE, "shared.txt", "one\n", "feat: shared one")
    world.git("repo-a", "checkout", "-q", "master")


def test_new_two_includes_build_the_release_branch(world, fixed_today, capsys):
    _setup(world)
    code, out, _ = _new(capsys)
    assert code == 0
    repo = _repo(out, "repo-a")
    assert repo["ready"] is True and repo["code_branch"] == CODE
    assert repo["worktree"] == str(world.release_dir() / "repo-a")
    upstream = subprocess.run(
        ["git", "-C", str(world.clone("repo-a")), "rev-parse", "--abbrev-ref", f"{CODE}@{{u}}"],
        capture_output=True,
        text=True,
    )
    assert upstream.returncode != 0
    assert _first_parent(world, "repo-a", CODE) == [
        "chore(TS-101): junta a feature/TS-101-one",
        "chore(TS-102): junta a feature/TS-102-two",
    ]
    assert Path(repo["worktree"]).is_relative_to(world.release_dir())
    assert not Path(repo["worktree"]).is_relative_to(world.clone("repo-a"))


def test_new_single_include_builds_nothing(world, fixed_today, capsys):
    _setup(world)
    code, out, _ = _new(capsys)
    repo = _repo(out, "repo-b")
    assert code == 0 and repo["code_branch"] == ONLY
    assert world.git("repo-b", "branch", "--list", CODE) == ""
    assert not (world.release_dir() / "repo-b").exists()


def test_new_clean_sandbox_makes_no_sdbx(world, fixed_today, capsys):
    _setup(world)
    code, out, _ = _new(capsys)
    assert code == 0
    for name in ("repo-a", "repo-b"):
        assert world.git(name, "branch", "-a", "--list", "*-sdbx") == ""
        assert _repo(out, name)["sdbx"] is None


def test_new_conflicting_sandbox_makes_the_sdbx_and_stops(world, fixed_today, capsys):
    _setup(world)
    _conflict_with_sandbox(world)
    code, out, _ = _new(capsys)
    assert code == 3
    conflict = out["conflict"]
    sdbx = world.release_dir() / "repo-a-sdbx"
    assert conflict["repo"] == "repo-a" and conflict["worktree"] == str(sdbx)
    assert conflict["merging"] is True and conflict["files"] == ["shared.txt"]
    head = world.git("repo-a", "-C", str(sdbx), "rev-parse", "--abbrev-ref", "HEAD")
    assert head == f"{CODE}-sdbx"


def test_new_after_the_resolution_is_ready(world, fixed_today, capsys):
    _setup(world)
    _conflict_with_sandbox(world)
    _new(capsys)
    sdbx = world.release_dir() / "repo-a-sdbx"
    (sdbx / "shared.txt").write_text("resolved\n")
    world.git("repo-a", "-C", str(sdbx), "add", "shared.txt")
    world.git("repo-a", "-C", str(sdbx), "commit", "-q", "--no-edit")
    code, out, _ = _new(capsys)
    assert code == 0
    repo = _repo(out, "repo-a")
    assert repo["ready"] is True and "shared.txt" in repo["sdbx_differs"]


def test_new_rerun_changes_nothing(world, fixed_today, capsys):
    _setup(world)
    _new(capsys)
    tip = world.git("repo-a", "rev-parse", CODE)
    code, _, _ = _new(capsys)
    assert code == 0 and world.git("repo-a", "rev-parse", CODE) == tip


def test_new_conflict_with_a_task_branch_exits_3(world, fixed_today, capsys):
    _setup(world)
    world.commit("repo-a", ONE, "shared.txt", "one\n", "feat: shared one")
    world.commit("repo-a", TWO, "shared.txt", "two\n", "feat: shared two")
    world.git("repo-a", "checkout", "-q", "master")
    code, out, _ = _new(capsys)
    assert code == 3
    assert out["conflict"]["files"] == ["shared.txt"] and out["conflict"]["merging"] is True
    assert out["conflict"]["worktree"] == str(world.release_dir() / "repo-a")


def test_new_merges_master_when_it_moved(world, fixed_today, capsys):
    _setup(world)
    _new(capsys)
    world.commit("repo-a", "master", "moved.txt", "m\n", "chore: master moves")
    code, _, _ = _new(capsys)
    assert code == 0
    assert (
        _first_parent(world, "repo-a", CODE)[-1] == "chore(TS-101, TS-102): atualiza com a master"
    )


def test_new_merge_in_progress_exits_2(world, fixed_today, capsys):
    _setup(world)
    world.commit("repo-a", ONE, "shared.txt", "one\n", "feat: shared one")
    world.commit("repo-a", TWO, "shared.txt", "two\n", "feat: shared two")
    world.git("repo-a", "checkout", "-q", "master")
    assert _new(capsys)[0] == 3
    code, _, err = _new(capsys)
    assert code == 2 and "merge" in err


def test_new_single_published_now_two_exits_2(world, fixed_today, capsys):
    _setup(world)
    published = {"repos": {"repo-a": {"shape": "single", "code_branch": ONE, "code_pr": 7}}}
    (world.release_dir() / "published.json").write_text(json.dumps(published))
    code, _, err = _new(capsys)
    assert code == 2
    assert f"repo-a was published from {ONE} (PR #7); with more task branches" in err
    assert world.git("repo-a", "branch", "--list", CODE) == ""


def test_new_refuses_a_release_branch_only_on_origin(world, fixed_today, capsys):
    _setup(world)
    world.git("repo-a", "push", "-q", "origin", f"{ONE}:refs/heads/{CODE}")
    code, _, err = _new(capsys)
    assert code == 2 and CODE in err


def test_new_single_merges_master_where_the_branch_is_checked_out(world, fixed_today, capsys):
    _setup(world)
    world.commit("repo-b", "master", "moved.txt", "m\n", "chore: master moves")
    world.git("repo-b", "checkout", "-q", ONLY)
    code, out, _ = _new(capsys)
    assert code == 0
    assert _first_parent(world, "repo-b", ONLY)[-1] == "chore(TS-201): atualiza com a master"
    assert _repo(out, "repo-b")["worktree"] == str(world.clone("repo-b").resolve())


def test_new_single_merges_master_in_a_worktree_when_not_checked_out(world, fixed_today, capsys):
    _setup(world)
    world.commit("repo-b", "master", "moved.txt", "m\n", "chore: master moves")
    world.git("repo-b", "checkout", "-q", "master")
    code, out, _ = _new(capsys)
    assert code == 0
    path = world.release_dir() / "repo-b"
    assert _repo(out, "repo-b")["worktree"] == str(path)
    assert not path.is_relative_to(world.clone("repo-b"))
    assert _first_parent(world, "repo-b", ONLY)[-1] == "chore(TS-201): atualiza com a master"


def test_new_refuses_a_past_date(world, fixed_today, capsys):
    world.write_release({"repo-a": [ONE, TWO]}, day="20261101")
    code, _, err = _new(capsys, day="20261101")
    assert code == 1 and "past" in err


def test_new_pushes_nothing_and_calls_no_gh(world, fixed_today, fake_gh, capsys):  # noqa: F811
    _setup(world)
    before = {n: world.refs(n) for n in ("repo-a", "repo-b")}
    _new(capsys)
    assert {n: world.refs(n) for n in ("repo-a", "repo-b")} == before
    assert fake_gh.calls == []


def test_new_refuses_stacked_branches_out_of_order(world, fixed_today, capsys):
    _stack(world)
    _setup(world, a=(TWO, ONE), b=())
    code, out, _ = _new(capsys)
    assert code == 1
    assert world.git("repo-a", "branch", "--list", CODE) == ""
    assert out["suggested_order"] == {"repo-a": [ONE, TWO]}


def test_new_stacked_in_order_merges_each_task(world, fixed_today, capsys):
    _stack(world)
    _setup(world, a=(ONE, TWO), b=())
    code, _, _ = _new(capsys)
    assert code == 0
    assert world.git("repo-a", "rev-list", "--count", f"{CODE}^1..{CODE}^2") == "1"


def test_new_reports_two_alembic_heads(world, fixed_today, capsys):
    world.migration("repo-a", ONE, "bbb000000002", REV_BASE)
    world.migration("repo-a", TWO, "ccc000000003", REV_BASE)
    world.git("repo-a", "checkout", "-q", "master")
    _setup(world)
    code, out, _ = _new(capsys)
    assert code == 1
    problems = _repo(out, "repo-a")["problems"]
    assert f"repo-a: 2 alembic heads at {CODE}: bbb000000002, ccc000000003" in problems


def test_new_reports_heads_on_the_sandbox_side(world, fixed_today, capsys):
    world.migration("repo-a", ONE, "bbb000000002", REV_BASE)
    world.migration("repo-a", "sandbox", "ddd000000004", REV_BASE)
    world.git("repo-a", "checkout", "-q", "master")
    _setup(world)
    code, out, _ = _new(capsys)
    assert code == 1
    assert any("the sandbox merge" in p for p in _repo(out, "repo-a")["problems"])


def test_new_refuses_a_local_branch_behind_origin(world, fixed_today, capsys, tmp_path):
    _setup(world)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(world.origin("repo-a")), str(other)], check=True)
    subprocess.run(["git", "-C", str(other), "checkout", "-q", ONE], check=True)
    (other / "more.txt").write_text("more\n")
    subprocess.run(["git", "-C", str(other), "add", "more.txt"], check=True, env=world.env)
    subprocess.run(
        ["git", "-C", str(other), "commit", "-q", "-m", "feat: more"], check=True, env=world.env
    )
    subprocess.run(["git", "-C", str(other), "push", "-q", "origin", ONE], check=True)
    code, out, _ = _new(capsys)
    assert code == 1
    assert (
        f"repo-a: local {ONE} is behind origin/{ONE}; pull it first" in out["repos"][0]["problems"]
    )
    assert world.git("repo-a", "branch", "--list", CODE) == ""
