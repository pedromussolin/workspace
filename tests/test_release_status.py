import argparse
import json

from fake_gh import fake_gh  # noqa: F401
from release_helpers import DAY, World, fixed_today  # noqa: F401

from ws.release import status

pytest_plugins = ["release_helpers"]

CODE = f"release/{DAY}"
ONE, TWO, ONLY = "feature/TS-101-one", "feature/TS-102-two", "feature/TS-201-only"
BASE = "origin/master"


def _run(capsys, day: str | None = DAY, **kwargs) -> tuple[int, dict]:
    args = argparse.Namespace(**{"project": "demo", "day": day, "links": False, **kwargs})
    code = status.run_status(args)
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else {}


def _release(world: World, *, repo_b: bool = True) -> None:
    include = {"repo-a": [ONE, TWO]}
    if repo_b:
        include["repo-b"] = [ONLY]
    world.write_release(include)
    world.branch("repo-a", CODE, BASE, push=False)
    for branch in (ONE, TWO):
        world.git(
            "repo-a",
            "merge",
            "--no-ff",
            "-m",
            f"chore({branch.split('/')[1][:6]}): junta a {branch}",
            branch,
        )
    world.git("repo-a", "checkout", "-q", "master")


def _repo(payload: dict, name: str) -> dict:
    return next(r for r in payload["repos"] if r["repo"] == name)


def test_status_multi_clean(world: World, fake_gh, capsys):  # noqa: F811
    _release(world, repo_b=False)
    fake_gh.add_pr("acme/repo-a", 12, CODE, "master")
    fake_gh.add_pr("acme/repo-a", 13, CODE, "sandbox")
    fake_gh.set_checks("acme/repo-a", 12, "MERGEABLE", {"ci": "SUCCESS"})
    code, payload = _run(capsys)
    assert code == 0
    repo = _repo(payload, "repo-a")
    assert repo["problems"] == [] and repo["shape"] == "multi"
    prs = {p["number"]: p for p in repo["prs"]}
    assert prs[12]["base"] == "master" and prs[12]["state"] == "OPEN"
    assert prs[12]["mergeable"] == "MERGEABLE" and prs[12]["checks"] == {"ci": "SUCCESS"}
    assert prs[13]["base"] == "sandbox"
    assert "links" not in payload


def test_status_single_clean(world: World, fake_gh, capsys):  # noqa: F811
    world.write_release({"repo-b": [ONLY]})
    fake_gh.add_pr("acme/repo-b", 5, ONLY, "master")
    code, payload = _run(capsys)
    assert code == 0
    repo = _repo(payload, "repo-b")
    assert repo["shape"] == "single" and repo["problems"] == []
    assert [p["number"] for p in repo["prs"]] == [5]


def test_status_behind_master_exits_1(world: World, fake_gh, capsys):  # noqa: F811
    _release(world, repo_b=False)
    world.commit("repo-a", "master", "m.txt", "m\n", "chore: master moves")
    code, payload = _run(capsys)
    assert code == 1
    assert any("master moved" in p for p in _repo(payload, "repo-a")["problems"])


def test_status_broken_mirror_exits_1(world: World, fake_gh, capsys):  # noqa: F811
    _release(world, repo_b=False)
    world.git("repo-a", "checkout", "-q", CODE)
    world.branch("repo-a", f"{CODE}-sdbx", CODE, push=False)
    world.git("repo-a", "merge", "--no-ff", "-m", "chore(TS-101): junta", "origin/sandbox")
    world.commit("repo-a", f"{CODE}-sdbx", "own.txt", "own\n", "feat: own", push=False)
    code, payload = _run(capsys)
    assert code == 1
    assert any("has commits of its own" in p for p in _repo(payload, "repo-a")["problems"])


def test_status_links_order_and_format(world: World, fake_gh, capsys):  # noqa: F811
    _release(world)
    fake_gh.add_pr("acme/repo-b", 7, ONLY, "master")
    fake_gh.add_pr("acme/repo-a", 12, CODE, "master")
    fake_gh.add_pr("acme/repo-a", 13, CODE, "sandbox")
    code, payload = _run(capsys, links=True)
    assert code == 0
    assert payload["links"] == [
        "repo-a, PR #12: https://github.com/acme/repo-a/pull/12",
        "repo-b, PR #7: https://github.com/acme/repo-b/pull/7",
        "repo-a (sandbox), PR #13: https://github.com/acme/repo-a/pull/13",
    ]


def test_status_without_a_date_lists_releases(world: World, fake_gh, capsys):  # noqa: F811
    world.write_release({"repo-a": [ONE, TWO]})
    world.write_release({"repo-b": [ONLY]}, day="20261127")
    fake_gh.add_pr("acme/repo-a", 12, CODE, "master")
    fake_gh.add_pr("acme/repo-a", 14, "feature/TS-9-x", "master")
    fake_gh.add_pr("acme/repo-a", 15, "release/20261204", "master")
    fake_gh.add_pr("acme/repo-a", 16, "release/20261211", "master", state="MERGED")
    code, payload = _run(capsys, day=None)
    assert code == 0
    rows = {r["date"]: r for r in payload["releases"]}
    assert set(rows) == {"20261120", "20261127", "20261204"}
    assert rows["20261120"]["folder"] and rows["20261127"]["folder"]
    assert not rows["20261204"]["folder"]
    assert [p["number"] for p in rows["20261120"]["open_prs"]] == [12]
    assert [p["number"] for p in rows["20261204"]["open_prs"]] == [15]
    assert rows["20261127"]["open_prs"] == []


def test_status_makes_no_gh_write(world: World, fake_gh, capsys):  # noqa: F811
    _release(world)
    fake_gh.add_pr("acme/repo-a", 12, CODE, "master")
    _run(capsys, links=True)
    _run(capsys, day=None)
    assert fake_gh.calls
    assert fake_gh.writes == []
