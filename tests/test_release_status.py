import argparse
import json

from fake_gh import fake_gh  # noqa: F401
from release_helpers import DAY, World, fixed_today  # noqa: F401

from ws.release import status

pytest_plugins = ["release_helpers"]

CODE = f"release/{DAY}"
ONE, TWO, ONLY = "feature/TS-101-one", "feature/TS-102-two", "feature/TS-201-only"
BASE = "origin/master"
ERR: list[str] = [""]


def _run(capsys, day: str | None = DAY, **kwargs) -> tuple[int, dict]:
    args = argparse.Namespace(**{"project": "demo", "day": day, "links": False, **kwargs})
    code = status.run_status(args)
    captured = capsys.readouterr()
    ERR[:] = [captured.err]
    out = captured.out
    return code, json.loads(out) if out.strip() else {}


def _copy(world: World, repo: str, code: str, suffix: str = "-sdbx", env: str = "sandbox") -> None:
    """The copy of `code` for the environment `env`, as `ws release new` makes it."""
    world.git(repo, "checkout", "-q", code)
    world.branch(repo, f"{code}{suffix}", code, push=False)
    world.git(
        repo, "merge", "--no-ff", "-m", f"chore(TS-101): junta a {code} na {env}", f"origin/{env}"
    )
    world.git(repo, "checkout", "-q", "master")


def _release(world: World, *, repo_b: bool = True, copies: bool = True) -> None:
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
    if copies:
        _copy(world, "repo-a", CODE)
        if repo_b:
            _copy(world, "repo-b", ONLY)


def _repo(payload: dict, name: str) -> dict:
    return next(r for r in payload["repos"] if r["repo"] == name)


def test_status_multi_clean(world: World, fake_gh, capsys):  # noqa: F811
    _release(world, repo_b=False)
    fake_gh.add_pr("acme/repo-a", 12, CODE, "master")
    fake_gh.add_pr("acme/repo-a", 13, f"{CODE}-sdbx", "sandbox")
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
    _copy(world, "repo-b", ONLY)
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


def _conflict(world: World) -> None:
    world.commit("repo-a", "sandbox", "shared.txt", "sandbox\n", "chore: shared sandbox")
    world.commit("repo-a", ONE, "shared.txt", "one\n", "feat: shared one")
    world.git("repo-a", "checkout", "-q", "master")


def _sdbx(world: World) -> None:
    world.git("repo-a", "checkout", "-q", CODE)
    world.branch("repo-a", f"{CODE}-sdbx", CODE, push=False)
    world.git(
        "repo-a", "merge", "--no-ff", "-X", "ours", "-m", "chore(TS-101): junta", "origin/sandbox"
    )


def test_status_broken_mirror_exits_1(world: World, fake_gh, capsys):  # noqa: F811
    _conflict(world)
    _release(world, repo_b=False, copies=False)
    _sdbx(world)
    world.commit("repo-a", f"{CODE}-sdbx", "own.txt", "own\n", "feat: own", push=False)
    code, payload = _run(capsys)
    assert code == 1
    assert any("has commits of its own" in p for p in _repo(payload, "repo-a")["problems"])


def test_status_links_order_and_format(world: World, fake_gh, capsys):  # noqa: F811
    _release(world)
    fake_gh.add_pr("acme/repo-b", 7, ONLY, "master")
    fake_gh.add_pr("acme/repo-a", 12, CODE, "master")
    fake_gh.add_pr("acme/repo-a", 13, f"{CODE}-sdbx", "sandbox")
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


def test_status_sandbox_only_release_pr_is_listed(world: World, fake_gh, capsys):  # noqa: F811
    fake_gh.add_pr("acme/repo-a", 13, f"{CODE}-sdbx", "sandbox")
    code, payload = _run(capsys, day=None)
    assert code == 0
    row = next(r for r in payload["releases"] if r["date"] == DAY)
    assert not row["folder"]
    assert [p["number"] for p in row["open_prs"]] == [13]


