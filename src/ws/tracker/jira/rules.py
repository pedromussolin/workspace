"""The rules of `ws card`: what each draft may do to which card, and the request it becomes."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from ws import cardpolicy
from ws.config import repo_root
from ws.identity import dev_id
from ws.taskmodel import Status
from ws.tracker import vocab
from ws.tracker.errors import TrackerSetup
from ws.tracker.jira.adf import AdfError, foreign_nodes, to_adf
from ws.tracker.jira.client import CATEGORY_STATUS, JiraClient, JiraError
from ws.tracker.jira.settings import JiraConfig
from ws.tracker.write import CREATED, UPPER_OUT_OF_SPRINTS, Draft
from ws.userconfig import ConfigInvalid, ConfigMissing, Person

MAX_SUMMARY = 255
WORKLOG_HOUR = 9

_PREFIX = re.compile(r"^\[[^\]]+\]")
_UPPER_TITLE = re.compile(r"^\[[^\]]+\] ")
_TIME = re.compile(r"^\d+[hm](\s+\d+[hm])*$")
_TIME_PART = re.compile(r"(\d+)([hm])")
_SAME_LINK = {("blocks", "out"), ("blocked_by", "in"), ("causes", "out"), ("caused_by", "in")}
_LINK_TYPE = {
    "blocks": "blocks",
    "blocked_by": "blocks",
    "relates": "relates",
    "causes": "causes",
    "caused_by": "causes",
}
"""The config key of the link type each draft kind uses."""
_REVERSED_LINK = {"blocked_by", "caused_by"}
_CONTRADICTION = {
    "blocks": "{key} is already blocked by {target}",
    "blocked_by": "{key} already blocks {target}",
    "causes": "{key} is already caused by {target}",
    "caused_by": "{key} already causes {target}",
}
_ESTIMATE_SCREEN = "timetracking"


@dataclass
class Verdict:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    resolved: dict = field(default_factory=dict)
    preview: list[str] = field(default_factory=list)
    requests: list[dict] = field(default_factory=list)
    before: dict = field(default_factory=dict)

    @property
    def request(self) -> dict | None:
        """The first request, the one that defines the draft (a create, an edit, a transition)."""
        return self.requests[0] if self.requests else None


@dataclass(frozen=True)
class Sprint:
    """The sprint a draft puts a card in."""

    id: int
    name: str
    end: date | None
    active: bool

    def label(self, *, create: bool) -> str:
        """The sprint as the preview shows it. The active sprint keeps the lines it always had:
        its full end date on a create, no date on an edit."""
        if self.end is None or (self.active and not create):
            return self.name
        if self.active:
            return f"{self.name} (termina em {self.end.isoformat()})"
        return f"{self.name} (termina em {self.end:%d/%m})"


def _sprint_order(sprint: dict) -> tuple:
    """Earliest start date first; sprints with no start date after them, by id."""
    start = _instant(sprint.get("startDate"))
    number = sprint.get("id")
    if isinstance(number, bool) or not isinstance(number, int):
        number = float("inf")
    return (start is None, start.timestamp() if start else 0.0, number)


def _instant(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def adf_text(node: dict) -> str:
    kind = node.get("type")
    if kind == "text":
        return node.get("text", "")
    if kind == "hardBreak":
        return "\n"
    children = [adf_text(child) for child in node.get("content", [])]
    if kind == "heading":
        return f"{'#' * node.get('attrs', {}).get('level', 2)} {''.join(children)}"
    if kind == "listItem":
        return "- " + "\n  ".join(children)
    if kind in ("paragraph", "codeBlock"):
        return "".join(children)
    return "\n".join(children)


class Context:
    """What the rules read from Jira, fetched once per run."""

    def __init__(
        self,
        client: JiraClient,
        settings: JiraConfig,
        me: dict,
        tz: ZoneInfo,
        today,
        people: dict[str, Person] | None = None,
        identity_email: str | None = None,
        config: object = None,
    ):
        self.client = client
        self.config = config
        self.people = people or {}
        self.own_dev_id = dev_id(identity_email) if identity_email else None
        self.settings = settings
        self.project = settings.project
        self.account_id = me["accountId"]
        self.name = me.get("displayName") or self.account_id
        self.tz = tz
        self.today: date = today
        self._issues: dict[str, dict | None] = {}
        self._meta: dict[str, list[dict]] = {}
        self._active_sprints: list[dict] | None = None
        self._open_sprints: list[dict] | None = None
        self._policies: dict[str | None, cardpolicy.Policy] = {}
        self.batch_started: set[str] = set()
        self.batch_worklogs: set[str] = set()

    @classmethod
    def load(
        cls,
        client: JiraClient,
        settings: JiraConfig,
        now: datetime,
        people: dict[str, Person] | None = None,
        identity_email: str | None = None,
        config: object = None,
    ) -> "Context":
        me = client.myself() or {}
        if not me.get("accountId"):
            raise JiraError("Jira did not say who the user is (accountId)")
        try:
            tz = ZoneInfo(me.get("timeZone"))
        except (ValueError, TypeError, OSError):
            raise JiraError("Jira did not give a valid time zone for the user") from None
        today = now.astimezone(tz).date()
        return cls(client, settings, me, tz, today, people, identity_email, config)

    def policy(self, item: str | None, epic_ref: str | None) -> cardpolicy.Policy:
        """The merged card policy of the project of an item or an epic, loaded once per project.
        A layer that is missing or invalid is a setup error (exit 2), not a problem of a draft."""
        root = repo_root()
        project = cardpolicy.project_for(item, epic_ref, root)
        if project not in self._policies:
            try:
                self._policies[project] = cardpolicy.load(self.config, project, root)
            except (ConfigMissing, ConfigInvalid) as error:
                raise TrackerSetup(str(error)) from None
        return self._policies[project]

    def key_in_project(self, key: str) -> bool:
        return re.fullmatch(rf"{re.escape(self.project)}-[1-9]\d*", key) is not None

    def _issue(self, key: str) -> dict | None:
        """Every rule reads the card from one fetch with all the fields any rule needs, so a
        card first read as an epic is not later judged by the few fields an epic needs."""
        cached = self._issues.get(key, False)
        if cached is not False:
            return cached
        names = ["summary", "status", "assignee", "description", "parent", "project"]
        names += ["priority", "duedate", "reporter", "issuetype", "issuelinks"]
        names += ["labels", "timetracking"]
        if self.settings.start_date_field:
            names.append(self.settings.start_date_field)
        if self.settings.sprint_field:
            names.append(self.settings.sprint_field)
        try:
            issue = self.client.issue(key, names)
        except JiraError as error:
            if error.status != 404:
                raise
            issue = None
        self._issues[key] = issue
        return issue

    def card_fields(self, key: str, verdict: Verdict) -> dict | None:
        """The fields of a card of the project, whoever owns it; None with the problem."""
        if not self.key_in_project(key):
            verdict.problems.append(f"{key} is not a card of project {self.project}")
            return None
        issue = self._issue(key)
        if issue is None:
            verdict.problems.append(f"card {key} was not found")
            return None
        fields = issue.get("fields") or {}
        if (fields.get("project") or {}).get("key") != self.project:
            verdict.problems.append(f"{key} does not belong to project {self.project}")
            return None
        return fields

    def is_mine(self, fields: dict) -> bool:
        people = (fields.get("assignee") or {}, fields.get("reporter") or {})
        return self.account_id in (person.get("accountId") for person in people)

    def writable_card(self, key: str, verdict: Verdict) -> dict | None:
        fields = self.card_fields(key, verdict)
        if fields is None:
            return None
        assignee = fields.get("assignee") or {}
        verdict.resolved["card"] = {
            "key": key,
            "status": (fields.get("status") or {}).get("name"),
            "assignee": assignee.get("displayName") or assignee.get("accountId"),
        }
        if not self.is_mine(fields):
            verdict.problems.append(
                f"card {key} is not yours: you are neither its assignee nor its reporter"
            )
            return None
        return fields

    def epic(self, key: str, verdict: Verdict) -> dict | None:
        if not self.key_in_project(key):
            verdict.problems.append(f"epic {key} is not a card of project {self.project}")
            return None
        issue = self._issue(key)
        if issue is None:
            verdict.problems.append(f"epic {key} was not found")
            return None
        fields = issue.get("fields") or {}
        problems = []
        if (fields.get("project") or {}).get("key") != self.project:
            problems.append(f"epic {key} does not belong to project {self.project}")
        if (fields.get("issuetype") or {}).get("hierarchyLevel") != 1:
            problems.append(f"{key} is not an epic")
        category = ((fields.get("status") or {}).get("statusCategory") or {}).get("key")
        if category == "done":
            problems.append(f"epic {key} is done")
        title = fields.get("summary") or ""
        prefix = _PREFIX.match(title)
        info = {"key": key, "title": title, "prefix": prefix.group(0) if prefix else None}
        verdict.resolved["epic"] = info
        verdict.problems.extend(problems)
        return None if problems else info

    def type_id(self, type_: str, verdict: Verdict) -> str | None:
        found = self.settings.types.get(type_)
        if not found:
            verdict.problems.append(
                f"type {type_!r} has no issue type id: add it to [tracker.jira.types] "
                "(ws tracker discover)"
            )
        return found

    def link_type(self, kind: str, verdict: Verdict) -> str | None:
        found = self.settings.links.get(kind)
        if not found:
            hint = f'; write {kind} = "<link type name>" there' if kind == "causes" else ""
            verdict.problems.append(
                f"link kind {kind!r} has no link type: add it to [tracker.jira.links] "
                f"(ws tracker discover){hint}"
            )
        return found

    def _entries(self, type_id: str) -> list[dict]:
        if type_id not in self._meta:
            meta = self.client.create_meta(self.project, type_id) or {}
            entries = meta.get("fields") or []
            if isinstance(entries, dict):
                entries = list(entries.values())
            self._meta[type_id] = entries
        return self._meta[type_id]

    def priorities(self, type_id: str) -> list[str]:
        names: list[str] = []
        for entry in self._entries(type_id):
            if "priority" in (entry.get("fieldId"), entry.get("key")):
                names = [item["name"] for item in entry.get("allowedValues") or []]
        return names

    def create_screen_has(self, type_id: str, field_id: str) -> bool:
        return any(field_id in (e.get("fieldId"), e.get("key")) for e in self._entries(type_id))

    def initiative(self, key: str, verdict: Verdict) -> dict | None:
        if not self.key_in_project(key):
            verdict.problems.append(f"initiative {key} is not a card of project {self.project}")
            return None
        issue = self._issue(key)
        if issue is None:
            verdict.problems.append(f"initiative {key} was not found")
            return None
        fields = issue.get("fields") or {}
        problems = []
        if (fields.get("project") or {}).get("key") != self.project:
            problems.append(f"initiative {key} does not belong to project {self.project}")
        if (fields.get("issuetype") or {}).get("hierarchyLevel") != 2:
            problems.append(f"{key} is not an initiative")
        category = ((fields.get("status") or {}).get("statusCategory") or {}).get("key")
        if category == "done":
            problems.append(f"initiative {key} is done")
        info = {"key": key, "title": fields.get("summary") or ""}
        verdict.resolved["initiative"] = info
        verdict.problems.extend(problems)
        return None if problems else info

    def person(self, ref: str, verdict: Verdict) -> str | None:
        if ref == "me" or ref == self.own_dev_id:
            return self.account_id
        found = self.people.get(ref)
        if found is None:
            verdict.problems.append(
                f"unknown person {ref!r}: run ws people add <e-mail> and paste the block into "
                "config.toml"
            )
            return None
        account_id = found.ids.get("jira")
        if not account_id:
            verdict.problems.append(
                f"person {ref!r} has no jira id; run ws people add <e-mail> and paste the block "
                "into config.toml"
            )
        return account_id

    def person_name(self, ref: str, account_id: str) -> str:
        """The name the preview shows: the tracker's display name, else the label, else the id."""
        if account_id == self.account_id:
            return self.name
        try:
            name = (self.client.user(account_id) or {}).get("displayName")
        except JiraError:
            name = None
        label = self.people[ref].label if ref in self.people else None
        return name or label or account_id

    def sprint(self, value: str, verdict: Verdict) -> Sprint | None:
        """The sprint a draft's `sprint` names: "active" (the board's one active sprint),
        "next" (its earliest future sprint) or the exact name of an open sprint of the board;
        None with the problem."""
        if value == "active":
            found = self._active_sprint(verdict)
        elif value == "next":
            found = self._next_sprint(verdict)
        else:
            found = self._named_sprint(value, verdict)
        if found is None:
            return None
        if isinstance(found.get("id"), bool) or not isinstance(found.get("id"), int):
            what = "the active sprint" if value == "active" else f"the sprint {found.get('name')}"
            verdict.problems.append(f"{what} has no numeric id")
            return None
        end = self._end_date(found.get("endDate"))
        verdict.resolved["sprint"] = {
            "id": found["id"],
            "name": found.get("name"),
            "end_date": end.isoformat() if end else None,
        }
        active = value == "active" or found.get("state") == "active"
        if active and end and end < self.today:
            verdict.warnings.append(
                f"the sprint {found.get('name')} ended on {end.isoformat()} and is still active"
            )
        return Sprint(found["id"], str(found.get("name")), end, active)

    def _active_sprint(self, verdict: Verdict) -> dict | None:
        """The board's one active sprint, from the read of the active sprints alone."""
        if self._active_sprints is None:
            self._active_sprints = self.client.active_sprints(self.settings.board_id)
        if len(self._active_sprints) != 1:
            names = ", ".join(str(item.get("name")) for item in self._active_sprints) or "none"
            verdict.problems.append(
                "the board needs exactly one active sprint, found "
                f"{len(self._active_sprints)} ({names})"
            )
            return None
        return self._active_sprints[0]

    def _open(self) -> list[dict]:
        if self._open_sprints is None:
            self._open_sprints = self.client.open_sprints(self.settings.board_id)
        return self._open_sprints

    def _next_sprint(self, verdict: Verdict) -> dict | None:
        future = [item for item in self._open() if item.get("state") == "future"]
        if not future:
            verdict.problems.append('the board has no future sprint for sprint = "next"')
            return None
        return min(future, key=_sprint_order)

    def _named_sprint(self, name: str, verdict: Verdict) -> dict | None:
        sprints = self._open()
        named = [item for item in sprints if item.get("name") == name]
        if len(named) == 1:
            return named[0]
        listed = ", ".join(str(item.get("name")) for item in sprints) or "none"
        if named:
            verdict.problems.append(
                f"{len(named)} open sprints of the board are named {name!r}; open sprints: {listed}"
            )
        else:
            verdict.problems.append(
                f"no open sprint of the board is named {name!r}; open sprints: {listed}"
            )
        return None

    def _end_date(self, value) -> date | None:
        moment = _instant(value)
        return moment.astimezone(self.tz).date() if moment else None


