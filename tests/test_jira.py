import base64
import json
from copy import deepcopy
from datetime import date

import pytest

from ws.cli import main
from ws.jira import (
    FIELDS,
    JiraClient,
    JiraError,
    SiteRefused,
    card_from_issue,
    my_tasks_jql,
    status_of,
    task_from_card,
)
from ws.taskmodel import Status
from ws.userconfig import save_jira_token

EMAIL = "dev@example.com"
CREDENTIAL = "sample-value"

REST_ISSUE = {
    "id": "10001",
    "key": "TS-101",
    "fields": {
        "summary": "[FRONT] Tela de exemplo",
        "status": {"name": "In Validation", "statusCategory": {"key": "indeterminate"}},
        "parent": {"key": "TS-100", "fields": {"summary": "[FRONT] Épico de exemplo"}},
        "reporter": {"accountId": "acc-me"},
        "updated": "2026-10-26T12:15:36.854-0300",
    },
}

MCP_NODE = {
    **deepcopy(REST_ISSUE),
    "expand": "renderedFields,names,schema",
    "webUrl": "https://example.atlassian.net/browse/TS-101",
}

CARD = {
    "key": "TS-101",
    "title": "[FRONT] Tela de exemplo",
    "status_name": "In Validation",
    "status_category": "indeterminate",
    "epic_key": "TS-100",
    "epic_title": "[FRONT] Épico de exemplo",
    "reporter_is_me": True,
    "updated": "2026-10-26T12:15:36.854000-03:00",
}


def _issue(number: int) -> dict:
    issue = deepcopy(REST_ISSUE)
    issue["key"] = f"TS-{number}"
    return issue


def _two_pages(fake) -> None:
    fake.pages = {
        None: {
            "issues": [_issue(n) for n in range(1, 101)],
            "nextPageToken": "page-2",
            "isLast": False,
        },
        "page-2": {"issues": [_issue(n) for n in range(101, 151)], "isLast": True},
    }


@pytest.mark.parametrize(
    ("name", "category", "expected"),
    [
        ("In Validation", "indeterminate", Status.VALIDATION),
        ("Cancelada", "done", Status.CANCELLED),
        ("Em andamento", "indeterminate", Status.IN_PROGRESS),
        ("To Do", "new", Status.TODO),
        ("Concluído", "done", Status.DONE),
    ],
)
def test_status_of(name, category, expected):
    overrides = {"In Validation": "validation", "Cancelada": "cancelled"}

    assert status_of(name, category, overrides) == expected


def test_status_of_rejects_unknown_category():
    with pytest.raises(ValueError, match="mystery"):
        status_of("Whatever", "mystery", {})


def test_my_tasks_jql_keeps_open_and_recently_updated():
    assert my_tasks_jql(date(2026, 10, 23)) == (
        'assignee = currentUser() AND (statusCategory != Done OR updated >= "2026-10-23") '
        "ORDER BY updated DESC"
    )


def test_card_from_issue_rest_and_mcp_shapes_are_equal():
    from_rest = card_from_issue(REST_ISSUE, "acc-me")
    from_mcp = card_from_issue(MCP_NODE, "acc-me")

    assert from_rest == from_mcp == CARD


def test_card_reporter_is_me_only_for_my_account():
    assert card_from_issue(REST_ISSUE, "acc-other")["reporter_is_me"] is False


def test_card_without_parent_has_null_epic():
    issue = deepcopy(REST_ISSUE)
    del issue["fields"]["parent"]

    card = card_from_issue(issue, "acc-me")

    assert card["epic_key"] is None
    assert card["epic_title"] is None


def test_card_from_issue_names_the_missing_field():
    issue = deepcopy(REST_ISSUE)
    del issue["fields"]["summary"]

    with pytest.raises(ValueError, match="summary"):
        card_from_issue(issue, "acc-me")


