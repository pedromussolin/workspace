"""`ws time report`: the hours worked per day and per card, from evidence only.

Evidence is, in this order: the marked intervals, the session activity where no mark covers, the
commits (who shares an overlap, and who shares the rest of a working day), and the workspace
commits on items that name a card. The day closes at no less than the floor among the planned
cards; intruders count apart. What the tracker already holds is subtracted. It never writes to the
tracker: `--drafts` writes drafts that go through `ws card preview` and the approval box.
Design: docs/specs/2026-11-24-time-tracking-design.md.
"""

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from ws import approval, cardaudit, cardpolicy, itemfile, standup, timelog, userconfig, workdays
from ws.config import repo_root
from ws.contracts import validate
from ws.timelog import REF, Interval, TimeRefused
from ws.tracker import port
from ws.tracker.port import Card, Tracker, TrackerError, TrackerSetup
from ws.userconfig import ConfigInvalid, ConfigMissing

SETUP = 2
TRACKER = 3
STEP = 30
WEEK = re.compile(r"(\d{4})-W(\d{2})")
ITEM_PATHSPEC = ":(glob)projects/*/tasks/*.md"
MAX_LISTED = 10


@dataclass(frozen=True)
class Request:
    card: str | None
    first: date | None
    last: date | None
    drafts: str | None
    unplanned: bool