def check(ctx: Context, draft: Draft) -> Verdict:
    verdict = Verdict()
    verdict.resolved["today"] = ctx.today.isoformat()
    {
        "create": _create,
        "edit": _edit,
        "move": _move,
        "comment": _comment,
        "worklog": _worklog,
        "link": _link,
    }[draft.op](ctx, draft, verdict)
    if verdict.problems:
        verdict.requests = []
    return verdict


def _summary_problems(title: str) -> list[str]:
    problems = []
    if not title.strip():
        problems.append("the title is empty")
    if "\n" in title or "\r" in title:
        problems.append("the title must be one line")
    if len(title) > MAX_SUMMARY:
        problems.append(f"the title has {len(title)} characters; the limit is {MAX_SUMMARY}")
    return problems


def _epic_prefix(epic_title: str | None) -> str | None:
    """The prefix of an epic's title without its brackets, None when it has none."""
    found = _PREFIX.match(epic_title or "")
    return found.group(0)[1:-1] if found else None


def _parse_sections(text: str, required: list[str]) -> tuple[dict[str, int], dict[str, str]]:
    """How many times each required `## heading` appears in a description (code blocks do not
    count) and the text under it, for the policy to judge."""
    counts = {name: 0 for name in required}
    lines: dict[str, list[str]] = {name: [] for name in required}
    current = None
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        elif not in_code and line.startswith("## "):
            current = line[3:].strip() if line[3:].strip() in counts else None
            if current:
                counts[current] += 1
            continue
        if current and line.strip():
            lines[current].append(line)
    return counts, {name: "\n".join(found) for name, found in lines.items()}


