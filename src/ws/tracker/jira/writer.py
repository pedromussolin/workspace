"""The Jira side of a card write: session, plan, guard, send and the epic listing.

Plain functions over the Jira settings and client; `ws.tracker.jira` wraps them in the writer
the core talks to.
"""

import re
from datetime import datetime
from pathlib import Path

from ws import userconfig
from ws.tracker import UnknownTracker, require_kind
from ws.tracker.errors import TrackerSetup
from ws.tracker.jira import rules
from ws.tracker.jira.adf import to_adf
from ws.tracker.jira.client import JiraClient, SiteRefused
from ws.tracker.jira.settings import JiraConfig
from ws.tracker.write import CREATED, from_document

REQUEST_TIMEOUT = 20

_PROJECT = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_ISSUE_LINK = "/rest/api/3/issueLink"


def needed_keys(writes: list[dict]) -> set[str]:
    needed = {"project"}
    for write in writes:
        op = write["op"]
        if op == "create":
            needed |= {"board_id", "types", "sprint_field"}
        if op == "edit":
            if "priority" in write or "type" in write:
                needed.add("types")
            if "start" in write:
                needed.add("start_date_field")
            if "sprint" in write:
                needed |= {"board_id", "sprint_field"}
        if op == "link":
            needed.add("links")
    return needed


def session(needed: set[str]) -> tuple[JiraConfig, JiraClient]:
    """The settings and a client, after checking the `needed` keys; the client's timeout is the
    module's `REQUEST_TIMEOUT` as it is at the call (a test patches it). The messages name the
    table the user has: `[tracker.jira]`, or the old `[jira]`."""
    try:
        config = userconfig.load_config()
        require_kind(config.tracker_kind)
        section = userconfig.load_tracker_table()[3]
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid, UnknownTracker) as error:
        raise TrackerSetup(str(error)) from None
    settings = config.tracker_settings
    missing = [name for name in sorted(needed) if not getattr(settings, name)]
    if missing:
        tables = {"types": f"[{section}.types]", "links": f"[{section}.links]"}
        hints = []
        if any(name not in tables for name in missing):
            hints.append('see the README section "Local config"')
        if any(name in tables for name in missing):
            hints.append("run ws tracker discover and paste its output into config.toml")
        raise TrackerSetup(
            f"config.toml [{section}] is missing "
            f"{', '.join(tables.get(name, name) for name in missing)}; {'; '.join(hints)}"
        )
    if not _PROJECT.fullmatch(settings.project):
        raise TrackerSetup(f"config.toml [{section}] project is not a valid project key")
    try:
        credential = userconfig.load_jira_token()
    except userconfig.ConfigMissing:
        raise TrackerSetup(
            "no Jira API key; run `ws config token jira` in your own terminal"
        ) from None
    except userconfig.ConfigInvalid as error:
        raise TrackerSetup(str(error)) from None
    try:
        client = JiraClient(settings.site, settings.email, credential, timeout=REQUEST_TIMEOUT)
    except SiteRefused as error:
        raise TrackerSetup(str(error)) from None
    return settings, client


def plan(
    client: JiraClient,
    settings,
    entries: list[dict],
    *,
    people,
    identity_email,
    now: datetime,
    config=None,
) -> dict:
    found, _ = plan_and_resolved(
        client,
        settings,
        entries,
        people=people,
        identity_email=identity_email,
        now=now,
        config=config,
    )
    return found


def plan_and_resolved(
    client: JiraClient,
    settings,
    entries: list[dict],
    *,
    people,
    identity_email,
    now: datetime,
    config=None,
) -> tuple[dict, list[dict]]:
    """The plan, and what the rules resolved for each step (`ws card check` prints it). `config`
    is the user config, where `[card] policy` names the company card policy."""
    context = rules.Context.load(client, settings, now, people, identity_email, config)
    for entry in entries:
        found = entry["write"] or {}
        if found.get("op") == "worklog":
            context.batch_worklogs.add(found["key"])
        elif found.get("op") == "edit" and "start" in found:
            context.batch_started.add(found["key"])
    verdicts = [
        rules.check(context, from_document(entry["write"]))
        if entry["write"]
        else rules.Verdict(problems=list(entry["problems"]))
        for entry in entries
    ]
    _batch_link_problems(settings, entries, verdicts)
    found = {
        "$schema": "card-plan",
        "version": 1,
        "tracker": "jira",
        "target": settings.site.rstrip("/"),
        "today": context.today.isoformat(),
        "steps": [_step(entry, verdict) for entry, verdict in zip(entries, verdicts, strict=True)],
    }
    return found, [verdict.resolved for verdict in verdicts]


def _step(entry: dict, verdict: rules.Verdict) -> dict:
    write = entry["write"] or {}
    return {
        "draft": entry["source"],
        "op": write.get("op", "unknown"),
        "card": verdict.resolved.get("card", {}).get("key"),
        "title": write.get("title") if write.get("op") == "create" else None,
        "preview": verdict.preview,
        "warnings": verdict.warnings,
        "problems": verdict.problems,
        "before": verdict.before,
        "native": verdict.requests,
    }


