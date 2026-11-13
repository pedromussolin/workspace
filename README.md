# workspace

Personal, private repo. It is the single home for planning projects (`projects/`) and personal
automations. It is AI first: Claude does the judgment work through skills and MCP servers, and the
`ws` CLI is the deterministic fallback for when an MCP server fails. Rules for people and agents
are in [CLAUDE.md](CLAUDE.md); the design is in
[docs/specs/](docs/specs/2026-10-22-workspace-foundation-design.md).

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone <this repo> ~/repos/workspace
cd ~/repos/workspace
uv tool install --editable .
ws setup
```

`ws setup` is idempotent and fixes by itself what it can, with no admin password:

- sets `core.hooksPath=.githooks` in the clone and makes the four hooks (`pre-commit`,
  `pre-merge-commit`, `commit-msg`, `pre-push`) executable; git skips a hook that is not;
- symlinks `skills/*` into `~/.claude/skills/` (the folder is created only when there is a skill);
- creates `~/.config/workspace/` and `private/` and fixes the modes below with `chmod`;
- downloads the common-word dictionaries of the new-word check, described below.

It prints a `fixed:` line per change and a `needs you:` line per problem left, and exits 0 when
nothing is left. What stays for you: a missing `names.toml`, a skill link that points elsewhere,
something that overrides the hooks path, and the Claude Code gates. `ws setup` never edits
`~/.claude/settings.json`: it prints one JSON block with every gate that is missing, and Claude
applies it after you approve.

`ws setup --check` is read-only and uses no network: it changes nothing and lists what setup would
fix (`would fix:`) and what needs you; it exits 1 unless everything is already in place.

The dictionaries are the Debian word lists `wamerican` and `wbrazilian`. They are read from
`~/.local/share/workspace/dict/` and then from `/usr/share/dict/`. When neither place has both
files, setup runs `apt-get download wamerican wbrazilian` in a temporary folder of
`~/.cache/workspace/` (apt checks the packages against its signed index, and no root is needed),
unpacks them with `dpkg -x` and copies the two files to the data dir. Without `apt-get`, or if the
download fails, setup says so and the manual command is `sudo apt-get install wamerican
wbrazilian`; the other steps still run.

Everything sensitive lives outside the repo, in `~/.config/workspace/`:

| File | Content |
|---|---|
| `names.toml` | real name to analog table and company domains; the single source for `ws mask` and the secrets hook |
| `private/<slug>.md` | real values of one project (hosts, URLs, real names behind the analogs) |
| `config.toml`, `credentials` | Jira site, and the Jira and GitHub tokens (`credentials`, mode 600) |

The folder is mode 700 and `names.toml` and `credentials` are mode 600; `ws setup` fixes any other
mode and says what it fixed.

Local data that never enters git lives in `~/.local/share/workspace/`: the dictionaries, and
`projects/<slug>/` for each project's worktrees, logs, locks, deploy files and evidence with real
data (`ws project new` creates it, mode 700). `~/.cache/workspace/` holds only what can be rebuilt.

## Local config

`~/.config/workspace/config.toml` holds the Jira and standup settings, with no secret in it. Create
it by hand; the values below are placeholders:

```toml
[jira]
site = "https://<site>.atlassian.net"
email = "<you>@<company>"
project = "<PROJECT>"
board_id = <board id>
start_date_field = "customfield_<n>"
sprint_field = "customfield_<n>"

[jira.types]
task = "<issue type id>"
bug = "<issue type id>"
hotfix = "<issue type id>"
improvement = "<issue type id>"
feature = "<issue type id>"
epic = "<issue type id>"
initiative = "<issue type id>"

[jira.links]
blocks = "<link type name>"
relates = "<link type name>"

[jira.status_overrides]
"Tarefas pendentes" = "todo"
"Em análise" = "todo"
"Em andamento" = "in_progress"
"Code Review" = "review"
"In Validation" = "validation"
"Verify" = "validation"
"Ready Deploy" = "ready_deploy"
"Block" = "blocked"
"Concluído" = "done"
"Cancelada" = "cancelled"

[tracker]
kind = "jira"

[identity]
email = "<you>@<company>"

[people."dev-<10 hex digits>"]
jira = "<account id>"
label = "<short name>"

[standup]
repo_roots = ["~/repos"]
stale_workdays = 3
```

- `[tracker] kind` names the tracker adapter; absent means `jira`, the only one that exists.
- `[jira.types]` maps each neutral card type to the id of the issue type in the project, and
  `[jira.links]` maps `blocks` and `relates` to the link type name. `[jira] issue_type` was
  replaced by `[jira.types]` and is refused: delete the `issue_type` line from `[jira]`, then
  run `ws tracker discover` and paste its output into `config.toml`.
- `[identity] email` is yours (absent means `[jira] email`). `[people."<dev id>"]` maps a dev id
  (`dev-` and the first 10 hex digits of the SHA-256 of the trimmed, lowercased e-mail) to the
  person's id in each tracker; `label` is only a reminder.

- `[jira.status_overrides]` maps a Jira status name to the neutral one (`todo`, `in_progress`,
  `review`, `validation`, `ready_deploy`, `blocked`, `done`, `cancelled`) when the status category alone is not enough.
- `[standup]` is optional; the two values above are its defaults. There is no e-mail to set for
  git: each repo's own `user.email` picks the commits.
- The keys after `email` (and `[jira.types]`, `[jira.links]`) are read by `ws card`; a missing one
  exits 2 naming it.
  `ws card` only touches cards of `project`.
- The API key must be an unscoped token: a scoped token only works through the
  `api.atlassian.com/ex/jira/<cloudId>` gateway, and `ws` calls the site URL.
- `ws setup` asks for `permissions.ask` rules on `Bash(ws card apply:*)`, on the Atlassian, GitHub
  and GitKraken write tools, and for the approval gate (see "Claude Code hooks" below), so every
  write needs your yes in Claude Code. `ws card apply --approve` refuses (exit 2) without the rule
  and the gate registered for `Bash`, and (exit 1) when it runs in the same shell session as the
  preview (a single command line cannot preview and apply; by hand, run the apply in another
  terminal tab).
- `site` must be `https://<name>.atlassian.net`: the API key is never sent anywhere else, and a
  `credentials` file that is a symlink or not yours is refused.
- The Jira API key is created on the Atlassian site and saved with `ws config token jira`, run in
  your own terminal, outside Claude (the command refuses to run without a terminal). It is stored
  in `~/.config/workspace/credentials` (mode 600) and never pasted in a chat.

### `[board]`

`ws board` moves cards by what the code proves. Without a `[board]` table in `config.toml` it exits
2 and says what to add, and the `daily` goes on with the activity alone. An environment is a
question (which commits are in it?) answered by one proof; a profile is an ordered list of
environments, and each repo, or glob of repos, uses one profile. The names below are placeholders:

```toml
[board]
remote = "origin"            # default
lookback_days = 120          # default
fetch = true                 # default
default_profile = "gitops"   # the profile of every repo without its own

# A profile: environments in order, statuses rising. Each environment has one proof.
[[board.profiles.gitops.environments]]
name = "sandbox"
status = "validation"
proof = "branch"
branches = ["sandbox", "staging"]   # the first that exists on the remote

[[board.profiles.gitops.environments]]
name = "master"
status = "ready_deploy"
proof = "branch"
branches = ["master", "main"]

[[board.profiles.gitops.environments]]
name = "production"
status = "done"
proof = "file"                      # GitOps: image tags written in a deploy repo
deploy_repo = "{repo}-argocd"
deploy_branch = "master"
image_tag = 'prod-([0-9a-f]{7,40})'

# Release by tag in the code repo itself.
[[board.profiles.release-tag.environments]]
name = "main"
status = "ready_deploy"
proof = "branch"
branches = ["main"]

[[board.profiles.release-tag.environments]]
name = "production"
status = "done"
proof = "tag"
tag = "v*"                          # the most recent tag matching the glob

# Anything else (a deploy API, Kubernetes, an observability tool): a read-only command that
# prints the deployed shas, one per line.
[[board.profiles.api.environments]]
name = "production"
status = "done"
proof = "command"
command = ["~/bin/deployed-sha", "{repo}", "{env}"]
timeout = 20                        # seconds, default 20

[board.repos."some-repo"]
profile = "release-tag"

[board.repos."data-*"]
inactive = ["sandbox"]              # declared, switched off: proves nothing in these repos

[board.repos."*-argocd"]
ignore = true                       # deploy repos are proof sources, not code

[board.repos."*-workspace"]
ignore = true

# Status names in the tracker for the statuses a move can reach (global: one board).
[board.statuses]
in_progress = "Em andamento"
validation = "In Validation"
ready_deploy = "Ready Deploy"
done = "Concluído"
```

- Each commit takes the highest environment that contains it; the card takes the lowest of its
  commits. The statuses of a profile must rise along its list.
- Proofs: `branch` (the tip of the first branch that exists on the remote), `tag` (the most recent
  tag matching the glob), `file` (the commit shas that `image_tag` captures in the deploy repo's
  branch) and `command` (a program that prints the deployed shas, one per line).
- A proof that errors holds the environment (fails closed): it stays in the repo's cap and no
  commit of that repo counts as being there, so the card stays below it.
  - `command`: a failure to run, a non-zero exit, a timeout, a line that is not a sha or a sha
    that does not resolve holds, with the warning `proof <repo>/<env>: ...`.
  - `file`: a `git grep` error holds, and so does a captured sha that does not resolve in the
    repo while others do (warning `deploy <repo>: tag <tag> not found in this repo`), both with
    the prefix `deploy <repo>: ...`.
  - `file`, not an error: a deploy repo that is not found (`deploy <repo>: <deploy repo> not
    found`) or no captured sha resolving in the repo (`deploy <repo>: no image tag of this repo
    in <deploy repo>`) means the environment is ignored for that repo: it is out of the cap and
    holds nothing.
- A `tag` proof fetches with `--tags`. A tag moved on the remote makes that repo's fetch fail, and
  its data is then stale (warning `fetch <repo>: ...`).
- A deploy repo shared by several apps needs an `image_tag` specific to the app, so only that
  app's tags are captured.
- A `command` proof must only read (it asks, it never changes anything): it runs without a shell,
  with `~`, `{repo}` and `{env}` expanded, and is stopped after `timeout` seconds. What it does is
  your responsibility.
- A repo uses the table whose key is its exact name, else the first glob that matches, else
  `default_profile`. `ignore = true` leaves a repo out; `inactive` switches environments off.
- `[board.statuses]` needs a name for every status any profile uses, plus `in_progress`, and each
  name must map back to its own status through `[jira.status_overrides]`.
- A bad value exits 2 with the key path.

## What protects the repo

Protection starts after `ws setup`: a fresh clone has no git hooks. From then on, the hooks call
`ws check-secrets` (secret patterns, real names, company domains) and fail closed, so without
`names.toml` they block everything:

| Hook | Checks |
|---|---|
| `pre-commit`, `pre-merge-commit` | the staged added lines (for a merge, every incoming line); also warns about new words |
| `commit-msg` | the commit message; also warns about new words |
| `pre-push` | every pushed commit: lines, message, author and committer e-mails; also blocks on new words |

### Claude Code hooks

The approval gate (`hooks/approval_gate.py`, rules in `hooks/gate/`) is a `PreToolUse` hook for
`Bash` and `mcp__*` tools: it asks you before a write that leaves the machine (a push, a GitHub,
GitKraken or Atlassian write, a card apply) and shows what will be sent. Two more hooks block
commits with a co-author trailer and hook bypasses. `ws setup` copies them to
`~/.claude/hooks/workspace/` (read-only files and a `manifest.json` of SHA-256 sums), reports a
missing, stale, edited or extra file (`--check` only reports) and prints the settings JSON that
registers `python3 -I -B "<copy>/<script>"` with a 30 s timeout. It updates the copy only when you
run it yourself in a terminal: it shows the diff of each changed file and asks `[s/N]`; run by an
agent it writes nothing there. The registration: the gate with the matcher `Bash|mcp__.*`, the other two
with `Bash`. Registrations that still point at the repo's `hooks/` or at `ask_card_apply.py` are
reported with what replaces them. The folder can be moved with `WS_CLAUDE_HOOKS_DIR`.

Another clone whose settings still register the old card hook keeps working:
`hooks/ask_card_apply.py` now runs the gate. After a pull, run `ws setup` there and apply what
it prints. The hooks need the system `python3` at 3.11 or newer (`ws setup` checks it); the
`[gate]` keys, the GitHub token and the `env` block below are per person and optional.
An MCP server that `hooks/gate/catalog.json` does not list asks before every call, reads
included, until its tools are classified there (a commit, so every clone gets them). The catalog
has a `pass` list (reads, local-only changes) and an `ask` list (writes) per server; a tool in
neither is unclassified, and the gate records its name (never its parameters) in
`~/.local/share/workspace/gate/unclassified.json`. `ws setup` warns about configured servers the
catalog lacks, and `ws gate catalog` lists them with the recorded tools.

The optional `[gate]` table of `config.toml` tunes the gate (`ws setup` reports a wrong type and
never writes it):

| Key | Meaning |
|---|---|
| `push_without_asking` | list of repo paths (`~` allowed) where a plain push goes without asking, when `push_remotes` also matches |
| `push_remotes` | list of push URLs of `origin` allowed for that no-box push (`git remote get-url --push --all origin`); missing or different, the push asks |
| `personal_github_owners` | list of GitHub owners that get the confidentiality check before a write |
| `environment_branches` | list of environment branches (`master`, `main`, `sandbox`, `staging`): a `git push`, a GitHub file or ref write and a PR merge into one of them are blocked; missing, the policy is off |
| `direct_push_repos` | `fnmatch` patterns on the repo name (`*-argocd`) where a write to an environment branch asks, with a warning, instead of being blocked; PR merges into one stay blocked |

#### Secrets outside the session environment

Every command Claude runs inherits the session environment, so a token exported in `~/.bashrc`
(a GitHub token, an API key) is readable by it. The GitHub token lives in
`~/.config/workspace/credentials` (`ws config token github`, in a terminal) and reaches the GitHub
MCP server through Claude Code's `headersHelper`, which runs `ws mcp-headers github` when the
server connects. The server is a user-scope one named `github` in `~/.claude.json`; its tools are
`mcp__github__*`, and the write ones are in the `ask` rules. Other secret variables are blanked in
Claude sessions only, with the `env` block of `~/.claude/settings.json` (`{"env": {"NAME": ""}}`),
so terminals and VS Code keep them. `ws setup` never writes those two files: it lists as
`needs you` the variables whose name looks like a secret (names only, never values), the settings
snippet that blanks them, and the exact `claude mcp add-json github '<json>' --scope user` command
when the server is missing or different. `WS_CLAUDE_JSON` and `WS_BIN` move `~/.claude.json` and the
`ws` path used in that command.

The gate `hooks/block_hook_bypass.py` blocks `--no-verify`, `git commit -n` and any
`core.hooksPath` override, in every repo; `ws setup` checks that it is registered. Exceptions go in
`.secrets-allow`, which is read from the index (an entry counts once staged) and excuses only the
span it matches, not the rest of the line.

The check cannot see names missing from `names.toml` or the content of binary files (a staged binary
is reported, not read).

A new-word gate covers the first gap: a capitalized word of three letters or more, in an added line
(outside the code of `ws`: `src/`, `tests/`, `hooks/`, `.githooks/`) or a commit message, that the
remote state, `.known-words` and the analogs of `names.toml` do not know may be a real name that has
no entry yet. The common-word dictionaries clear such a word only at the start of a sentence (after
a period, colon, `!`, `?`, a table pipe, or at the start of a line, list item or heading); in the
middle of one it is still reported, because a name may be an ordinary word. The commit hooks only
warn; `pre-push` blocks until each word is answered with `ws names add` (real name) or `ws names
known` (harmless term). The pending list is computed from the unpushed commits, nothing is stored.
Design: [docs/specs/](docs/specs/2026-10-26-new-name-check-design.md).

## The `ws` command

| Command | What it does |
|---|---|
| `ws setup [--check]` | Fixes by itself the hooks path and modes, the skill links, `~/.config/workspace/` (folders and modes) and the common-word dictionaries; prints `fixed:` and `needs you:` lines, the Claude Code gates as one JSON block; `--check` only reports |
| `ws check-secrets [--staged \| --all \| PATH…]` | Scans for secret patterns, real names and company domains; the git hooks run it |
| `ws mask [--in-place \| --check] [FILE \| -]` | Replaces real names with analogs; `--check` exits 1 if a real name remains |
| `ws names check (--staged \| --message FILE \| --range REVS) [--against REV] [--tip REV] [--warn]` | Lists the new words (capitalized words unknown to the remote state, `.known-words` and the analogs); exit 1 when there are any, always 0 with `--warn`; the hooks run it |
| `ws names pending [--range REVS] [--json]` | The new words of the unpushed commits, with where each appears |
| `ws names known WORD…` | Appends harmless words to `.known-words`, without repeats; commit the file |
| `ws names add REAL --analog ANALOG [--case-sensitive]` | Appends a real name and its analog to `names.toml`, keeping its mode and content; refuses a duplicate |
| `ws names review` | Asks in the terminal about each pending word (real name, harmless, skip), then lists the files and unpushed commits that carry the real names added |
| `ws project new <slug>` | Copies `templates/project/` into `projects/<slug>/` |
| `ws slot [-n N] -- <cmd>` | Runs a heavy command in one of N slots (file lock), so parallel agents do not exhaust memory; the command holds the lock and gets SIGTERM, SIGHUP and SIGINT forwarded, so the slot lasts until it exits |
| `ws config token jira` | Reads the Jira API key from the terminal (hidden) and stores it in `~/.config/workspace/credentials` with mode 600; refuses to run outside a terminal |
| `ws config token github` | Same for the GitHub token (`[github]` table of the same file; the other tables are kept); `ws mcp-headers github` reads it back |
| `ws mcp-headers github` | Meant for Claude Code's `headersHelper`: prints `{"Authorization": "Bearer <token>"}` and nothing else; exit 2 without a token, or when `CLAUDE_CODE_MCP_SERVER_NAME` is unset (a guard against casual use, not a barrier: the approval gate asks before any command that names `ws mcp-headers`) |
| `ws gate catalog [--json]` | Lists the MCP servers configured in Claude Code (plugins, user and local scope, claude.ai connectors; read-only, names only) that `hooks/gate/catalog.json` does not know, and the tools the gate asked about without knowing them, with counts and the next command |
| `ws gate catalog pass SERVER TOOL…` | Puts the tools in the `pass` list of the server in the repo's `catalog.json` (creating the server), takes them out of `ask` and of the unclassified record; commit the file and run `ws setup` to update the protected copy |
| `ws gate catalog ask SERVER TOOL…` | Same for the `ask` list (writes); a name outside `[A-Za-z0-9_.-]+` is refused |
| `ws standup collect [--today YYYY-MM-DD]` | Prints as JSON the activity of the user since the previous workday: commits and branches of every git repo under `repo_roots`, PRs from one GitHub search, the "Próximo passo" of each project and `warnings`; the skill `daily` runs it |
| `ws task list [--since YYYY-MM-DD] [--role mine\|following\|all]` | Prints the user's Jira cards as compact JSON (each card with `is_epic`) through the REST API (the main source of the `daily` skill; the Atlassian MCP is its fallback); exit 2 without config or API key, exit 1 on a Jira error; `--role` picks the cards where the user is the assignee (`mine`, default), the reporter with someone else as assignee (`following`), or both (`all`) |
| `ws item new PROJECT --type T [--epic K] [--assignee A] [--reporter R] --heading "..." [--slug S]` | Creates an item file in `projects/<project>/tasks/` from the template of the type and prints its repo-relative path; `--epic` is optional (an item can exist before its epic); `me` is written as the user's dev id |
| `ws item check [PROJECT...] [--tracker]` | Validates the items against `project.toml` and each other and prints `{"problems", "drift", "pending", "orphans"}`; offline by default (the last three stay empty), with `--tracker` it compares each item with its card; exit 1 with problems, 2 setup, 3 tracker error |
| `ws item drafts [PROJECT...] [--only REFS]` | Writes the `/card` drafts that align the tracker with the items (edits, links, creates) and prints `{"folder", "count", "need_text", "waiting", "by_hand"}`; nothing goes to the tracker |
| `ws item pull ITEM --fields F,...` | Copies the tracker's values of those contract keys into the item, leaving every other byte; a link list (`blocks`, `blocked_by`, `relates`) keeps the entries whose item has no card yet and the item's spelling of the links the card has, gains the card's other links and loses the rest; prints `{"path", "changed"}` with the old and the written value of each changed key |
| `ws item sync [PROJECT...]` | Rewrites each tracked item's `[tracker]` table (status, priority, due, sprint, synced) from its card |
| `ws item table PROJECT` | Refreshes the items table of the project's `README.md` between its markers |
| `ws item set-card ITEM (REF \| --none)` | Settles an item whose create was uncertain or whose write-back failed: records the card, or releases the item |
| `ws standup report --activity FILE [--cards FILE] [--board FILE] [--today YYYY-MM-DD] [--top N]` | Groups the activity by task key and prints, as JSON, the `yesterday` and `today` topics, the `next_steps`, the `blockers`, the commits without a key and the `warnings`, with the status suggestions inside their task; `--top N` keeps only the first N of `yesterday` and `today` and `more` counts what was cut; `moves` lists every card move; `--board FILE` (the `ws board status` output) brings the status suggestions, `moves` and `to_confirm`, and its warnings join `warnings`; without `--cards` Jira is unavailable and the report comes from the activity alone (exit 2 on bad input); the skill `daily` writes the standup from it (short by default, with `--top 3`; detailed on request) |
| `ws card check DRAFT` | Validates a card draft (create, edit, move, comment, worklog, link) against live Jira and prints a JSON verdict: `ok`, `problems`, `warnings` and the resolved values; exit 1 a rule failed, 2 setup needed, 3 Jira refused or unreachable |
| `ws card epics` | Lists the epics of your open cards, plus the epics and initiatives you own and the open epics under those initiatives (`key`, `title`, `prefix`, `status`, `level`, `parent`) |
| `ws tracker discover` | Prints the `[jira.types]` and `[jira.links]` blocks of the project's Jira, for you to paste in `config.toml` (read only); exit 2 on setup, 3 when Jira refuses |
| `ws people me` / `ws people add EMAIL [--account ID]` | `me` prints your dev id; `add` prints the `[people."dev-…"]` block of a colleague (searches the account by e-mail unless `--account`; never prints the e-mail; read only) |
| `ws card preview PATH` | Checks a draft or a folder of drafts (under `cards/drafts/`), prints the PT-BR preview and the requests, stores a pending record and prints its approval code; writes nothing to Jira |
| `ws card apply PATH --approve CODE` | The only command that writes: re-checks against live Jira and sends exactly what the preview showed, once; Claude Code asks you first (the `ask` rule and the approval gate, whose box shows the preview's summary), exit 2 when those are not set up; on a real terminal it shows the summary and asks `Gravar no Jira? [s/N]` instead; a failed or uncertain draft goes to `cards/uncertain/` |
| `ws board status --cards FILE [--today YYYY-MM-DD]` | Finds, for the open cards of `FILE` (the `ws task list` output), the highest environment (`[board]`) that holds their commits and prints as JSON the `moves` (key, from, to, environment, stale), the cards `held` and `limited`, the `to_confirm` and the `warnings`; runs `git fetch` in every repo first; reads Jira only through the file; exit 2 without config, `[board]` or with bad input |
| `ws board drafts --board FILE` | Writes one `move` draft per move of the `ws board status` output into a new folder under `cards/drafts/` and prints `{"folder", "count"}`; `ws card preview` and `ws card apply` do the rest |
| `ws task status --cards FILE --activity FILE [--today YYYY-MM-DD]` | Compares the cards with the activity and prints `tasks` (the neutral tasks) and `stuck` (active cards with no activity for the configured workdays) |
| `ws git assemble --base B --from WIP --to FINAL` | Builds FINAL from B by cherry-picking WIP, optionally rewriting subjects (keyed by subject or sha), and checks the 72-character limit; refuses a dirty work tree and merge commits in the range |
| `ws git merge-rehearsal --repo R --base B BRANCH…` | Merges the branches over B in a throwaway worktree (a fresh checkout with no dependencies installed), applies known conflict resolutions, runs an optional check |
| `ws checkpoint check SLUG` | Validates the project's `CONTINUE.md` (required sections `## Onde parei` and `## Próximo passo` filled in, size limit on the next step) and `decisions.md`; prints a JSON verdict, exit 0 when ok, 1 otherwise |
| `ws checkpoint diff SLUG [--include PATH...]` | Shows what a checkpoint commit would take: the project's changed and new files and the diffstat; new binary files, or over-200 KB files under `evidence/` or `attachments/`, are listed as refused unless included |
| `ws checkpoint commit SLUG -m MESSAGE [--include PATH...] [--amend]` | On `main` only, and only with the repo hooks installed (`ws setup`): validates the message and the check, refuses changes outside `projects/<slug>/` (the one exception is `.known-words`, committed along), refuses unpushed commits touching other paths, refuses new binaries (any folder) and large files (`evidence/`, `attachments/`) without `--include`, commits that folder (`--amend` rewrites the single unpushed checkpoint commit), pulls with rebase (a conflict aborts it and keeps the commit), checks again and pushes, printing `commits_pushed`; network calls time out after 120 s; the skill `checkpoint` runs it |

Development: `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`.

## Evals

`skills/daily` has an eval suite in `evals/`, run by `claude plugin eval` (Claude Code 2.1.269 or
later). Every run is a real Claude session on your plan, about 0.25 USD per standup run. The data
is made up: a fixed Monday, fake git repos and a fake Jira site, with the Atlassian tools answered
by `evals/mocks/`. `.claude-plugin/plugin.json` declares a fake `atlassian` MCP server
(`command: false`) only so those tools can be mocked: do not install or enable this repo as a
plugin.

The sandbox of the runs needs `bubblewrap` and `socat` (`ws setup` tells you when they are
missing). Run the suite through the script, which also puts a `ws` of this checkout first on
`PATH` (the installed one is not visible inside the sandbox):

```bash
scripts/run-evals                                              # every case, 3 runs, with and without the plugin
scripts/run-evals --case jira-down --runs 1 --ablation none    # one case, one run
```

The first run asks "Trust this plugin directory?"; other arguments go to `claude plugin eval`
(`--tag daily` runs only the cases that use the skill). The suite refuses a repo whose `.venv` was
built with uv's default hard links: the script says so, and `rm -rf .venv && UV_LINK_MODE=copy uv
sync` fixes it. A case passes at score 1.0, and the delta against the run without the plugin should
be positive on `daily-request`, `monday-includes-friday` and `topics-trace-to-data`. Reports land
in `evals/results/` (not versioned).

| Case | Passes when |
|---|---|
| `daily-request` | "daily" produces the short standup (Ontem, Hoje, Impedimentos) |
| `bug-request-no-standup` | "bom dia, me ajuda com esse bug" gets no standup |
| `plain-greeting-no-standup` | "bom dia" alone gets no standup |
| `monday-includes-friday` | on a Monday, "daily detalhado" has Friday's card key under Ontem and not Thursday's |
| `topics-trace-to-data` | every task line of the short text ends with a card key that exists, with no sha, PR number or repo name |
| `out-of-sync-card` | the short text's "Para você:" note holds the suggested moves, and no write tool is called |
| `jira-down` | with Jira failing, the "Para você:" note says "Jira indisponível", Impedimentos says "indisponível" and nothing is written |
| `daily-detailed` | "daily detalhado" puts the suggestion inside the card's topic and summarises the commits without a key |

## Projects

Prose under `projects/` is in PT-BR; folder and file names are in English.

| Project | What it is |
|---|---|
| [artemis-v2](projects/artemis-v2/README.md) | Planning of V2 of the Artemis project: closing and reconciliation of settlement batches, and taking over the Mercato Libero settlement flow |
| [whitelabel-restructure](projects/whitelabel-restructure/README.md) | Epic that restructures the partner portal front end: brand themes, dark mode, own components, new architecture |
| [valids](projects/valids/README.md) | The VALIDs feature: the controllership's allowance dashboard (PDD) on the partner portal, fed by the data lake |
| [operations-screens-migration](projects/operations-screens-migration/README.md) | Takeover of the screens, routines and tools a departing developer built for the operations team on an automation EC2 (provisional name) |
| [ai-studies](projects/ai-studies/README.md) | Study guide of the AI concepts used in this workspace |
| [standalone](projects/standalone/README.md) | Tasks that belong to no project |

New projects start with `ws project new <slug>`.

A project with a `project.toml` (`epics`, the project's epic refs, and an optional initiative) keeps
one item file per task in `tasks/`. The front matter holds the card's contract (`card`, `type`,
`epic`, `assignee`, `reporter`, `blocks`, `blocked_by`, `relates`, `docs`; people as dev ids, never
`me`) and a `[tracker]` table that only `ws item sync` writes. The `ws item` commands never write to
the tracker; `/card` does. See `docs/specs/2026-11-13-task-items-design.md`.
