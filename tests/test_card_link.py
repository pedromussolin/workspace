import pytest
from test_card import (
    approve,
    claude_settings,  # noqa: F401
    make_draft,
    passing,
    preview,
    problems,
    world,  # noqa: F401
)

from ws import card
from ws.cli import main
from ws.config import data_dir
from ws.tracker.jira import writer
from ws.tracker.jira.client import JiraError

ISSUE_LINK = ("POST", "/rest/api/3/issueLink")


def link_draft(key="TS-101", **kinds):
    return make_draft("l.md", "link", key=key, **kinds)


def blocks(other, side="outwardIssue"):
    return {"type": {"name": "Blocks"}, side: {"key": other}}


def bodies(world):  # noqa: F811
    return [r["body"] for r in world.requests_to(*ISSUE_LINK)]


def test_link_adds_only_missing_links(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuelinks=[blocks("TS-120")])
    world.set_card("TS-102")

    path = link_draft(blocks=["TS-120", "TS-102"])
    verdict = passing(path, capsys)
    out, _ = preview(path, capsys)

    assert "  TS-101 bloqueia TS-120: já existe\n  TS-101 bloqueia TS-102\n" in out
    assert [r["body"]["outwardIssue"]["key"] for r in verdict["requests"]] == ["TS-102"]


def test_link_blocked_by_reverses_the_sides(world, capsys):  # noqa: F811
    path = link_draft(blocked_by=["TS-120"])
    verdict = passing(path, capsys)

    assert verdict["requests"] == [
        {
            "method": "POST",
            "path": "/rest/api/3/issueLink",
            "body": {
                "type": {"name": "Blocks"},
                "inwardIssue": {"key": "TS-120"},
                "outwardIssue": {"key": "TS-101"},
            },
        }
    ]
    assert "  TS-101 é bloqueado por TS-120\n" in preview(path, capsys)[0]


def test_link_relates(world, capsys):  # noqa: F811
    path = link_draft(relates=["TS-120"])
    verdict = passing(path, capsys)

    [request] = verdict["requests"]
    assert request["body"]["type"] == {"name": "Relates"}
    assert request["body"]["inwardIssue"] == {"key": "TS-101"}
    assert "  TS-101 relaciona-se com TS-120\n" in preview(path, capsys)[0]


def test_link_contradicting_an_existing_link_is_refused(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuelinks=[blocks("TS-120", "inwardIssue")])

    assert problems(link_draft(blocks=["TS-120"]), capsys) == (
        "TS-101 is already blocked by TS-120"
    )


def test_link_blocked_by_contradicting_an_existing_link_is_refused(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuelinks=[blocks("TS-120")])

    assert problems(link_draft(blocked_by=["TS-120"]), capsys) == "TS-101 already blocks TS-120"


def test_link_target_outside_the_project_is_refused(world, capsys):  # noqa: F811
    assert "OTHER-1 is not a card of project TS" in problems(
        link_draft(relates=["OTHER-1"]), capsys
    )


def test_link_target_that_does_not_exist_is_refused(world, capsys):  # noqa: F811
    assert "card TS-999 was not found" in problems(link_draft(relates=["TS-999"]), capsys)


def test_link_needs_one_writable_side(world, capsys):  # noqa: F811
    refused = problems(link_draft("TS-102", blocks=["TS-103"]), capsys)
    assert "card TS-103 is not yours" in refused

    passing(link_draft("TS-102", blocks=["TS-101"]), capsys)
    passing(link_draft("TS-101", blocks=["TS-102", "TS-103"]), capsys)


def test_link_with_everything_existing_changes_nothing(world, capsys):  # noqa: F811
    world.set_card("TS-101", issuelinks=[blocks("TS-120")])

    assert problems(link_draft(blocks=["TS-120"]), capsys) == "the draft adds no link"


def test_guard_allows_issue_links_only_inside_the_project():
    def request(inward, outward):
        return {
            "method": "POST",
            "path": "/rest/api/3/issueLink",
            "body": {"inwardIssue": {"key": inward}, "outwardIssue": {"key": outward}},
        }

    assert writer.guard("TS", [request("TS-1", "TS-2")]) is None
    assert writer.guard("TS", [request("TS-1", "OTHER-1")]) == "POST /rest/api/3/issueLink"
    assert writer.guard("TS", [request("OTHER-1", "TS-1")]) == "POST /rest/api/3/issueLink"
    assert writer.guard("TS", [{"method": "POST", "path": "/rest/api/3/issueLink"}])


