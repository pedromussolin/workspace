# Backlog

Open items left by subproject 1 (foundation), found by the final review and its re-review on
2026-10-26. None blocks daily use; each was weighed and parked.

## Next

The new-name check: catches a real name that is not in `names.toml` yet, which none of the items
below covers. Design: [docs/specs/2026-10-26-new-name-check-design.md](specs/2026-10-26-new-name-check-design.md).

## Confidentiality check

Frozen since 2026-10-26: these items move only when a real case shows up.

| Item | Why it waits | Fix when picked up |
|---|---|---|
| `pre-push` does not scan the lines a merge commit itself introduces (a conflict resolution) | `pre-commit` and `pre-merge-commit` catch them at commit time; this only matters when a hook did not run | scan merges with `git show --remerge-diff` in `--range` |
| An AI-added `.secrets-allow` entry needs no human click | the root `CLAUDE.md` asks the agent to say so in the reply | an `ask` permission rule on Edit and Write of `.secrets-allow` |
| File names are not scanned (a file named after a partner passes) | no such file today | check staged paths with the same name rules |
| Assignment shapes still missed: `DB_PASS=…`, camelCase `dbPassword=…`, a `\n` escape right before the keyword | rare in planning notes | widen `secret-assignment`, with prose and placeholder tests |
| Secret formats outside the spec's set: PEM headers, AWS `AKIA` keys, `Bearer`/JWT, Azure `AccountKey=` | the spec fixed the rule set | add one rule per format |
| `secret-assignment` is slow on very long `a_a_a_…` lines (seconds at 20 000 characters) | only synthetic or generated lines trigger it | bound the identifier prefix |
| PT-BR commit messages where senha, token or secret is followed by a colon and a word are blocked by `commit-msg` | rewording the message is enough | a message-scoped allow entry, or skip prose shapes in messages |
| `#` lines are skipped by `commit-msg` | same as git's comment stripping; `pre-push` scans the stored message | none needed unless messages are kept with `--cleanup=verbatim` |

## Gates and tools

| Item | Why it waits | Fix when picked up |
|---|---|---|
| The bypass gate misses `xargs git …`, `find -exec git …`, git aliases and quoted operators | best effort; `pre-push` scans every pushed commit | none planned |
| The bypass gate blocks plain reads such as `git config core.hooksPath` and `git grep -e --no-verify` | workaround: `git config --get`, or `--` before the pattern | allow read-only `git config` forms |
| `ws slot` overrides an inherited ignored SIGINT, and Ctrl+C reaches the child twice | harmless for build and test commands | keep `SIG_IGN` when inherited; do not forward SIGINT from a tty |
| The `check-secrets` tail line suggests `.secrets-allow` for a co-author trailer finding, which cannot be allowed | cosmetic | a rule-specific hint |
| README `ws check-secrets` row omits `--message` and `--range` | docs drift | update the row |
| The Claude `Read` deny rule does not cover `cat` of `~/.config/workspace/credentials` | the file does not exist yet | subproject 2, with the credentials |

## Projects and skills

| Item | Why it waits | Fix when picked up |
|---|---|---|
| `skills/change-request/references/tests.md` keeps the old 12-minute Docker recipe | a faster recipe exists in the user's notes | update the recipe |
| `projects/whitelabel-restructure/CONTINUE.md` "Leia antes" does not name the root `CLAUDE.md` | the project is active in another chat; the project `CLAUDE.md` already points there | one line, when that chat is idle |

## Subagents: model and effort per role

Decided with the user on 2026-10-27, after the phase A plan picked a model and an effort per task
by hand. The common practice is a fixed model per role, in configuration, chosen by the
orchestrator by role name; routing by a classifier belongs to the API layer, not to coding agents.

| Item | Why it waits | Fix when picked up |
|---|---|---|
| Agent definitions per role, versioned in the repo | phase A first | `agents/<role>.md` with `model`, `effort` and tools in the frontmatter (light implementer, implementer, reviewer, final reviewer), linked into `~/.claude/agents` by `ws setup` like the skills. Two final reviewers (user, 2026-10-27): Opus when the change is large, crosses several parts, or touches security or writes outside (Jira, GitHub, GMUD); Sonnet with high effort for a contained change with a fixed contract and task reviews done |
| The role of each task stays in the plan | already done by hand in the phase A plan ("Execution" table) | the plan template names a role per task instead of a model; no skill, since a skill would keep the rule as prose |
| A hard rule against a subagent that inherits the orchestrator's model | today it depends on remembering to set `model` | a Claude Code `PreToolUse` hook on `Agent` that blocks a call with neither a role nor a `model` |

