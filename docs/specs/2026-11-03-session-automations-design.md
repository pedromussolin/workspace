# Session automations: design

Four automations chosen by the user on 2026-11-03: **A** handoff and the session hooks, **B** daily
by period, **C** `ws env check`, **D** the `deploy-check` skill. Status: implemented on 2026-11-17 (A and B joined `main` then; C and D before), approved by the user on
2026-11-03 (see "Decisions"); plan in `docs/plans/2026-11-03-session-automations.md`. Each part is independent and can be built by its own agent in a separate worktree
(see "Parallel build"); only Step 0 comes first.

## Goal

The recurring session chores run the same way every time, from a script, without losing context or
quality: a long chat ends in a deliberate handoff that a new chat finds by itself; the standup covers
any period and gives a text for a manager; the env vars a repo reads are checked against the
Parameter Store before a merge; a deploy is checked in Datadog with ready queries, in the user's
deploy order.

## Why

Measured on 2026-11-03 over 30 days of the user's Claude Code transcripts:

- **Handoff:** asked for explicitly 13 times, each written by hand with a different shape. Main
  sessions reach 500k–966k tokens of context, and every call re-reads it: the two biggest sessions
  alone re-read 930M tokens in a week. The user's rule is "qualidade e contexto em primeiro lugar":
  auto-compaction was approved and then dropped on purpose, because it summarizes at an arbitrary
  moment and loses detail. A deliberate handoff at a natural pause keeps the detail and starts the
  next chat small.
- **Deploy:** about 270 requests about deploy, image tags, sandbox and release.
- **Datadog:** 77 requests and 1,189 MCP calls (`aggregate_spans` 305, `search_datadog_logs` 268,
  `analyze_datadog_logs` 191, `search_datadog_spans` 121). The Datadog skill was loaded in 37 chats:
  the model rediscovers the same queries every time.
- **Parameter Store:** "check that no env var is missing in the Parameter Store before the merge",
  42 requests in 14 days, each done by hand with the user's listing script.
- **Standup:** `ws standup collect` only takes `--today`, so a weekly or monthly summary is built by
  hand.

## Principles (all four parts)

- **Script first** (root `CLAUDE.md`): a `ws` command does the deterministic part (collect, parse,
  compare, render files, build queries); the skill decides, asks and writes the prose.
- **Quality and context first; tokens second.** A command prints what the decision needs, in the
  smallest faithful shape (counts plus the items that carry information, never a raw dump), and
  never drops information silently: whatever it leaves out is counted or listed as a warning.
- **Read-only** outside the workspace, except the writes listed per part. Nothing here commits,
  pushes, stashes or merges in a company repo, writes to Jira, GitHub, AWS or Datadog.
- **Language:** commands, flags, JSON keys and messages in English; what people read (handoff file,
  standup, manager text, check verdicts) in PT-BR.
- **Confidentiality:** values that are company-specific (Parameter Store prefixes, AWS profiles,
  Datadog service names and env tags, real names) live only in `~/.config/workspace/config.toml` or
  in private files outside git; the repo gets the generic shape (see "Confidentiality").
- **Local config:** each new command reads only its own table through `userconfig.load_table`
  (Step 0); a missing `[jira]` never breaks `ws env check` or `ws deploy-check`.

## Step 0: shared scaffolding (orchestrator, one commit before the agents)

So the four agents touch disjoint files:

- `src/ws/userconfig.py`: a public `load_table(name) -> dict` (missing file: `ConfigMissing`; table
  absent: `{}`; not a table: `ConfigInvalid`). Each module validates its own keys. Also
  `load_standup() -> StandupConfig`, because `load_config` requires `[jira] site` and `email`, and
  `ws handoff collect` needs only `[standup]`.
- `src/ws/cli.py`: registers three new command groups by calling `register(subparsers)` from
  `ws.handoff_cli`, `ws.envcheck_cli` and `ws.deploycheck_cli`, created as stubs that exit 2 with
  "not implemented yet". Part B edits the existing `standup` and `task` parsers in `cli.py`; no other
  part touches the file.
- The README command table and `docs/manual.md` are updated by the orchestrator at integration,
  from each agent's report.

## A. Handoff and the session hooks

### Decisions

- **The handoff file is private:** `HANDOFF-YYYYMMDD-<topic>.md` in the project's private folder,
  outside git: `~/.local/share/workspace/projects/<slug>/` (created by `ws project new`, mode 700;
  `ws handoff new` creates it for an existing project that lacks it). Mode 600. It may hold real
  names, branch names and paths; it never holds secrets, Parameter Store values or log dumps. A chat
  that belongs to no project uses the slug `standalone`.
- **Template basis:** the shape the user already writes by hand: the private handoff of 2026-11-03
  in the workspace project folder and the three legacy ones in the old front-project folder (title
  with date and topic, one line on why the chat stopped, a section per front with state, user
  decisions, what was deliberately not done and next steps, interrupted agents with their saved
  briefs, what only the user can do, files, and the order to resume).
- **Then the checkpoint:** for a workspace project with a `CONTINUE.md`, the existing `checkpoint`
  flow updates "Onde parei" (with a one-line pointer to the private file) and "Próximo passo",
  masked, and commits and pushes the project folder. `standalone` has no `CONTINUE.md`: skipped, and
  the reply says so.
- **Then the memory pointer:** one memory file per project, `handoff-<slug>.md`, overwritten by
  each new handoff, and one index line for it in `MEMORY.md`, replaced in place. One line per
  project, not one per handoff, so the always-loaded index does not grow (today it already has two
  hand-made handoff pointers, which the first run replaces). The model writes it with its own memory
  mechanism, in the session's memory folder: the frontmatter and metadata of those files belong to
  the harness, so a `ws` writer could drift from it. This is the one write of this part that is not
  a script.
- **No auto-compaction.** The context hook only warns; the model proposes a handoff and waits for
  the user's yes.
