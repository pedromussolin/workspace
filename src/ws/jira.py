"""Jira adapter: REST client and the compact card, the neutral input of `ws task status`."""

import base64
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

from ws.taskmodel import Status, Task

FIELDS = ["summary", "status", "parent", "reporter", "updated", "issuetype"]

PAGE_SIZE = 100
META_PAGE_SIZE = 200
MAX_META_PAGES = 50

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


CLOUD_SITE = re.compile(r"https://[a-z0-9-]+\.atlassian\.net/?")
# A test seam: only the test fixture of the fake Jira server adds its own address here.
EXTRA_ALLOWED_SITES: set[str] = set()


class SiteRefused(ValueError):
    pass


def check_site(site: str) -> str:
    """The API key goes only to an Atlassian Cloud site, over https; a typo or a planted config
    must not send it anywhere else."""
    if CLOUD_SITE.fullmatch(site) or site.rstrip("/") in EXTRA_ALLOWED_SITES:
        return site
    raise SiteRefused(f"Jira site {site!r} is refused: it must be https://<name>.atlassian.net")


class JiraError(Exception):
    """`status` is the HTTP status (None without an answer); `uncertain` means a write may have
    been applied anyway (no answer, or a 5xx), so the caller checks before retrying."""

    def __init__(self, message: str, status: int | None = None, uncertain: bool = False):
        super().__init__(message)
        self.status = status
        self.uncertain = uncertain


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
    level = (fields.get("issuetype") or {}).get("hierarchyLevel")
    is_epic = isinstance(level, int) and not isinstance(level, bool) and level >= 1
    return {
        "key": key,
        "title": _required(fields, "summary", where),
        "status_name": _required(status, "name", f"{where}.status"),
        "status_category": category,
        "epic_key": parent.get("key"),
        "epic_title": (parent.get("fields") or {}).get("summary"),
        "reporter_is_me": reporter.get("accountId") == my_account_id,
        "updated": updated.isoformat(),
        "is_epic": is_epic,
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
        is_epic=bool(card.get("is_epic", False)),
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would forward the credential and turn a POST into a GET; it is an error."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _segment(value: object) -> str:
    return urllib.parse.quote(str(value), safe="")


class JiraClient:
    def __init__(self, site: str, email: str, credential: str, timeout: int = 20):
        self.site = check_site(site).rstrip("/")
        self.timeout = timeout
        credentials = base64.b64encode(f"{email}:{credential}".encode()).decode()
        self._authorization = f"Basic {credentials}"

    def myself(self) -> dict:
        return self.get("/rest/api/3/myself")

    def search(self, jql: str, fields: list[str]) -> list[dict]:
        issues: list[dict] = []
        cursor = None
        while True:
            params = {"jql": jql, "fields": ",".join(fields), "maxResults": str(PAGE_SIZE)}
            if cursor:
                params["nextPageToken"] = cursor
            page = self.get("/rest/api/3/search/jql", params)
            issues.extend(page.get("issues", []))
            cursor = page.get("nextPageToken")
            if page.get("isLast", True) or not cursor:
                return issues

    def get(self, path: str, query: dict[str, str] | None = None):
        return self._request("GET", path, query=query)

    def post(self, path: str, body: dict):
        return self._request("POST", path, body)

    def put(self, path: str, body: dict):
        return self._request("PUT", path, body)

    def issue(self, key: str, fields: list[str]) -> dict:
        return self.get(f"/rest/api/3/issue/{_segment(key)}", {"fields": ",".join(fields)})

    def transitions(self, key: str) -> list[dict]:
        page = self.get(
            f"/rest/api/3/issue/{_segment(key)}/transitions", {"expand": "transitions.fields"}
        )
        return (page or {}).get("transitions", [])

    def active_sprints(self, board_id: int) -> list[dict]:
        page = self.get(f"/rest/agile/1.0/board/{_segment(board_id)}/sprint", {"state": "active"})
        return (page or {}).get("values", [])

    def create_meta(self, project: str, type_id: str) -> dict:
        path = f"/rest/api/3/issue/createmeta/{_segment(project)}/issuetypes/{_segment(type_id)}"
        return self._pages(path, "fields")

    def _pages(self, path: str, key: str) -> dict:
        """A paged listing as one page: the `key` lists of every page joined. A page without
        a list under `key` (another shape) is returned as it came."""
        first: dict | None = None
        items: list = []
        start = 0
        for _ in range(MAX_META_PAGES):
            page = self.get(path, {"startAt": str(start), "maxResults": str(META_PAGE_SIZE)}) or {}
            first = page if first is None else first
            got = page.get(key)
            if not isinstance(got, list):
                return page
            items.extend(got)
            start += len(got)
            total = page.get("total")
            if not got or not isinstance(total, int) or start >= total:
                break
        return {**(first or {}), key: items}

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict[str, str] | None = None,
    ) -> dict | list | None:
        suffix = f"?{urllib.parse.urlencode(query)}" if query else ""
        headers = {"Authorization": self._authorization, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.site}{path}{suffix}", data=data, headers=headers, method=method
        )
        write = method != "GET"
        try:
            with _OPENER.open(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            detail = _error_detail(error)
            raise JiraError(
                f"Jira answered HTTP {error.code} for {method} {path}{detail}",
                status=error.code,
                uncertain=write and (error.code >= 500 or 300 <= error.code < 400),
            ) from None
        except (OSError, http.client.HTTPException) as error:
            raise JiraError(
                f"could not reach Jira for {method} {path}: {error}", uncertain=write
            ) from None
        if not raw.strip():
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise JiraError(
                f"Jira sent an unreadable answer for {method} {path}: {error}", uncertain=write
            ) from None

    def user(self, account_id: str) -> dict:
        return self.get("/rest/api/3/user", {"accountId": account_id}) or {}

    def issue_types(self, project: str) -> list[dict]:
        path = f"/rest/api/3/issue/createmeta/{_segment(project)}/issuetypes"
        return self._pages(path, "issueTypes").get("issueTypes", [])

    def link_types(self) -> list[dict]:
        return (self.get("/rest/api/3/issueLinkType") or {}).get("issueLinkTypes", [])

    def user_search(self, query: str) -> list[dict]:
        found = self.get("/rest/api/3/user/search", {"query": query})
        return found if isinstance(found, list) else []

    def edit_meta(self, key: str) -> dict:
        found = self.get(f"/rest/api/3/issue/{_segment(key)}/editmeta") or {}
        fields = found.get("fields") if isinstance(found, dict) else None
        return fields if isinstance(fields, dict) else {}


def _error_detail(error: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(error.read())
    except (OSError, ValueError, http.client.HTTPException):
        return ""
    if not isinstance(payload, dict):
        return ""
    messages = [str(item) for item in payload.get("errorMessages") or []]
    fields = payload.get("errors")
    if isinstance(fields, dict):
        messages.extend(f"{name}: {text}" for name, text in fields.items())
    return f": {'; '.join(messages)}" if messages else ""
