# Agents

How a controller briefs subagents, and how agents work, in every repo.
`instructions/user.md` imports this file. Decision:
[0008](../adr/0008-gate-denies-endless-waits.md).

- A brief carries:
  - the excerpts of the repo rules (`.ai/` in the company repos, `docs/conventions/` in the
    workspace) and of the documents the task uses, with their paths;
  - what was already ruled out;
  - the report file;
  - the reply contract.

  One task per agent, sized to about 200k tokens of context. A larger task is split into agents
  in sequence, each writing its delivery to a file for the next. [review]
- A brief for a screen in the front (`apl-credit-whitelabel`) starts from
  `~/repos/workspace/templates/briefs/front-screen.md`. It names the repo skill to load first
  (`new-page`, `new-component`, `fix-bug` or `validate-change`), says to read `.ai/README.md` in
  its order, names the reference screens to open, and requires the smoke prints and the screen's
  states before the agent reports. The controller then has `review-screen` run by a fresh agent,
  briefed from `~/repos/workspace/templates/briefs/front-screen-review.md` in the builder's
  worktree (read only, since the screen has no commit yet), and opens the prints before showing
  the screen to the user. [review]
- Never wait in a loop, and never use `pgrep -f`/`pkill -f`. Run long commands in the background
  and wait for the notification. An unavoidable wait runs under `timeout N`. [gate]
- Write files with the Write or Edit tools, never a Bash heredoc. [review]
- Never store a command in a shell variable: see the Bash section of
  [`instructions/user.md`](../../instructions/user.md). [gate]
- Never run a command covered by an `ask` rule, not even with `--help`: `ws observe run`,
  `ws card apply`, `ws release publish|move`, push, `gh` writes. Read the argparse code instead.
  [gate]
- Agents work in their own worktree and branch, never merge or push, and never dispatch
  subagents. The controller reviews, merges the agents' branches into the task branch, runs the
  suite and pushes. [review]
- Up to five agents at once, each with a disjoint set of files. Each gets the lightest model and
  effort the task allows, recorded in the plan; a task that comes back with a defect the agent
  should have caught moves up a level. [review]
- A development server runs directly, in the agent's own worktree and on its own port range. A
  heavy command (front build and tests, Playwright, a full suite) runs through
  `ws slot -- <cmd>`. [review]
- A "never", "only" or "must" line that an agent writes into a rule document (a convention, a
  `SKILL.md`, a project `CLAUDE.md`) needs a recorded decision: `decisions.md`, an ADR or the
  user's words. Before merging, the controller checks each such line and asks the user about any
  without one, or stricter than the practice. [review]
- At the end of a work block, sweep for leftover loops, pytest runs, containers and temp folders
  (`ps`), ending each one by its PID. [review]
