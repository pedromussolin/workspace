# workspace

Personal, private repo. It is the single home for planning projects (`projetos/`) and personal
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

`ws setup` is idempotent. It sets `core.hooksPath=.githooks` in the clone, symlinks `skills/*` into
`~/.claude/skills/`, checks that every file in `.githooks/` is executable and that the hooks path
resolves to it, checks the files below (and their modes) and the Claude Code gates, and prints what
is missing. It never edits `~/.claude/settings.json`; it prints the JSON to add.

Everything sensitive lives outside the repo, in `~/.config/workspace/`:

| File | Content |
|---|---|
| `names.toml` | real name to analog table and company domains; the single source for `ws mask` and the secrets hook |
| `private/<slug>.md` | real values of one project (hosts, URLs, real names behind the analogs) |
| `config.toml`, `credentials` | Jira site and API token (mode 600), created with the Jira subprojects |

The folder is mode 700 and `names.toml` and `credentials` are mode 600; `ws setup` reports any other
mode.

## What protects the repo

Protection starts after `ws setup`: a fresh clone has no git hooks. From then on, the hooks call
`ws check-secrets` (secret patterns, real names, company domains) and fail closed, so without
`names.toml` they block everything:

| Hook | Checks |
|---|---|
| `pre-commit`, `pre-merge-commit` | the staged added lines (for a merge, every incoming line) |
| `commit-msg` | the commit message |
| `pre-push` | every pushed commit: lines, message, author and committer e-mails |

A Claude Code gate, `hooks/block_hook_bypass.py`, blocks `--no-verify`, `git commit -n` and any
`core.hooksPath` override, in every repo; `ws setup` checks that it is registered. Exceptions go in
`.secrets-allow`, which is read from the index (an entry counts once staged) and excuses only the
span it matches, not the rest of the line.

The check cannot see names missing from `names.toml` or the content of binary files (a staged binary
is reported, not read).

## The `ws` command

| Command | What it does |
|---|---|
| `ws setup` | Sets the git hooks path and checks the hooks, links the skills, checks `~/.config/workspace/` (files and modes) and the Claude Code gates |
| `ws check-secrets [--staged \| --all \| PATH…]` | Scans for secret patterns, real names and company domains; the git hooks run it |
| `ws mask [--in-place \| --check] [FILE \| -]` | Replaces real names with analogs; `--check` exits 1 if a real name remains |
| `ws project new <slug>` | Copies `templates/project/` into `projetos/<slug>/` |
| `ws slot [-n N] -- <cmd>` | Runs a heavy command in one of N slots (file lock), so parallel agents do not exhaust memory; the command holds the lock and gets SIGTERM, SIGHUP and SIGINT forwarded, so the slot lasts until it exits |
| `ws git assemble --base B --from WIP --to FINAL` | Builds FINAL from B by cherry-picking WIP, optionally rewriting subjects (keyed by subject or sha), and checks the 72-character limit; refuses a dirty work tree and merge commits in the range |
| `ws git merge-rehearsal --repo R --base B BRANCH…` | Merges the branches over B in a throwaway worktree (a fresh checkout with no dependencies installed), applies known conflict resolutions, runs an optional check |

Development: `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`.

## Projects

Content under `projetos/` is in PT-BR.

| Project | What it is |
|---|---|
| [artemis-v2](projetos/artemis-v2/README.md) | Planning of V2 of the Artemis project: closing and reconciliation of settlement batches |
| [reestrutura-whitelabel](projetos/reestrutura-whitelabel/README.md) | Epic that restructures the partner portal front end: brand themes, dark mode, own components, new architecture |
| [estudos-ia](projetos/estudos-ia/README.md) | Study guide of the AI concepts used in this workspace |

New projects start with `ws project new <slug>`.
