import json
from datetime import UTC, date, datetime

import pytest
from fake_tracker import FakeTracker, make_card
from test_card import (
    SPRINT_FIELD,
    START_FIELD,
    claude_settings,  # noqa: F401
    world,  # noqa: F401
)

from ws.identity import dev_id
from ws.taskmodel import Status
from ws.tracker.jira.adapter import JIRA_CAPABILITIES
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
        due=date(2026, 11, 5),
        start=date(2026, 10, 26),
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


def test_jira_card_reads_the_start_date(world):  # noqa: F811
    world.set_card("TS-104", **{START_FIELD: "2026-11-10"})
    world.set_card("TS-105", **{START_FIELD: None})

    tracker = _tracker()

    assert tracker.card("TS-104").start == date(2026, 11, 10)
    assert tracker.card("TS-105").start is None
    asked = [r for r in world.fake.requests if r["path"] == "/rest/api/3/issue/TS-104"]
    assert START_FIELD in asked[0]["query"]["fields"]


def test_jira_card_without_a_start_date_field_is_not_asked_for_it(world, ws_config):  # noqa: F811
    world.set_card("TS-104")
    config = ws_config / "config.toml"
    config.write_text(
        config.read_text().replace(f'start_date_field = "{START_FIELD}"\n', ""), encoding="utf-8"
    )

    tracker = _tracker()
    found = tracker.card("TS-104")

    assert found.start is None
    asked = [r for r in world.fake.requests if r["path"] == "/rest/api/3/issue/TS-104"]
    assert START_FIELD not in asked[0]["query"]["fields"]
    assert tracker.capabilities == JIRA_CAPABILITIES - {"start_date"}


def test_jira_with_a_start_date_field_can_set_the_start(world):  # noqa: F811
    assert _tracker().capabilities == JIRA_CAPABILITIES


def test_jira_today_is_in_the_users_time_zone(world, monkeypatch):  # noqa: F811
    monkeypatch.setattr(
        "ws.tracker.jira.adapter._now", lambda: datetime(2026, 11, 16, 1, 30, tzinfo=UTC)
    )

    assert _tracker().today() == date(2026, 11, 15)


@pytest.mark.parametrize("zone", ["Not/AZone", None, ""])
def test_jira_today_refuses_a_bad_or_missing_time_zone(world, zone):  # noqa: F811
    world.set_myself(zone)

    with pytest.raises(TrackerError, match="time zone"):
        _tracker().today()


def test_fake_tracker_has_today_and_start():
    fake = FakeTracker([make_card("TS-1", start=date(2026, 11, 10))], today=date(2026, 11, 20))

    assert isinstance(fake, Tracker)
    assert fake.today() == date(2026, 11, 20)
    assert FakeTracker().today() == date(2026, 11, 16)
    assert fake.card("TS-1").start == date(2026, 11, 10)
    assert make_card("TS-2").start is None


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
    path.write_text(path.read_text(encoding="utf-8").replace('kind = "jira"', 'kind = "monday"'))

    with pytest.raises(TrackerSetup, match="has no adapter yet"):
        open_tracker()


def test_open_tracker_needs_the_types(ws_config, fake_jira):
    (ws_config / "config.toml").write_text(
        f'[tracker]\nkind = "jira"\n[tracker.jira]\nsite = "{fake_jira.site}"\nemail = "dev@example.com"\nproject = "TS"\n'  # noqa: E501
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


def test_jira_description_is_plain_text(world):  # noqa: F811
    doc = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Pronto quando"}],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "a"}]}
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "b"}]}
                        ],
                    },
                ],
            },
        ],
    }
    world.set_card("TS-104", description=doc)
    tracker = _tracker()

    assert tracker.description("TS-104") == "## Pronto quando\n- a\n- b"
    asked = [r for r in world.fake.requests if r["path"] == "/rest/api/3/issue/TS-104"]
    assert asked[-1]["query"]["fields"] == "description"

    world.set_card("TS-105", description=None)
    assert tracker.description("TS-105") is None

    world.fake.routes[("GET", "/rest/api/3/issue/TS-106")] = (404, "{}")
    assert tracker.description("TS-106") is None

    world.fake.routes[("GET", "/rest/api/3/issue/TS-107")] = (500, "{}")
    with pytest.raises(TrackerError):
        tracker.description("TS-107")


def test_fake_tracker_has_description():
    tracker = FakeTracker(descriptions={"TS-1": "## Pronto quando\n- a"})

    assert isinstance(tracker, Tracker)
    assert "description" in tracker.capabilities
    assert tracker.description("TS-1") == "## Pronto quando\n- a"
    assert tracker.description("TS-2") is None


def test_jira_description_keeps_code_fences_mentions_and_cards(world):  # noqa: F811
    doc = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Fale com "},
                    {"type": "mention", "attrs": {"id": "acc-other", "text": "@Ana"}},
                    {"type": "text", "text": " em "},
                    {"type": "inlineCard", "attrs": {"url": "https://example.test/x"}},
                ],
            },
            {
                "type": "codeBlock",
                "content": [{"type": "text", "text": "# comment\nx = 1"}],
            },
        ],
    }
    world.set_card("TS-104", description=doc)

    assert _tracker().description("TS-104") == (
        "Fale com @Ana em https://example.test/x\n```\n# comment\nx = 1\n```"
    )


def test_open_tracker_dispatches_on_the_configured_kind(world, ws_config, monkeypatch):  # noqa: F811
    import sys
    import types

    from ws import tracker

    seen = []
    stub = types.ModuleType("ws_stub_adapter")
    stub.open_tracker = lambda config: seen.append(config.tracker_kind) or "opened"
    stub.parse_settings = lambda table, path: None
    monkeypatch.setitem(sys.modules, "ws_stub_adapter", stub)
    monkeypatch.setitem(tracker.ADAPTERS, "stub", "ws_stub_adapter")
    monkeypatch.setattr(tracker, "KNOWN_KINDS", (*tracker.KNOWN_KINDS, "stub"))
    path = ws_config / "config.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('kind = "jira"', 'kind = "stub"'))

    assert open_tracker() == "opened"
    assert seen == ["stub"]


def test_open_tracker_unknown_kind_is_a_setup_problem(world, ws_config):  # noqa: F811
    path = ws_config / "config.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('kind = "jira"', 'kind = "monday"'))

    with pytest.raises(TrackerSetup, match="monday"):
        open_tracker()


def test_open_tracker_missing_config_is_a_setup_problem(ws_config):
    with pytest.raises(TrackerSetup):
        open_tracker()


def test_tracker_error_keeps_status_and_uncertain():
    from ws.tracker import errors, port

    error = errors.TrackerError("boom", status=503, uncertain=True)

    assert (str(error), error.status, error.uncertain) == ("boom", 503, True)
    assert errors.TrackerError("plain").status is None
    assert errors.TrackerError("plain").uncertain is False
    assert port.TrackerError is errors.TrackerError
    assert port.TrackerSetup is errors.TrackerSetup


def test_writer_protocol_lists_the_port_members():
    from ws.tracker.port import Writer

    members = {
        "name",
        "target",
        "plan",
        "guard",
        "send",
        "apply",
        "created_key",
        "find_hint",
        "render_body",
        "card_url",
    }
    assert members <= set(Writer.__protocol_attrs__)
    assert set(Tracker.__protocol_attrs__) <= set(Writer.__protocol_attrs__)