def test_task_from_card_builds_the_neutral_task():
    task = task_from_card(CARD, "https://example.atlassian.net", {"In Validation": "validation"})

    assert task.ref == "jira:TS-101"
    assert task.url == "https://example.atlassian.net/browse/TS-101"
    assert task.status == Status.VALIDATION
    assert task.requested_by_other is False
    assert task.updated.isoformat() == CARD["updated"]


def test_task_from_card_names_the_missing_field():
    card = {key: value for key, value in CARD.items() if key != "status_category"}

    with pytest.raises(ValueError, match="status_category"):
        task_from_card(card, "https://example.atlassian.net", {})


def test_client_myself_sends_basic_auth(fake_jira):
    client = JiraClient(fake_jira.site, EMAIL, CREDENTIAL)

    assert client.myself() == {"accountId": "acc-me"}

    expected = base64.b64encode(f"{EMAIL}:{CREDENTIAL}".encode()).decode()
    assert fake_jira.requests[0]["authorization"] == f"Basic {expected}"


def test_client_reads_every_page(fake_jira):
    _two_pages(fake_jira)
    client = JiraClient(fake_jira.site, EMAIL, CREDENTIAL)

    issues = client.search("assignee = currentUser()", FIELDS)

    assert [issue["key"] for issue in issues] == [f"TS-{n}" for n in range(1, 151)]
    first, second = fake_jira.requests
    assert first["query"]["jql"] == "assignee = currentUser()"
    assert first["query"]["fields"] == ",".join(FIELDS)
    assert first["query"]["maxResults"] == "100"
    assert "nextPageToken" not in first["query"]
    assert second["query"]["nextPageToken"] == "page-2"
    assert second["query"]["jql"] == first["query"]["jql"]


def test_client_401_raises_jira_error_with_status(fake_jira):
    fake_jira.status = 401
    client = JiraClient(fake_jira.site, EMAIL, CREDENTIAL)

    with pytest.raises(JiraError, match="401"):
        client.myself()


def test_client_unreachable_site_raises_jira_error(fake_jira):
    site = fake_jira.site
    fake_jira.server.shutdown()
    fake_jira.server.server_close()

    with pytest.raises(JiraError, match="reach"):
        JiraClient(site, EMAIL, CREDENTIAL, timeout=2).myself()


@pytest.fixture
def jira_config(ws_config, fake_jira):
    (ws_config / "config.toml").write_text(
        f'[jira]\nsite = "{fake_jira.site}"\nemail = "{EMAIL}"\n', encoding="utf-8"
    )
    save_jira_token(CREDENTIAL)
    return ws_config


def test_task_list_prints_cards_as_json(jira_config, fake_jira, capsys):
    fake_jira.pages = {None: {"issues": [REST_ISSUE], "isLast": True}}

    code = main(["task", "list", "--since", "2026-10-23"])

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"platform": "jira", "cards": [CARD]}
    search = fake_jira.requests[-1]["query"]
    assert search["jql"] == my_tasks_jql(date(2026, 10, 23))
    assert search["fields"] == ",".join(FIELDS)


def test_task_list_defaults_since_to_previous_workday(jira_config, fake_jira, monkeypatch):
    class Monday(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 26)

    monkeypatch.setattr("ws.cli.date", Monday)
    fake_jira.pages = {None: {"issues": [], "isLast": True}}

    assert main(["task", "list"]) == 0
    assert fake_jira.requests[-1]["query"]["jql"] == my_tasks_jql(date(2026, 10, 23))


def test_task_list_without_config_exits_2(ws_config, capsys):
    code = main(["task", "list"])

    assert code == 2
    assert "config.toml" in capsys.readouterr().err


def test_task_list_without_token_exits_2(jira_config, capsys):
    (jira_config / "credentials").unlink()

    code = main(["task", "list"])

    assert code == 2
    assert "credentials" in capsys.readouterr().err


