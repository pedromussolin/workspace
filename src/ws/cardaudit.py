"""`ws card audit`: reads cards and reports, per card, the gaps against the card policy.

The policy is the merged one of the card's project (`ws.cardpolicy`); the tracker is reached only
through the read side of the port. With `--drafts DIR` it also writes one `edit` draft per card
with every computed value and lists what only a person or the model can fill. It never writes to
the tracker. Design: docs/specs/2026-11-24-card-policy-design.md, "Where the policy applies".
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from ws import approval, cardpolicy, userconfig
from ws.config import data_dir, repo_root
from ws.contracts import validate
from ws.taskmodel import Status
from ws.tracker import port
from ws.tracker.port import Card, CardQuery, People, Tracker, TrackerError, TrackerSetup
from ws.userconfig import ConfigInvalid, ConfigMissing

SETUP = 2
TRACKER = 3

WHO = re.compile(r"me|dev-[0-9a-f]{10}")
REF = re.compile(r"[A-Z][A-Z0-9_]*-[0-9]+")
EPIC_PREFIX = re.compile(r"^\[([^\[\]]+)\]")
CATEGORY_RULE = re.compile(r"categories\.([^.]+)\.(?:derive|required)")


class Refused(Exception):
    """A reason to stop, with the exit code it ends in."""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    audit = commands.add_parser(
        "audit",
        help="Report the gaps of cards against the card policy (JSON); never writes to the "
        "tracker.",
    )
    audit.add_argument(
        "--sprint",
        metavar="SPRINT",
        help="active, next or the exact name of a sprint (default: active).",
    )
    audit.add_argument(
        "--who",
        action="append",
        metavar="WHO",
        help="Whose cards: me or a dev id (repeatable; default: me).",
    )
    audit.add_argument(
        "--keys", metavar="REF,REF", help="These cards instead of a sprint and people."
    )
    audit.add_argument(
        "--drafts",
        metavar="DIR",
        help="Write an edit draft per writable card with the computed values into DIR, a new or "
        "empty folder under cards/drafts, and list what needs input.",
    )
    audit.set_defaults(handler=lambda args: run(args.sprint, args.who, args.keys, args.drafts))


def parse_sections(text: str | None) -> dict[str, str]:
    """The description by its `## ` headings; a heading seen twice keeps both bodies."""
    sections: dict[str, str] = {}
    current = None
    in_code = False
    for line in (text or "").splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        elif not in_code and line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, "")
            continue
        if current is not None:
            sections[current] += line + "\n"
    return sections


def _ref_order(ref: str) -> tuple:
    prefix, _, number = ref.rpartition("-")
    return (prefix, int(number) if number.isdigit() else 0, ref)


class Auditor:
    """Turns tracker cards into neutral cards and evaluates them; policies and epic titles are
    read once."""

    def __init__(self, tracker: Tracker, config: object, root: Path):
        self.tracker = tracker
        self.config = config
        self.root = root
        self.me = tracker.me()
        self.policies: dict[str | None, cardpolicy.Policy] = {}
        self._epics: dict[str, str | None] = {}

    def policy(self, card: Card) -> cardpolicy.Policy:
        project = cardpolicy.project_for(None, card.parent, self.root)
        if project not in self.policies:
            self.policies[project] = cardpolicy.load(self.config, project, self.root)
        return self.policies[project]

    def _epic_prefix(self, ref: str | None) -> str | None:
        if not ref:
            return None
        if ref not in self._epics:
            epic = self.tracker.card(ref)
            found = EPIC_PREFIX.match(epic.title) if epic else None
            self._epics[ref] = found.group(1) if found else None
        return self._epics[ref]

    def neutral(self, card: Card, policy: cardpolicy.Policy) -> dict:
        required = policy.data.get("sections", {}).get(card.type, {}).get("required")
        text = self.tracker.description(card.ref) if required else None
        return {
            "type": card.type,
            "title": card.title,
            "epic": card.parent,
            "epic_prefix": self._epic_prefix(card.parent),
            "labels": list(card.labels),
            "estimate_minutes": card.estimate_minutes,
            "spent_minutes": card.spent_minutes,
            "start": card.start.isoformat() if card.start else None,
            "due": card.due.isoformat() if card.due else None,
            "sprint": card.sprint,
            "assignee": card.assignee,
            "reporter": card.reporter,
            "sections": parse_sections(text),
            "status": card.status.value,
            "links": [{"kind": link.kind, "ref": link.ref} for link in card.links],
        }

    def writable(self, card: Card) -> bool:
        """ADR 0009: the user is the card's assignee or its reporter."""
        return self.me in (card.assignee, card.reporter)

    def audit(self, card: Card) -> dict:
        policy = self.policy(card)
        gaps = cardpolicy.evaluate(policy, self.neutral(card, policy), "audit")
        return {
            "ref": card.ref,
            "title": card.title,
            "assignee": self.tracker.display_name(card.assignee) if card.assignee else None,
            "writable": self.writable(card),
            "gaps": gaps,
        }


