# Agents

How a controller briefs subagents, and how agents work in this repo. Decision:
[0008](../adr/0008-gate-denies-endless-waits.md).

- A brief carries:
  - the relevant convention excerpts, with their paths;
  - what was already ruled out;
  - the report file;
  - the reply contract.

  One task per agent, sized to about 200k tokens of context. [review]
- Never wait in a loop, and never use `pgrep -f`/`pkill -f`. Run long commands in the background
  and wait for the notification. [gate]
- Write files with the Write or Edit tools, never a Bash heredoc. [review]
- Never store a command in a shell variable. [gate]
- Never run a command covered by an `ask` rule, not even with `--help`: `ws observe run`,
  `ws card apply`, `ws release publish|move`, push, `gh` writes. Read the argparse code instead.
  [gate]
- Agents work in their own worktree and branch, never merge or push, and never dispatch
  subagents. The controller reviews, merges, runs the suite and pushes. [review]
- At the end of a work block, sweep for leftover loops, pytest runs, containers and temp folders.
  [review]
