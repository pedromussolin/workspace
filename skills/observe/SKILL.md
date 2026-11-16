---
name: observe
description: Keeps the daily observation of switched-off jobs (database counts, observability tool counts, manual confirmations) until they can be switched off for good, and prints the GMUD evidence. Use when the user asks to start, run or see an observation ("observa o TS-5738", "roda a observação", "como está a observação", "evidência da observação para a GMUD"). Read-only: it never writes to the task tracker.
---

# Observe

A job was switched off, and the user wants proof that nothing needed it. An observation is a plan of
checks that run once per business day for N days. Each check gives one number or one yes/no, and the
plan says what is expected (for example `== 0`). After N clean days the job can be switched off for
good. `ws observe` does the deterministic part: it validates the plan, queries the database, records
each value with its real start and end time, and prints the status and the report. You ask the user,
run the commands in order and carry the observability tool's answer. Lines to the user are PT-BR;
these instructions are in English.

The plan lives outside the repo, in `~/.local/share/workspace/projects/<slug>/observations/<TASK>.toml`.
The results go beside it. The commands keep rows and log lines out of their output; never add them.

## Steps

### New

1. Ask, in plain words: which job, the date it was switched off, N (the number of business days,
   default 5) and each check. A check is one of three kinds: `database` (a count from the
   database), `observability` (a count from the observability tool) or `manual` (a question the
   user answers yes or no). For a database or observability check, ask what result is expected:
   `expect` is only `== N` or `<= N`, such as `== 0` or `<= 3`. A manual check has no expected
   value; its answer "yes" passes.
2. Run `ws observe new TASK --project SLUG --job "<text>" --switched-off YYYY-MM-DD [--days N]
   [--timezone TZ]`. It writes a plan with commented examples.
3. Fill the `[[checks]]` tables with Edit, following the commented examples that `ws observe new`
   wrote. Each check has `id` (lowercase letters, digits and hyphens), `kind` and, optionally,
   `label`, plus the fields of its kind:
   - `database`: `sql` (reads one number), `expect` and `database` (the config name, default
     `replica`). The `sql` may use the placeholders `:day`, `:day_from` and `:day_to` (the day and
     the window bounds); without one it reads the current state.
   - `observability`: `signal` (`traces`, `logs` or `metrics`), `query` and `expect`.
   - `manual`: `question`, and no `expect`.
4. Run `ws observe check TASK` until the exit code is 0. At exit 1, show the problems in PT-BR and
   fix only what the user settles.

When a check means "zero calls", prefer a metrics count over all ingested traffic (for example, a
hits metric) to indexed traces or logs. Retention filters and sampling can hide calls from indexed
data, so a zero there is weaker evidence. Say so when the user picks the signal.

### Run

1. Run `ws observe run TASK` as its own Bash call, with nothing chained to it. It queries the
   production replica, so Claude Code asks the user first. The approval box shows the task and the
   database checks, never the SQL, and the user approves there. If the user refuses, stop. Never try
   another way to query the database.
2. Read the JSON: `day`, `day_number`, `recorded`, `observability`, `ask`, `problems`, `warnings`.
   Run the commands the JSON gives exactly as printed. Never rebuild them by hand: they carry the
   `--project` and `--check` flags the plan needs.
3. When `observability` is not null: run the command in `observability.next` (a
   `ws observe request` line with the right flags) and send its stdout to the tool named in
   `observability.tool`, verbatim: no edit, no summary. Save the tool's JSON answer with Write at
   `observability.result_path`, then run `ws observe record TASK --result <result_path>` (add
   `--project SLUG` when `next` has it). At a stale hash (`changed since the request`), run
   `observability.next` again.
4. When the request fails or the tool does not answer, run `ws observe fallback` with the same
   flags as `observability.next`. It prints `calls`, the plain calls to make in the observability
   tool, and `record`, one item per check. For each answer, run that item's `command` with `<N>`
   replaced by the count.
5. For each item of `ask`, ask the user its `question` in PT-BR, then run its `yes` or its `no`
   command (each is a `ws observe record` line). A "yes" passes. Never answer for the user.
6. Say what ran, in PT-BR: the day, which checks passed or failed and which are missing. A failing
   verdict is exit 0: report it, do not treat it as an error.

Exit 1: show the problems in PT-BR and fix only what the user settles (`run` goes on with the other
checks; `--check ID` reruns one). Exit 2 or 3: show stderr and stop.

### Status

Run `ws observe status [--project SLUG]`. Show one PT-BR line per plan. Say "pode desligar de vez"
only as advice: the user decides, and this skill switches nothing off.

### Report

Run `ws observe report TASK` and show its PT-BR Markdown as is. It is the evidence for the GMUD
(the production change record): days by checks, real times and the verdict.

## Rules

- Never write to the task tracker.
- Never change, stop or restart a job.
- Never run SQL or any database command outside `ws observe run`, and never try another way to
  reach the database.
- Never paste a row, a log line or a customer value in the chat or in a file.
- Never edit a results file by hand; use `record`.
- Never send the observability tool anything but the text of `ws observe request`, verbatim.
