# `ws observe`: design

Date: 2026-11-15. Status: approved by the user. Plan: `docs/plans/2026-11-15-observe.md`.

## Intent

The legacy VM's jobs are switched off one by one (`projects/vm-migration/estimate.md`); each is
gone only after N business days (usually 5) of daily checks (no trace of the sweep, no stuck open
batch, file and database matching, zero calls of a route), done by hand today, with GMUD times
rebuilt later. From 08/12 on. All but the judgement is `ws` code; the skill decides, asks, writes.

## Goals, non-goals, anti-goals

- **Goals.** A plan per task; a daily run records each value with real times; `status` (day k of
  N, pending, streak, "pode desligar de vez", "atenção"); a PT-BR GMUD `report`; a daily line.
- **Non-goals.** Switching jobs; alerts; checks beyond one number or a yes/no. **Anti-goals.** No
  write to the database, observability tool or task tracker; no row, log line or customer value in
  any output; no automatic switch-off or reset; no plan or result in the repo; no provider name
  outside adapters.

## Approaches

- **Database query: `ws` runs it (picked)**: guard, read-only session, timeout, one number and lock
  are tested code; no row reaches the chat; times are real. Printing the command for the model
  (rejected) makes the guard advice. **Timing: a run a day in the session (picked)**: the
  observability tool answers through the session's MCP (the user's OAuth), the database through
  the VPN and the user's access, manual checks need the user. A scheduled cloud agent (rejected)
  has none of it and would take company queries off the machine; a local cron cannot reach the MCP.

## Ports and adapters

| Port | Neutral interface | First adapter |
|---|---|---|
| task tracker | existing `ws.tracker.port.Tracker` (`card(ref)`: the title), `vocab.REF` | Jira |
| observability | `ws.observability.port.Observability`: `kind`, `tool`, `request(doc) -> str` (text the tool runs), `fallback(doc) -> list[dict]` | `datadog_adapter`: program for the MCP `execute_code` from `src/ws/data/datadog_count.js`, as `deploy_check.js` |
| database | `ws.database.port.Database`: `rules` (extra refusals), `scalar_text(sql, bounds, timeout) -> str`; `ws.database.scalar(...)`: guard, lock, one number | `postgres_adapter`: psql in Docker with the user's pgpass |

Adapters are found by module name (`<kind>_adapter`), opened from config (`[observability]
provider`, `[database.<name>] engine`). Neutral modules (`ws.observe*`, each `port.py`,
`ws.database.guard`, `ws.contracts`) import no adapter and name no provider (tested). Signals:
`traces`, `logs`, `metrics` (a count; for metrics, the sum over the window).

## Contracts

Each exchange is a JSON document with `"version": 1` and a schema in `src/ws/data/contracts/<name>
.schema.json`, checked by `ws.contracts` (stdlib, shared with the tracker work): `validate(document,
schema_name) -> list[str]` (`$.path: message`; empty when valid), `load_schema(name)`; subset
`type`, `required`, `properties`, `enum`, `items`, `additionalProperties: false`, `const` (dates
and patterns in code). `check`, `run` and `record` validate every document they read or send.

| Schema | Document |
|---|---|
| `observe-plan` | the plan; the TOML maps 1:1 (date → `"YYYY-MM-DD"`); `ws observe show TASK --json` |
| `observe-result`, `observe-status` | one results row; `status --json` (`version`, `today`, `plans`, `problems`) |
| `observability-request` | `task`, `day`, `counts[]` (`check`, `signal`, `query`, `from`, `to`, `hash`) |
| `observability-result` | `task`, `day`, `provider`, `counts[]` (`check`, `hash`, `value`, `started`, `finished`), `failed[]` (`check`, `reason`) |
| `database-request` / `-result` | `database`, `sql`, `bounds` (`day`, `day_from`, `day_to`), `timeout_seconds` / `database`, `value`, `started`, `finished` |

## The plan

`~/.local/share/workspace/projects/<slug>/observations/<TASK>.toml`, folders 700, file 600
(`WS_DATA_DIR` moves the root): it holds company queries and product ids.

```toml
version = 1
task = "TS-5738"
job = "fechamento de lotes"
switched_off = 2026-12-08   # day 1 is the next business day
days = 5                    # default; timezone defaults to "America/Sao_Paulo"
[[checks]]
id = "sweep-calls"          # [a-z0-9][a-z0-9-]*, unique, at most 40 characters
kind = "observability"      # observability | database | manual (question, no expect)
signal = "traces"           # traces | logs | metrics
query = "<query in the provider's language>"
expect = "== 0"             # "== 0" or "<= N"; label = "..." optional on every check
```

A database check has `database` (a `[database.<name>]` entry, default `replica`) and `sql` (`select
count(*) from <table> where <stuck> and updated_at < :day_to`); a manual one a `question` that yes
passes. `hash`: 12 hex digits of the SHA-256 of the check's canonical JSON without `id` and
`label`; a row with another hash is `stale`.

