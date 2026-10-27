import base64
import json
import threading
from copy import deepcopy
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from ws.cli import main
from ws.jira import (
    FIELDS,
    JiraClient,
    JiraError,
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


class FakeJira:
    def __init__(self, server: ThreadingHTTPServer):
        self.server = server
        self.requests: list[dict] = []
        self.pages: dict[str | None, dict] = {}
        self.status = 200

    @property
    def site(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"


@pytest.fixture
def fake_jira():
    state: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            parsed = urlparse(self.path)
            query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
            fake = state["fake"]
            fake.requests.append(
                {
                    "path": parsed.path,
                    "query": query,
                    "authorization": self.headers.get("Authorization"),
                }
            )
            if fake.status != 200:
                body = json.dumps({"errorMessages": ["denied"]})
                status = fake.status
            elif parsed.path == "/rest/api/3/myself":
                body, status = json.dumps({"accountId": "acc-me"}), 200
            elif parsed.path == "/rest/api/3/search/jql":
                body, status = json.dumps(fake.pages[query.get("nextPageToken")]), 200
            else:
                body, status = "{}", 404
            payload = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fake = FakeJira(server)
    state["fake"] = fake
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield fake
    server.shutdown()
    server.server_close()
    thread.join()


def _two_pages(fake: FakeJira) -> None:
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
