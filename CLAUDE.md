@AGENTS.md

# Claude Code

What follows holds only for Claude Code; everything else is in `AGENTS.md` and `docs/`.

## Company-repo rules do not apply here

`~/repos/CLAUDE.md` is also loaded in this repo, because it sits under `~/repos`. Its git rules are
for the company repos and do not apply here: no `TS-…` branches or commit prefixes, no `-sdbx`
replication, no "never commit on master". This repo follows
[docs/conventions/git.md](docs/conventions/git.md).

## Two kinds of skills

- `skills/`: the skills for daily use (`/card`, `/daily`, `/release`, ...). `ws setup` symlinks
  each one into `~/.claude/skills/`, so they work in every repo.
- `.claude/skills/`: the skills for building this repo, one per guide in `docs/how-to/`. Claude
  Code loads them only in a session inside this repo; `ws setup` does not link them.

## The approval gate

`hooks/approval_gate.py` (rules in `hooks/gate/`) runs before every Bash and MCP call. It shows a
box before a write that leaves the machine (a push, a `gh` or MCP write, `ws card apply`,
`ws release publish|move`, `ws observe run`) and denies waits that may never end. The box is the
user's: the model never answers it, and a subagent never runs a command that would open one. Rules:
[safety](docs/conventions/safety.md), [agents](docs/conventions/agents.md).

## Memory is not a source of rules

The rules of this repo are in `AGENTS.md`, `docs/conventions/` and the project `CLAUDE.md` files.
The auto memory is not a source of rules.