def _iso(text: str, flag: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise TimeRefused(f"{flag} must be a date like 2026-11-24, got {text!r}") from None


def make_request(
    card: str | None,
    from_: str | None,
    to: str | None,
    week: str | None,
    drafts: str | None,
    unplanned: bool,
) -> Request:
    modes = [card is not None, from_ is not None or to is not None, week is not None]
    if sum(modes) != 1:
        raise TimeRefused("use one of --card, --from with --to, or --week")
    if (drafts is not None or unplanned) and card is None:
        raise TimeRefused("--drafts and --unplanned need --card")
    if card is not None:
        if not REF.fullmatch(card):
            raise TimeRefused(f"{card!r} is not a card ref like TS-123")
        return Request(card, None, None, drafts, unplanned)
    if week is not None:
        found = WEEK.fullmatch(week)
        if not found:
            raise TimeRefused(f"--week must look like 2026-W48, got {week!r}")
        try:
            first = date.fromisocalendar(int(found.group(1)), int(found.group(2)), 1)
        except ValueError:
            raise TimeRefused(f"{week} is not a week of that year") from None
        return Request(None, first, first + timedelta(days=6), None, False)
    if from_ is None or to is None:
        raise TimeRefused("--from and --to go together")
    first, last = _iso(from_, "--from"), _iso(to, "--to")
    if last < first:
        raise TimeRefused("--from is after --to")
    return Request(None, first, last, None, False)


def _ref_order(ref: str) -> tuple:
    prefix, _, number = ref.rpartition("-")
    return (prefix, int(number) if number.isdigit() else 0)


def duration_text(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    return " ".join(
        part for part in (f"{hours}h" if hours else "", f"{rest}m" if rest else "") if part
    )


def _local(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp).astimezone()


def _points(raw: list[dict], first: date, last: date) -> list[tuple[datetime, str]]:
    """One `(moment, card)` per card key of each commit that falls in the days."""
    found = []
    for item in raw:
        at = _local(item["at"])
        if first <= at.date() <= last:
            found.extend((at, key) for key in item["keys"])
    return found


def _item_commits(
    cfg: userconfig.StandupConfig, first: date, last: date, warnings: list[str]
) -> list[tuple[datetime, str]]:
    """The workspace commits that touch an item file naming a card, one point per card."""
    root = repo_root()
    try:
        email = standup.author_email(root)
        if email is None:
            warnings.append("workspace: git user.email is not set, item commits left out")
            return []
        out = standup._git(
            root,
            "log",
            "--exclude=refs/stash",
            "--all",
            "--no-merges",
            "--name-only",
            f"--since={(first - timedelta(days=1)).isoformat()} 00:00:00",
            f"--until={(last + timedelta(days=1)).isoformat()} 23:59:59",
            f"--author=<{email}>",
            "--fixed-strings",
            f"--format=@@%H{standup.FIELD_SEPARATOR}%aI",
            "--",
            ITEM_PATHSPEC,
        )
    except (RuntimeError, OSError) as error:
        warnings.append(f"workspace: item commits left out ({error})")
        return []
    cards: dict[str, str | None] = {}
    found: dict[tuple[str, str], datetime] = {}
    for line in standup._lines(out):
        if line.startswith("@@"):
            sha, stamp = line[2:].split(standup.FIELD_SEPARATOR, 1)
            at = _local(stamp)
            continue
        if line not in cards:
            try:
                item = itemfile.read_item(root / line)
                cards[line] = item.card if item else None
            except (itemfile.ItemError, OSError):
                cards[line] = None
        if cards[line] and first <= at.date() <= last:
            found[(sha, cards[line])] = at
    return [(at, ref) for (_, ref), at in found.items()]


def _resolve(tracker: Tracker, refs: set[str], warnings: list[str]) -> dict[str, Card]:
    """The cards of the tracker for each ref; one it does not have (another project, or text
    that only looks like a key) is left out of the report."""
    found: dict[str, Card] = {}
    missing = []
    for ref in sorted(refs, key=_ref_order):
        card = tracker.card(ref)
        if card is None:
            missing.append(ref)
        else:
            found[ref] = card
    if missing:
        listed = ", ".join(missing[:MAX_LISTED]) + (", ..." if len(missing) > MAX_LISTED else "")
        warnings.append(
            f"{len(missing)} refs are not cards of the configured project, left out: {listed}"
        )
    return found


def _unplanned(config: object, cards: dict[str, Card]) -> set[str]:
    """The cards that carry a label the card policy of their project lists as unplanned."""
    policies: dict[str | None, cardpolicy.Policy] = {}
    out = set()
    for ref, card in cards.items():
        project = cardpolicy.project_for(None, card.parent, repo_root())
        if project not in policies:
            policies[project] = cardpolicy.load(config, project, repo_root())
        if set(card.labels) & cardpolicy.unplanned_labels(policies[project]):
            out.add(ref)
    return out


def split_day(
    day: date, intervals: list[Interval], commits: dict[str, list[datetime]]
) -> dict[str, dict[str, float]]:
    """Minutes per card and source (`marked`, `hook`) inside one day.

    Where intervals of different cards overlap, the overlap is split by the commits each card
    has inside it (equally when there is none). A card with an interval of no length is still
    listed: it was touched."""
    clipped = [part for item in intervals if (part := timelog.clip(item, day)) is not None]
    out: dict[str, dict[str, float]] = {}
    for part in clipped:
        out.setdefault(part.card, {"marked": 0.0, "hook": 0.0})
    pieces = [part for part in clipped if part.end > part.start]
    points = sorted({stamp for part in pieces for stamp in (part.start, part.end)})
    windows: list[list] = []
    for begin, end in zip(points, points[1:], strict=False):
        active = [part for part in pieces if part.start <= begin and part.end >= end]
        if not active:
            continue
        cards = frozenset(part.card for part in active)
        source = "marked" if any(part.source == "marked" for part in active) else "hook"
        if windows and windows[-1][1] == begin and windows[-1][2] == cards:
            windows[-1][1] = end
        else:
            windows.append([begin, end, cards, source])
    for begin, end, cards, source in windows:
        minutes = (end - begin).total_seconds() / 60
        weights = {
            card: sum(1 for stamp in commits.get(card, []) if begin <= stamp < end)
            for card in cards
        }
        total = sum(weights.values())
        for card in cards:
            share = weights[card] / total if total else 1 / len(cards)
            out[card][source] += minutes * share
    return out


def _distribute(need: int, weights: dict[str, int]) -> dict[str, int]:
    """`need` minutes in steps of 30 by weight, every weighted card with at least one step when
    there are enough; what is left under a step goes to the heaviest card, so the sum is exact."""
    order = sorted(weights, key=lambda ref: (-weights[ref], _ref_order(ref)))
    units, rest = divmod(need, STEP)
    shares = dict.fromkeys(order, 0)
    if units >= len(order):
        spare = units - len(order)
        total = sum(weights.values())
        remainders = {}
        for ref in order:
            whole, remainder = divmod(spare * weights[ref], total)
            shares[ref] = 1 + whole
            remainders[ref] = remainder
        left = units - sum(shares.values())
        for ref in sorted(order, key=lambda r: -remainders[r])[:left]:
            shares[ref] += 1
    else:
        for ref in order[:units]:
            shares[ref] = 1
    minutes = {ref: shares[ref] * STEP for ref in order}
    minutes[order[0]] += rest
    return {ref: value for ref, value in minutes.items() if value > 0}


def close_day(
    base: dict[str, dict[str, float]],
    unplanned: set[str],
    commits: dict[str, int],
    items: dict[str, int],
    floor: int,
    closed: bool,
) -> tuple[dict[str, dict[str, int]], int, bool]:
    """The rows of a day (`marked`, `hook`, `commits`, `filled` per card), the minutes with no
    evidence, and whether the fallback of rule 5 had to be used.

    A closed working day is filled up to `floor` among the planned cards: by their commits of
    the day; without any, by the workspace commits on items; without those, equally among the
    planned cards the day touched. Intruders never fill it. A card with commits and no minutes
    at all gets 30."""
    rows = {
        ref: {
            "marked": round(value["marked"]),
            "hook": round(value["hook"]),
            "commits": 0,
            "filled": 0,
        }
        for ref, value in base.items()
    }
    for ref in commits:
        rows.setdefault(ref, {"marked": 0, "hook": 0, "commits": 0, "filled": 0})
    planned = [ref for ref in rows if ref not in unplanned]
    need = floor - sum(rows[ref]["marked"] + rows[ref]["hook"] for ref in planned) if closed else 0
    fallback = False
    missing = 0
    if need > 0:
        weights = {ref: commits[ref] for ref in planned if commits.get(ref)}
        if not weights:
            fallback = True
            weights = {ref: count for ref, count in items.items() if ref not in unplanned}
        if not weights:
            weights = dict.fromkeys(planned, 1)
        if weights:
            for ref, minutes in _distribute(need, weights).items():
                rows.setdefault(ref, {"marked": 0, "hook": 0, "commits": 0, "filled": 0})
                rows[ref]["filled"] = minutes
        missing = need - sum(row["filled"] for row in rows.values())
    for ref, row in rows.items():
        if commits.get(ref) and sum(row.values()) == 0:
            row["commits"] = STEP
    return rows, max(missing, 0), fallback


@dataclass
class Evidence:
    intervals: list[Interval]
    commits: list[tuple[datetime, str]]
    items: list[tuple[datetime, str]]


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=n) for n in range((last - first).days + 1)]