_SECTION_GAP = re.compile(r"section '(.*)' is missing or empty")


def _section_problems(gaps: list[dict], counts: dict[str, int]) -> list[str]:
    """The description problems: what the policy found missing or empty, said as the headings
    appear, plus a heading that appears twice."""
    empty = {m.group(1) for g in gaps if (m := _SECTION_GAP.fullmatch(g["detail"]))}
    problems = []
    for name, count in counts.items():
        if count == 0:
            problems.append(f"the description needs a '## {name}' section")
        elif count > 1:
            problems.append(f"the section '## {name}' appears more than once")
        elif name in empty:
            problems.append(f"the section '## {name}' is empty")
    return problems


def _required_sections(policy: cardpolicy.Policy, type_: str) -> list[str]:
    return list(policy.data.get("sections", {}).get(type_, {}).get("required", []))


def _gap_message(gap: dict, sprint: str | None = None) -> str:
    """A gap that is a problem of the draft, in the words `ws card check` has always used."""
    if gap["rule"] == "title.format":
        return f"the {gap['detail']}"
    if gap["rule"] == "create.due_with_sprint":
        return f'due is required with sprint = "{sprint}"'
    return f"{gap['detail']} (card policy: {gap['rule']})"


def _title_message(gap: dict, epic_prefix: str | None) -> str:
    if epic_prefix and gap["detail"].startswith("title must start with"):
        return f"the title must start with the epic's prefix [{epic_prefix}] and a space"
    return _gap_message(gap)


def _padding_warning(policy: cardpolicy.Policy) -> str | None:
    percent = policy.data.get("estimate", {}).get("padding_percent", 0)
    if percent > 0:
        return f"Estimativa original: confira se já inclui a folga de {percent:g}% do padrão."
    return None