def test_applying_a_link_draft_sends_one_post_per_missing_link(world, capsys):  # noqa: F811
    world.fake.routes[ISSUE_LINK] = (201, "")
    world.set_card("TS-101", issuelinks=[blocks("TS-120")])
    path = link_draft(blocks=["TS-120"], blocked_by=["TS-102"])
    _, code = preview(path, capsys)
    assert world.writes() == []

    assert approve(path, code) == 0

    assert bodies(world) == [
        {
            "type": {"name": "Blocks"},
            "inwardIssue": {"key": "TS-102"},
            "outwardIssue": {"key": "TS-101"},
        }
    ]
    out = capsys.readouterr().out
    assert "Vinculado: TS-101 é bloqueado por TS-102" in out
    assert "TS-120" not in out
    assert not path.exists()


def test_a_failing_link_reports_the_links_already_created(world, capsys, monkeypatch):  # noqa: F811
    world.fake.routes[ISSUE_LINK] = (201, "")
    path = link_draft(blocks=["TS-102"], relates=["TS-120"], blocked_by=["TS-103"])
    _, code = preview(path, capsys)
    real, calls = card._send, []

    def flaky(client, request):
        calls.append(request)
        if len(calls) == 2:
            raise JiraError("boom", status=500)
        return real(client, request)

    monkeypatch.setattr(card, "_send", flaky)

    assert approve(path, code) == 3

    text = capsys.readouterr().out
    assert "l.md: 1 vínculo(s) já criado(s); o restante não foi enviado" in text
    assert "Vinculado: TS-101 bloqueia TS-102" in text
    assert "TS-120" not in text.split("Vinculado:")[1]
    assert "a transição foi aplicada" not in text
    assert len(bodies(world)) == 1


def test_link_kind_without_a_link_type_is_a_problem(world, ws_config, capsys):  # noqa: F811
    config = ws_config / "config.toml"
    text = config.read_text(encoding="utf-8")
    config.write_text(text.replace('relates = "Relates"\n', ""), encoding="utf-8")

    message = problems(link_draft(relates=["TS-120", "TS-102"]), capsys)

    assert message == (
        "link kind 'relates' has no link type: add it to [tracker.jira.links] (ws tracker discover)"
    )


def batch_problems(capsys, *drafts):
    for name, key, kind, target in drafts:
        make_draft(name, "link", key=key, **{kind: [target]})
    assert main(["card", "preview", str(data_dir() / "cards" / "drafts")]) == 1
    return capsys.readouterr().out


@pytest.mark.parametrize(
    "second",
    [("TS-120", "blocked_by", "TS-101"), ("TS-101", "blocks", "TS-120")],
)
def test_the_same_link_in_two_drafts_of_a_batch_is_refused(world, capsys, second):  # noqa: F811
    out = batch_problems(capsys, ("1-a.md", "TS-101", "blocks", "TS-120"), ("2-b.md", *second))

    assert "  2-b.md: the Blocks link between TS-101 and TS-120 is also asked by 1-a.md" in out
    assert "1-a.md:" not in out
    assert world.writes() == []


def test_a_link_both_ways_in_a_batch_is_refused(world, capsys):  # noqa: F811
    out = batch_problems(
        capsys, ("1-a.md", "TS-101", "blocks", "TS-120"), ("2-b.md", "TS-120", "blocks", "TS-101")
    )

    assert (
        "  2-b.md: TS-120 and TS-101 are linked by Blocks in both directions: here and in "
        "1-a.md; keep one"
    ) in out
    assert world.writes() == []


def test_relates_in_both_orders_in_a_batch_is_the_same_link(world, capsys):  # noqa: F811
    out = batch_problems(
        capsys, ("1-a.md", "TS-101", "relates", "TS-120"), ("2-b.md", "TS-120", "relates", "TS-101")
    )

    assert "  2-b.md: the Relates link between TS-120 and TS-101 is also asked by 1-a.md" in out