def _compute(
    days: list[date],
    evidence: Evidence,
    unplanned: set[str],
    floor: int,
    extra: frozenset[date],
    today: date,
    warnings: list[str],
) -> list[dict]:
    by_day_intervals: dict[date, list[Interval]] = defaultdict(list)
    for item in evidence.intervals:
        for day in _days(item.start.date(), item.end.date()):
            by_day_intervals[day].append(item)
    commit_times: dict[date, dict[str, list[datetime]]] = defaultdict(lambda: defaultdict(list))
    for at, ref in evidence.commits:
        commit_times[at.date()][ref].append(at)
    item_counts: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for at, ref in evidence.items:
        item_counts[at.date()][ref] += 1
    out = []
    fallback_used = False
    for day in days:
        workday = workdays.is_business_day(day, extra)
        closed = day < today
        times = commit_times.get(day, {})
        base = split_day(day, by_day_intervals.get(day, []), times)
        rows, missing, fallback = close_day(
            base,
            unplanned,
            {ref: len(stamps) for ref, stamps in times.items()},
            dict(item_counts.get(day, {})),
            floor if workday else 0,
            closed,
        )
        fallback_used = fallback_used or fallback
        if not rows and not (workday and closed):
            continue
        planned_minutes = sum(
            sum(row.values()) for ref, row in rows.items() if ref not in unplanned
        )
        intruder_minutes = sum(sum(row.values()) for ref, row in rows.items() if ref in unplanned)
        out.append(
            {
                "date": day.isoformat(),
                "workday": workday,
                "closed": closed,
                "floor_minutes": floor if workday else 0,
                "planned_minutes": planned_minutes,
                "intruder_minutes": intruder_minutes,
                "below_floor": workday and closed and planned_minutes < floor,
                "cards": [
                    {
                        "ref": ref,
                        "unplanned": ref in unplanned,
                        "minutes": sum(row.values()),
                        "sources": dict(row),
                        "logged_minutes": 0,
                        "to_log_minutes": sum(row.values()),
                    }
                    for ref, row in sorted(rows.items(), key=lambda pair: _ref_order(pair[0]))
                    if sum(row.values()) > 0
                ],
                "no_evidence_minutes": missing,
            }
        )
    if fallback_used:
        warnings.append(
            "the tracker gives no status history, so the cards in progress on a day without "
            "commits were not used (rule 5); only workspace item commits and the cards the day "
            "touched were"
        )
    return out