def _split_gaps(gaps: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """The gaps by where the check says them: title, sections, the sprint's due date, the rest."""
    title = [g for g in gaps if g["rule"] == "title.format"]
    sections = [g for g in gaps if g["rule"] == "sections.required"]
    due = [g for g in gaps if g["rule"] == "create.due_with_sprint"]
    rest = [g for g in gaps if g not in title + sections + due]
    return title, sections, due, rest


def _say_rest(verdict: Verdict, gaps: list[dict]) -> None:
    for gap in gaps:
        if gap["severity"] == "suggestion":
            verdict.warnings.append(gap["detail"])
        else:
            verdict.problems.append(_gap_message(gap))


def _convert(text: str, label: str, verdict: Verdict) -> dict | None:
    if not text.strip():
        verdict.problems.append(f"the {label} is empty")
        return None
    try:
        doc = to_adf(text)
    except AdfError as error:
        verdict.problems.append(
            f"the {label} cannot be converted: {error} (lines count from the first line after "
            "the front matter)"
        )
        return None
    if not doc["content"]:
        verdict.problems.append(f"the {label} has no content")
        return None
    return doc


def _dates_problems(start: date | None, due: date | None) -> list[str]:
    if start and due and start > due:
        return [f"start {start.isoformat()} is after due {due.isoformat()}"]
    return []


def _duration(text: str, name: str) -> tuple[str, int, list[str]]:
    """`text` as hours and minutes (`2h`, `30m`, `1h 30m`) with the spaces collapsed, its minutes,
    and what is wrong with it; the format of a worklog's `time` and of an `estimate`."""
    spent = " ".join(text.split())
    if not _TIME.match(spent):
        return spent, 0, [f"{name} must be hours and minutes only, like 2h, 30m or 1h 30m"]
    problems = []
    parts = _TIME_PART.findall(spent)
    if len({unit for _, unit in parts}) != len(parts):
        problems.append(f"{name} repeats a unit; write it like 1h 30m")
    minutes = sum(int(number) * (60 if unit == "h" else 1) for number, unit in parts)
    if not minutes:
        problems.append(f"{name} must be more than zero")
    return spent, minutes, problems


def _minutes_text(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    return " ".join(
        part for part in (f"{hours}h" if hours else "", f"{rest}m" if rest else "") if part
    )


def _label_problems(labels: list[str]) -> list[str]:
    return [
        f"label {label!r} has whitespace; the tracker refuses it, use a hyphen or an underscore"
        for label in labels
        if re.search(r"\s", label)
    ]


def _create(ctx: Context, draft: Draft, verdict: Verdict) -> None:
    values = draft.values
    type_ = values["type"]
    if type_ in vocab.UPPER_TYPES:
        _create_upper(ctx, draft, verdict)
        return
    type_id = ctx.type_id(type_, verdict)
    if type_id is None:
        return
    epic = ctx.epic(values["epic"], verdict)
    link = {"epic": epic, "line": f"Épico: {epic['key']} {epic['title']}"} if epic else None
    prefix = _epic_prefix(epic["title"]) if epic else None
    _create_issue(ctx, draft, verdict, type_id, link, link_required=True, epic_prefix=prefix)


def _create_upper(ctx: Context, draft: Draft, verdict: Verdict) -> None:
    values = draft.values
    type_ = values["type"]
    type_id = ctx.type_id(type_, verdict)
    if type_id is None:
        return
    if not _UPPER_TITLE.match(draft.title):
        article = "an epic" if type_ == "epic" else "an initiative"
        verdict.problems.append(f"{article} title starts with [PREFIX]")
    link = None
    if "parent" in values and not ctx.settings.premium:
        verdict.problems.append(
            "without premium the initiative is a link: create the epic first, then edit it with "
            "`parent`"
        )
    elif "parent" in values:
        initiative = ctx.initiative(values["parent"], verdict)
        if not ctx.create_screen_has(type_id, "parent"):
            verdict.problems.append(
                f"the epic create screen has no parent: create it without parent and link it to "
                f"{values['parent']} by hand in the tracker"
            )
        elif initiative:
            link = {
                "epic": initiative,
                "line": f"Iniciativa: {initiative['key']} {initiative['title']}",
            }
    _create_issue(ctx, draft, verdict, type_id, link, link_required="parent" in values)


def _create_issue(
    ctx: Context,
    draft: Draft,
    verdict: Verdict,
    type_id: str,
    link: dict | None,
    *,
    link_required: bool,
    epic_prefix: str | None = None,
) -> None:
    values = draft.values
    type_ = values["type"]
    title = draft.title
    policy = ctx.policy(values.get("item"), values.get("epic"))
    labels = values.get("labels", [])
    estimate, minutes, estimate_problems = None, 0, []
    if "estimate" in values:
        estimate, minutes, estimate_problems = _duration(values["estimate"], "estimate")
    sprint_value = values.get("sprint")
    wants_sprint = sprint_value not in (None, "backlog")
    required = _required_sections(policy, type_)
    counts, sections = _parse_sections(draft.body, required)
    gaps = cardpolicy.evaluate(
        policy,
        {
            "type": type_,
            "title": title,
            "epic": values.get("epic"),
            "epic_prefix": epic_prefix,
            "labels": labels,
            "estimate_minutes": minutes,
            "due": values.get("due"),
            "sprint": sprint_value if wants_sprint else None,
            "assignee": values.get("assignee", "me"),
            "reporter": values.get("reporter", "me"),
            "sections": sections,
        },
        "create",
    )
    if estimate_problems:
        gaps = [gap for gap in gaps if gap["field"] != "estimate"]
    title_gaps, section_gaps, due_gaps, other_gaps = _split_gaps(gaps)
    if type_ in vocab.CARD_TYPES:
        verdict.problems.extend(_title_message(gap, epic_prefix) for gap in title_gaps)
    verdict.problems.extend(_summary_problems(title))
    verdict.problems.extend(_section_problems(section_gaps, counts))
    description = _convert(draft.body, "description", verdict)
    allowed = ctx.priorities(type_id)
    if values["priority"] not in allowed:
        verdict.problems.append(
            f"priority {values['priority']!r} is not allowed; the project accepts "
            f"{', '.join(allowed) or 'none (no priority field on the create screen)'}"
        )
    assignee_ref = values.get("assignee", "me")
    reporter_ref = values.get("reporter", "me")
    assignee = ctx.person(assignee_ref, verdict)
    reporter = ctx.person(reporter_ref, verdict)
    due = values.get("due")
    # "backlog" is refused on a create by the card-write check; here it sends no sprint.
    if due and due < ctx.today:
        verdict.problems.append(f"due {due.isoformat()} is before today ({ctx.today.isoformat()})")
    verdict.problems.extend(_gap_message(gap, sprint_value) for gap in due_gaps)
    verdict.problems.extend(_label_problems(labels))
    verdict.problems.extend(estimate_problems)
    _say_rest(verdict, other_gaps)
    if estimate and not estimate_problems and (warning := _padding_warning(policy)):
        verdict.warnings.append(warning)
    sent = ["summary", "description", "assignee"]
    sent += ["labels"] if labels else []
    sent += ["reporter"] if "reporter" in values else []
    sent += ["parent"] if type_ in vocab.CARD_TYPES else []
    sent += ["duedate"] if due else []
    sent += [ctx.settings.sprint_field] if wants_sprint else []
    for name in sent:
        if not ctx.create_screen_has(type_id, name):
            verdict.problems.append(
                f"the create screen of {vocab.TYPE_LABELS[type_]} has no {name}"
            )
    sprint = ctx.sprint(sprint_value, verdict) if wants_sprint else None
    if verdict.problems or not (assignee and reporter and description):
        return
    if link_required and not link:
        return
    if wants_sprint and not sprint:
        return
    fields = {
        "project": {"key": ctx.project},
        "issuetype": {"id": type_id},
        "summary": title,
        "description": description,
        "priority": {"name": values["priority"]},
        "assignee": {"accountId": assignee},
    }
    if "reporter" in values:
        fields["reporter"] = {"accountId": reporter}
    if link:
        fields["parent"] = {"key": link["epic"]["key"]}
    if due:
        fields["duedate"] = due.isoformat()
    if labels:
        fields["labels"] = labels
    sprint_line = "Sprint: (nenhuma)"
    if sprint:
        fields[ctx.settings.sprint_field] = sprint.id
        sprint_line = f"Sprint: {sprint.label(create=True)}"
    after = None
    if estimate and ctx.create_screen_has(type_id, _ESTIMATE_SCREEN):
        fields[_ESTIMATE_SCREEN] = {"originalEstimate": estimate}
    elif estimate:
        # The create screen has no estimate: the card is made first, then edited under the same
        # approval, as a move to in progress sets the start date.
        after = {
            "method": "PUT",
            "path": f"/rest/api/3/issue/{CREATED}",
            "body": {"fields": {_ESTIMATE_SCREEN: {"originalEstimate": estimate}}},
        }
    verdict.requests = [{"method": "POST", "path": "/rest/api/3/issue", "body": {"fields": fields}}]
    verdict.requests += [after] if after else []
    heading = {"epic": "épico", "initiative": "iniciativa"}.get(type_, "card")
    verdict.preview = [
        f"Criar {heading} no projeto {ctx.project}",
        f"Tipo: {vocab.TYPE_LABELS[type_]}",
        f"Título: {title}",
        *([link["line"]] if link else []),
        f"Prioridade: {values['priority']}",
        f"Responsável: {ctx.person_name(assignee_ref, assignee)}",
        f"Relator: {ctx.person_name(reporter_ref, reporter)}",
        sprint_line,
        f"Prazo: {due.isoformat() if due else '(nenhum)'}",
        *([f"Categorias: {', '.join(labels)}"] if labels else []),
        *([f"Estimativa original: {estimate}"] if estimate else []),
        "Descrição:",
        *[f"  {line}" for line in adf_text(description).splitlines()],
    ]


def _card_type(ctx: Context, fields: dict) -> str | None:
    """The neutral type of an existing card, from its issue type id; None when unknown."""
    found = (fields.get("issuetype") or {}).get("id")
    return next((name for name, type_id in ctx.settings.types.items() if type_id == found), None)


_LEVELS = {-1: "a subtask", 0: "a card", 1: "an epic", 2: "an initiative"}


def _level_problems(key: str, level, values: dict) -> list[str]:
    """`type` and `epic` belong to a card (level 0), `parent` to an epic (level 1); moving a
    card between levels is not an edit."""
    what = _LEVELS.get(level, "of an unknown level")
    problems = []
    if "type" in values and level != 0:
        problems.append(f"{key} is {what}: changing a card's level is done by hand in the tracker")
    if "epic" in values and level != 0:
        problems.append(
            "an epic has no epic; use parent for its initiative"
            if level == 1
            else f"{key} is {what}; only a card has an epic"
        )
    if "parent" in values and level != 1:
        problems.append(
            "parent is only for an epic; a card uses epic"
            if level == 0
            else f"{key} is {what}; only an epic has a parent"
        )
    return problems


def _parse_day(value) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _edit(ctx: Context, draft: Draft, verdict: Verdict) -> None:
    values = draft.values
    key = values["key"]
    current = ctx.writable_card(key, verdict)
    if current is None:
        return
    settings = ctx.settings
    changes: dict = {}
    updates: dict = {}
    before: dict = {}
    lines = [f"Editar o card {key}"]
    level = (current.get("issuetype") or {}).get("hierarchyLevel")
    verdict.problems.extend(_level_problems(key, level, values))
    meta = ctx.client.edit_meta(key)

    new_epic = ctx.epic(values["epic"], verdict) if "epic" in values and level == 0 else None
    current_parent = current.get("parent") or {}
    if new_epic and current_parent.get("key") != new_epic["key"]:
        changes["parent"] = {"key": new_epic["key"]}
        before["parent"] = current_parent.get("key")
        lines.append(f"Épico: {current_parent.get('key') or '(nenhum)'} -> {new_epic['key']}")
    if "title" in values:
        verdict.problems.extend(_summary_problems(values["title"]))
    if "title" in values and level in (1, 2) and not _UPPER_TITLE.match(values["title"]):
        verdict.problems.append(f"{_LEVELS[level]} title starts with [PREFIX]")
    epic_prefix = None
    if level == 0 and ("title" in values or "epic" in values):
        if "epic" in values:
            epic_title = new_epic["title"] if new_epic else None
            check_prefix = new_epic is not None
        else:
            epic_title = (current_parent.get("fields") or {}).get("summary")
            check_prefix = bool(current_parent)
            if check_prefix and epic_title is None:
                verdict.problems.append("the card's current epic could not be read")
                check_prefix = False
        epic_prefix = _epic_prefix(epic_title) if check_prefix else None
    epic_ref = values.get("epic") or current_parent.get("key") or (key if level == 1 else None)
    policy = ctx.policy(None, epic_ref)
    type_ = values["type"] if "type" in values and level == 0 else None
    type_ = type_ or _card_type(ctx, current) or "task"
    held = [item for item in current.get("labels") or [] if isinstance(item, str)]
    labels = [x for x in held if x not in values.get("remove_labels", [])]
    labels += [x for x in dict.fromkeys(values.get("add_labels", [])) if x not in labels]
    tracked = current.get("timetracking") or {}
    seconds = tracked.get("originalEstimateSeconds")
    minutes = seconds // 60 if isinstance(seconds, int) and not isinstance(seconds, bool) else 0
    estimate_problems: list[str] = []
    if "estimate" in values:
        _, minutes, estimate_problems = _duration(values["estimate"], "estimate")
    required = _required_sections(policy, type_)
    counts, sections = _parse_sections(draft.body, required) if draft.body.strip() else ({}, {})
    changed = [*values, *(["description"] if draft.body.strip() else [])]
    if "epic" in values and policy.data.get("title", {}).get("format") == "epic_prefix":
        changed.append("title")
    gaps = cardpolicy.evaluate(
        policy,
        {
            "type": type_,
            "title": values.get("title", current.get("summary") or ""),
            "epic": values.get("epic") or current_parent.get("key"),
            "epic_prefix": epic_prefix,
            "labels": labels,
            "estimate_minutes": minutes,
            "due": values.get("due") or current.get("duedate"),
            "assignee": values.get("assignee") or (current.get("assignee") or {}).get("accountId"),
            "reporter": values.get("reporter") or (current.get("reporter") or {}).get("accountId"),
            "sections": sections,
            "changed": changed,
        },
        "edit",
    )
    if estimate_problems:
        gaps = [gap for gap in gaps if gap["field"] != "estimate"]
    title_gaps, section_gaps, _, other_gaps = _split_gaps(gaps)
    if level == 0:
        verdict.problems.extend(_title_message(gap, epic_prefix) for gap in title_gaps)
    if "title" in values and values["title"] != current.get("summary"):
        changes["summary"] = values["title"]
        before["summary"] = current.get("summary")
        lines.append(f"Título: {current.get('summary')} -> {values['title']}")

    if "type" in values and level == 0:
        target = ctx.type_id(values["type"], verdict)
        old_type = current.get("issuetype") or {}
        if target and target != old_type.get("id"):
            allowed = [
                item.get("id") for item in (meta.get("issuetype") or {}).get("allowedValues", [])
            ]
            if target not in allowed:
                verdict.problems.append(
                    f"the card's edit screen does not allow type {values['type']}: "
                    "change it with the tracker's move, by hand"
                )
            else:
                changes["issuetype"] = {"id": target}
                before["issuetype"] = old_type.get("id")
                old_label = vocab.TYPE_LABELS.get(_card_type(ctx, current)) or old_type.get("name")
                lines.append(
                    f"Tipo: {old_label or '(nenhum)'} -> {vocab.TYPE_LABELS[values['type']]}"
                )
    for person_field, label in (("assignee", "Responsável"), ("reporter", "Relator")):
        if person_field not in values:
            continue
        account_id = ctx.person(values[person_field], verdict)
        old_person = current.get(person_field) or {}
        if account_id and account_id != old_person.get("accountId"):
            changes[person_field] = {"accountId": account_id}
            before[person_field] = old_person.get("accountId")
            old_name = old_person.get("displayName") or old_person.get("accountId")
            new_name = ctx.person_name(values[person_field], account_id)
            lines.append(f"{label}: {old_name or '(ninguém)'} -> {new_name}")
    links: list[dict] = []
    if "parent" in values and level == 1 and not settings.premium:
        if set(values) - {"key", "parent"} or draft.body.strip():
            verdict.problems.append(
                "without premium the initiative is a link: put `parent` in its own draft"
            )
        else:
            links = _initiative_link(ctx, key, values["parent"], current, verdict, lines)
    elif "parent" in values and level == 1:
        initiative = ctx.initiative(values["parent"], verdict)
        if "parent" not in meta:
            verdict.problems.append(
                f"the edit screen has no parent: link {key} to {values['parent']} by hand "
                "in the tracker"
            )
        elif initiative and values["parent"] != current_parent.get("key"):
            changes["parent"] = {"key": values["parent"]}
            before["parent"] = current_parent.get("key")
            lines.append(f"Pai: {current_parent.get('key') or '(nenhum)'} -> {values['parent']}")

    if "priority" in values:
        type_id = (current.get("issuetype") or {}).get("id")
        allowed = ctx.priorities(type_id) if type_id else None
        if allowed is not None and values["priority"] not in allowed:
            verdict.problems.append(
                f"priority {values['priority']!r} is not allowed; the project accepts "
                f"{', '.join(allowed) or 'none (no priority field on the create screen)'}"
            )
        old = (current.get("priority") or {}).get("name")
        if values["priority"] != old:
            changes["priority"] = {"name": values["priority"]}
            before["priority"] = old
            lines.append(f"Prioridade: {old or '(nenhuma)'} -> {values['priority']}")

    old_start = _parse_day(current.get(settings.start_date_field))
    old_due = _parse_day(current.get("duedate"))
    if "start" in values or "due" in values:
        verdict.problems.extend(
            _dates_problems(values.get("start", old_start), values.get("due", old_due))
        )
    if "start" in values and values["start"] != old_start:
        changes[settings.start_date_field] = values["start"].isoformat()
        before[settings.start_date_field] = old_start.isoformat() if old_start else None
        lines.append(f"Início: {old_start or '(nenhum)'} -> {values['start'].isoformat()}")
    if "due" in values and values["due"] != old_due:
        changes["duedate"] = values["due"].isoformat()
        before["duedate"] = old_due.isoformat() if old_due else None
        lines.append(f"Prazo: {old_due or '(nenhum)'} -> {values['due'].isoformat()}")

    _edit_labels(values, current, verdict, updates, before, lines)
    _edit_estimate(values, current, verdict, changes, before, lines)
    _say_rest(verdict, other_gaps)
    if "estimate" in values and not estimate_problems and (warning := _padding_warning(policy)):
        verdict.warnings.append(warning)

    upper = isinstance(level, int) and level >= 1
    if "sprint" in values and upper and values["sprint"] != "backlog":
        verdict.problems.append(UPPER_OUT_OF_SPRINTS)
    elif "sprint" in values:
        _edit_sprint(ctx, values["sprint"], current, verdict, changes, before, lines)

    if draft.body.strip():
        verdict.problems.extend(_section_problems(section_gaps, counts))
        old_doc = current.get("description")
        if old_doc:
            try:
                foreign = foreign_nodes(old_doc)
            except (KeyError, TypeError, AttributeError):
                foreign = {"unreadable"}
            if foreign:
                verdict.problems.append(
                    "the current description holds content that cannot be written back: "
                    + ", ".join(sorted(foreign))
                )
        new_doc = _convert(draft.body, "description", verdict)
        if new_doc is not None and new_doc != old_doc:
            changes["description"] = new_doc
            before["description"] = old_doc
            lines.append("Descrição, antes:")
            lines.extend(
                f"  {line}" for line in (adf_text(old_doc).splitlines() if old_doc else ["(vazia)"])
            )
            lines.append("Descrição, depois:")
            lines.extend(f"  {line}" for line in adf_text(new_doc).splitlines())

    for name in (*changes, *updates):
        # Jira's editmeta leaves `timetracking` out even where the card view shows the
        # estimate and a PUT sets it (checked on the real site on 2026-11-24).
        if name == _ESTIMATE_SCREEN:
            continue
        if name not in meta:
            verdict.problems.append(f"the edit screen of {key} has no {name}")
    if not changes and not updates and not links and not verdict.problems:
        verdict.problems.append("the draft changes nothing on the card")
        if lines and lines[-1].endswith(": já existe"):
            # The plan shows the initiative's link that is already there, as the `link` op does.
            verdict.preview = lines
    if verdict.problems:
        return
    body = {name: part for name, part in (("fields", changes), ("update", updates)) if part}
    verdict.requests = links or [
        {"method": "PUT", "path": f"/rest/api/3/issue/{key}", "body": body}
    ]
    verdict.before = before
    verdict.preview = lines


def _edit_labels(
    values: dict, current: dict, verdict: Verdict, updates: dict, before: dict, lines: list[str]
) -> None:
    """Adds and removes labels, never replacing the list: a label already on the card is not
    added again, one that is not there is not removed, as an existing link is skipped."""
    verdict.problems.extend(
        _label_problems([*values.get("add_labels", []), *values.get("remove_labels", [])])
    )
    held = [item for item in current.get("labels") or [] if isinstance(item, str)]
    add = [label for label in values.get("add_labels", []) if label not in held]
    remove = [label for label in values.get("remove_labels", []) if label in held]
    if not (add or remove):
        return
    updates["labels"] = [*({"add": label} for label in add), *({"remove": x} for x in remove)]
    before["labels"] = held
    shown = [*(f"+ {label}" for label in add), *(f"- {label}" for label in remove)]
    lines.append(f"Categorias: {', '.join(shown)}")


def _edit_estimate(
    values: dict, current: dict, verdict: Verdict, changes: dict, before: dict, lines: list[str]
) -> None:
    if "estimate" not in values:
        return
    text, minutes, found = _duration(values["estimate"], "estimate")
    verdict.problems.extend(found)
    tracked = current.get("timetracking") or {}
    seconds = tracked.get("originalEstimateSeconds")
    old = seconds // 60 if isinstance(seconds, int) and not isinstance(seconds, bool) else None
    if found or minutes == old:
        return
    was = tracked.get("originalEstimate") or (_minutes_text(old) if old else None)
    changes[_ESTIMATE_SCREEN] = {"originalEstimate": text}
    before[_ESTIMATE_SCREEN] = was
    lines.append(f"Estimativa original: {was or '(nenhuma)'} -> {text}")


def _initiative_link(
    ctx: Context, key: str, initiative: str, current: dict, verdict: Verdict, lines: list[str]
) -> list[dict]:
    """Without premium an epic cannot have an initiative as its parent, so `parent`, alone in its
    draft, ties them by the `initiative_link` link, the request a `link` draft sends; nothing
    when that link is already there, either way."""
    found = ctx.initiative(initiative, verdict)
    type_name = ctx.link_type(ctx.settings.initiative_link, verdict)
    if not (found and type_name):
        return []
    line = f"Iniciativa: {initiative} (por link {type_name})"
    if _existing_link(current.get("issuelinks") or [], type_name, initiative):
        lines.append(f"{line}: já existe")
        return []
    lines.append(line)
    return [_link_request(type_name, key, initiative)]


def _edit_sprint(
    ctx: Context,
    value: str,
    current: dict,
    verdict: Verdict,
    changes: dict,
    before: dict,
    lines: list[str],
) -> None:
    """Puts the card in the sprint `value` names, or out of its open sprint for "backlog"
    (the field set to null). Closed sprints in the field are history: they are not the
    card's sprint. For "active" the line stays as it always was, every sprint of the field
    shown."""
    field = ctx.settings.sprint_field
    old = [item for item in (current.get(field) or []) if isinstance(item, dict)]
    held = [item for item in old if item.get("state") != "closed"]
    if value == "backlog":
        if not held:
            return
        target, label = None, "backlog (nenhuma sprint)"
    else:
        sprint = ctx.sprint(value, verdict)
        if sprint is None or any(item.get("id") == sprint.id for item in old):
            return
        target, label = sprint.id, sprint.label(create=False)
    changes[field] = target
    before[field] = [item.get("id") for item in old] or None
    shown = old if value == "active" else held
    names = ", ".join(str(item.get("name")) for item in shown) or "(nenhuma)"
    lines.append(f"Sprint: {names} -> {label}")


def _move(ctx: Context, draft: Draft, verdict: Verdict) -> None:
    key = draft.values["key"]
    if "to" in draft.values and "status" in draft.values:
        verdict.problems.append("a move needs exactly one of to or status, not both")
        return
    if "to" not in draft.values and "status" not in draft.values:
        verdict.problems.append("missing key 'to' for op move")
        return
    if draft.body.strip():
        verdict.problems.append("a move has no body")
    current = ctx.writable_card(key, verdict)
    if current is None:
        return
    available = ctx.client.transitions(key)
    matches = _transitions_to(ctx, draft, available, verdict)
    if matches is None:
        return
    chosen = matches[0]
    if not chosen.get("id"):
        verdict.problems.append(f"the transition {chosen.get('name')!r} has no id in Jira's answer")
        return
    required = sorted(
        (item.get("name") or name)
        for name, item in (chosen.get("fields") or {}).items()
        if item.get("required")
    )
    if required:
        verdict.problems.append(
            f"the transition {chosen.get('name')!r} requires fields ({', '.join(required)}); "
            "do it by hand in Jira"
        )
    if _destination_status(ctx, chosen.get("to") or {}) == Status.DONE:
        _finish_problems(ctx, key, current, verdict)
    if verdict.problems:
        return
    destination = (chosen.get("to") or {}).get("name")
    verdict.resolved["transition"] = {"id": chosen.get("id"), "to": destination}
    verdict.before = {"status": verdict.resolved["card"]["status"]}
    verdict.requests = [
        {
            "method": "POST",
            "path": f"/rest/api/3/issue/{key}/transitions",
            "body": {"transition": {"id": chosen.get("id")}},
        }
    ]
    verdict.preview = [
        f"Mover o card {key}",
        f"Status: {verdict.resolved['card']['status']} -> {destination}",
    ]
    if _starts_work(ctx, chosen.get("to") or {}):
        _add_start_date(ctx, key, current, verdict)


def _finish_problems(ctx: Context, key: str, current: dict, verdict: Verdict) -> None:
    """What the card policy requires of a card that is done: a start date, time spent. What the
    same batch sets (a start date, a worklog) counts."""
    parent = (current.get("parent") or {}).get("key")
    level = (current.get("issuetype") or {}).get("hierarchyLevel")
    policy = ctx.policy(None, parent or (key if level == 1 else None))
    required = policy.data.get("finish", {}).get("require", [])
    field = ctx.settings.start_date_field
    start = current.get(field) if field else None
    if "start" in required and not field:
        verdict.warnings.append(
            "start_date_field is not in config.toml [tracker.jira]; the policy's start rule was "
            "not checked"
        )
        start = True
    seconds = (current.get("timetracking") or {}).get("timeSpentSeconds")
    spent = seconds // 60 if isinstance(seconds, int) and not isinstance(seconds, bool) else 0
    card = {
        "start": start or key in ctx.batch_started,
        "spent_minutes": spent or (1 if key in ctx.batch_worklogs else 0),
    }
    verdict.problems.extend(
        _gap_message(gap) for gap in cardpolicy.evaluate(policy, card, "finish")
    )


def _transitions_to(
    ctx: Context, draft: Draft, available: list[dict], verdict: Verdict
) -> list[dict] | None:
    """The one transition the draft's `to` (a status name) or `status` (a neutral status) points
    at; a problem naming the options when there is none or more than one."""
    names = ", ".join(sorted({(item.get("to") or {}).get("name") or "?" for item in available}))
    if "status" in draft.values:
        wanted = draft.values["status"]
        matches = [
            item for item in available if _destination_status(ctx, item.get("to") or {}) == wanted
        ]
        label = f"the status {wanted!r}"
    else:
        target = vocab.fold(draft.values["to"])
        matches = [
            item
            for item in available
            if vocab.fold((item.get("to") or {}).get("name") or "") == target
        ]
        label = repr(draft.values["to"])
    if not matches:
        hint = "; use to with one of them" if "status" in draft.values else ""
        verdict.problems.append(
            f"no available transition leads to {label}; available: {names or 'none'}{hint}"
        )
        return None
    if len(matches) > 1:
        listing = ", ".join(f"{item.get('name')} (id {item.get('id')})" for item in matches)
        hint = ""
        if "status" in draft.values:
            names = sorted({(item.get("to") or {}).get("name") or "?" for item in matches})
            listing += f"; destinations: {', '.join(names)}"
            hint = "; use to with one of the destinations"
            if len(names) == 1:
                hint = "; the destination name does not tell them apart, do it by hand"
        verdict.problems.append(f"more than one transition leads to {label}: {listing}{hint}")
        return None
    return matches


def _destination_status(ctx: Context, destination: dict) -> str | None:
    name = destination.get("name") or ""
    overrides = ctx.settings.status_overrides
    if name in overrides:
        return str(overrides[name])
    category = (destination.get("statusCategory") or {}).get("key")
    status = CATEGORY_STATUS.get(category)
    return status.value if status else None


def _starts_work(ctx: Context, destination: dict) -> bool:
    name = destination.get("name") or ""
    overrides = ctx.settings.status_overrides
    if name in overrides:
        return overrides[name] == Status.IN_PROGRESS
    category = (destination.get("statusCategory") or {}).get("key")
    return CATEGORY_STATUS.get(category) == Status.IN_PROGRESS


def _add_start_date(ctx: Context, key: str, current: dict, verdict: Verdict) -> None:
    """Moving to in progress is when the task starts: an empty start date becomes today, sent
    right after the transition under the same approval."""
    field_name = ctx.settings.start_date_field
    if not field_name:
        verdict.warnings.append(
            "start_date_field is not in config.toml [tracker.jira]; the start date will not be set"
        )
        return
    old_start = _parse_day(current.get(field_name))
    verdict.before[field_name] = old_start.isoformat() if old_start else None
    if old_start:
        return
    due = _parse_day(current.get("duedate"))
    if due and ctx.today > due:
        verdict.warnings.append(
            f"the start date (today, {ctx.today.isoformat()}) is after the due date "
            f"{due.isoformat()}"
        )
    verdict.requests.append(
        {
            "method": "PUT",
            "path": f"/rest/api/3/issue/{key}",
            "body": {"fields": {field_name: ctx.today.isoformat()}},
        }
    )
    verdict.preview.append(f"Data de início: hoje, {ctx.today.strftime('%d/%m')}")
    ctx.batch_started.add(key)


def _comment(ctx: Context, draft: Draft, verdict: Verdict) -> None:
    key = draft.values["key"]
    current = ctx.writable_card(key, verdict)
    body = _convert(draft.body, "comment", verdict)
    if current is None or body is None:
        return
    verdict.requests = [
        {"method": "POST", "path": f"/rest/api/3/issue/{key}/comment", "body": {"body": body}}
    ]
    verdict.preview = [f"Comentar no card {key}", *[f"  {x}" for x in adf_text(body).splitlines()]]


def _worklog(ctx: Context, draft: Draft, verdict: Verdict) -> None:
    key = draft.values["key"]
    spent, _, found = _duration(draft.values["time"], "time")
    verdict.problems.extend(found)
    day = draft.values.get("day", ctx.today)
    if day > ctx.today:
        verdict.problems.append(f"day {day.isoformat()} is after today ({ctx.today.isoformat()})")
    current = ctx.writable_card(key, verdict)
    comment = None
    if draft.body.strip():
        comment = _convert(draft.body, "worklog comment", verdict)
    if current is None or verdict.problems:
        return
    started = datetime.combine(day, time(WORKLOG_HOUR), tzinfo=ctx.tz).strftime(
        "%Y-%m-%dT%H:%M:%S.000%z"
    )
    body: dict = {"timeSpent": spent, "started": started}
    if comment:
        body["comment"] = comment
    verdict.requests = [
        {"method": "POST", "path": f"/rest/api/3/issue/{key}/worklog", "body": body}
    ]
    verdict.preview = [f"Lançar horas no card {key}", f"Tempo: {spent}", f"Início: {started}"]
    if comment:
        verdict.preview.extend(["Comentário:", *[f"  {x}" for x in adf_text(comment).splitlines()]])


def _existing_link(links: list, type_name: str, other: str) -> str | None:
    """How the card is already tied to `other` by this link type: "out" (it is the outward
    side, so it blocks `other`), "in" (it is blocked by `other`) or None."""
    for link in links:
        if (link.get("type") or {}).get("name") != type_name:
            continue
        if (link.get("outwardIssue") or {}).get("key") == other:
            return "out"
        if (link.get("inwardIssue") or {}).get("key") == other:
            return "in"
    return None


def _link(ctx: Context, draft: Draft, verdict: Verdict) -> None:
    key = draft.values["key"]
    fields = ctx.card_fields(key, verdict)
    verdict.resolved["card"] = {"key": key}
    targets = [
        (kind, target)
        for kind in vocab.DRAFT_LINK_KINDS
        for target in dict.fromkeys(draft.values.get(kind, []))
    ]
    target_fields = {target: ctx.card_fields(target, verdict) for _, target in targets}
    names = {kind: _LINK_TYPE[kind] for kind, _ in targets}
    type_names = {name: ctx.link_type(name, verdict) for name in dict.fromkeys(names.values())}
    if fields is None or verdict.problems:
        return
    if not ctx.is_mine(fields):
        for _, target in targets:
            if not ctx.is_mine(target_fields[target]):
                verdict.problems.append(
                    f"card {target} is not yours: you are neither its assignee nor its "
                    f"reporter, and the same goes for {key}"
                )
    links = fields.get("issuelinks") or []
    for kind, target in targets:
        type_name = type_names[names[kind]]
        found = _existing_link(links, type_name, target)
        line = f"{key} {vocab.LINK_LABELS[kind]} {target}"
        if (kind, found) in _SAME_LINK or (kind == "relates" and found):
            verdict.preview.append(f"{line}: já existe")
            continue
        if found:
            verdict.problems.append(_CONTRADICTION[kind].format(key=key, target=target))
            continue
        inward, outward = (target, key) if kind in _REVERSED_LINK else (key, target)
        verdict.preview.append(line)
        verdict.requests.append(_link_request(type_name, inward, outward))
    if not verdict.problems and not verdict.requests:
        verdict.problems.append("the draft adds no link")


def _link_request(type_name: str, inward: str, outward: str) -> dict:
    return {
        "method": "POST",
        "path": "/rest/api/3/issueLink",
        "body": {
            "type": {"name": type_name},
            "inwardIssue": {"key": inward},
            "outwardIssue": {"key": outward},
        },
    }