- **Both hooks go through the protected copy** (`~/.claude/hooks/workspace/`): an informational
  hook that ran from the repo could be edited by an agent to inject text into every session. For the
  same reason they use the standard library only and never import or run `ws` (an editable install
  of the repo); they read `config.toml` and the data folder themselves, with the `WS_CONFIG_DIR` and
  `WS_DATA_DIR` overrides the tests use.

### `ws handoff collect [--all] [--no-prs]`

Read-only JSON. Repos: every git repo directly under `[standup] repo_roots` (the daily's
`_find_repos`), plus the workspace repo itself (its agent worktrees live under
`.claude/worktrees/`). Every git call runs as `git -C <repo>` with `GIT_OPTIONAL_LOCKS=0` (so
`status` never takes the index lock under a parallel agent) and a 15 s timeout; no fetch, so ahead
and behind are as of the last fetch (`"fetched": false`).

Per repo: current branch (or the detached sha), default branch (`origin/HEAD`), upstream and
`ahead`/`behind`/`gone` (`for-each-ref --format=%(upstream:short) %(upstream:track)`), uncommitted
files (`status --porcelain=v1 -z`: count and the first 10 paths), stash count, worktrees
(`worktree list --porcelain`: path, branch, short head, locked, prunable, and for each its own
uncommitted count and ahead/behind), and the local-only branches: committed in the last 14 days and
ahead of their upstream or with none.

Without `--all`, a repo appears only when it has something to say (not on its default branch,
ahead, behind, uncommitted files, a stash, extra worktrees or local-only branches); the rest is
`clean_repos: <n>`. A clean repo carries no handoff information, so this loses none.

PRs: the user's open PRs from one `gh api graphql` search (`is:pr is:open author:@me`, first 50):
repo, number, title, url, base, head, draft, review decision, updated. `gh` failing → a warning.

Handoffs: the newest 5 handoff files from the hook's locations (below), each with path (with `~`),
project, modified time, title (the H1) and `closed`.

Warnings also count the session hooks' failures of the last 7 days from their error log, so a
silently broken hook shows up at the next handoff.

```json
{
  "generated_at": "2026-11-03T17:40:00-03:00",
  "fetched": false,
  "repos": [
    {"name": "<repo>", "path": "~/repos/<repo>", "branch": "feature/TS-1-x", "default_branch": "master",
     "upstream": "origin/feature/TS-1-x", "ahead": 2, "behind": 0, "gone": false,
     "uncommitted": {"count": 3, "paths": ["src/a.py"], "more": 0}, "stashes": 0,
     "worktrees": [{"path": "~/repos/<repo>-wt/25", "branch": "...", "head": "abc1234",
                    "uncommitted": 0, "ahead": 1, "behind": 0, "locked": false, "prunable": false}],
     "local_branches": [{"name": "...", "ahead": 3, "upstream": null, "last_commit": "2026-11-02"}]}
  ],
  "clean_repos": 31,
  "prs": [{"repo": "<repo>", "number": 12, "title": "...", "url": "...", "base": "master",
           "head": "release/20261103", "draft": false, "review": "APPROVED", "updated": "..."}],
  "handoffs": [{"path": "~/.local/share/workspace/projects/<slug>/HANDOFF-20261103-x.md",
                "project": "<slug>", "modified": "...", "title": "...", "closed": false}],
  "warnings": []
}
```

Exit 0 with warnings; 2 when the config is invalid.

### `ws handoff new SLUG --topic TOPIC`, `refresh`, `check`

- `ws handoff new SLUG --topic TOPIC [--date YYYY-MM-DD]`: the slug must be a folder under
  `projects/` (or `standalone`); the topic matches `^[a-z0-9]+(-[a-z0-9]+)*$`, at most 40
  characters. Creates the private folder if missing (700) and the file from `templates/handoff.md`
  (600), with the date filled in and the "Estado dos repositórios" block rendered from a fresh
  collect. An existing file is refused (exit 1, naming it). Prints `{"path": ..., "repos": n,
  "prs": n, "warnings": [...]}`.
- `ws handoff refresh FILE [--diff]`: re-renders only the block between the
  `<!-- ws:state:begin -->` and `<!-- ws:state:end -->` markers. With `--diff` it writes nothing and
  prints what changed since the file was written (a branch that moved, a PR merged, a worktree gone):
  the resume step of the skill uses it.
- `ws handoff check FILE`: a JSON verdict like `ws checkpoint check`, exit 0 or 1. Problems: the file
  is outside the private project folders and the `extra_globs` folders, or its name does not match,
  or its mode is not 600; no `# Handoff DD/MM/AAAA: <tema>` title; no front section (`## N. <frente>`)
  or a front without a filled `**Próximos passos:**`; the state block missing; `## Ordem sugerida ao
  retomar` empty; a template placeholder left. Warnings: over 300 lines; a path under `/tmp/` (gone
  after a WSL shutdown; the user keeps drafts outside `/tmp`).

The state block is Markdown, more compact than the JSON for the model to read: tables of the repos
with something to say, the worktrees, the local-only branches and the open PRs, and a footer "Contagem
à frente/atrás pelo último fetch; N repositórios limpos omitidos."

### The handoff file (`templates/handoff.md`, PT-BR)

```markdown
# Handoff {{data}}: <tema em poucas palavras>

<Por que o chat parou e como ler este arquivo, em 1 a 3 linhas.>

## 1. <Frente>

**Estado:** <o que está pronto, o que está pela metade e onde: branch, worktree, commit>

**Decisões do usuário:** <decisões desta sessão, com as palavras dele quando importarem>

**Decidido e não feito de propósito:** <o que ficou de fora e por quê; apague se não houver>

**Próximos passos:**
1. <ação concreta>

## Agentes interrompidos

<worktree, branch, último commit, se a suíte passou, onde está o brief salvo; apague se não houver>

## Para o usuário fazer

<o que só ele pode fazer; apague se não houver>

## Estado dos repositórios

<!-- ws:state:begin: gerado por ws handoff; para atualizar, ws handoff refresh -->
<!-- ws:state:end -->

## Ordem sugerida ao retomar

1. Ler este arquivo inteiro.
```

