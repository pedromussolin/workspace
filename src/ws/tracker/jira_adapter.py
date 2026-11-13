"""The Jira adapter of the tracker port: cards read through the REST API."""

from datetime import date

from ws import jira
from ws.jira import JiraClient, JiraError
from ws.tracker.port import Card, CardQuery, Link, TrackerError
from ws.userconfig import JiraConfig

JIRA_CAPABILITIES = frozenset(
    {
        "worklog",
        "sprint",
        "start_date",
        "initiative",
        "set_reporter",
        "change_type",
        "link_types",
    }
)

_BASE_FIELDS = [
    "summary",
    "status",
    "assignee",
    "parent",
    "project",
    "priority",
    "duedate",
    "reporter",
    "issuetype",
    "issuelinks",
]


class JiraTracker:
    kind = "jira"
    capabilities = JIRA_CAPABILITIES

    def __init__(self, client: JiraClient, settings: JiraConfig):
        self._client = client
        self._settings = settings
        self._me: str | None = None
        self._cards: dict[str, Card | None] = {}
        self._names: dict[str, str] = {}

    def _fields(self) -> list[str]:
        names = list(_BASE_FIELDS)
        if self._settings.sprint_field:
            names.append(self._settings.sprint_field)
        return names

    def me(self) -> str:
        if self._me is None:
            try:
                self._me = self._client.myself()["accountId"]
            except (JiraError, KeyError, TypeError, ValueError) as error:
                raise TrackerError(str(error)) from None
        return self._me

    def card(self, ref: str) -> Card | None:
        if ref in self._cards:
            return self._cards[ref]
        try:
            try:
                issue = self._client.issue(ref, self._fields())
            except JiraError as error:
                if error.status != 404:
                    raise
                issue = None
            found = None
            if issue is not None:
                project = ((issue.get("fields") or {}).get("project") or {}).get("key")
                if project == self._settings.project:
                    found = self._neutral(issue)
        except (JiraError, KeyError, TypeError, ValueError, AttributeError) as error:
            raise TrackerError(str(error)) from None
        self._cards[ref] = found
        return found

    def cards(self, query: CardQuery) -> list[Card]:
        if not query.parent_in:
            return []
        clauses = [
            f'project = "{self._settings.project}"',
            f"parent in ({', '.join(query.parent_in)})",
            jira.role_jql(query.role),
        ]
        if query.open_only:
            clauses.append("statusCategory != Done")
        try:
            issues = self._client.search(" AND ".join(clauses), self._fields())
            found = [self._neutral(issue) for issue in issues]
        except (JiraError, KeyError, TypeError, ValueError, AttributeError) as error:
            raise TrackerError(str(error)) from None
        for item in found:
            self._cards.setdefault(item.ref, item)
        return found

    def display_name(self, account: str) -> str:
        if account not in self._names:
            try:
                name = (self._client.user(account) or {}).get("displayName")
            except (JiraError, AttributeError):
                name = None
            self._names[account] = name or account
        return self._names[account]

    def _neutral(self, issue: dict) -> Card:
        settings = self._settings
        fields = jira._required(issue, "fields", "issue")
        status = jira._required(fields, "status", "issue fields")
        category = (status.get("statusCategory") or {}).get("key")
        kind = fields.get("issuetype") or {}
        by_id = {type_id: neutral for neutral, type_id in settings.types.items()}
        level = kind.get("hierarchyLevel")
        due = fields.get("duedate")
        return Card(
            ref=jira._required(issue, "key", "issue"),
            title=jira._required(fields, "summary", "issue fields"),
            type=by_id.get(str(kind.get("id"))),
            level=level if isinstance(level, int) and not isinstance(level, bool) else 0,
            parent=(fields.get("parent") or {}).get("key"),
            assignee=(fields.get("assignee") or {}).get("accountId"),
            reporter=(fields.get("reporter") or {}).get("accountId"),
            status=jira.status_of(status.get("name"), category, settings.status_overrides),
            due=date.fromisoformat(due) if due else None,
            priority=(fields.get("priority") or {}).get("name"),
            sprint=self._sprint(
                fields.get(settings.sprint_field) if settings.sprint_field else None
            ),
            links=self._links(fields.get("issuelinks") or []),
        )

    @staticmethod
    def _sprint(entries) -> str | None:
        if not isinstance(entries, list) or not entries:
            return None
        active = [entry for entry in entries if entry.get("state") == "active"]
        return (active or entries)[-1].get("name")

    def _links(self, links: list) -> tuple[Link, ...]:
        blocks = self._settings.links.get("blocks")
        relates = self._settings.links.get("relates")
        found = []
        for link in links:
            name = (link.get("type") or {}).get("name")
            outward = (link.get("outwardIssue") or {}).get("key")
            inward = (link.get("inwardIssue") or {}).get("key")
            if name and name == blocks:
                if outward:
                    found.append(Link("blocks", outward))
                elif inward:
                    found.append(Link("blocked_by", inward))
            elif name and name == relates and (outward or inward):
                found.append(Link("relates", outward or inward))
        return tuple(found)
