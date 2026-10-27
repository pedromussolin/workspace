"""Jira adapter: REST client and the compact card, the neutral input of `ws task status`."""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

from ws.taskmodel import Status, Task

FIELDS = ["summary", "status", "parent", "reporter", "updated"]

PAGE_SIZE = 100

CARD_FIELDS = (
    "key",
    "title",
    "status_name",
    "status_category",
    "epic_key",
    "epic_title",
    "reporter_is_me",
    "updated",
)

CATEGORY_STATUS = {
    "new": Status.TODO,
    "indeterminate": Status.IN_PROGRESS,
    "done": Status.DONE,
}


class JiraError(Exception):
    pass


def my_tasks_jql(since: date) -> str:
    return (
        "assignee = currentUser() AND "
        f'(statusCategory != Done OR updated >= "{since.isoformat()}") '
        "ORDER BY updated DESC"
    )


def _required(source: dict, name: str, where: str):
    value = source.get(name)
    if value is None:
        raise ValueError(f"{where} is missing {name}")
    return value


def card_from_issue(issue: dict, my_account_id: str) -> dict:
    key = _required(issue, "key", "issue")
    fields = _required(issue, "fields", f"issue {key}")
    where = f"issue {key} fields"
    status = _required(fields, "status", where)
    category = _required(
        status.get("statusCategory") or {}, "key", f"{where}.status.statusCategory"
    )
    parent = fields.get("parent") or {}
    reporter = fields.get("reporter") or {}
    updated = datetime.fromisoformat(_required(fields, "updated", where))
    return {
        "key": key,
        "title": _required(fields, "summary", where),
        "status_name": _required(status, "name", f"{where}.status"),
        "status_category": category,
        "epic_key": parent.get("key"),
        "epic_title": (parent.get("fields") or {}).get("summary"),
        "reporter_is_me": reporter.get("accountId") == my_account_id,
        "updated": updated.isoformat(),
    }


def status_of(name: str, category: str, overrides: dict[str, str]) -> Status:
    if name in overrides:
        return Status(overrides[name])
    try:
        return CATEGORY_STATUS[category]
    except KeyError:
        raise ValueError(f"unknown status category {category!r} for status {name!r}") from None


def task_from_card(card: dict, site: str, overrides: dict[str, str]) -> Task:
    for name in CARD_FIELDS:
        if name not in card:
            raise ValueError(f"card is missing {name}")
    key = card["key"]
    return Task(
        ref=f"jira:{key}",
        key=key,
        title=card["title"],
        url=f"{site.rstrip('/')}/browse/{key}",
        status=status_of(card["status_name"], card["status_category"], overrides),
        epic_key=card["epic_key"],
        epic_title=card["epic_title"],
        requested_by_other=not card["reporter_is_me"],
        updated=datetime.fromisoformat(card["updated"]),
    )


class JiraClient:
    def __init__(self, site: str, email: str, credential: str, timeout: int = 20):
        self.site = site.rstrip("/")
        self.timeout = timeout
        credentials = base64.b64encode(f"{email}:{credential}".encode()).decode()
        self._authorization = f"Basic {credentials}"

    def myself(self) -> dict:
        return self._get("/rest/api/3/myself", {})

    def search(self, jql: str, fields: list[str]) -> list[dict]:
        issues: list[dict] = []
        cursor = None
        while True:
            params = {"jql": jql, "fields": ",".join(fields), "maxResults": str(PAGE_SIZE)}
            if cursor:
                params["nextPageToken"] = cursor
            page = self._get("/rest/api/3/search/jql", params)
            issues.extend(page.get("issues", []))
            cursor = page.get("nextPageToken")
            if page.get("isLast", True) or not cursor:
                return issues

    def _get(self, path: str, params: dict[str, str]) -> dict:
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        request = urllib.request.Request(
            f"{self.site}{path}{query}",
            headers={"Authorization": self._authorization, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise JiraError(f"Jira answered HTTP {error.code} for {path}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise JiraError(f"could not reach Jira for {path}: {error}") from None
