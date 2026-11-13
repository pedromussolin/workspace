import json

import pytest
from fake_tracker import FakeTracker, make_card
from test_card import (
    SPRINT_FIELD,
    claude_settings,  # noqa: F401
    world,  # noqa: F401
)

from ws.identity import dev_id
from ws.taskmodel import Status
from ws.tracker.jira_adapter import JIRA_CAPABILITIES
from ws.tracker.port import (
    CAPABILITIES,
    Card,
    CardQuery,
    Link,
    People,
    Tracker,
    TrackerError,
    TrackerSetup,
    open_tracker,
)
from ws.userconfig import load_config


def _tracker():
    return open_tracker()


def test_jira_card_is_the_neutral_card(world):  # noqa: F811
    world.set_card(
        "TS-104",
        reporter={"accountId": "acc-other"},
        issuetype={"id": "6", "name": "Melhoria", "hierarchyLevel": 0},
        status={"name": "In Progress", "statusCategory": {"key": "indeterminate"}},
        **{
            SPRINT_FIELD: [
                {"name": "Sprint 54", "state": "closed"},
                {"name": "Sprint 55", "state": "active"},
            ]
        },
        issuelinks=[
            {"type": {"name": "Blocks"}, "outwardIssue": {"key": "TS-120"}},
            {"type": {"name": "Blocks"}, "inwardIssue": {"key": "TS-121"}},
            {"type": {"name": "Relates"}, "inwardIssue": {"key": "TS-122"}},
            {"type": {"name": "Duplicate"}, "inwardIssue": {"key": "TS-123"}},
        ],
    )

    found = _tracker().card("TS-104")

    assert found == Card(
        ref="TS-104",
        title="[FRONT] Tela de exemplo",
        type="improvement",
        level=0,
        parent="TS-100",
        assignee="acc-me",
        reporter="acc-other",
        status=Status.IN_PROGRESS,
        due=__import__("datetime").date(2026, 11, 5),
        priority="Medium",
        sprint="Sprint 55",
        links=(Link("blocks", "TS-120"), Link("blocked_by", "TS-121"), Link("relates", "TS-122")),
    )


def test_jira_card_absent_or_of_another_project_is_none(world):  # noqa: F811
    tracker = _tracker()

    assert tracker.card("TS-999") is None
    assert tracker.card("TS-130") is None


def test_jira_unmapped_type_is_none(world):  # noqa: F811
    world.set_card("TS-104", issuetype={"id": "10001", "name": "Other", "hierarchyLevel": 0})

    assert _tracker().card("TS-104").type is None


def test_jira_card_is_read_once(world):  # noqa: F811
    tracker = _tracker()
    tracker.card("TS-101")
    tracker.card("TS-101")
    tracker.me()
    tracker.me()

    paths = [request["path"] for request in world.fake.requests]
    assert paths.count("/rest/api/3/issue/TS-101") == 1
    assert paths.count("/rest/api/3/myself") == 1


def test_jira_cards_query_by_parent_and_role(world):  # noqa: F811
    world.fake.pages = {None: {"issues": [], "isLast": True}}
    tracker = _tracker()

    assert tracker.cards(CardQuery(("TS-100", "TS-111"), role="all")) == []

    (search,) = [r for r in world.fake.requests if r["path"] == "/rest/api/3/search/jql"]
    assert search["query"]["jql"] == (
        'project = "TS" AND parent in (TS-100, TS-111) AND '
        "(assignee = currentUser() OR reporter = currentUser()) AND statusCategory != Done"
    )
    world.fake.requests.clear()
    assert tracker.cards(CardQuery(())) == []
    assert world.fake.requests == []


def test_jira_cards_without_the_open_filter(world):  # noqa: F811
    world.fake.pages = {None: {"issues": [], "isLast": True}}

    _tracker().cards(CardQuery(("TS-100",), role="mine", open_only=False))

    jql = world.fake.requests[-1]["query"]["jql"]
    assert jql == 'project = "TS" AND parent in (TS-100) AND assignee = currentUser()'


