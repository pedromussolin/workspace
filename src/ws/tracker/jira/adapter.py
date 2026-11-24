"""The Jira adapter of the tracker port: cards read and written through the REST API."""

from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ws import userconfig
from ws.taskmodel import Task
from ws.tracker import write
from ws.tracker.errors import TrackerError, TrackerSetup
from ws.tracker.jira import client as jira
from ws.tracker.jira import discover, writer
from ws.tracker.jira.client import JiraClient, JiraError, SiteRefused
from ws.tracker.jira.settings import JiraConfig
from ws.tracker.port import Card, CardQuery, Link
from ws.userconfig import UserConfig

JIRA_CAPABILITIES = frozenset(
    {
        "worklog",
        "sprint",
        "start_date",
        "initiative",
        "set_reporter",
        "change_type",
        "link_types",
        "description",
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
    "labels",
    "timetracking",
    "timeoriginalestimate",
    "timespent",
    "created",
]


def _plain(node: dict) -> str:
    kind = node.get("type")
    attrs = node.get("attrs") or {}
    if kind == "text":
        return node.get("text", "")
    if kind == "hardBreak":
        return "\n"
    if kind == "mention":
        return attrs.get("text") or ""
    if kind == "inlineCard":
        return attrs.get("url") or ""
    children = [_plain(child) for child in node.get("content", [])]
    if kind == "heading":
        return f"{'#' * attrs.get('level', 2)} {''.join(children)}"
    if kind == "listItem":
        return "- " + "\n  ".join(children)
    if kind == "codeBlock":
        return "```\n" + "".join(children) + "\n```"
    if kind == "paragraph":
        return "".join(children)
    return "\n".join(children)


def _now() -> datetime:
    return datetime.now(UTC)


class _LazyClient:
    """The client of a tracker opened for reads that need only the connection: the token and the
    site are checked when the first request is made, so each read checks its own keys first."""

    def __init__(self, settings: JiraConfig):
        self._settings = settings
        self._client: JiraClient | None = None

    def __getattr__(self, name: str):
        if self._client is None:
            try:
                self._client = JiraClient(
                    self._settings.site, self._settings.email, userconfig.load_jira_token()
                )
            except (userconfig.ConfigMissing, userconfig.ConfigInvalid, SiteRefused) as error:
                raise TrackerSetup(str(error)) from None
        return getattr(self._client, name)


class JiraTracker:
    """Reads cards and, as the `Writer` of `ws card`, plans and sends the drafts.

    `config` gives the people and the identity the rules resolve (loaded when the plan needs it
    if not given); `today` and the plan start from the module's `_now`, which a test patches.
    `resolved` holds what the rules resolved for each step of the last plan.
    """

    kind = "jira"
    name = "Jira"

    def __init__(
        self,
        client: JiraClient,
        settings: JiraConfig,
        config: UserConfig | None = None,
    ):
        self._client = client
        self._settings = settings
        self._config = config
        self.target = settings.site.rstrip("/")
        self.capabilities = (
            JIRA_CAPABILITIES if settings.start_date_field else JIRA_CAPABILITIES - {"start_date"}
        )
        self.resolved: list[dict] = []
        self._myself: dict | None = None
        self._cards: dict[str, Card | None] = {}
        self._names: dict[str, str] = {}

    def _require(self) -> None:
        """What reading cards needs in the config: the project and the types, as `ws card`."""
        if isinstance(self._client, _LazyClient):
            self._settings, self._client = writer.session({"project", "types"})

    def _fields(self) -> list[str]:
        names = list(_BASE_FIELDS)
        if self._settings.sprint_field:
            names.append(self._settings.sprint_field)
        if self._settings.start_date_field:
            names.append(self._settings.start_date_field)
        return names

    def _account_data(self) -> dict:
        self._require()
        if self._myself is None:
            try:
                data = self._client.myself()
                if not data["accountId"]:
                    raise ValueError("myself answered without an account id")
            except (JiraError, KeyError, TypeError, ValueError) as error:
                raise TrackerError(str(error)) from None
            self._myself = data
        return self._myself

    def me(self) -> str:
        return self._account_data()["accountId"]

    def today(self) -> date:
        zone = self._account_data().get("timeZone")
        try:
            return _now().astimezone(ZoneInfo(zone)).date()
        except (ZoneInfoNotFoundError, ValueError, TypeError, OSError) as error:
            raise TrackerError(f"unusable tracker time zone {zone!r}: {error}") from None

    def card(self, ref: str) -> Card | None:
        self._require()
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
        self._require()
        if not (query.parent_in or query.sprint or query.assignees):
            return []
        clauses = [f'project = "{self._settings.project}"']
        if query.parent_in:
            clauses.append(f"parent in ({', '.join(query.parent_in)})")
        clauses.append(
            jira.assignees_jql(query.assignees) if query.assignees else jira.role_jql(query.role)
        )
        if query.sprint:
            clauses.append(jira.sprint_jql(query.sprint))
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
        self._require()
        if account not in self._names:
            try:
                name = (self._client.user(account) or {}).get("displayName")
            except (JiraError, AttributeError):
                name = None
            self._names[account] = name or account
        return self._names[account]

    def description(self, ref: str) -> str | None:
        self._require()
        try:
            issue = self._client.issue(ref, ["description"])
        except JiraError as error:
            if error.status == 404:
                return None
            raise TrackerError(str(error)) from None
        try:
            document = ((issue or {}).get("fields") or {}).get("description")
            text = _plain(document).strip() if isinstance(document, dict) else ""
        except (TypeError, AttributeError) as error:
            raise TrackerError(str(error)) from None
        return text or None

    def list_tasks(self, since: date, role: str) -> dict:
        try:
            account_id = self._client.myself()["accountId"]
            issues = self._client.search(jira.tasks_jql(since, role), jira.FIELDS)
            cards = [jira.card_from_issue(issue, account_id) for issue in issues]
        except (JiraError, KeyError, TypeError, ValueError) as error:
            raise TrackerError(str(error)) from None
        return {"platform": "jira", "role": role, "cards": cards}

    def discover_toml(self) -> str:
        if not self._settings.project:
            raise TrackerSetup("[tracker.jira] project is not set")
        try:
            return discover.discover_toml(
                self._client.issue_types(self._settings.project), self._client.link_types()
            )
        except (JiraError, TypeError, ValueError) as error:
            raise TrackerError(str(error)) from None

    def accounts_for(self, email: str) -> list[str]:
        try:
            users = [u for u in self._client.user_search(email.strip()) if u.get("accountId")]
        except (JiraError, TypeError, AttributeError) as error:
            raise TrackerError(str(error)) from None
        return [user["accountId"] for user in users]

    def account_for(self, email: str) -> str | None:
        found = self.accounts_for(email)
        return found[0] if len(found) == 1 else None

    def plan(self, entries: list[dict]) -> dict:
        config = self._config if self._config is not None else userconfig.load_config()
        try:
            found, self.resolved = writer.plan_and_resolved(
                self._client,
                self._settings,
                entries,
                people=config.people,
                identity_email=config.identity_email,
                now=_now(),
            )
        except (KeyError, TypeError, AttributeError) as error:
            raise TrackerError(f"unexpected answer from {self.name} ({error!r})") from None
        return found

    def guard(self, calls: list[dict]) -> str | None:
        return writer.guard(self._settings.project, calls)

    def send(self, call: dict) -> object:
        return writer.send(self._client, call)

    def apply(self, plan: dict, send: Callable[[dict], object] | None = None) -> Iterator[dict]:
        return write.apply_steps(self, plan, send or self.send)

    def created_key(self, reply: object) -> str | None:
        return writer.created_key(reply)

    def find_hint(self, title: str) -> str:
        return writer.find_hint(self._settings.project, title)

    def render_body(self, markdown: str) -> dict:
        return writer.render_body(markdown)

    def card_url(self, key: str) -> str:
        return writer.card_url(self._settings.site, key)

    def epics(self) -> list[dict]:
        """The open epics and initiatives the user works on, for `ws card epics`."""
        try:
            return writer.epics(self._client, self._settings)
        except (KeyError, TypeError, AttributeError) as error:
            raise TrackerError(f"unexpected answer from {self.name} ({error!r})") from None

    def _neutral(self, issue: dict) -> Card:
        settings = self._settings
        fields = jira._required(issue, "fields", "issue")
        status = jira._required(fields, "status", "issue fields")
        category = (status.get("statusCategory") or {}).get("key")
        kind = fields.get("issuetype") or {}
        by_id = {type_id: neutral for neutral, type_id in settings.types.items()}
        level = kind.get("hierarchyLevel")
        due = fields.get("duedate")
        start = fields.get(settings.start_date_field) if settings.start_date_field else None
        created = fields.get("created")
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
            start=date.fromisoformat(start[:10]) if start else None,
            labels=tuple(item for item in fields.get("labels") or () if isinstance(item, str)),
            estimate_minutes=self._minutes(
                fields, "originalEstimateSeconds", "timeoriginalestimate"
            ),
            spent_minutes=self._minutes(fields, "timeSpentSeconds", "timespent"),
            created=date.fromisoformat(created[:10]) if created else None,
        )

    @staticmethod
    def _minutes(fields: dict, tracked: str, plain: str) -> int | None:
        """Minutes from the seconds of the `timetracking` field, else of the plain field; None
        when the card has none."""
        seconds = (fields.get("timetracking") or {}).get(tracked)
        if seconds is None:
            seconds = fields.get(plain)
        if isinstance(seconds, bool) or not isinstance(seconds, int | float) or seconds <= 0:
            return None
        return round(seconds / 60)

    @staticmethod
    def _sprint(entries) -> str | None:
        if not isinstance(entries, list) or not entries:
            return None
        active = [entry for entry in entries if entry.get("state") == "active"]
        return (active or entries)[-1].get("name")

    def _links(self, links: list) -> tuple[Link, ...]:
        blocks = self._settings.links.get("blocks")
        relates = self._settings.links.get("relates")
        causes = self._settings.links.get("causes")
        found = []
        for link in links:
            name = (link.get("type") or {}).get("name")
            outward = (link.get("outwardIssue") or {}).get("key")
            inward = (link.get("inwardIssue") or {}).get("key")
            if name and name in (blocks, causes):
                kinds = ("blocks", "blocked_by") if name == blocks else ("causes", "caused_by")
                if outward:
                    found.append(Link(kinds[0], outward))
                elif inward:
                    found.append(Link(kinds[1], inward))
            elif name and name == relates and (outward or inward):
                found.append(Link("relates", outward or inward))
        return tuple(found)


def task_from_listing(card: dict, settings: JiraConfig) -> Task:
    return jira.task_from_card(card, settings.site, settings.status_overrides)


def open_tracker(config: UserConfig, connection_only: bool = False) -> JiraTracker:
    if connection_only:
        return JiraTracker(_LazyClient(config.tracker_settings), config.tracker_settings)
    settings, client = writer.session({"project", "types"})
    return JiraTracker(client, settings)


def open_writer(config: UserConfig, entries: list[dict]) -> JiraTracker:
    """The writer of `ws card`: the session checks the keys the drafts need; `today` and the plan
    start from this module's `_now`."""
    writes = [entry["write"] for entry in entries if entry["write"]]
    settings, client = writer.session(writer.needed_keys(writes))
    return JiraTracker(client, settings, config)
