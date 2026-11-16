# Tracker write port: rulings and follow-ups

Decisions made on the user's behalf while building the neutral tracker port (plan
`docs/plans/2026-11-15-tracker-write-port.md`, spec
`docs/specs/2026-11-15-tracker-write-port-design.md`), each with what it costs if wrong, and the
items left for later. Source: the execution log, deleted after the merge.

## User decisions (16/11)

- Only cards where the user is the assignee or the reporter are written, also for sprint and due
  date changes.
- The daily keeps a fallback through the MCP of the tracker chosen in the config (read only), with
  neutral words in the skill and the vendor calls in `references/<kind>.md`. This became a general
  rule in the root `CLAUDE.md`: reads go through `ws` first and fall back to the configured
  provider's MCP; writes never go through an MCP.
- `/card` manages sprints in any way (`active`, `next`, `backlog`, a sprint name), always behind
  the preview and the approval box (Task 19).

## Rulings

- The contract test of the schema folder names its schemas instead of counting them, and
  `card-write` is one flat closed schema with the per-operation rules in code, because the
  contract validator has no `oneOf`. Cost if wrong: none.
- `check_document` validates dates, so a draft that passes the check always loads. Cost: a few
  lines.
- Stage A kept the old messages for two odd drafts (a blank comment, a move with a body) even
  where the new contract also refuses them, because Stage A changes nothing the user sees. Cost:
  two edge drafts show the old message.
- The core refuses an unparsed draft even if a future adapter forgets to, and the apply checks
  that every step got its own result. Cost: none.
- Opening the tracker needs only the connection settings; each read asks for the keys it uses,
  with each command's old messages and exit codes; `ws people add` keeps its "found N accounts"
  line. Cost: a small adapter rework.
- An unknown tracker kind exits 2 with a clear message in every command, instead of silently
  reading the Jira settings. Cost: a typo in `kind` shows exit 2 instead of a listing.
- A config with no tracker table still loads; only using the tracker fails, naming
  `[tracker] kind`, so commands without a tracker keep working. Cost: the error shows at first
  use instead of at load.
- The contract tests also cover uncertain results and the guard on the memory tracker, and the
  memory tracker treats an unknown card like a 404. Cost: none.
- Sprint management was built in the port branch, not on main, to avoid writing it twice. Two old
  tests that pinned "only the active sprint" became tests of the new behaviour. Cost: the feature
  reached main only with the branch.
- The branch suite ran after each wave merge, after a fixture drift slipped through one merge.
- The board names the table to fix from the configured kind (`[tracker.<kind>.status_overrides]`).
  Cost: none.
- The release reads only the tracker link (kind and site), not the whole config, so an unrelated
  section can never break a release. Cost: one small helper.
- A `.md` draft and its `.json` twin produce the same requests; their approval codes differ only
  by the file name shown in the preview, which the code covers. Cost: none.
- Removing the old module paths changed the tests that imported them; two tests that only checked
  those paths were deleted. Cost: none.
- One fix wave closed the final review: `.json` drafts follow every draft rule, an order-dependent
  test was fixed, provider names left the help texts, the daily fallback reads the right table,
  and the branch was merged with main (three conflicts, both sides kept).

## Parked (next tracker card)

- A `.json` create with a padded `" backlog "` sprint passes the check; harmless, since no sprint
  is sent for the backlog.
- The provider-word test exempts all of `load_config`; move the old-table fallback into its own
  helper and narrow the exemption.
- Some messages (`rules.py`, `adapter.py`) still name `[tracker.jira]` for a user who still has
  the old `[jira]` table.
- How Jira answers `sprint = null` on a card that also lists closed sprints is confirmed on the
  first real use.

## Deferred (small follow-ups)

- Scanner gaps in the boundary test (`from importlib import import_module`, a relative module
  string); the neutral module list is fixed instead of globbed.
- `run_check` parses a `.json` twice; deeply nested JSON raises `RecursionError`; duplicate JSON
  keys keep the last.
- The `resolved` side channel and `epics()` sit outside the `Writer` protocol.
- Minor test and annotation nits recorded per task (fixtures shared across test modules, a few
  untested branches).