def _batch_link_problems(settings, entries: list[dict], verdicts: list[rules.Verdict]) -> None:
    """Each draft checks its links against Jira alone; across the drafts of one batch, a link
    asked twice, or asked both ways, is refused on the later draft."""
    symmetric = settings.links.get("relates")
    seen: dict[tuple[str, str, str], str] = {}
    for entry, verdict in zip(entries, verdicts, strict=True):
        name = Path(entry["source"]["path"]).name
        mine = []
        for request in verdict.requests:
            if request["path"] != _ISSUE_LINK:
                continue
            body = request["body"]
            link = (
                body["type"]["name"],
                body["inwardIssue"]["key"],
                body["outwardIssue"]["key"],
            )
            type_name, inward, outward = link
            reverse = (type_name, outward, inward)
            if link in seen or (type_name == symmetric and reverse in seen):
                earlier = seen.get(link) or seen[reverse]
                verdict.problems.append(
                    f"the {type_name} link between {inward} and {outward} is also asked by "
                    f"{earlier}"
                )
            elif reverse in seen:
                verdict.problems.append(
                    f"{inward} and {outward} are linked by {type_name} in both directions: here "
                    f"and in {seen[reverse]}; keep one"
                )
            mine.append(link)
        for link in mine:
            seen.setdefault(link, name)
        if verdict.problems:
            verdict.requests = []


def guard(project: str, calls: list[dict]) -> str | None:
    """The last line of defence: only the known request shapes, only on cards of the project."""
    key = rf"{re.escape(project)}-[1-9]\d*"
    allowed = {
        ("POST", re.compile(r"/rest/api/3/issue")),
        ("PUT", re.compile(rf"/rest/api/3/issue/({key}|{re.escape(CREATED)})")),
        ("POST", re.compile(rf"/rest/api/3/issue/{key}/(transitions|comment|worklog)")),
    }
    for request in calls:
        if request["method"] == "POST" and request["path"] == _ISSUE_LINK:
            body = request.get("body") or {}
            sides = [(body.get(side) or {}).get("key") for side in ("inwardIssue", "outwardIssue")]
            if all(isinstance(side, str) and re.fullmatch(key, side) for side in sides):
                continue
        if not any(
            request["method"] == method and pattern.fullmatch(request["path"])
            for method, pattern in allowed
        ):
            return f"{request['method']} {request['path']}"
    return None


def send(client: JiraClient, call: dict):
    if call["method"] == "PUT":
        return client.put(call["path"], call["body"])
    return client.post(call["path"], call["body"])


def created_key(reply) -> str | None:
    return reply.get("key") if isinstance(reply, dict) else None


def find_hint(project: str, title: str) -> str:
    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')

    phrase = f'"{escape(title)}"'
    jql = f'project = "{project}" AND summary ~ "{escape(phrase)}" ORDER BY created DESC'
    return f"use esta JQL: {jql}"


def render_body(markdown: str) -> dict:
    return to_adf(markdown)


def card_url(site: str, key: str) -> str:
    return f"{site.rstrip('/')}/browse/{key}"


def card_url_template(settings) -> str:
    return card_url(settings.site, "{key}")


def _epic_entry(issue: dict, level: int, parent: str | None) -> dict:
    fields = issue.get("fields") or {}
    title = fields.get("summary") or ""
    prefix = re.match(r"^\[[^\]]+\]", title)
    return {
        "key": issue["key"],
        "title": title,
        "prefix": prefix.group(0) if prefix else None,
        "status": (fields.get("status") or {}).get("name"),
        "level": level,
        "parent": parent,
    }


def _owned_levels(types: dict[str, str]) -> dict[str, int]:
    levels = {"epic": 1, "initiative": 2}
    return {types[name]: level for name, level in levels.items() if types.get(name)}


def epics(client: JiraClient, settings) -> list[dict]:
    jql = f'assignee = currentUser() AND project = "{settings.project}" AND statusCategory != Done'
    found_epics: dict[str, dict] = {}
    for issue in client.search(jql, ["parent"]):
        parent = (issue.get("fields") or {}).get("parent") or {}
        fields = parent.get("fields") or {}
        status = fields.get("status") or {}
        done = (status.get("statusCategory") or {}).get("key") == "done"
        if (fields.get("issuetype") or {}).get("hierarchyLevel") != 1 or done:
            continue
        found_epics.setdefault(parent["key"], _epic_entry(parent, 1, None))
    levels = _owned_levels(settings.types)
    if levels:
        wanted = ", ".join(levels)
        owned = (
            f"issuetype in ({wanted}) AND (assignee = currentUser() "
            "OR reporter = currentUser()) AND statusCategory != Done "
            f'AND project = "{settings.project}"'
        )
        fields = ["summary", "status", "issuetype", "parent"]
        initiatives = []
        for issue in client.search(owned, fields):
            issue_fields = issue.get("fields") or {}
            level = levels.get((issue_fields.get("issuetype") or {}).get("id"))
            if level is None:
                continue
            parent = (issue_fields.get("parent") or {}).get("key")
            entry = _epic_entry(issue, level, parent)
            found_epics[issue["key"]] = {**found_epics.get(issue["key"], {}), **entry}
            if level == 2:
                initiatives.append(issue["key"])
        if initiatives:
            children = f"parent in ({', '.join(initiatives)}) AND statusCategory != Done"
            for issue in client.search(children, fields):
                parent = ((issue.get("fields") or {}).get("parent") or {}).get("key")
                found_epics.setdefault(issue["key"], _epic_entry(issue, 1, parent))
    return list(found_epics.values())