### The skill `handoff`

Description (third person, it alone decides the trigger): writes a handoff for a new chat (a
private HANDOFF file with every front, the repos, worktrees and open PRs, then the project's
checkpoint and a memory pointer), and resumes from one. Use when the user asks for it ("handoff",
"faz a passagem", "passagem de chat", "vou fechar o chat", "vou desligar", "shutdown", "continua do
handoff"), or says yes after the model proposed one because the context grew; never on its own.

Writing a handoff:

1. **Project:** the slug of the project the session works on; otherwise ask; no project →
   `standalone`.
2. **In-flight work:** list the running agents and ask whether to wait for them or stop them; never
   stop one silently. For each agent: worktree, branch, last commit, whether its suite passed. A
   brief that exists only in the chat is saved to `<private folder>/agents/brief-<name>.md`, so the
   next chat can relaunch it. Nothing is committed, stashed or pushed to save work: the state block
   shows what is uncommitted.
3. `ws handoff new <slug> --topic <tema>`.
4. **Write the prose** in the file with Edit: one section per front, the user's decisions in their
   words when they matter, what was deliberately not done, concrete next steps, the order to
   resume. Cite files and lines, never paste logs or values.
5. `ws handoff refresh <file>` when something changed since step 3, then `ws handoff check <file>`
   until ok.
6. **Checkpoint:** for a workspace project with a `CONTINUE.md`, the `checkpoint` skill's steps
   (masked text; "Onde parei" points to the private file by its `~` path).
7. **Memory pointer:** overwrite `handoff-<slug>.md` in the session's memory folder (what the
   handoff covers, the path, "ler inteiro antes de agir") and replace that project's line in
   `MEMORY.md`, for example
   `- [Handoff <slug>](handoff-<slug>.md) — retomar pelo HANDOFF-<data>-<tema>.md`.
8. **Reply:** the path, the sentence to open the next chat with ("Continue do handoff <path>"), and
   what is left for the user.

Resuming: read the file in full; `ws handoff refresh <file> --diff` and report what changed since
it was written before acting; continue from "Ordem sugerida ao retomar". When the user says a
handoff is finished, write `Status: encerrado` on its second line (the hook stops listing it).

Never: commit, push, stash or merge in a company repo; stop agents without asking; copy the handoff
or its real names into the repo; compact the context; start a handoff without the user's word.

### Hook `context_watch.py` (UserPromptSubmit)

- **Input:** the hook JSON on stdin; it uses `session_id` (must match `^[A-Za-z0-9-]{1,64}$`) and
  `transcript_path`. UserPromptSubmit fires for the main session's prompts (also when a background
  agent reports back to it), not for the prompts inside a subagent, so it measures the main context.
  It takes no matcher.
- **Measure:** the last transcript entry with `type` `assistant`, `isSidechain` false and a
  `message.usage` whose sum is above 0 (a `<synthetic>` model entry is skipped); context =
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. The file is read backwards
  from the end in 1 MB chunks, up to 16 MB (the biggest transcript today is 265 MB; its last entry is
  near the end), dropping the partial first line of a chunk.
- **The transcript format is not documented** (the hooks reference, checked 2026-11-03, documents
  neither `message.usage` on transcript entries nor `isSidechain`, and says the file is written
  asynchronously and may lag). The fields above were observed in the user's transcripts on
  2026-11-03, and the tests pin that shape. A format change means no warning, never a blocked
  prompt; a transcript over 1 MB with no usable entry is logged as `context_watch no-usage`, so the
  next `ws handoff collect` shows it. A lagging file at worst delays the warning by one prompt.
- **Bands:** the first warning at `warn_at` (300,000), then one at every `step` (100,000) above it,
  once per band. State in `~/.cache/workspace/context-watch/<session_id>.json` (the highest band
  warned); a context that drops below a band (a `/clear` or a manual `/compact`) resets it. Files
  older than 7 days are removed, at most once a day.
- **Output** (exit 0, JSON): `hookSpecificOutput.additionalContext` for the model, about 60 tokens:
  "Context is at 312k tokens. At the next natural pause (after the current step, never in the middle
  of an edit or with agents running), propose a handoff to the user (skill `handoff`). Do not start
  it without their yes, and do not compact." And `systemMessage`, one PT-BR line for the user:
  "Contexto em 312 mil tokens: o Claude vai propor um handoff na próxima pausa." Below the threshold
  or in an already warned band: no output. The reference documents `systemMessage` as a universal
  field shown to the user, but not its combination with `additionalContext`: the build tests it in a
  real session first, and without it the hook keeps only the note to the model.
- **Failure:** never blocks the prompt. Every path exits 0 (UserPromptSubmit's exit 2 would block
  the prompt); any exception or a 2 s internal deadline (`signal.alarm`) means no
  output, and one line `<iso time> context_watch <ExceptionType>` is appended to
  `~/.cache/workspace/hooks/errors.log` (the last 200 lines kept; never the prompt or the transcript).
- **Budget:** under 100 ms typical; registration timeout 10 s.

### Hook `handoff_pointer.py` (SessionStart)

- **Matcher** `startup|clear|compact` (not `resume` or `fork`: those sessions already have their
  context). The additional context goes in at the start of the conversation.
- **Finds** `<data dir>/projects/*/HANDOFF-*.md` and the `[handoff] extra_globs` (`~` expanded),
  skips files whose first 10 lines hold `Status: encerrado`, keeps those modified in the last
  `max_age_days` (7), newest first, at most `max_listed` (3).
- **Output** (exit 0, JSON `hookSpecificOutput.additionalContext`), only when something is found:

  ```text
  Recent handoffs (newest first). If the user's request continues one, read it in full before acting; otherwise ignore them:
  - ~/.local/share/workspace/projects/<slug>/HANDOFF-20261103-<tema>.md (03/11 14:02): <the H1, cut at 120 characters>
  ```

  Paths and one line each, never content: at most about 150 tokens.