def test_jira_cards_are_neutral_cards(world):  # noqa: F811
    issue = {"key": "TS-104", "fields": world_fields(world, "TS-104")}
    world.fake.pages = {None: {"issues": [issue], "isLast": True}}

    (found,) = _tracker().cards(CardQuery(("TS-100",)))

    assert found.ref == "TS-104"
    assert found.type == "task"


def world_fields(env, key):
    env.set_card(key)
    _, body = env.fake.routes[("GET", f"/rest/api/3/issue/{key}")]
    return json.loads(body)["fields"]


def test_jira_errors_are_tracker_errors(world):  # noqa: F811
    tracker = _tracker()
    world.fake.routes.clear()
    world.fake.status = 500

    with pytest.raises(TrackerError):
        tracker.card("TS-104")
    with pytest.raises(TrackerError):
        tracker.me()
    with pytest.raises(TrackerError):
        tracker.cards(CardQuery(("TS-100",)))


def test_jira_capabilities_lack_only_epic_parent():
    assert set(CAPABILITIES) - JIRA_CAPABILITIES == {"epic_parent"}


def test_jira_display_name_falls_back_to_the_account(world):  # noqa: F811
    world.fake.routes[("GET", "/rest/api/3/user")] = (200, json.dumps({"displayName": "Ana X"}))
    tracker = _tracker()

    assert tracker.display_name("acc-ana") == "Ana X"
    world.fake.routes[("GET", "/rest/api/3/user")] = (404, "{}")
    assert tracker.display_name("acc-zed") == "acc-zed"


def test_open_tracker_refuses_an_unknown_kind(world, ws_config):  # noqa: F811
    path = ws_config / "config.toml"
    path.write_text('[tracker]\nkind = "monday"\n' + path.read_text(encoding="utf-8"))

    with pytest.raises(TrackerSetup, match="has no adapter yet"):
        open_tracker()


def test_open_tracker_needs_the_types(ws_config, fake_jira):
    (ws_config / "config.toml").write_text(
        f'[jira]\nsite = "{fake_jira.site}"\nemail = "dev@example.com"\nproject = "TS"\n'
    )

    with pytest.raises(TrackerSetup, match="types"):
        open_tracker()


def test_people_resolve_both_ways(world):  # noqa: F811
    people = People.from_config(load_config(), "acc-me")
    ana = dev_id("ana@example.com")
    own = dev_id("dev@example.com")

    assert people.account(own) == "acc-me"
    assert people.dev_id("acc-me") == own
    assert people.account(ana) == "acc-ana"
    assert people.dev_id("acc-ana") == ana
    assert people.account("dev-0000000000") is None
    assert people.dev_id("acc-zed") is None
    assert people.problem(own) is None
    assert people.problem(ana) is None
    assert people.problem("dev-0000000000") == (
        "unknown person 'dev-0000000000': run ws people add <e-mail> and paste the block into "
        "config.toml"
    )


def test_people_without_a_tracker_id_have_a_problem():
    from ws.userconfig import Person

    people = People({"dev-1111111111": Person("dev-1111111111", {})}, "jira", "dev-2", "acc-me")

    assert people.problem("dev-1111111111").startswith("person 'dev-1111111111' has no jira id")
    assert people.account("dev-1111111111") is None


def test_fake_tracker_is_a_tracker():
    assert isinstance(FakeTracker(), Tracker)


def test_fake_tracker_filters_by_parent_role_and_open():
    mine = make_card("TS-1")
    followed = make_card("TS-2", assignee="acc-other")
    others = make_card("TS-3", assignee="acc-other", reporter="acc-other")
    done = make_card("TS-4", status=Status.DONE)
    elsewhere = make_card("TS-5", parent="TS-200")
    fake = FakeTracker([mine, followed, others, done, elsewhere])

    def refs(**query):
        return [item.ref for item in fake.cards(CardQuery(("TS-100",), **query))]

    assert refs(role="mine") == ["TS-1"]
    assert refs(role="following") == ["TS-2"]
    assert refs(role="all") == ["TS-1", "TS-2"]
    assert refs(role="all", open_only=False) == ["TS-1", "TS-2", "TS-4"]
    assert fake.card("TS-3") is others
    assert fake.reads == ["TS-3"]