def _draft_text(ref: str, add: list[str], remove: list[str]) -> str:
    lines = ['op = "edit"', f"key = {json.dumps(ref)}", f"add_labels = {json.dumps(add)}"]
    if remove:
        lines.append(f"remove_labels = {json.dumps(remove)}")
    return "+++\n" + "\n".join(lines) + "\n+++\n"


def _computed_labels(
    policy: cardpolicy.Policy, card: Card, gaps: list[dict]
) -> tuple[list[str], list[str]]:
    """The labels the computed fixes add, and the ones of the same group they replace."""
    add: list[str] = []
    remove: list[str] = []
    for gap in gaps:
        value = gap["fix"].get("value")
        found = CATEGORY_RULE.fullmatch(gap["rule"])
        if value is None or not found:
            continue
        group = policy.data.get("categories", {}).get(found.group(1), {}).get("values", [])
        add.append(value)
        remove += [label for label in card.labels if label in group and label != value]
    return list(dict.fromkeys(add)), list(dict.fromkeys(remove))


def check_folder(argument: str) -> Path:
    """The folder drafts go to: new or empty, and under `cards/drafts` so a preview can read it."""
    folder = Path(argument).expanduser()
    root = (data_dir() / "cards" / "drafts").resolve()
    if folder.is_symlink() or not folder.resolve().is_relative_to(root) or folder.resolve() == root:
        raise Refused(f"{argument} is not a folder inside {root}", 1)
    if folder.exists() and not folder.is_dir():
        raise Refused(f"{argument} exists and is not a folder", 1)
    if folder.is_dir() and any(folder.iterdir()):
        raise Refused(f"{argument} is not empty; use a new folder", 1)
    return folder.resolve()


def _write_private(path: Path, text: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)


def write_drafts(
    folder: Path, auditor: Auditor, found: list[tuple[Card, dict]], display: str
) -> dict:
    """One `edit` draft per writable card with a computed fix; the rest is listed, not drafted."""
    approval.ensure_store(folder.parent)
    approval.ensure_store(folder)
    count = 0
    need_input = []
    not_writable = []
    for card, entry in found:
        if not entry["gaps"]:
            continue
        if not entry["writable"]:
            not_writable.append(card.ref)
            continue
        add, remove = _computed_labels(auditor.policy(card), card, entry["gaps"])
        if add:
            _write_private(folder / f"{card.ref}.md", _draft_text(card.ref, add, remove))
            count += 1
        need_input += [
            {
                "ref": card.ref,
                "rule": gap["rule"],
                "field": gap["field"],
                "detail": gap["detail"],
            }
            for gap in entry["gaps"]
            if gap["fix"].get("needs") == "input"
        ]
    return {
        "folder": display,
        "count": count,
        "need_input": need_input,
        "not_writable": not_writable,
    }