- **Failure:** same as `context_watch`: exit 0, no output, one line in the error log.

### Installation through `ws setup`

What `ws setup` does today (`src/ws/bootstrap.py`): it copies every file matching `hooks/*.py`,
`hooks/gate/*.py` and `hooks/gate/*.json` to `~/.claude/hooks/workspace/` (read-only files, folders
555, a `manifest.json` of SHA-256 sums); it reports a missing, stale, edited or extra file; it
updates the copy only when run by the user in a terminal, showing the diff of each file and asking
`[s/N]` (run by an agent it writes nothing there); and it prints, never writes, the settings JSON
that registers `python3 -I -B "<copy>/<script>"`. The registrations live in `HOOK_REGISTRATIONS`
(script, matcher, probe tools) and are all `PreToolUse` today (`_hook_gate`, `_hook_commands`).

The two new scripts sit at `hooks/` top level, so the `*.py` glob copies them with no change. The
code change is to give each registration its event:

- `HOOK_REGISTRATIONS` gains an `event` and a timeout: the three gates stay `PreToolUse` with 30 s;
  `context_watch.py` is `UserPromptSubmit` with no matcher; `handoff_pointer.py` is `SessionStart`
  with the matcher `startup|clear|compact` and the probes `startup`, `clear`, `compact`; both 10 s
  (the current minimum).
- `_hook_gate` groups the printed entries by event; `_hook_commands(settings, event)` reads the
  entries of one event; `_registration_state` is unchanged otherwise (same copy path, `-I`, matcher
  coverage, timeout checks).
- `ws setup --check` reports the two hooks like the gates; the user applies the printed block after
  approving it, as today.

### Config (`config.toml`)

```toml
[handoff]
extra_globs = ["~/repos/<legacy folder>/HANDOFF-*.md"]   # optional
max_age_days = 7
max_listed = 3

[context_watch]
warn_at = 300000
step = 100000
```

Both tables are optional; the hooks read them with `tomllib` like the gate does (`WS_CONFIG_DIR`
override), and a missing or invalid table means the defaults.

### Tests

pytest, throwaway repos and fakes, no network: collect on repos with each kind of state (detached
HEAD, gone upstream, worktree with changes, prunable worktree, stash, local-only branch), the clean
filter and `--all`, a git timeout becomes a warning, `GIT_OPTIONAL_LOCKS=0` is set, `gh` faked
(answer, failure); `new` refuses an unknown slug, a bad topic and an existing file, sets the modes;
`refresh` touches only the marked block and `--diff` writes nothing; every `check` rule. The hooks,
fed JSON on stdin: a synthetic transcript (sidechain and synthetic entries skipped, a 3 MB last
line, a missing file), each band once, the reset, a bad `session_id`, an exception and the deadline
give exit 0 and no output; the pointer's age, limit, `encerrado` and output size. `ws setup`: the new
registrations printed per event, recognized when present, a wrong matcher or a repo path reported.

### Files

`src/ws/handoff.py`, `src/ws/handoff_cli.py`, `templates/handoff.md`, `hooks/context_watch.py`,
`hooks/handoff_pointer.py`, `src/ws/bootstrap.py`, `skills/handoff/SKILL.md`, tests
`tests/test_handoff.py`, `tests/test_context_watch.py`, `tests/test_handoff_pointer.py` and the
registration cases in `tests/test_bootstrap.py`.

## B. Daily by period

### `ws standup period TEXT [--today YYYY-MM-DD]`

A PT-BR period parser (`src/ws/period.py`) that prints
`{"since": "2026-10-27", "until": "2026-11-02", "label": "semana passada (27/10 a 02/11)",
"workdays": 5, "warnings": []}`. The text is lowercased, accents removed, spaces collapsed, and a
leading "de", "da", "do", "na", "no" or "em" dropped. Accepted forms:

| Text | Period |
|---|---|
| `hoje`; `ontem` | today; the previous workday (as the daily) |
| `esta semana`, `essa semana`, `semana atual` | Monday of this week to today |
| `semana passada`, `última semana` | Monday to Sunday of the previous week |
| `últimos N dias`; `últimos N dias úteis` | N calendar days ending today; N workdays ending today (`workdays_before`) |
| `este mês`, `esse mês`; `mês passado` | the 1st to today; the whole previous month |
| `outubro`, `out`, `outubro de 2026`, `10/2026` | that month; without a year, the latest one that started on or before today |
| `20/10 a 31/10`, `de 20/10 até 31/10`, `20/10/2026 a 31/10/2026`, `2026-10-20..2026-10-31` | the range; a day without a year is the latest such day not after today, and the start is inferred before the end |
| `20/10`; `desde 20/10` | that day; that day to today |

An `until` after today is clipped to today, with a warning; `since` after `until`, a window over
120 days, or an unknown text → exit 2 with the accepted forms. Workdays come from `ws.workdays`
(Monday to Friday; holidays are still not counted).

### `ws standup collect --since D [--until D]`