## Next skills

Chosen by the user on 2026-10-27, in this order of priority: 1, 3, 2, then 4, 5, 6 and 7.

Status on 2026-10-27 (afternoon): **3 done** (`ws checkpoint` and the skill, on `main`); **1 done**
(`ws card` and the `/card` skill; the `ask` rules and the hook are installed; the first real write
waits for the user's Jira API key); **2 designed** (`docs/specs/2026-10-27-release-design.md`, with
decisions to confirm); 4–7 not started. Each one
follows "script first" (root `CLAUDE.md`): the `ws` command does the deterministic part, the skill
decides, asks and writes the prose.

| # | Skill | What it does | The script part |
|---|---|---|---|
| 1 | Jira write (phase B of the task-driven-work spec) | create a card, move its status, comment, log work; always a preview and the user's approval first; only the user's own cards; title prefix = epic prefix. Card model (from the user's own cards, 2026-10-27): type Tarefa; always filled (user's rule): the required fields plus parent epic, priority, assignee (the user) and sprint; description sections `## Contexto`, `## Desenho combinado`, `## A fazer antes de implementar`, `## Pronto quando`; every card has a start date and a due date (user's choice). Design: `docs/specs/2026-10-27-card-write-design.md` | `ws task plan` writes the plan file, `ws task apply --dry-run` validates it, `ws task apply` executes through the REST API (the MCP as fallback); the daily's status suggestions feed the plan |
| 2 | Release | release branches `release/YYYYMMDD` and `-sdbx` in the company repos, PRs to master, the sandbox merge, moving a release to another date (close and reopen the PRs) | `ws release new DATE`, `ws release move OLD NEW`, `ws release status`; replaces the one-off scripts of each deploy; prints the PR links for the GMUD Design: `docs/specs/2026-10-27-release-design.md`. |
| 3 | Checkpoint (end of an iteration) | update `CONTINUE.md` (with "## Próximo passo", which the daily reads), the decisions and the task table, then commit and push the workspace | `ws checkpoint check` validates the sections, `ws checkpoint commit` runs the git steps; the model writes only the text Design: `docs/specs/2026-10-27-checkpoint-design.md`. |
| 4 | Replica query | read-only queries on the production replica, one at a time, with a timeout, formatted for the DBA review | `ws replica query FILE` enforces a read-only transaction, `statement_timeout` and a single statement, and writes the result outside the repo |
| 5 | Local validation | the right checks of each company repo before any environment (Docker for the assignment backend, `validate.sh` for the front, the heavy-command slot) | `ws validate REPO` runs the per-repo recipe from the local config |
| 6 | GMUD evidence (extends `change-request`) | gather the Datadog numbers and the screenshots of a deploy | a script per evidence kind (Playwright screenshots, Datadog queries through the API when a key exists, the MCP otherwise) |
| 7 | Board review | the user's open cards (status not done or cancelled), grouped by epic, the stale ones flagged (no update and no own commit for N workdays), and what to close or move; it took over the open-card list the daily dropped on 2026-10-27 | `ws board review` prints the JSON (cards through `ws task list`, activity through `ws standup collect`, the rules in code); any change goes through item 1's `ws task apply` with approval |

## Daily

| Item | Why it waits | Fix when picked up |
|---|---|---|
| In the MCP fallback the model still builds `cards.json` by hand (and the Write tool may be denied in a sandbox) | the REST path (`ws task list`) is the main path once the user creates the Jira API key, which removes the hand-built file in daily use | the user runs `ws config token jira` in their own terminal; if the MCP path stays relevant, a `ws task import` that maps the raw MCP answer to compact cards with `card_from_issue` |
| A full eval run costs about 6–7.5 USD (2026-10-27) | the suite exists; one-run validations cost about 1 USD | full runs only before merging a big change to the skill; one-run validations for small ones |