def _accounts(people: People, own_account: str, who: list[str]) -> tuple[str, ...]:
    accounts = []
    for item in who:
        if item != "me" and (problem := people.problem(item)):
            raise Refused(problem, SETUP)
        account = own_account if item == "me" else people.account(item)
        if account and account not in accounts:
            accounts.append(account)
    return tuple(accounts)


def _select(tracker: Tracker, config: userconfig.UserConfig, sprint, who, keys) -> list[Card]:
    if keys:
        cards = []
        for ref in keys:
            found = tracker.card(ref)
            if found is None:
                raise Refused(f"card {ref} is not in the configured project", 1)
            cards.append(found)
        return cards
    people = People.from_config(config, tracker.me())
    accounts = _accounts(people, tracker.me(), who)
    return tracker.cards(CardQuery(sprint=sprint, assignees=accounts, open_only=False))


def _arguments(sprint: str | None, who: list[str] | None, keys: str | None):
    if keys is not None:
        if sprint is not None or who:
            raise Refused("--keys replaces --sprint and --who; use one or the other", 1)
        refs = list(dict.fromkeys(ref.strip() for ref in keys.split(",") if ref.strip()))
        bad = [ref for ref in refs if not REF.fullmatch(ref)]
        if not refs or bad:
            raise Refused(f"--keys needs card refs like TS-123, got {', '.join(bad) or keys!r}", 1)
        return None, [], refs
    people = who or ["me"]
    bad = [item for item in people if not WHO.fullmatch(item)]
    if bad:
        raise Refused(f"--who takes me or a dev id (dev- and 10 hex), got {', '.join(bad)}", 1)
    return sprint or "active", people, []


def report(auditor: Auditor, cards: list[Card]) -> tuple[dict, list[tuple[Card, dict]]]:
    found = [
        (card, auditor.audit(card))
        for card in sorted(cards, key=lambda item: _ref_order(item.ref))
        if card.status != Status.CANCELLED and card.level == 0
    ]
    by_rule: dict[str, int] = {}
    for _, entry in found:
        for gap in entry["gaps"]:
            by_rule[gap["rule"]] = by_rule.get(gap["rule"], 0) + 1
    document = {
        "$schema": "card-audit",
        "version": 1,
        "cards": [entry for _, entry in found],
        "summary": {
            "cards": len(found),
            "with_gaps": sum(1 for _, entry in found if entry["gaps"]),
            "by_rule": dict(sorted(by_rule.items())),
        },
    }
    return document, found


def run(
    sprint: str | None = None,
    who: list[str] | None = None,
    keys: str | None = None,
    drafts: str | None = None,
) -> int:
    try:
        sprint, who, refs = _arguments(sprint, who, keys)
        folder = check_folder(drafts) if drafts is not None else None
        config = userconfig.load_config()
        tracker = port.open_tracker()
        auditor = Auditor(tracker, config, repo_root())
        cards = _select(tracker, config, sprint, who, refs)
        document, found = report(auditor, cards)
        if folder is not None:
            document["drafts"] = write_drafts(folder, auditor, found, drafts)
    except Refused as error:
        print(f"ws card audit: {error}", file=sys.stderr)
        return error.code
    except (TrackerSetup, ConfigMissing, ConfigInvalid) as error:
        print(f"ws card audit: {error}", file=sys.stderr)
        return SETUP
    except TrackerError as error:
        print(f"ws card audit: {error}", file=sys.stderr)
        return TRACKER
    except (KeyError, TypeError, AttributeError) as error:
        print(f"ws card audit: unexpected answer from the tracker ({error!r})", file=sys.stderr)
        return TRACKER
    except OSError as error:
        print(f"ws card audit: file error: {error}", file=sys.stderr)
        return 1
    problems = validate(document, "card-audit")
    if problems:
        print(f"ws card audit: internal error: {'; '.join(problems)}", file=sys.stderr)
        return 1
    print(json.dumps(document, ensure_ascii=False, indent=2))
    return 0
