import argparse
import json

from fake_gh import fake_gh  # noqa: F401
from release_helpers import World

from ws.release import branches

pytest_plugins = ["release_helpers"]


def _run(capsys, **kwargs) -> tuple[int, dict]:
    args = argparse.Namespace(**{"project": None, "tasks": [], "items": [], "repos": [], **kwargs})
    code = branches.run_branches(args)
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else {}


def _repo(payload: dict, name: str) -> dict:
    return next(r for r in payload["repos"] if r["repo"] == name)


def _entry(payload: dict, name: str, branch: str) -> dict:
    return next(b for b in _repo(payload, name)["branches"] if b["branch"] == branch)


def _stack(world: World) -> None:
    """TS-102 is recut from TS-101, as in a stacked release."""
    world.git("repo-a", "push", "-q", "origin", "--delete", "feature/TS-102-two")
    world.git("repo-a", "branch", "-q", "-D", "feature/TS-102-two")
    world.branch("repo-a", "feature/TS-102-two", "feature/TS-101-one")
    world.commit("repo-a", "feature/TS-102-two", "two.txt", "two\n", "feat: two")
    world.git("repo-a", "checkout", "-q", "master")


def _items(world: World, fronts: dict[str, tuple[str, str, str]]) -> None:
    tasks = world.root / "root" / "projects" / "demo" / "tasks"
    tasks.mkdir(parents=True)
    (tasks.parent / "project.toml").write_text("epics = []\n", encoding="utf-8")
    for name, (card, status, extra) in fronts.items():
        text = f'+++\ncard = "{card}"\n{extra}\n[tracker]\nstatus = "{status}"\n+++\n# {card}\n'
        (tasks / name).write_text(text, encoding="utf-8")


def test_branches_finds_task_branches_by_key(world, capsys):
    code, out = _run(capsys, tasks=["TS-101"])
    assert code == 0
    entry = _entry(out, "repo-a", "feature/TS-101-one")
    assert (entry["key"], entry["local"], entry["remote"]) == ("TS-101", True, True)
    assert (entry["ahead"], entry["merged"], entry["sdbx"]) == (1, False, None)
    assert [b["branch"] for b in _repo(out, "repo-b")["branches"]] == []


def test_branches_reports_the_sdbx_copy_inside_the_entry(world, capsys):
    world.branch("repo-a", "feature/TS-101-one-sdbx", "feature/TS-101-one")
    world.git("repo-a", "checkout", "-q", "master")
    code, out = _run(capsys, tasks=["TS-101"])
    names = [b["branch"] for b in _repo(out, "repo-a")["branches"]]
    assert names == ["feature/TS-101-one"]
    sdbx = _entry(out, "repo-a", "feature/TS-101-one")["sdbx"]
    assert sdbx == {"branch": "feature/TS-101-one-sdbx", "contains": True}


def test_branches_reports_merged(world, capsys):
    world.git("repo-a", "checkout", "-q", "master")
    world.git("repo-a", "merge", "-q", "--no-ff", "-m", "merge", "feature/TS-101-one")
    world.git("repo-a", "push", "-q", "origin", "master")
    code, out = _run(capsys, tasks=["TS-101"])
    assert _entry(out, "repo-a", "feature/TS-101-one")["merged"] is True


def test_branches_key_boundary(world, capsys):
    code, out = _run(capsys, tasks=["TS-10"])
    assert _repo(out, "repo-a")["branches"] == []
    assert out["unmatched"] == ["TS-10"]


def test_branches_suggests_the_order_of_stacked_branches(world, capsys):
    _stack(world)
    code, out = _run(capsys, tasks=["TS-102", "TS-101"])
    repo = _repo(out, "repo-a")
    assert repo["suggested_order"] == ["feature/TS-101-one", "feature/TS-102-two"]
    assert _entry(out, "repo-a", "feature/TS-102-two")["contains"] == ["feature/TS-101-one"]
    assert repo["problems"] == []