def _subtract_logged(
    days: list[dict], tracker: Tracker, config_me: str, refs: set[str], warnings: list[str]
) -> None:
    """Take from each card and day what the user already logged in the tracker (never twice)."""
    if "worklog" not in tracker.capabilities:
        warnings.append("the tracker has no worklog read: nothing was subtracted")
        return
    logged: dict[tuple[str, str], int] = defaultdict(int)
    for ref in sorted(refs, key=_ref_order):
        for entry in tracker.worklogs(ref):
            if entry.author == config_me:
                logged[(ref, entry.day.isoformat())] += entry.minutes
    for day in days:
        for row in day["cards"]:
            done = logged.get((row["ref"], day["date"]), 0)
            row["logged_minutes"] = done
            row["to_log_minutes"] = max(0, row["minutes"] - done)


def build(request: Request, config: userconfig.UserConfig, tracker: Tracker, now: datetime) -> dict:
    today = now.date()
    warnings: list[str] = []
    extra = workdays.extra_holidays()
    if request.card:
        card_row = tracker.card(request.card)
        if card_row is None:
            raise TimeRefused(f"card {request.card} is not in the configured project")
        began = card_row.start or card_row.created
        if began is None:
            raise TimeRefused(f"{request.card} has no start or creation date; use --from and --to")
        first, last = began, today
    else:
        first, last = request.first, min(request.last, today)
        if request.last > today:
            warnings.append(f"days after today ({today.isoformat()}) were left out")
    days = _days(first, last) if last >= first else []
    events, skipped = timelog.read(first, max(last, first))
    if skipped:
        warnings.append(f"{skipped} unreadable lines of the time log were skipped")
    intervals = timelog.evidence(events, config.time.idle_minutes, now, warnings)
    raw = standup.collect_timed(config.standup, repo_root(), first, max(last, first), warnings)
    commits = _points(raw, first, last)
    bare = sum(1 for item in raw if not item["keys"])
    if bare:
        warnings.append(f"{bare} commits name no card and were left out")
    items = _item_commits(config.standup, first, last, warnings)
    refs = {item.card for item in intervals} | {ref for _, ref in commits}
    refs |= {ref for _, ref in items} | ({request.card} if request.card else set())
    cards = _resolve(tracker, refs, warnings)
    unplanned = _unplanned(config, cards)
    kept = Evidence(
        [item for item in intervals if item.card in cards],
        [point for point in commits if point[1] in cards],
        [point for point in items if point[1] in cards],
    )
    rows = _compute(days, kept, unplanned, config.time.day_floor_minutes, extra, today, warnings)
    if request.card:
        worked = [
            day["date"] for day in rows if any(r["ref"] == request.card for r in day["cards"])
        ]
        if not worked:
            raise TimeRefused(f"no evidence of work on {request.card} up to {today.isoformat()}")
        rows = [day for day in rows if worked[0] <= day["date"] <= worked[-1]]
    wanted = {request.card} if request.card else {r["ref"] for day in rows for r in day["cards"]}
    _subtract_logged(rows, tracker, tracker.me(), wanted, warnings)
    summary = []
    for ref in sorted(wanted, key=_ref_order):
        mine = [r for day in rows for r in day["cards"] if r["ref"] == ref]
        summary.append(
            {
                "ref": ref,
                "unplanned": ref in unplanned or (ref == request.card and request.unplanned),
                "total_minutes": sum(r["minutes"] for r in mine),
                "logged_minutes": sum(r["logged_minutes"] for r in mine),
                "to_log_minutes": sum(r["to_log_minutes"] for r in mine),
            }
        )
    if request.card:
        for day in rows:
            day["cards"] = [r for r in day["cards"] if r["ref"] == request.card]
            for found in day["cards"]:
                found["unplanned"] = summary[0]["unplanned"]
    return {
        "$schema": "time-report",
        "version": 1,
        "window": {
            "from": rows[0]["date"] if rows else first.isoformat(),
            "to": rows[-1]["date"] if rows else last.isoformat(),
        },
        "days": rows,
        "cards": summary,
        "warnings": warnings,
    }