def test_task_list_jira_error_exits_1(jira_config, fake_jira, capsys):
    fake_jira.status = 401

    code = main(["task", "list"])

    assert code == 1
    assert "401" in capsys.readouterr().err


def _client(fake, timeout=20):
    return JiraClient(fake.site, EMAIL, CREDENTIAL, timeout=timeout)


def test_request_returns_the_json_body_and_sends_json_headers(fake_jira):
    fake_jira.routes[("POST", "/rest/api/3/issue")] = (201, json.dumps({"key": "TS-9"}))

    result = _client(fake_jira)._request("POST", "/rest/api/3/issue", {"fields": {"a": 1}})

    assert result == {"key": "TS-9"}
    (sent,) = fake_jira.requests
    assert sent["content_type"] == "application/json"
    assert sent["body"] == {"fields": {"a": 1}}


def test_request_204_is_none(fake_jira):
    fake_jira.routes[("PUT", "/rest/api/3/issue/TS-1")] = (204, "")

    assert _client(fake_jira)._request("PUT", "/rest/api/3/issue/TS-1", {"fields": {}}) is None


def test_request_empty_body_with_200_is_none(fake_jira):
    fake_jira.routes[("POST", "/rest/api/3/issue/TS-1/transitions")] = (200, "")

    assert _client(fake_jira).post("/rest/api/3/issue/TS-1/transitions", {}) is None


def test_request_400_puts_jira_messages_in_the_error(fake_jira):
    body = json.dumps({"errorMessages": ["bad thing"], "errors": {"duedate": "invalid date"}})
    fake_jira.routes[("POST", "/rest/api/3/issue")] = (400, body)

    with pytest.raises(JiraError) as raised:
        _client(fake_jira).post("/rest/api/3/issue", {})

    message = str(raised.value)
    assert "400" in message
    assert "bad thing" in message
    assert "duedate: invalid date" in message
    assert raised.value.status == 400
    assert raised.value.uncertain is False
    encoded = base64.b64encode(f"{EMAIL}:{CREDENTIAL}".encode()).decode()
    assert CREDENTIAL not in message
    assert encoded not in message
    assert "Basic" not in message


def test_request_401_has_status(fake_jira):
    fake_jira.status = 401

    with pytest.raises(JiraError) as raised:
        _client(fake_jira).myself()

    assert raised.value.status == 401
    assert raised.value.uncertain is False


def test_request_write_timeout_is_uncertain(fake_jira):
    fake_jira.delay = 1.5

    with pytest.raises(JiraError) as raised:
        _client(fake_jira, timeout=0.3).post("/rest/api/3/issue", {})

    assert raised.value.status is None
    assert raised.value.uncertain is True


def test_request_write_connection_error_is_uncertain(fake_jira):
    site = fake_jira.site
    fake_jira.server.shutdown()
    fake_jira.server.server_close()

    with pytest.raises(JiraError) as raised:
        JiraClient(site, EMAIL, CREDENTIAL, timeout=2).post("/rest/api/3/issue", {})

    assert raised.value.status is None
    assert raised.value.uncertain is True


def test_request_5xx_on_a_write_is_uncertain(fake_jira):
    fake_jira.routes[("POST", "/rest/api/3/issue")] = (503, "{}")

    with pytest.raises(JiraError) as raised:
        _client(fake_jira).post("/rest/api/3/issue", {})

    assert raised.value.status == 503
    assert raised.value.uncertain is True


def test_request_5xx_on_a_read_is_not_uncertain(fake_jira):
    fake_jira.status = 500

    with pytest.raises(JiraError) as raised:
        _client(fake_jira).myself()

    assert raised.value.status == 500
    assert raised.value.uncertain is False


def test_issue_asks_for_the_fields(fake_jira):
    fake_jira.routes[("GET", "/rest/api/3/issue/TS-1")] = (200, json.dumps({"key": "TS-1"}))

    assert _client(fake_jira).issue("TS-1", ["summary", "status"]) == {"key": "TS-1"}

    assert fake_jira.requests[0]["query"] == {"fields": "summary,status"}


