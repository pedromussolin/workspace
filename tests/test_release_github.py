import os
import subprocess

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
        Gh().write(("pr", "create", "-R", SLUG, "--title", "t"), "corpo")


def test_write_timeout_is_uncertain(fake_gh):  # noqa: F811
    fake_gh.hang("pr create")
    with pytest.raises(GhUncertain):
        Gh(timeout=0.5).write(("pr", "create", "-R", SLUG, "--title", "t"), "corpo")


def test_write_422_is_failed(fake_gh):  # noqa: F811
    fake_gh.fail("pr create", "HTTP 422: Validation Failed")
    with pytest.raises(GhFailed) as caught:
        Gh().write(("pr", "create", "-R", SLUG, "--title", "t"), "corpo")
    assert not isinstance(caught.value, GhUncertain)


def test_checks_reads_conclusions(fake_gh):  # noqa: F811
    fake_gh.add_pr(SLUG, 4, "h", "master")
    fake_gh.set_checks(SLUG, 4, "MERGEABLE", {"build": "SUCCESS", "lint": "FAILURE"})
    assert Gh().checks(SLUG, 4) == {
        "mergeable": "MERGEABLE",
        "checks": {"build": "SUCCESS", "lint": "FAILURE"},
    }


def test_fake_unsupported_verb_exits_1(fake_gh):  # noqa: F811
    done = subprocess.run(["gh", "pr", "merge", "1"], capture_output=True, text=True)
    assert done.returncode == 1
    assert "unsupported" in done.stderr


@pytest.mark.parametrize(
    "args",
    [
        ("pr", "merge", "1", "-R", SLUG),
        ("api", "-X", "DELETE", "repos/acme/repo-a"),
        ("repo", "delete", SLUG),
        ("frobnicate", "x"),
        (),
    ],
)
def test_write_refuses_verbs_outside_the_allowlist(fake_gh, args):  # noqa: F811
    with pytest.raises(GhFailed, match="refused"):
        Gh().write(args, None)
    assert fake_gh.calls == []


def test_write_refuses_a_body_in_the_args_when_body_is_given(fake_gh):  # noqa: F811
    for extra in ("--body", "--body-file"):
        with pytest.raises(GhFailed, match="refused"):
            Gh().write(("pr", "create", "-R", SLUG, "--title", "t", extra, "x"), "corpo")
    assert fake_gh.calls == []


@pytest.mark.parametrize("output", ["", "not json", "{}", "[1]", '{"number": 1}'])
def test_reads_with_unexpected_output_fail_without_echoing_it(fake_gh, output):  # noqa: F811
    fake_gh.add_pr(SLUG, 1, "h", "master")
    fake_gh.raw_output(output)
    for call in (
        lambda: Gh().pr(SLUG, 1),
        lambda: Gh().prs(SLUG),
        lambda: Gh().checks(SLUG, 1),
    ):
        try:
            call()
        except GhFailed as error:
            assert "unexpected gh output" in str(error)
            assert "not json" not in str(error)
        else:
            assert output in ("{}", '{"number": 1}')  # checks tolerates a bare object


def test_require_auth_timeout_is_not_logged_out(fake_gh):  # noqa: F811
    fake_gh.hang("auth status")
    with pytest.raises(GhMissing, match="did not answer in time"):
        Gh(timeout=0.5).require_auth()


def test_4xx_with_uncertain_letters_inside_words_stays_failed(fake_gh):  # noqa: F811
    fake_gh.fail("pr create", "HTTP 422: title is not retimed out-of-band; EOFs; timeouts differ")
    with pytest.raises(GhFailed) as caught:
        Gh().write(("pr", "create", "-R", SLUG, "--title", "t"), "corpo")
    assert not isinstance(caught.value, GhUncertain)


def test_fake_create_needs_title_and_body(fake_gh):  # noqa: F811
    with pytest.raises(GhFailed, match="title is required"):
        Gh().write(("pr", "create", "-R", SLUG), "corpo")
    with pytest.raises(GhFailed, match="body is required"):
        Gh().write(("pr", "create", "-R", SLUG, "--title", "t"), None)


def test_fake_edit_applies_title_base_and_labels(fake_gh):  # noqa: F811
    fake_gh.add_pr(SLUG, 1, "h", "master")
    Gh().write(
        ("pr", "edit", "1", "-R", SLUG, "--title", "novo", "--base", "sandbox", "--add-label", "x"),
        None,
    )
    pr = Gh().pr(SLUG, 1)
    assert (pr.title, pr.base, pr.labels) == ("novo", "sandbox", ("x",))
    with pytest.raises(GhFailed, match="unknown flag"):
        Gh().write(("pr", "edit", "1", "-R", SLUG, "--milestone", "m"), None)


def test_fake_rejects_unknown_json_field_and_state(fake_gh):  # noqa: F811
    for args in (
        ["pr", "list", "-R", SLUG, "--json", "nope"],
        ["pr", "list", "-R", SLUG, "--state", "bogus"],
    ):
        assert subprocess.run(["gh", *args], capture_output=True).returncode == 1


def test_fake_takes_a_dash_value_for_a_known_flag(fake_gh):  # noqa: F811
    Gh().write(("pr", "create", "-R", SLUG, "--title", "-x"), "corpo")
    fake_gh.add_pr(SLUG, 5, "h", "master")
    Gh().write(("pr", "comment", "5", "-R", SLUG, "--body", "- item"), None)
    assert Gh().pr(SLUG, 1).title == "-x"
    with pytest.raises(GhFailed, match="unknown flag"):
        Gh().write(("pr", "comment", "5", "-R", SLUG, "--nope", "x"), None)


def test_comments_reads_the_texts(fake_gh):  # noqa: F811
    fake_gh.add_pr(SLUG, 7, "h", "master")
    assert Gh().comments(SLUG, 7) == []
    argv = ("pr", "comment", "7", "-R", SLUG, "--body", "ola")
    Gh().write(argv, None)
    assert Gh().comments(SLUG, 7) == ["ola"]
