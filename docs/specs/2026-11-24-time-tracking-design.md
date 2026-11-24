# Time spent from real hours

Status: approved by the user on 2026-11-24.

## Problem

The company's card standard asks for the time actually spent on each card when it is done, and
an original estimate. The user works at least 8h48 per working day on planned cards (44 h a week;
holidays do not count), intruder cards come on top, and the days are often longer. Several cards
move at the same time, with parallel chats and agents. Numbers made up from the plan or guessed
from "days on the card" in git came out wrong (one card guessed at 43h30 took about 13 h), and an
estimate padded on a card that had no plan made a 30-minute card look like a 1-hour plan. The user
wants real hours.

## Rules (the user's, 2026-11-24)

1. Time spent comes only from evidence: hours marked during the work, the activity the session
   hook records, commits, or the user's word. Never from a plan.
2. A card with a plan made before the work has original estimate = plan + the policy's padding.
   A card without a plan (an intruder, a card opened after the work) has original estimate = the
   real time spent, without padding.
3. Time spent is logged when the card is done, for the whole period it was worked, one worklog per
   day on the right date.
4. Inside one day, the hours not covered by marked or hook intervals are split among the planned
   cards touched that day by their share of the day's commits; the day closes at no less than the
   floor (8h48, `[time] day_floor`). Intruders are counted apart and never fill the floor.
5. A day without commits takes its cards from the workspace commits on items that name a card
   (`projects/*/tasks/*.md` with `card = "…"`) and from the cards in progress that day; what is left
   is listed as "no evidence" for the user.

## Storage

`~/.local/share/workspace/timelog/<YYYY-MM>.jsonl`, private (0600), append-only, outside the repo.
One JSON object per line:

```json
{"v": 1, "event": "start", "card": "TS-1", "at": "2026-11-24T14:05:00-03:00", "source": "manual"}
{"v": 1, "event": "stop", "card": "TS-1", "at": "2026-11-24T16:40:00-03:00", "source": "manual"}
{"v": 1, "event": "activity", "card": "TS-1", "at": "2026-11-24T15:12:09-03:00", "source": "hook", "repo": "acme-api", "branch": "feature/TS-1-x"}
```

`card` is null on an activity outside a card branch. Times carry the local offset.

## Commands

- `ws time start REF [--at HH:MM]`: opens an interval for the card (now, or today at the given
  time). Several cards may be open at once. Starting a card already open is a no-op with a note.
- `ws time stop [REF] [--at HH:MM]`: closes the card's open interval; without REF, closes all.
- `ws time status`: open intervals and today's minutes per card, JSON.
- `ws time report (--card REF | --from DATE --to DATE | --week YYYY-Www) [--drafts DIR]
  [--unplanned]`: per day and per card, JSON (contract `time-report` v1):
  `days: [{date, workday, floor_minutes, planned_minutes, intruder_minutes, below_floor,
  cards: [{ref, minutes, sources: {marked, hook, commits, filled}}], no_evidence_minutes}]`,
  `cards: [{ref, total_minutes, logged_minutes, to_log_minutes}]`.
  - Marked intervals first; then hook intervals (activity on the same card with gaps of at most
    `[time] idle_minutes`, default 30, makes one interval; only where no marked interval covers);
    overlapping intervals of different cards split the overlap by their commit share in that
    window, equally without commits; then the floor fill of rule 4; then rule 5.
  - Worklogs already in the tracker for the card and day are subtracted (never logged twice).
  - `--drafts DIR` (with `--card`): one `worklog` draft per day with time to log (`day`, `time`),
    and with `--unplanned` an `edit` draft with `estimate` = the card's total real time (rule 2).
    A card carrying a label the policy lists as unplanned (the intruder labels) is unplanned
    without the flag. Never writes to the tracker: the drafts go through `ws card preview` and the
    approval box.
- Commits: every repo under the configured repos root, author = that repo's `user.email`, all
  branches, card ref from the message or the branch name (as `ws standup collect` does).

## Session hook

`hooks/time_activity.py` on `UserPromptSubmit`: appends one `activity` event with the time, the
repo and branch of the session's working directory and the card ref from the branch name. It never
blocks, never prints, and fails silent. Registered by `ws setup` like the other session hooks.

## Skill and chats

- `/card iniciar` runs `ws time start REF` after the start is applied; moving a card to done runs
  `ws time report --card REF --drafts …` and puts the worklogs (and the unplanned estimate) in the
  same preview.
- In any chat on a card, the model runs `ws time start` when work on the card begins and
  `ws time stop` when it stops or switches card (the hook covers what is missed).

## Out of scope

Logging during the week (only at done, rule 3); other people's time (only the user's own commits
and marks).