def test_transitions_expands_their_fields(fake_jira):
    body = json.dumps({"transitions": [{"id": "31", "name": "Done"}]})
    fake_jira.routes[("GET", "/rest/api/3/issue/TS-1/transitions")] = (200, body)

    assert _client(fake_jira).transitions("TS-1") == [{"id": "31", "name": "Done"}]

    assert fake_jira.requests[0]["query"] == {"expand": "transitions.fields"}


def test_active_sprints_uses_the_agile_path(fake_jira):
    body = json.dumps({"values": [{"id": 7, "name": "Sprint 7"}]})
    fake_jira.routes[("GET", "/rest/agile/1.0/board/12/sprint")] = (200, body)

    assert _client(fake_jira).active_sprints(12) == [{"id": 7, "name": "Sprint 7"}]

    assert fake_jira.requests[0]["query"] == {"state": "active"}


def test_create_meta_lists_the_types_then_reads_the_named_one(fake_jira):
    types = {"issueTypes": [{"id": "1", "name": "Bug"}, {"id": "2", "name": "Task"}]}
    detail = {"fields": [{"fieldId": "priority", "allowedValues": [{"name": "High"}]}]}
    fake_jira.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes")] = (
        200,
        json.dumps(types),
    )
    fake_jira.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes/2")] = (
        200,
        json.dumps(detail),
    )

    assert _client(fake_jira).create_meta("TS", "Task") == detail

    assert [r["path"] for r in fake_jira.requests] == [
        "/rest/api/3/issue/createmeta/TS/issuetypes",
        "/rest/api/3/issue/createmeta/TS/issuetypes/2",
    ]


def test_create_meta_unknown_type_is_an_error(fake_jira):
    types = {"issueTypes": [{"id": "1", "name": "Bug"}]}
    fake_jira.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes")] = (
        200,
        json.dumps(types),
    )

    with pytest.raises(JiraError, match="Task"):
        _client(fake_jira).create_meta("TS", "Task")


def test_truncated_answer_to_a_write_is_uncertain(fake_jira):
    fake_jira.truncate = True
    fake_jira.routes[("POST", "/rest/api/3/issue")] = (201, json.dumps({"key": "TS-9"}))

    with pytest.raises(JiraError) as raised:
        _client(fake_jira).post("/rest/api/3/issue", {})

    assert raised.value.uncertain is True


def test_truncated_error_body_keeps_the_real_status(fake_jira):
    fake_jira.truncate = True
    fake_jira.routes[("POST", "/rest/api/3/issue")] = (400, json.dumps({"errorMessages": ["x"]}))

    with pytest.raises(JiraError) as raised:
        _client(fake_jira).post("/rest/api/3/issue", {})

    assert raised.value.status == 400


def test_non_json_200_is_uncertain_on_a_write_and_not_on_a_read(fake_jira):
    fake_jira.routes[("POST", "/rest/api/3/issue")] = (200, "<html>")
    fake_jira.routes[("GET", "/rest/api/3/myself")] = (200, "<html>")

    with pytest.raises(JiraError) as write:
        _client(fake_jira).post("/rest/api/3/issue", {})
    with pytest.raises(JiraError) as read:
        _client(fake_jira).myself()

    assert write.value.uncertain is True
    assert read.value.uncertain is False


def test_non_json_error_body_falls_back_to_the_plain_message(fake_jira):
    fake_jira.routes[("POST", "/rest/api/3/issue")] = (400, "<html>nope</html>")

    with pytest.raises(JiraError) as raised:
        _client(fake_jira).post("/rest/api/3/issue", {})

    assert str(raised.value) == "Jira answered HTTP 400 for POST /rest/api/3/issue"


