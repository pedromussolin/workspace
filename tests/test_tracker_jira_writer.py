import json
from pathlib import Path

from test_card import (
    EMAIL,
    NOW,
    SPRINT_FIELD,  # noqa: F401
    claude_settings,  # noqa: F401
    make_draft,
    world,  # noqa: F401
)
from test_card_epics import searches  # noqa: F401
from test_card_golden import DRAFTS, ISSUE_LINK

from ws import contracts, userconfig
from ws.carddraft import parse_draft
from ws.config import data_dir
from ws.tracker.jira import adf, rules, writer
from ws.tracker.jira.client import JiraClient
from ws.tracker.jira.settings import JiraConfig
from ws.tracker.write import from_document, to_document

SITE = "https://example.atlassian.net"


def _client(world):  # noqa: F811
    return JiraClient(world.fake.site, EMAIL, "sample-value")


def _entry(path: Path) -> dict:
    raw = path.read_bytes()
    draft = parse_draft(raw)
    return {
        "source": {"path": str(path), "sha256": draft.sha256},
        "write": to_document(draft),
        "problems": [],
    }


def _plan(world, entries):  # noqa: F811
    config = userconfig.load_config()
    return writer.plan(
        _client(world),
        config.tracker_settings,
        entries,
        people=config.people,
        identity_email=config.identity_email,
        now=NOW,
    )


def test_plan_steps_carry_the_rules_requests(world):  # noqa: F811
    world.set_card("TS-101", **{"customfield_10015": None})
    world.fake.routes[ISSUE_LINK] = (201, "")
    entries = [_entry(DRAFTS[op](f"{number}-{op}.md")) for number, op in enumerate(DRAFTS, 1)]
    config = userconfig.load_config()
    context = rules.Context.load(
        _client(world), config.tracker_settings, NOW, config.people, config.identity_email
    )

    plan = _plan(world, entries)

    assert contracts.validate({**plan, "summary": [], "code": "x"}, "card-plan") == []
    assert plan["tracker"] == "jira"
    assert plan["target"] == world.fake.site
    assert plan["today"] == "2026-10-27"
    assert [step["op"] for step in plan["steps"]] == [
        "create",
        "create",
        "edit",
        "move",
        "comment",
        "worklog",
        "link",
    ]
    for entry, step in zip(entries, plan["steps"], strict=True):
        verdict = rules.check(context, from_document(entry["write"]))
        assert step["native"] == verdict.requests
        assert step["native"]
        assert step["preview"] == verdict.preview
        assert step["draft"] == entry["source"]
    assert plan["steps"][2]["card"] == "TS-101"
    assert plan["steps"][0]["title"] == "[FRONT] Título curto"
    assert plan["steps"][2]["title"] is None


def test_plan_refuses_a_link_asked_twice_in_a_batch(world):  # noqa: F811
    world.fake.routes[ISSUE_LINK] = (201, "")
    first = make_draft("a.md", "link", key="TS-101", blocks=["TS-120"])
    second = make_draft("b.md", "link", key="TS-101", blocks=["TS-120"])

    plan = _plan(world, [_entry(first), _entry(second)])

    one, two = plan["steps"]
    assert one["problems"] == [] and one["native"]
    assert two["native"] == []
    [problem] = two["problems"]
    assert problem.endswith("is also asked by a.md")


def test_plan_of_an_unparsed_entry_keeps_its_problems(world):  # noqa: F811
    source = {"path": str(data_dir() / "cards" / "drafts" / "x.md"), "sha256": "0" * 64}
    entries = [{"source": source, "write": None, "problems": ["op: missing"]}]

    plan = _plan(world, entries)

    [step] = plan["steps"]
    assert step["draft"] == source
    assert step["problems"] == ["op: missing"]
    assert (step["native"], step["preview"], step["warnings"], step["before"]) == ([], [], [], {})
    assert (step["card"], step["title"]) == (None, None)


def test_guard_accepts_known_shapes_and_refuses_others():
    ok = [
        {"method": "POST", "path": "/rest/api/3/issue", "body": {}},
        {"method": "PUT", "path": "/rest/api/3/issue/TS-101", "body": {}},
        {"method": "POST", "path": "/rest/api/3/issue/TS-101/transitions", "body": {}},
        {"method": "POST", "path": "/rest/api/3/issue/TS-101/comment", "body": {}},
        {"method": "POST", "path": "/rest/api/3/issue/TS-101/worklog", "body": {}},
        {
            "method": "POST",
            "path": "/rest/api/3/issueLink",
            "body": {"inwardIssue": {"key": "TS-1"}, "outwardIssue": {"key": "TS-2"}},
        },
    ]
    assert writer.guard("TS", ok) is None
    for bad in [
        {"method": "DELETE", "path": "/rest/api/3/issue/TS-101", "body": None},
        {"method": "PUT", "path": "/rest/api/3/issue/OTHER-1", "body": {}},
        {"method": "PUT", "path": "/rest/api/3/issue/TS-0", "body": {}},
        {"method": "POST", "path": "/rest/api/3/issue/TS-101/watchers", "body": {}},
        {
            "method": "POST",
            "path": "/rest/api/3/issueLink",
            "body": {"inwardIssue": {"key": "OTHER-1"}, "outwardIssue": {"key": "TS-2"}},
        },
    ]:
        assert writer.guard("TS", [*ok, bad]) == f"{bad['method']} {bad['path']}"


def test_find_hint_is_the_old_jql_line():
    hint = writer.find_hint("TS", 'Título "com aspas"')

    assert hint == (
        'use esta JQL: project = "TS" AND summary ~ '
        '"\\"Título \\\\\\"com aspas\\\\\\"\\"" ORDER BY created DESC'
    )


def test_render_body_is_to_adf():
    assert writer.render_body("## Contexto\n\n- um\n") == adf.to_adf("## Contexto\n\n- um\n")


def test_card_url_and_template():
    assert writer.card_url(SITE, "TS-7") == f"{SITE}/browse/TS-7"
    assert writer.card_url(f"{SITE}/", "TS-7") == f"{SITE}/browse/TS-7"
    settings = JiraConfig(site=f"{SITE}/", email=EMAIL, status_overrides={})
    assert writer.card_url_template(settings) == f"{SITE}/browse/{{key}}"
    assert writer.created_key({"key": "TS-9"}) == "TS-9"
    assert writer.created_key("") is None


def test_epics_lists_open_epics_and_initiatives(world, searches):  # noqa: F811
    settings = userconfig.load_config().tracker_settings

    found = writer.epics(_client(world), settings)

    assert sorted((entry["key"], entry["level"], entry["parent"]) for entry in found) == [
        ("TS-140", 2, None),
        ("TS-141", 1, "TS-140"),
        ("TS-142", 1, "TS-150"),
    ]
    json.dumps(found)


def test_needed_keys_follow_the_operations():
    assert writer.needed_keys([]) == {"project"}
    assert writer.needed_keys([{"op": "create"}, {"op": "link"}]) == {
        "project",
        "board_id",
        "types",
        "sprint_field",
        "links",
    }
    assert writer.needed_keys([{"op": "edit", "start": "2026-11-01"}]) == {
        "project",
        "start_date_field",
    }
