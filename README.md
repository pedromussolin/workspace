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
`~/.claude/skills/`, checks the files below and the Claude Code gates, and prints what is missing.
It never edits `~/.claude/settings.json`; it prints the JSON to add.

Everything sensitive lives outside the repo, in `~/.config/workspace/`:

| File | Content |
|---|---|
| `names.toml` | real name to analog table and company domains; the single source for `ws mask` and the secrets hook |
| `private/<slug>.md` | real values of one project (hosts, URLs, real names behind the analogs) |
| `config.toml`, `credentials` | Jira site and API token (mode 600), created with the Jira subprojects |

Without `names.toml` the pre-commit hook blocks every commit, so a fresh clone cannot publish
unmasked text by accident.

## The `ws` command

| Command | What it does |
|---|---|
| `ws setup` | Sets the git hooks path, links the skills, checks `~/.config/workspace/` and the Claude Code gates |
| `ws check-secrets [--staged \| --all \| PATH…]` | Scans for secret patterns, real names and company domains; the pre-commit hook runs it with `--staged` |
| `ws mask [--in-place \| --check] [FILE \| -]` | Replaces real names with analogs; `--check` exits 1 if a real name remains |
| `ws project new <slug>` | Copies `templates/project/` into `projetos/<slug>/` |
| `ws slot [-n N] -- <cmd>` | Runs a heavy command in one of N slots (file lock), so parallel agents do not exhaust memory |
| `ws git assemble --base B --from WIP --to FINAL` | Builds FINAL from B by cherry-picking WIP, optionally rewriting subjects, and checks the 72-character limit |
| `ws git merge-rehearsal --repo R --base B BRANCH…` | Merges the branches over B in a throwaway worktree, applies known conflict resolutions, runs an optional check |

Development: `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`.

## Projects

Content under `projetos/` is in PT-BR.

| Project | What it is |
|---|---|
| [artemis-v2](projetos/artemis-v2/README.md) | Planning of V2 of the Artemis project: closing and reconciliation of settlement batches |
| [reestrutura-whitelabel](projetos/reestrutura-whitelabel/README.md) | Epic that restructures the partner portal front end: brand themes, dark mode, own components, new architecture |
| [estudos-ia](projetos/estudos-ia/README.md) | Study guide of the AI concepts used in this workspace |

New projects start with `ws project new <slug>`.