**Business days and windows.** `ws.workdays` gains holidays (fixed national, movable bank ones from the date of easter: carnaval
Monday and Tuesday, the Friday before easter, corpus christi; `[workdays] holidays`); old callers
keep their behaviour. Day k: the k-th business day after `switched_off`. Window of D: 00:00 of the
day after `max(previous business day of D, switched_off)` to 00:00 after D, local (a Monday covers
the weekend). Due day: the previous business day of today; `--day` must be one up to it.

## Commands (`ws observe ...`)

Help says "task", "task tracker", "observability tool", "database". TASK is `vocab.REF`; without
`--project` every project is searched (two matches: a problem).
- `new TASK --project SLUG --job TEXT --switched-off DATE [--days N] [--timezone TZ]`: header and
  commented examples (the skill fills `[[checks]]` with Edit); refuses an existing file. `check
  TASK`: contract, guard on each SQL, modes back to 700/600. `show TASK --json`.
- `run TASK [--day DATE] [--check ID]...`: database checks in order, recorded. JSON: `task`, `day`,
  `day_number`, `window`, `recorded`, `observability` (`tool`, `checks`, `next`, `result_path`),
  `ask` (manual questions), `problems`, `warnings`.
- `request TASK [--day DATE]`: the tool's text, verbatim (Datadog: counts in `Promise.allSettled`,
  returns an `observability-result` timed by its own clock); `fallback`: classic-tool calls, JSON.
- `record TASK --result FILE` (the tool's answer, hashes checked) or `--check ID [--day DATE]
  (--value N --hash H | --yes | --no) [--by NAME]` (fallback, manual; `by`: login name).
- `status [--project SLUG] [--json]` (text: a PT-BR line per plan); `report TASK`: PT-BR Markdown,
  title by the tracker port (dropped on failure), days × checks (value, ok or falhou, real start
  and end, local with offset), hashes, verdict.

## Results and status

`<TASK>.results.jsonl` beside the plan (600, temp file and `os.replace`). Row: `version`, `day`,
`check`, `kind`, `value` (number; boolean for manual), `expect`, `verdict` (`pass`, `fail`),
`started`, `finished` (UTC), `window`, `hash`, `times` (`run`, `tool`, `record`), `by`. A row for
the same `day` and `check` replaces the old one; errors are never rows. Status per plan: `due_day`,
`day`, `pending`, `missing_days` (backfilled by `run --day`), `stale`, `attention_days`, `streak`
(days with every check `pass`, counted back from the due day, or the day before when only it is
pending; a failing, missing or stale day stops it), `state`: `waiting`, `done` (streak ≥ N, "pode
desligar de vez"), `attention` (latest complete day failed), `observing`. Nothing resets.

## Database guard and the Postgres adapter

Neutral guard: refuses empty text, comments, a `;` outside a literal (a last one is dropped), a
first word other than `select` or `with`, and, outside literals and quoted identifiers, the write,
schema and session words (`insert`, `update`, `delete`, `into`, `set`, `begin`...: the list is in
the plan) plus the adapter's `rules`. Placeholders `:day`, `:day_from`, `:day_to`; none means a
snapshot (a past `--day` warns). `scalar` holds a `flock` on `data_dir()/observe.lock` (one query
at a time) and accepts one number. Postgres (`[database.replica]`: `engine`, `timeout_seconds`
120, `replica_only` true, `host`, `port`, `name`, `user`, `pgpass`, `runner` docker or local,
`image`, `docker_args`) adds refusals (backslash, `$`, `pg_` and `lo_` prefixes, `copy`, `do`...),
runs `docker run --rm -i` with the pgpass mounted read-only (never read by `ws`) and `psql -X -q -A
-t -v ON_ERROR_STOP=1 -f -`: `statement_timeout`, `BEGIN TRANSACTION READ ONLY`, a
`pg_is_in_recovery()` check (`\gset`, `\if`), `SELECT (<sql>)::numeric` (two rows or columns fail
on the server). Its stderr becomes a fixed reason and is dropped: it may hold values.

## Exit codes and failure

0 ok, a failing verdict too; 1 invalid input, plan or document, SQL refused, not a business day,
no or two plans, stale hash, lock busy, not one number; 2 setup (config, Docker, pgpass, login, not
a replica, unknown adapter); 3 database unreachable, timed out or refusing. `run` goes on after 1
or 3 (`--check ID` reruns that one), stops at 2, exits 2, then 3, then 1. stderr: `ws observe: `.

## Daily, change request, skill; later; builder

- **daily**: `ws observe status --json`; a plan pending, `done` or in `attention` adds one line to
  "Para você:" ("observação: TS-5738 dia 3 de 5 (pendente), TS-5753 pode desligar de vez; peça
  /observe"); a failure is one more warning. **change-request**: the survey takes `ws observe
  report TASK` as execution evidence. **observe** (no clash in `skills/`): new, run (`request`
  verbatim to `observability.tool`, the answer saved at `result_path`, `record --result`, manual
  questions), status, report; never writes the tracker, changes a job, or runs SQL outside `ws`.
- **Left for later:** `ws deploy-check` is still Datadog-only and should move onto the
  observability port. **Left to the builder:** PT-BR wording, `new`'s examples, key order, stderr
  patterns, fixtures.