def test_status_links_warn_about_a_repo_without_pr(world: World, fake_gh, capsys):  # noqa: F811
    _release(world)
    fake_gh.add_pr("acme/repo-a", 12, CODE, "master")
    code, payload = _run(capsys, links=True)
    err = ERR[0]
    assert code == 0
    assert payload["links"] == ["repo-a, PR #12: https://github.com/acme/repo-a/pull/12"]
    assert f"repo-b: no code PR for {ONLY}; the links are incomplete" in err
    assert any("repo-a: no sandbox PR" in w for w in _repo(payload, "repo-a")["warnings"])
    assert any("repo-b: no sandbox PR" in w for w in _repo(payload, "repo-b")["warnings"])


def test_status_gh_failure_exits_2(world: World, fake_gh, capsys):  # noqa: F811
    _release(world)
    fake_gh.fail("pr list", "boom")
    code, _ = _run(capsys)
    assert code == 2
    assert "gh" in ERR[0]


def test_status_missing_folder_exits_2(world: World, fake_gh, capsys):  # noqa: F811
    code, _ = _run(capsys)
    assert code == 2
    assert "not found" in ERR[0]


def test_status_merged_pr_still_appears(world: World, fake_gh, capsys):  # noqa: F811
    world.write_release({"repo-b": [ONLY]})
    _copy(world, "repo-b", ONLY)
    fake_gh.add_pr("acme/repo-b", 5, ONLY, "master", state="MERGED", merged_at="2026-11-01")
    code, payload = _run(capsys)
    assert code == 0
    assert [(p["number"], p["state"]) for p in _repo(payload, "repo-b")["prs"]] == [(5, "MERGED")]


def test_status_links_follow_the_config_order(world: World, fake_gh, capsys):  # noqa: F811
    _release(world)
    world.write_release({"repo-b": [ONLY], "repo-a": [ONE, TWO]})
    fake_gh.add_pr("acme/repo-a", 10, CODE, "master")
    fake_gh.add_pr("acme/repo-b", 20, ONLY, "master")
    code, payload = _run(capsys, links=True)
    assert [r["repo"] for r in payload["repos"]] == ["repo-a", "repo-b"]
    assert [line.split(",")[0] for line in payload["links"]] == ["repo-a", "repo-b"]


def test_status_links_keep_the_sandbox_pr_of_a_merged_sdbx(world: World, fake_gh, capsys):  # noqa: F811
    _conflict(world)
    _release(world, repo_b=False, copies=False)
    _sdbx(world)
    world.git("repo-a", "push", "-q", "origin", CODE, f"{CODE}-sdbx")
    fake_gh.add_pr("acme/repo-a", 10, CODE, "master")
    fake_gh.add_pr("acme/repo-a", 11, f"{CODE}-sdbx", "sandbox", state="MERGED", merged_at="x")
    world.git("repo-a", "checkout", "-q", "sandbox")
    world.git("repo-a", "merge", "-q", "--no-ff", "-m", "Merge pull request #11", f"{CODE}-sdbx")
    world.git("repo-a", "push", "-q", "origin", "sandbox")
    world.git("repo-a", "checkout", "-q", "master")
    code, payload = _run(capsys, links=True)
    assert code == 0
    assert (
        payload["links"][-1] == "repo-a (sandbox), PR #11: https://github.com/acme/repo-a/pull/11"
    )
    assert _repo(payload, "repo-a")["warnings"] == []


def test_status_release_merged_into_master_is_reported_merged(world: World, fake_gh, capsys):  # noqa: F811
    _release(world, repo_b=False)
    world.git("repo-a", "push", "-q", "origin", CODE)
    world.git("repo-a", "merge", "-q", "--no-ff", "-m", "Merge pull request #10", CODE)
    world.git("repo-a", "push", "-q", "origin", "master")
    fake_gh.add_pr("acme/repo-a", 10, CODE, "master", state="MERGED", merged_at="x")
    code, payload = _run(capsys, links=True)
    repo = _repo(payload, "repo-a")
    assert code == 0
    assert repo["merged"] is True and repo["problems"] == []
    assert payload["links"][0] == "repo-a, PR #10: https://github.com/acme/repo-a/pull/10"


def test_status_open_release_is_not_merged(world: World, fake_gh, capsys):  # noqa: F811
    _release(world, repo_b=False)
    code, payload = _run(capsys)
    assert code == 0 and _repo(payload, "repo-a")["merged"] is False


