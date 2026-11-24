# workspace

Entry point for any AI tool, and for people, that builds or changes this repo.

## Project overview

Personal, private repo: planning projects under `projects/`, versioned Claude skills under
`skills/`, and the `ws` CLI (Python 3.12, standard library only, run with `uv`). The skills do
the judgment work; `ws` does every step that can be deterministic. Setup details, local config and
the full command table: [README.md](README.md). Every flow without AI: [docs/manual.md](docs/manual.md).
Project rules: the `CLAUDE.md` inside each project folder, read when working there.

## Setup

```bash
git clone <this repo> ~/repos/workspace
cd ~/repos/workspace
uv tool install --editable .
ws setup
```

`ws setup` is idempotent: it sets the git hooks path (a fresh clone has no hooks), links
`skills/*` into `~/.claude/skills/` and prints the Claude Code gates to add. `ws setup --check`
only reports.

## Commands

| What | Command |
|---|---|
| Quick checks of a change | `scripts/validate` |
| Tests | `uv run pytest -q -p no:cacheprovider --basetemp=$HOME/.cache/ws-pytest/<name> [FILES]`, then `chmod -R u+w` and `rm -rf` that folder |
| Lint and format | `uv run ruff check`, `uv run ruff format --check` |
| Evals (real API cost) | `scripts/run-evals --case NAME --runs 1` |
| New words to answer | `ws names pending` |

## Layout

| Path | What lives there |
|---|---|
| `projects/<slug>/` | one planning project: `README.md`, `CLAUDE.md`, `CONTINUE.md`, `decisions.md`, `project.toml` (epics, optional), `tasks/`, `evidence/`, `attachments/` |
| `projects/standalone/` | tasks that belong to no project: a `README.md` with the task table and `tasks/` |
| `instructions/` | global Claude Code instructions (PT-BR), linked by `ws setup`: `user.md` as `~/.claude/CLAUDE.md`, `company-repos.md` as `~/repos/CLAUDE.md` |
| `templates/project/` | template copied by `ws project new <slug>` |
| `skills/` | daily-use Claude skills, symlinked into `~/.claude/skills` by `ws setup` |
| `.claude/skills/` | skills for building this repo, one per how-to guide; not linked |
| `src/ws/`, `tests/` | the `ws` CLI and its pytest suite |
| `hooks/` | Claude Code hook scripts (the approval gate), registered in `~/.claude/settings.json` |
| `.githooks/`, `.secrets-allow`, `.known-words` | git hooks (`pre-commit`, `pre-merge-commit`, `commit-msg`, `pre-push`), the allowed exceptions and the answered new words |
| `scripts/`, `evals/` | `validate`, `run-evals` and helpers; the eval cases of the skills |
| `docs/conventions/`, `docs/how-to/`, `docs/adr/` | rules, step-by-step guides, decision records |
| `docs/specs/`, `docs/plans/`, `docs/research/` | designs, implementation plans and rulings, research notes |

What lives outside the repo (config, local data, cache): [commands](docs/conventions/commands.md).

## Boundaries

- Never put in the repo: secrets, real names, internal hosts or URLs, customer data, company code.
- Never read `~/.config/workspace/credentials`. `ws` never edits `~/.claude/settings.json`; Claude
  applies the block `ws setup` prints only after the user says yes.
- Never skip a hook. A word goes to `.known-words` only after the user's answer. A true false
  positive goes to `.secrets-allow`, and the reply says it was added.
- Never write through an MCP. The production replica is read-only: `ws observe run` for an
  observation, or a direct read-only query with a timeout, one at a time
  ([safety](docs/conventions/safety.md)).
- Never answer an approval box for the user.

## Conventions

The rules, one file per area. Each rule line ends with how it is enforced: `[test: tests/<file>.py]`
(a pytest test), `[hook]` (a git hook), `[gate]` (the Claude Code approval gate), `[script]`
(`scripts/validate`) or `[review]` (only a reviewer catches it).

- [providers](docs/conventions/providers.md): ports, adapters, the MCP fallback for reads.
- [contracts](docs/conventions/contracts.md): versioned JSON and its schemas.
- [skills](docs/conventions/skills.md): descriptions, the approval box, neutral words, script
  first, the context budget.
- [commands](docs/conventions/commands.md): the `ws` CLI, exit codes, where config and data live.
- [safety](docs/conventions/safety.md): external writes, the production replica, the gate.
- [testing](docs/conventions/testing.md): pytest, golden pins, evals.
- [agents](docs/conventions/agents.md): briefs, waiting, files, what agents never run.
- [git](docs/conventions/git.md): sync and commits.
- [language](docs/conventions/language.md): English names, content in the language of its context.
- [confidentiality](docs/conventions/confidentiality.md): what never enters the repo, masking, new
  words, private values.

## How-to guides

- [Add a skill](docs/how-to/new-skill.md)
- [Add a `ws` command](docs/how-to/new-command.md)
- [Add a port or a provider adapter](docs/how-to/new-provider.md)
- [Add a gate rule](docs/how-to/new-gate-rule.md)
- [Add an eval](docs/how-to/new-eval.md)
- [Validate a change](docs/how-to/validate-change.md)

## Decisions

Architecture decisions are numbered records in [docs/adr/](docs/adr/README.md); the index also
links the older rulings in `docs/plans/`.

## Commits

- Pull before working; at the end of each iteration, commit and push straight to `main`, without
  asking. Agents work in their own worktree and branch and never merge or push.
- Atomic commits, prefix `feat:`, `fix:`, `docs:`, `chore:` or `test:`, no task ID, PT-BR, at most
  72 characters, no `Co-Authored-By`. Run `git diff` before the message. Never `--no-verify`.
- Details: [git](docs/conventions/git.md). For people: [CONTRIBUTING.md](CONTRIBUTING.md).
