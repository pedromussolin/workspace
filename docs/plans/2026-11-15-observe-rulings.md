# ws observe: rulings and follow-ups

Decisions made on the user's behalf while building the post-deploy observation plan (plan
`docs/plans/2026-11-15-observe.md`, spec `docs/specs/2026-11-15-observe-design.md`), each with
what it costs if wrong, and the small items left for later. Source: the execution log, deleted
after the merge.

## User decisions

- The AI may use the observe skill by itself, but every query on the production replica asks the
  user first, through the approval box on `ws observe run` (15/11). This replaced the first ruling,
  which had set `disable-model-invocation: true` on the skill.

## Rulings

- The metrics fallback uses the observability tool's scalar format with an aggregator, the same
  request as the bundled program, departing from the brief, so the model never sums by hand. Cost
  if wrong: one changed fallback shape.
- The database guard is stricter than the brief (it refuses `$`, backslash, `query_to_`,
  `cursor_to_`, `table_to_`, `brin_` and more): refusing more is the safe side for SQL on the
  production replica. Cost if wrong: a legitimate query must be rewritten.
- `ws observe report` takes the task title from the tracker port, as the spec says. The plan line
  "never reads the pgpass file nor the credentials file" means the observe modules never open
  those files; the tracker port reading its own token is the path `ws task list` already uses, and
  a tracker failure only drops the title. Cost if wrong: remove the title lookup.
- The `observe-result` and `observe-status` contracts changed in Task 6 (window as a list of
  strings, `by` optional; status has `first_day` instead of `switched_off`) to match the code that
  writes them. Nothing written earlier breaks. The plan text (lines 98-105) is stale on this.
- Small fixes before merging Task 6: a non-finite or negative `--result` count is refused; the
  tool's failure reason becomes a fixed text; today is computed in the plan's time zone; the result
  file is read without following a link and is set to 600 only under the plan folder, after it
  parses; `request` honours the `--check` subset.
- Task 7 round 1 also fixed the "observability is null" wording, the README exit 2 precision and
  the README flags, since they decide which command the AI runs.
- One fix wave after the final review carried all four important findings and all the minor ones,
  including `ws observe close`, so the first plan that reaches `done` (about 15/12) has a way out.
  Cost if wrong: one small subcommand and one optional plan field.
- The guard's column hint goes only to a word of the engine list that is not a call (never to a
  prefix or a statement keyword), and every quoted identifier is now checked against the refused
  prefixes in any position: `from "pg_stat_activity"` passed the guard, and the old hint even
  suggested the quotes. Verified on a throwaway local database. Cost if wrong: a business column
  whose name starts with a refused prefix cannot be read.

## Before the first real use

- Run `ws setup` by hand: it installs the ask rule and the gate box for `ws observe run`, and links
  the skill.
- Before 08/12, the user runs one real count per signal (traces, logs, metrics) through the
  observability tool, to confirm the response shapes (the bundled program now fails loudly on a
  bucket without a number, and on a response with no bucket list).

## Deferred (follow-ups)

- `ws observe new` prints its JSON without `version`.
- The gate box could show "changed since the last approved run" by comparing the plan's check hash
  with the last row's hash.
- A business column whose name starts with a refused prefix (`pg_` as a short form of "pagamento")
  cannot be read at all: say so in the skill or the README.
- The connect timeout applies once per address of the host name; a host with two addresses could
  reach the subprocess timeout.
- An `OSError` from writing a row or opening the lock file ends in a traceback.
- `MAX_DAYS` is defined twice; `project` is unused in `record_result` and `record_one`;
  `observe_cli.py` mixes argument wiring and orchestration; a test module imports helpers from
  another test module.
- `ws.contracts` re-checks the schema on every call; some malformed schemas raise `TypeError`
  instead of a problem; the list form of `items` is not supported.
- The skill test splits the front matter by hand; no test pins the daily keys or the rule that
  `run` goes in its own call.
- A plan with no database check still asks in the box (safe side); a script file that runs
  `ws observe run` is not seen by the box (the same limit as `ws card apply`).