def test_redirect_is_not_followed(fake_jira):
    fake_jira.routes[("POST", "/rest/api/3/issue")] = (302, "")

    with pytest.raises(JiraError) as raised:
        _client(fake_jira).post("/rest/api/3/issue", {})

    assert raised.value.status == 302
    assert raised.value.uncertain is True
    assert [r["path"] for r in fake_jira.requests] == ["/rest/api/3/issue"]


def test_redirect_on_a_read_is_not_uncertain(fake_jira):
    fake_jira.routes[("GET", "/rest/api/3/myself")] = (301, "")

    with pytest.raises(JiraError) as raised:
        _client(fake_jira).myself()

    assert raised.value.uncertain is False
    assert len(fake_jira.requests) == 1


def test_path_segments_are_quoted(fake_jira):
    with pytest.raises(JiraError):
        _client(fake_jira).issue("a/b", ["summary"])

    assert fake_jira.requests[0]["path"] == "/rest/api/3/issue/a%2Fb"


def test_query_special_characters_are_encoded(fake_jira):
    fake_jira.routes[("GET", "/rest/api/3/search/jql")] = (200, json.dumps({"issues": []}))

    _client(fake_jira).search('summary ~ "a&b=c" ORDER BY x', ["summary"])

    assert fake_jira.requests[0]["query"]["jql"] == 'summary ~ "a&b=c" ORDER BY x'


def test_null_pages_are_tolerated(fake_jira):
    fake_jira.routes[("GET", "/rest/api/3/issue/TS-1/transitions")] = (200, "")
    fake_jira.routes[("GET", "/rest/agile/1.0/board/1/sprint")] = (200, "")

    assert _client(fake_jira).transitions("TS-1") == []
    assert _client(fake_jira).active_sprints(1) == []


def test_create_meta_type_without_id_is_an_error(fake_jira):
    fake_jira.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes")] = (
        200,
        json.dumps({"issueTypes": [{"name": "Task"}]}),
    )

    with pytest.raises(JiraError, match="no id"):
        _client(fake_jira).create_meta("TS", "Task")


@pytest.mark.parametrize(
    "site",
    [
        "https://example.atlassian.net",
        "https://example.atlassian.net/",
        "https://my-team-2.atlassian.net",
    ],
)
def test_the_client_accepts_atlassian_cloud_sites(site):
    assert JiraClient(site, EMAIL, CREDENTIAL).site == site.rstrip("/")


@pytest.mark.parametrize(
    "site",
    [
        "http://example.atlassian.net",
        "https://example.atlassian.net.evil.example",
        "https://evil.example/example.atlassian.net",
        "https://example.atlassian.net:8443",
        "https://example.atlassian.net/path",
        "https://.atlassian.net",
        "https://Example.atlassian.net",
        "https://example.atlassian.com",
        "http://127.0.0.1:9",
        "",
    ],
)
def test_the_client_refuses_to_send_the_key_anywhere_else(site):
    with pytest.raises(SiteRefused, match="atlassian.net"):
        JiraClient(site, EMAIL, CREDENTIAL)


def test_the_test_seam_is_empty_by_default_and_opens_only_what_it_lists(fake_jira, monkeypatch):
    assert JiraClient(fake_jira.site, EMAIL, CREDENTIAL).site == fake_jira.site

    monkeypatch.setattr("ws.jira.EXTRA_ALLOWED_SITES", set())

    with pytest.raises(SiteRefused):
        JiraClient(fake_jira.site, EMAIL, CREDENTIAL)


def test_task_list_with_a_site_that_is_not_atlassian_exits_2(ws_config, capsys):
    (ws_config / "config.toml").write_text(
        f'[jira]\nsite = "https://evil.example"\nemail = "{EMAIL}"\n', encoding="utf-8"
    )
    save_jira_token(CREDENTIAL)

    assert main(["task", "list"]) == 2
    assert "atlassian.net" in capsys.readouterr().err
