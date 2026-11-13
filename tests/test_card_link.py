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

    assert card.guard("TS", [request("TS-1", "TS-2")]) is None
    assert card.guard("TS", [request("TS-1", "OTHER-1")]) == "POST /rest/api/3/issueLink"
    assert card.guard("TS", [request("OTHER-1", "TS-1")]) == "POST /rest/api/3/issueLink"
    assert card.guard("TS", [{"method": "POST", "path": "/rest/api/3/issueLink"}])


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
