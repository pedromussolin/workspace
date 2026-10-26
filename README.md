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
| `config.toml`, `credentials` | Jira site and API token (mode 600), created with the Jira subprojects |

The folder is mode 700 and `names.toml` and `credentials` are mode 600; `ws setup` fixes any other
mode and says what it fixed.

Local data that never enters git lives in `~/.local/share/workspace/`: the dictionaries, and
`projects/<slug>/` for each project's worktrees, logs, locks, deploy files and evidence with real
data (`ws project new` creates it, mode 700). `~/.cache/workspace/` holds only what can be rebuilt.

## What protects the repo

Protection starts after `ws setup`: a fresh clone has no git hooks. From then on, the hooks call
`ws check-secrets` (secret patterns, real names, company domains) and fail closed, so without
`names.toml` they block everything:

| Hook | Checks |
|---|---|
| `pre-commit`, `pre-merge-commit` | the staged added lines (for a merge, every incoming line); also warns about new words |
| `commit-msg` | the commit message; also warns about new words |
| `pre-push` | every pushed commit: lines, message, author and committer e-mails; also blocks on new words |

A Claude Code gate, `hooks/block_hook_bypass.py`, blocks `--no-verify`, `git commit -n` and any
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
| `ws git assemble --base B --from WIP --to FINAL` | Builds FINAL from B by cherry-picking WIP, optionally rewriting subjects (keyed by subject or sha), and checks the 72-character limit; refuses a dirty work tree and merge commits in the range |
| `ws git merge-rehearsal --repo R --base B BRANCH…` | Merges the branches over B in a throwaway worktree (a fresh checkout with no dependencies installed), applies known conflict resolutions, runs an optional check |

Development: `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`.

## Projects

Prose under `projects/` is in PT-BR; folder and file names are in English.

| Project | What it is |
|---|---|
| [artemis-v2](projects/artemis-v2/README.md) | Planning of V2 of the Artemis project: closing and reconciliation of settlement batches |
| [whitelabel-restructure](projects/whitelabel-restructure/README.md) | Epic that restructures the partner portal front end: brand themes, dark mode, own components, new architecture |
| [ai-studies](projects/ai-studies/README.md) | Study guide of the AI concepts used in this workspace |
| [standalone](projects/standalone/README.md) | Tasks that belong to no project |

New projects start with `ws project new <slug>`.