def test_branches_lists_migrations(world, capsys):
    world.branch("repo-a", "feature/TS-103-mig", "master")
    world.migration("repo-a", "feature/TS-103-mig", "bbb000000002", "aaa000000001")
    world.git("repo-a", "checkout", "-q", "master")
    code, out = _run(capsys, tasks=["TS-103"])
    entry = _entry(out, "repo-a", "feature/TS-103-mig")
    assert entry["migrations"] == [{"revision": "bbb000000002", "down": ["aaa000000001"]}]


def test_branches_from_items(world, capsys):
    _items(
        world,
        {
            "01-a.md": ("TS-101", "validation", 'blocks = ["TS-102"]\n'),
            "02-b.md": ("TS-102", "in_progress", ""),
            "03-c.md": ("TS-103", "done", ""),
        },
    )
    code, out = _run(capsys, items=["demo"])
    assert code == 0
    assert [i["card"] for i in out["items"]] == ["TS-101", "TS-102"]
    assert out["items"][0]["blocks"] == ["TS-102"]
    assert [b["key"] for b in _repo(out, "repo-a")["branches"]] == ["TS-101", "TS-102"]
    assert _repo(out, "repo-a")["suggested_order"] == [
        "feature/TS-101-one",
        "feature/TS-102-two",
    ]


def test_branches_is_read_only(world, fake_gh, capsys):  # noqa: F811
    before = {n: world.refs(n) for n in ("repo-a", "repo-b")}
    _run(capsys, tasks=["TS-101", "TS-102", "TS-201"])
    assert {n: world.refs(n) for n in ("repo-a", "repo-b")} == before
    assert fake_gh.calls == []


def test_branches_orders_stacked_branches_with_chained_migrations(world, capsys):
    world.git("repo-a", "push", "-q", "origin", "--delete", "feature/TS-102-two")
    world.git("repo-a", "branch", "-q", "-D", "feature/TS-102-two")
    world.migration("repo-a", "feature/TS-101-one", "a1000000001", "aaa000000001")
    world.migration("repo-a", "feature/TS-101-one", "a2000000002", "a1000000001")
    world.branch("repo-a", "feature/TS-102-two", "feature/TS-101-one")
    world.migration("repo-a", "feature/TS-102-two", "b1000000003", "a2000000002")
    world.git("repo-a", "checkout", "-q", "master")
    code, out = _run(capsys, tasks=["TS-102", "TS-101"])
    repo = _repo(out, "repo-a")
    assert repo["suggested_order"] == ["feature/TS-101-one", "feature/TS-102-two"]
    assert repo["problems"] == []


def test_branches_reports_a_real_cycle(world, capsys):
    _stack(world)
    _items(
        world,
        {
            "01-a.md": ("TS-101", "in_progress", 'blocked_by = ["TS-102"]\n'),
            "02-b.md": ("TS-102", "in_progress", ""),
        },
    )
    code, out = _run(capsys, items=["demo"])
    assert code == 0
    assert any("cycle" in p for p in _repo(out, "repo-a")["problems"])


def test_branches_warns_on_a_dangling_link(world, capsys):
    _items(world, {"01-a.md": ("TS-101", "in_progress", 'blocks = ["../nope/tasks/x.md"]\n')})
    args = argparse.Namespace(project=None, tasks=[], items=["demo"], repos=[])
    assert branches.run_branches(args) == 0
    captured = capsys.readouterr()
    err, out = captured.err, json.loads(captured.out)
    assert "TS-101 blocks ../nope/tasks/x.md" in err
    assert out["items"][0]["blocks"] == []


def test_branches_fetch_failure_is_a_warning(world, capsys):
    world.git("repo-b", "remote", "set-url", "origin", str(world.root / "nowhere.git"))
    code, out = _run(capsys, tasks=["TS-201"], repos=["repo-b"])
    repo = _repo(out, "repo-b")
    assert code == 0 and repo["problems"] == []
    assert len(repo["warnings"]) == 1 and repo["warnings"][0].startswith("fetch failed: ")


def test_branches_repo_flag_follows_the_config_order(world, capsys):
    code, out = _run(capsys, tasks=["TS-101"], repos=["repo-b", "repo-a", "repo-b"])
    assert code == 0 and [r["repo"] for r in out["repos"]] == ["repo-a", "repo-b"]
    assert _run(capsys, tasks=["TS-101"], repos=["repo-x"])[0] == 2