`--since`/`--until` (ISO dates, `until` defaults to today) are exclusive with `--today`. The
`window` gains `kind`: `daily` (today's behavior, unchanged) or `period`. In a period:

- commits: `git log --since=<since> 00:00:00 --until=<until> 23:59:59`;
- branches: those whose tip or creation date falls in the window;
- PRs: the search `is:pr author:@me updated:>=<since>`, paginated by cursor up to 300 (more → a
  warning), with `createdAt`, `closedAt` and `baseRefName` added; a PR is kept when it was created,
  merged or closed in the window, or is still open;
- `last_activity` is computed inside the window; `next_steps` stays (it is the current state).

`ws standup report` refuses a `period` activity (exit 2, "use ws standup summary"), so the daily
never mixes the two.

### `ws task list` and the card fields

The JQL already returns the cards updated since `since` and the open ones. Each card gains
`status_changed` (Jira's `statuscategorychangedate`) and `resolved` (`resolutiondate`), null when
absent; `Task` gains an optional `status_changed`. The MCP fallback of the daily skill asks for the
same two fields.

### `ws standup summary --activity FILE [--cards FILE] [--top N]`

Groups the period's work by theme (the card's epic; cards without an epic go to "Sem épico"), the
themes ordered by activity. Per task: key, title, current status, url, commits, active days, first
and last day, up to 5 subjects, the PRs (ref, state, base, merged date, title) and an `outcome` by
the first rule that matches:

| `outcome` | Rule |
|---|---|
| `production` | a PR of the card merged in the window into the default branch (`master`, `main`) |
| `homologation` | a PR merged in the window into another base (release, sandbox), or the current status is `validation` or `ready_deploy` |
| `review` | an open PR |
| `done_without_pr` | status `done` with `status_changed` in the window and no PR |
| `in_progress` | commits in the window and none of the above |

Each outcome carries its `evidence` ("PR <repo>#12 merged into master on 2026-10-28"). Also:
`blockers` (cards in Block, and the stuck ones by the daily's rule), `keyless` (count, repos, up to
10 subjects), `totals` (tasks, commits, PRs merged, per outcome), `more` per theme when `--top` cut
it, and `warnings`. The status is today's, not the one at the end of a past period: the JSON says so
(`status_as_of`) and the text too.

### The skill `daily`, period mode

The description adds the period and the manager text ("daily da semana passada", "resumo de
outubro", "o que fiz de 20/10 a 31/10", "texto para o gestor", "para a 1:1"). `SKILL.md` gains a
short "Period" entry and the detail goes to `references/period.md`:

1. `ws standup period "<texto>"`; when a year or a clip was inferred, show the label before going on.
2. `ws standup collect --since S --until U > ~/.local/share/workspace/standup/activity-period.json`.
3. Cards as today (`ws task list --since S`, MCP fallback).
4. `ws standup summary ... --top 3` (without `--top` when detailed).
5. Write, from the summary only:
   - **Resumo por tarefa** (default): a header with the label, one block per theme, one line per
     task with its outcome in plain words and the key, "E mais N."; about 200 words. Detailed on
     request ("detalhado"): every task, what moved, the PRs in words, the keyless commits.
   - **Texto para gestor ou 1:1** (on request, or "os dois"): one paragraph per theme with the
     deliveries (production, homologation) and the blockers, plain PT-BR, keys in parentheses. A
     stuck card is a question to the user before it is called a blocker, as in the daily.

The daily's rules hold: describe the task, never the person (no first or second person); no sha,
repo or jargon in the short text; nothing is written anywhere.

### Tests and evals

pytest: every parser form with a fixed `today` (year boundary, a month not yet started this year,
clipping, the 120-day limit, accents and the leading words), the collector's window on a throwaway
repo (commits on the edges of the window), the PR window and pagination with a fake `gh`, each
`outcome` rule, `--top`, `report` refusing a period. Evals (the existing suite, about 0.25 USD a
run, run with `--runs 1` while building): `period-last-week` (the summary for "resumo da semana
passada" on the fixed Monday: label, themes, no Ontem/Hoje) and `manager-text` (paragraphs per theme,
no first person, every key exists). The Jira mocks gain the two fields.

### Files

`src/ws/period.py`, `src/ws/standup.py`, `src/ws/standupsummary.py`, `src/ws/standupreport.py` (the
refusal), `src/ws/jira.py`, `src/ws/taskmodel.py`, `src/ws/cli.py` (`standup` and `task` parsers),
`skills/daily/SKILL.md`, `skills/daily/references/period.md`, tests `tests/test_period.py`,
`tests/test_standup.py`, `tests/test_standupsummary.py`, `tests/test_jira.py`, and
`evals/period-last-week/`, `evals/manager-text/`, `evals/mocks/`.

## C. `ws env check`

### What the repos do (read-only inspection, 2026-11-03)

- **The three Python APIs** (BFF, shared service, data-lake API) never call the Parameter Store
  themselves. Their `entrypoint.sh` installs the platform's boot loader and runs it with the app name
  (a literal equal to the repo name) and the realm; it exports only the lines that match
  `^[A-Za-z_][A-Za-z0-9_]*=`, and when it fails the app starts anyway, with a warning
  (`entrypoint.sh:93-106` in the three repos).
- **Name mapping** (the loader's source is in no repo; inferred from the API template's README and
  the infra resources): a parameter `<prefix>/CFG/FASTAPI/TITLE` or `<prefix>/CFG_FASTAPI_TITLE`
  becomes `CFG_FASTAPI_TITLE`: the prefix (realm, environment, app) is stripped and `/` becomes `_`.
  This is the flattening the user's `diff-parameter-store` script also applies (legacy nested names
  versus the flat form). One app uses a different realm in production, so the prefix is per repo and
  per environment.
- **Reading:** pydantic-settings in one file per repo (BFF and shared `src/config/__init__.py`,
  data-lake `src/shared/config/__init__.py`). Every group class is `(StripQuotesMixin, BaseSettings)`
  with `env_prefix="CFG_<GROUP>_"` and `case_sensitive=False`; the root class has `env_prefix="CFG_"`
  and holds the groups as fields; there is no nested delimiter. The only direct read is
  `os.getenv("CFG_ENVIRONMENT")`. Rough counts: BFF about 103 names (48 without a default), shared
  about 117 static, data-lake 50 (14 without a default).
- **Runtime prefixes (shared service):** three classes have no prefix and are built with
  `_env_prefix=<settings_prefix>` (`src/shared/repository/file_storage.py:176, 211, 233`), where the
  prefix is a database column the API can edit, seeded by a migration; about 60 more names, whose
  prefixes carry partner names. One migration also reads about 30 names through its own `env()`
  helper, some built with f-strings, needed only at `alembic upgrade`.
- **The front** reads `window.__CONFIG__` (`src/environments/environment.ts:19`), written at container
  start by `entrypoint.sh:6-23` from 5 variables, plus one more that becomes nginx config: 6 names.
  Today they come from the argocd values (`env` or `extraEnv`), not from the Parameter Store; moving
  them is decision D104 of `projects/whitelabel-restructure/decisions.md`, not merged yet.
- **argocd:** `apps/<app>/<realm>-<env>/values.yaml`; the image tag in
  `standard-service-chart.image.tag` (`sand-<sha>`, `prod-<sha>`); the chart's external-secrets
  option is off everywhere; no role annotation in these repos (the role is attached outside them).
  Some values still set plain env vars (the front's whole config, the data-lake workers' flags),
  which is what the user's rule forbids.
- **Traps for a scanner:** a nested group field on the root class (`log: LogSettings`) is not a
  name; the attribute name is not the prefix (always use `env_prefix`); `@property` and
  `computed_field` are not names; names also appear in docstrings and error strings, so no grep of
  string literals; tests set names with `os.environ.setdefault`; a committed `.devcontainer/.env` is
  loaded when `CFG_ENVIRONMENT` is unset, so that name is required in sandbox and prod even though it
  has a default; the local checkouts are often on another branch than the one being deployed.

### The command

`ws env check REPO --env ENV (--ref REF | --deployed) [--json]`. Read-only, names only, never a
value.

- `REPO` is a key of `[env_check.repos]`; `ENV` a key of its `prefix` table (`sandbox`, `prod`, and
  `staging` when configured).
- **Which code:** `--ref` (a branch, a release branch or a sha) is required, because a checkout's
  current branch is often not what goes to the environment; `--deployed` takes the sha of the image
  tag in that environment's argocd values. The files are read with `git ls-tree -r` and
  `git cat-file --batch` at that commit, never from the working tree; a commit missing locally → exit
  2 ("git fetch first"; `ws` never fetches).
- **Code names, Python** (an AST pass, standard library): every class whose bases reach `BaseSettings`
  takes its `env_prefix` from `model_config = SettingsConfigDict(...)`; each class-level annotated
  field gives `validation_alias` when present, otherwise `prefix + field`, uppercased; required when
  it has no default. Fields typed with another settings class, properties and computed fields are
  skipped. Classes listed under `dynamic` in the config are expanded with each configured prefix
  (tagged `dynamic`). Calls to the configured helpers (`os.getenv`, `os.environ.get`,
  `os.environ[...]`, and per repo e.g. `env`, `env_list`) with a literal first argument give names;
  an f-string argument gives an `unresolved` entry with `path:line`, never silently dropped. Files
  under `tests/` are skipped; files under the migration globs go to a `migration_only` bucket.
  `always_required` (e.g. `CFG_ENVIRONMENT`) overrides a default.
- **Code names, shell** (the front): `${NAME}`, `${NAME-…}`, `${NAME:-…}` in the configured files,
  minus the names the script assigns itself.
- **Store names:** listed per environment (see "The store source"), kept only under the configured
  prefix (`startswith(prefix + "/")`: a substring filter would also take the BFF's parameters for the
  front, whose app name is a prefix of the BFF's), the prefix stripped, `/` and `-` turned into `_`,
  uppercased. A normalized name that is not a valid identifier is reported as `invalid_in_store` (the
  entrypoint drops it, so it never reaches the pod).
- **argocd names:** the `env` and `extraEnv` blocks of the environment's values file(s) (the front
  has one per brand in production), read by a small indentation-based reader for the chart layouts
  in use (a list of `name:` items or a map); anything it cannot read is a warning with `file:line`.
  Names matching `role_vars` (patterns with `*`) are the pod's role and are fine there.

Output buckets, each name with where it is read (up to 3 `path:line` and a count):

| Bucket | Meaning |
|---|---|
| `missing_required` | read by the code, no default, not in the store |
| `missing_with_default` | read by the code with a default, not in the store (the rule says it should be there) |
| `in_argocd` | set in argocd and not a role var: should move to the store |
| `only_in_store` | in the store, read by no code at that commit (obsolete, or read in a way the scanner does not see) |
| `invalid_in_store`, `migration_only`, `unresolved` | as above |

The default output is a short PT-BR text for the chat (the commit checked, then one block per
bucket, the empty ones omitted, and the counts); `--json` gives the same data. Exit 0 when
`missing_required` and `in_argocd` are empty; 1 otherwise; 2 setup (config, credentials, commit not
found); 3 the store unreachable.

### The store source

The user's script `~/bashes/list-parameter-store` (read 2026-11-03): one optional positional filter
(a case-insensitive substring of the full name) and `--type string|secure|list`; it refuses to run
unless `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN` are exported (an AWS
profile alone is not enough) and checks `aws sts get-caller-identity`; it always reads the whole
account (`get-parameters-by-path --path / --recursive --with-decryption`) and filters afterwards; it
prints `[Type] NAME=VALUE` lines with color codes and a total. So every run decrypts every secret of
the account and prints the matching values.

Two sources, chosen by `[env_check] source` (decision 1). Script first: whichever the source,
`ws env check` itself calls it, parses its answer and compares, the same way every time; the model
only runs the command and reads its output, never calls `aws` or the script by hand.

- `aws` (the default): `aws ssm describe-parameters --profile <profile> --parameter-filters
  "Key=Path,Option=Recursive,Values=<prefix>" --query "Parameters[].Name" --output json`, following
  `NextToken`. `DescribeParameters` never returns values, needs no decryption, and works with the
  profiles in `~/.aws` (per environment in the config). An expired or missing profile → exit 2 with
  the profile name; an access error → exit 3.
- `script` (the user's script, kept as an option): `ws` runs the script with the app's prefix as the
  filter, reads its stdout in memory, strips the color codes, keeps the text between `] ` and the
  first `=` (a parameter name cannot contain `=`) and drops the rest of the line at once. The raw
  output is never printed, logged, written or put in an exception message; a failure prints only the
  exit code and a fixed PT-BR hint. Without the three variables in the environment → exit 2, saying
  to export them in the terminal that runs the command.

### Config

```toml
[env_check]
source = "aws"                           # or "script"
script = "~/bashes/list-parameter-store"
role_vars = ["<VAR>", "<PREFIX>_*"]      # the pod's role: allowed in argocd, never "missing"

[env_check.repos.<repo>]
path = "~/repos/<repo>"
argocd = "~/repos/<repo>-argocd"
kind = "python"                          # or "shell"
prefix = { sandbox = "<prefix>", prod = "<prefix>" }
values = { sandbox = ["<values path>"], prod = ["<values path>"] }
profile = { sandbox = "<aws profile>", prod = "<aws profile>" }   # only for source = "aws"
helpers = ["env", "env_list"]            # optional
migration_globs = ["migrations/**"]      # optional
always_required = ["CFG_ENVIRONMENT"]    # optional
shell_files = ["entrypoint.sh"]          # kind = "shell"

[env_check.repos.<repo>.dynamic]         # optional: class name → runtime prefixes
"<ClassName>" = ["CFG_<...>_"]
```

### Tests

Synthetic mini repos built in the test (no company code): each scanner rule and trap (nested group,
alias, property, computed field, docstring and error-string names, f-string helper call, tests
folder, migration glob, dynamic class, `always_required`); reading at a ref with a dirty working
tree; `--deployed` from a values file; the shell profile; the argocd reader on each layout; a fake
script on `PATH` whose output carries fake values, and an assertion that no value reaches stdout,
stderr, the JSON or an exception (also on its failure); the prefix filter against a longer app name
that shares it; a fake `aws` for the other source; every bucket and exit code.

### Files

`src/ws/envcheck.py`, `src/ws/envcheck_cli.py`, `tests/test_envcheck.py`. No skill: the command is
listed in the README, the `deploy-check` skill calls it in its "before the merge" step, and after
the build the user's memory note on the Parameter Store rule is pointed at it (outside the repo, with
the user's ok).

## D. The skill `deploy-check`

### Can it be a script?

Yes, most of it, without Datadog keys. A Python script calling the Datadog API needs an API key and
an application key that the user may not have and that would be one more secret to keep; the
Datadog MCP uses OAuth with the user's own permissions. The MCP has `execute_code`: it runs a
JavaScript program on the MCP server against the official Datadog SDK, with the user's permissions
and no credential exposed, and returns only what the program returns; several queries run in one
call, in parallel. It is already in the `pass` list of the gate catalog. So:

- `ws` builds everything deterministic: the services in deploy order, the deploy moment, the time
  windows, and the program itself (a versioned template with the parameters inserted as one JSON
  literal);
- the model calls `execute_code` once per service with that program, verbatim, and writes the
  verdict in PT-BR;
- the program computes the comparison and returns a compact verdict (under 2 KB).

The classic tools stay as a fallback, with the same queries, printed by `ws`.

### `ws deploy-check plan --env ENV [--at ISO] [--only KEY...]`

For each service of `[deploy_check] order` (shared service, BFF, front): the Datadog service and env
tag, and the deploy: with `--at`, that moment; otherwise the last commit of the local argocd repo
that touched the environment's values file (`git log -1 -- <values>`: sha, committer time, subject,
expected to be "Update image tag in values.yaml"), and the image tag and `DD_VERSION` read from it
(the version Datadog should show). A local argocd repo behind its upstream (last fetch) → a warning
to pull first; `ws` never pulls. Windows: before `[T − 30 min, T)`, after `[T + 5 min, T + 35 min)`,
baseline for new errors `[T − 24 h, T)`; `complete` false with `ready_at` when the after window has
not ended (the check then compares rates over the elapsed part and says so). A naive `--at` (no
offset) is local time of the machine, converted to UTC. A missing `DD_VERSION` in the values file is
a warning (the version check will be `sem_dados`).

### `ws deploy-check script KEY --env ENV [--at ISO]` and `queries`

`script` prints the JavaScript for `execute_code` (template `src/ws/data/deploy_check.js`). It runs,
with `Promise.allSettled` so one failed query still returns the others:

| Check | Query (SDK) | Before × after |
|---|---|---|
| traffic | spans `service:S env:E` + `span_filter`, count | requests per minute |
| errors | the same with `status:error`, count | error rate |
| 5xx | the same with `@http.status_code:[500 TO 599]`, count | 5xx rate |
| p95 | `pc95` of `@duration` (ns → ms) | relative and absolute change |
| error logs | logs `service:S env:E status:error`, count | per minute |
| new errors | logs grouped by `@error.kind` and error spans by `resource_name` and `@error.type` (top 50) | in the after window and absent from the 24 h baseline |
| version | spans grouped by `version` in the after window | share of the expected version |

Each check returns `ok`, `atencao`, `piorou` or `sem_dados` by fixed thresholds (an error or 5xx
rate up more than 50% with at least `min_requests` in both windows is `piorou` only when it also
means at least `min_extra_errors` (default 10) more errors than the before rate gives for the after
window, otherwise `atencao`; the same for error logs; p95 up more than 30% and 50 ms;
a new error signature → `atencao`, 10 or more occurrences → `piorou`; under `min_requests` →
`sem_dados`), with the numbers, and a top-level verdict. A front service of `kind = "rum"` uses RUM
error events instead of spans; `kind = "logs"` only the log checks. The filters and the version tag
are checked once against the real services during the build (read-only calls) and kept in the local
config, not in the repo.

`queries KEY --env ENV` prints, as JSON, the same checks as calls to the classic tools
(`aggregate_spans`, `analyze_datadog_logs`, `search_datadog_logs`) with their exact arguments, for
when `execute_code` is unavailable or fails.

### The skill

Description: checks a deploy in Datadog per service (errors, 5xx, p95 latency, new errors, before
and after the deploy, and the new version serving traffic) and walks the user's deploy order. Use
when the user asks to check a deploy or whether the next service can go ("confere o deploy", "como
está o BFF depois do deploy", "deploy-check", "posso subir o front?"). Read-only.

1. The environment and the services; the deploy moment from argocd or the user.
2. `ws deploy-check plan --env <env>`; say where the deploy is in the order and, when an after
   window is not complete, when it will be.
3. Per service: `ws deploy-check script <key> --env <env>`, then `execute_code` with that code
   verbatim (timeout 120). No Datadog skill loading and no SDK search: the program was verified at
   build time. On `invalid_request` or a failed run: `ws deploy-check queries` and the classic tools,
   and tell the user the program needs a fix.
4. The verdict in PT-BR: per service a table (check, antes, depois, situação), the new errors with
   counts and a one-line description (never a log line with customer data), the version share.
5. **Order:** shared service, then BFF, then front. "Pode seguir" for the next service only when the
   previous one serves the expected version (at least 95% of the after window's traffic) and no
   check `piorou`; otherwise what to look at. The skill only advises: the tag commits and any
   rollback are the user's.
6. **Before the merge** (when the user asks to prepare a deploy): `ws env check <repo> --env <env>
   --ref <branch>` per service.

Never: change argocd, roll back, create or edit Datadog notebooks, dashboards or monitors (the
user's MCP credentials have no write permission anyway), paste raw logs.

### Config

```toml
[deploy_check]
order = ["shared", "bff", "front"]
window_minutes = 30
settle_minutes = 5
baseline_hours = 24
min_requests = 50
min_extra_errors = 10

[deploy_check.env_tags]
sandbox = "<env tag>"
prod = "<env tag>"

[deploy_check.services.bff]
service = "<datadog service>"
kind = "apm"                                   # apm | rum | logs
span_filter = "<extra filter for entry spans>" # optional
argocd = "~/repos/<repo>-argocd"
values = { sandbox = "<values path>", prod = "<values path>" }
```

### Tests

`plan` on a throwaway argocd repo (the tag commit found, `DD_VERSION` read, a repo behind its
upstream warned, `--at`, incomplete windows); `script` embeds exactly the parameters as one JSON
literal and nothing else changes (a snapshot), and no config value reaches it unescaped;
`queries` arguments. The program's comparison is a pure function in the template, run with `node`
on fixture numbers (skipped when `node` is missing), with the SDK calls stubbed: every verdict
threshold, `sem_dados`, a partial result.

### Files

`src/ws/deploycheck.py`, `src/ws/deploycheck_cli.py`, `src/ws/data/deploy_check.js` (package data),
`skills/deploy-check/SKILL.md`, `skills/deploy-check/references/fallback.md`,
`tests/test_deploycheck.py`. The gate catalog needs no change.

## Confidentiality

- In the repo: generic shapes only (`<prefix>`, `<env tag>`, `<datadog service>`); no Parameter
  Store prefix or realm, AWS profile, account, host, Datadog service name, partner prefix of the
  runtime classes, or real name. Test fixtures use made-up names.
- In `config.toml` (outside git): the mappings of C and D, the legacy handoff glob.
- In private files: the handoff (real names allowed, never secrets or values).
- `ws env check` never handles a value outside memory, never prints one; its output (names and
  `path:line`) may go to the chat, never to the repo.
- `ws mask --check` on the spec and on every new file before committing; the pre-commit hook
  enforces it.

## Parallel build

After Step 0, four agents, one worktree each, disjoint files:

| Agent | Part | Files |
|---|---|---|
| 1 | A: handoff, hooks, setup | `src/ws/handoff.py`, `src/ws/handoff_cli.py`, `templates/handoff.md`, `hooks/context_watch.py`, `hooks/handoff_pointer.py`, `src/ws/bootstrap.py`, `skills/handoff/`, their tests |
| 2 | B: daily by period | `src/ws/period.py`, `standup.py`, `standupsummary.py`, `standupreport.py`, `jira.py`, `taskmodel.py`, `cli.py`, `skills/daily/`, `evals/`, their tests |
| 3 | C: env check | `src/ws/envcheck.py`, `src/ws/envcheck_cli.py`, `tests/test_envcheck.py` |
| 4 | D: deploy-check | `src/ws/deploycheck.py`, `src/ws/deploycheck_cli.py`, `src/ws/data/`, `skills/deploy-check/`, `tests/test_deploycheck.py` |

Each agent runs `uv run pytest -q`, `uv run ruff check` and `uv run ruff format --check` (through
`ws slot` when several run at once), commits on its branch and reports its README rows. The
orchestrator reviews each diff, merges, updates the README and the manual, and the user runs
`ws setup` in a terminal for the hooks (diff and `[s/N]`) and applies the printed settings block.

## Decisions (user, 2026-11-03)

The spec was approved with these answers to its open questions:

1. **Parameter Store source:** the default is `aws` (`describe-parameters` with the environment's
   profile: names only, never a value, no decryption); the user's script stays as the `script`
   option. Script first, in the user's words: every source is called by `ws env check`
   deterministically, and the model only runs the command (the script decrypts every secret of the
   account on each run, filters by substring and needs the three AWS variables exported, which
   Claude sessions do not have).
2. **The front's names in argocd:** reported as they are, under `in_argocd`, with exit 1 until D104
   is merged; no special case.
3. **Context warning:** at 300k, then every 100k, with the one-line notice to the user besides the
   note to the model.
4. **Deploy-check windows:** 30 min before against 30 min after, the after window starting 5 min
   after the deploy; new errors against a 24 h baseline.

## Out of scope

The release automation (`docs/specs/2026-10-27-release-design.md`, next batch); hours per card;
auto-compaction; holidays in the workdays; the GMUD evidence (backlog item 6), which may later reuse
the deploy-check output; any write to argocd, AWS, Datadog, Jira or GitHub.