def write_drafts(folder: Path, display: str, request: Request, document: dict) -> dict:
    """One `worklog` draft per day with minutes to log, and the `estimate` draft of an unplanned
    card (its estimate is its real time, with no padding)."""
    approval.ensure_store(folder.parent)
    approval.ensure_store(folder)
    ref = request.card
    summary = document["cards"][0]
    files = []
    for day in document["days"]:
        minutes = day["cards"][0]["to_log_minutes"] if day["cards"] else 0
        if minutes <= 0:
            continue
        name = f"{ref}-worklog-{day['date']}.md"
        text = (
            f'+++\nop = "worklog"\nkey = {json.dumps(ref)}\n'
            f"time = {json.dumps(duration_text(minutes))}\nday = {day['date']}\n+++\n"
        )
        cardaudit.write_private(folder / name, text)
        files.append(name)
    if (request.unplanned or summary["unplanned"]) and summary["total_minutes"] > 0:
        name = f"{ref}-estimate.md"
        text = (
            f'+++\nop = "edit"\nkey = {json.dumps(ref)}\n'
            f"estimate = {json.dumps(duration_text(summary['total_minutes']))}\n+++\n"
        )
        cardaudit.write_private(folder / name, text)
        files.append(name)
    return {"folder": display, "count": len(files), "files": files}


def _now() -> datetime:
    return timelog._now()


def run(
    card: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    week: str | None = None,
    drafts: str | None = None,
    unplanned: bool = False,
) -> int:
    try:
        request = make_request(card, from_, to, week, drafts, unplanned)
        folder = cardaudit.check_folder(drafts) if drafts is not None else None
        config = userconfig.load_config()
        tracker = port.open_tracker()
        document = build(request, config, tracker, _now())
        if folder is not None:
            document["drafts"] = write_drafts(folder, drafts, request, document)
    except (TimeRefused, cardaudit.Refused) as error:
        print(f"ws time report: {error}", file=sys.stderr)
        return error.code
    except (TrackerSetup, ConfigMissing, ConfigInvalid) as error:
        print(f"ws time report: {error}", file=sys.stderr)
        return SETUP
    except TrackerError as error:
        print(f"ws time report: {error}", file=sys.stderr)
        return TRACKER
    except (KeyError, TypeError, AttributeError) as error:
        print(
            f"ws time report: unexpected answer from the tracker ({error!r})",
            file=sys.stderr,
        )
        return TRACKER
    except (OSError, RuntimeError) as error:
        print(f"ws time report: {error}", file=sys.stderr)
        return 1
    problems = validate(document, "time-report")
    if problems:
        print(f"ws time report: internal error: {'; '.join(problems)}", file=sys.stderr)
        return 1
    print(json.dumps(document, ensure_ascii=False, indent=2))
    return 0
