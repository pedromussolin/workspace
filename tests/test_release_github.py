import os

import pytest
from fake_gh import FakeGh, fake_gh  # noqa: F401

from ws.release.github import Gh, GhFailed, GhMissing, GhUncertain

SLUG = "acme/repo-a"


def test_require_auth_without_gh(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(GhMissing, match="gh is not installed"):
        Gh().require_auth()


def test_require_auth_logged_out(fake_gh):  # noqa: F811
    fake_gh.logged_out()
    with pytest.raises(GhMissing, match="gh is not logged in: run gh auth login"):
        Gh().require_auth()


def test_require_auth_ok(fake_gh):  # noqa: F811
    Gh().require_auth()
    assert fake_gh.calls == [["auth", "status"]]


def test_prs_filters_by_head(fake_gh):  # noqa: F811
    fake_gh.add_pr(SLUG, 1, "release/20261120", "master")
    fake_gh.add_pr(SLUG, 2, "feature/TS-1-x", "master", state="MERGED", merged_at="2026-11-01")
    found = Gh().prs(SLUG, head="release/20261120")
    assert [(p.number, p.state, p.base, p.head) for p in found] == [
        (1, "OPEN", "master", "release/20261120")
    ]
    assert len(Gh().prs(SLUG)) == 2
    assert [p.number for p in Gh().prs(SLUG, state="open")] == [1]
    assert Gh().prs(SLUG, base="sandbox") == []
    assert [p.merged_at for p in Gh().prs(SLUG, head="feature/TS-1-x")] == ["2026-11-01"]


def test_pr_reads_body_labels_and_assignees(fake_gh):  # noqa: F811
    fake_gh.add_pr(SLUG, 7, "h", "master", body="texto", labels=("release",), assignees=("ana",))
    pr = Gh().pr(SLUG, 7)
    assert pr.body == "texto"
    assert pr.labels == ("release",)
    assert pr.assignees == ("ana",)
    assert pr.url == f"https://github.com/{SLUG}/pull/7"


def test_write_create_returns_the_url_and_sends_the_body_by_file(fake_gh):  # noqa: F811
    argv = ("pr", "create", "-R", SLUG, "--base", "master", "--head", "h", "--title", "t")
    url = Gh().write(argv, "corpo")
    assert url == f"https://github.com/{SLUG}/pull/1"
    assert fake_gh.bodies[1] == "corpo"
    sent = fake_gh.writes[0]
    assert "--body-file" in sent
    assert not os.path.exists(sent[sent.index("--body-file") + 1])
    assert [p["number"] for p in fake_gh.prs(SLUG)] == [1]
    assert Gh().write(argv, "outro").endswith("/pull/2")


def test_write_edit_without_body_has_no_file(fake_gh):  # noqa: F811
    fake_gh.add_pr(SLUG, 3, "h", "master")
    Gh().write(("pr", "comment", "3", "-R", SLUG, "--body", "oi"), None)
    assert "--body-file" not in fake_gh.writes[0]


def test_write_5xx_is_uncertain(fake_gh):  # noqa: F811
    fake_gh.fail("pr create", "HTTP 502")
    with pytest.raises(GhUncertain):
        Gh().write(("pr", "create", "-R", SLUG), "corpo")


def test_write_timeout_is_uncertain(fake_gh):  # noqa: F811
    fake_gh.hang("pr create")
    with pytest.raises(GhUncertain):
        Gh(timeout=0.5).write(("pr", "create", "-R", SLUG), "corpo")


def test_write_422_is_failed(fake_gh):  # noqa: F811
    fake_gh.fail("pr create", "HTTP 422: Validation Failed")
    with pytest.raises(GhFailed) as caught:
        Gh().write(("pr", "create", "-R", SLUG), "corpo")
    assert not isinstance(caught.value, GhUncertain)


def test_checks_reads_conclusions(fake_gh):  # noqa: F811
    fake_gh.add_pr(SLUG, 4, "h", "master")
    fake_gh.set_checks(SLUG, 4, "MERGEABLE", {"build": "SUCCESS", "lint": "FAILURE"})
    assert Gh().checks(SLUG, 4) == {
        "mergeable": "MERGEABLE",
        "checks": {"build": "SUCCESS", "lint": "FAILURE"},
    }


def test_unsupported_verb_exits_1(fake_gh):  # noqa: F811
    with pytest.raises(GhFailed, match="unsupported"):
        Gh().write(("pr", "merge", "1", "-R", SLUG), None)