def test_status_listing_fetches_and_reads_release_branches(world: World, fake_gh, capsys):  # noqa: F811
    world.branch("repo-b", "release/20261204", "master", push=False)
    world.git(
        "repo-b",
        "push",
        "-q",
        "origin",
        "release/20261204",
        "release/20261204:release/20261204-sdbx",
    )
    world.git("repo-b", "push", "-q", "origin", "release/20261204:release/20261204-sdbx-old")
    world.git("repo-b", "checkout", "-q", "master")
    world.git("repo-b", "update-ref", "-d", "refs/remotes/origin/release/20261204")
    fake_gh.add_pr("acme/repo-a", 17, "release/20261211-sdbx-old", "sandbox")
    code, payload = _run(capsys, day=None)
    assert code == 0 and payload["warnings"] == []
    rows = {r["date"]: r for r in payload["releases"]}
    assert set(rows) == {"20261204"}
    assert [b["branch"] for b in rows["20261204"]["branches"]] == [
        "release/20261204",
        "release/20261204-sdbx",
    ]


def test_status_exit_codes(world: World, fake_gh, capsys):  # noqa: F811
    world.write_release({"repo-a": [ONE, TWO]})
    assert _run(capsys, day="2026-1120")[0] == 2 and "is not a day" in ERR[0]
    folder = world.release_dir()
    (folder / "release.toml").write_text(
        'repos = ["repo-a", "repo-b"]\n[include]\nrepo-a = ["x/TS-1"]\n'
    )
    assert _run(capsys)[0] == 1 and "repo-b is in repos but has no include list" in ERR[0]


def _staging(world: World) -> None:
    world.add_staging()
    _release(world)
    _copy(world, "repo-a", CODE, "-stg", "staging")


def test_status_pr_kind_is_the_environment_name(world: World, fake_gh, capsys):  # noqa: F811
    _staging(world)
    fake_gh.add_pr("acme/repo-a", 12, CODE, "master")
    fake_gh.add_pr("acme/repo-a", 13, f"{CODE}-sdbx", "sandbox")
    fake_gh.add_pr("acme/repo-a", 14, f"{CODE}-stg", "staging")
    code, payload = _run(capsys)
    assert code == 0
    repo = _repo(payload, "repo-a")
    assert [(p["number"], p["kind"]) for p in repo["prs"]] == [
        (12, "code"),
        (13, "sandbox"),
        (14, "staging"),
    ]
    assert list(repo["environments"]) == ["sandbox", "staging"]


def test_status_covers_only_the_default_and_the_existing_copies(world: World, fake_gh, capsys):  # noqa: F811
    _staging(world)
    _, payload = _run(capsys)
    assert list(_repo(payload, "repo-a")["environments"]) == ["sandbox", "staging"]
    assert list(_repo(payload, "repo-b")["environments"]) == ["sandbox"]


def test_status_links_put_environments_after_code(world: World, fake_gh, capsys):  # noqa: F811
    _staging(world)
    fake_gh.add_pr("acme/repo-a", 14, f"{CODE}-stg", "staging")
    fake_gh.add_pr("acme/repo-a", 12, CODE, "master")
    fake_gh.add_pr("acme/repo-a", 13, f"{CODE}-sdbx", "sandbox")
    fake_gh.add_pr("acme/repo-b", 7, ONLY, "master")
    code, payload = _run(capsys, links=True)
    assert code == 0
    assert payload["links"] == [
        "repo-a, PR #12: https://github.com/acme/repo-a/pull/12",
        "repo-b, PR #7: https://github.com/acme/repo-b/pull/7",
        "repo-a (sandbox), PR #13: https://github.com/acme/repo-a/pull/13",
        "repo-a (staging), PR #14: https://github.com/acme/repo-a/pull/14",
    ]
    warnings = _repo(payload, "repo-b")["warnings"]
    assert warnings == [f"repo-b: no sandbox PR for {ONLY}; the links are incomplete"]


def test_status_listing_knows_every_configured_suffix(world: World, fake_gh, capsys):  # noqa: F811
    world.add_staging()
    fake_gh.add_pr("acme/repo-a", 18, "release/20261211-stg", "staging")
    fake_gh.add_pr("acme/repo-a", 19, "release/20261211-qa", "staging")
    _, payload = _run(capsys, day=None)
    rows = {r["date"]: r for r in payload["releases"]}
    assert [p["number"] for p in rows["20261211"]["open_prs"]] == [18]
