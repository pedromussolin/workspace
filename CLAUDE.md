@AGENTS.md
@docs/conventions/confidentiality.md

# Claude Code

What follows holds only for Claude Code; everything else is in `AGENTS.md` and `docs/`. The
confidentiality rules are imported above because forgetting them costs the most; the other
conventions are read on demand.

## Company-repo rules do not apply here

`~/repos/CLAUDE.md` is also loaded in this repo, because it sits under `~/repos`. Its part for
every repo (communication, Bash, reading, agents, cards and hours) holds here too. Its part for the
company repos (git, task flow, code) does not: no `TS-…` branches or commit prefixes, no `-sdbx`
replication, no review before each commit, no "never commit on master". This repo follows
[docs/conventions/git.md](docs/conventions/git.md) and the language and confidentiality rules
below.

Sessions usually start in `~/repos`, where this file loads only after a file of this repo is read,
and a conversation summary can drop it. Before changing this repo, make sure this file and
`AGENTS.md` are in context; read them again if not.

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
