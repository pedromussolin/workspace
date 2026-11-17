---
status: accepted
date: 2026-11-16
---

# Denied endless waits in the approval gate

## Context and Problem Statement

Background agents waited for a process with a `while`/`until` loop around `sleep`, or polled with
`pgrep -f`, whose pattern also matches the Bash tool's own shell, so the wait never ended. A box
on such a command only stalls an agent that nobody is watching.

## Considered Options

1. Ask, as for other risky commands.
2. Deny, with the reason going to the model.

## Decision Outcome

Option 2. The gate denies, in any part of the command (`bash -c` scripts and subshells included):

- a `while`/`until` loop that runs `sleep`, unless `timeout` with a non-zero duration runs it and
  the loop is not sent off with `&`, `nohup` or `setsid` inside it;
- `pgrep -f`/`pkill -f`, unless the pattern holds a bracket class that does not match the command
  (`'[p]ytest'`) or `pgrep -A` leaves out its ancestors.

Agents run long commands in the background and wait for the notification. Rules:
[safety](../conventions/safety.md), [agents](../conventions/agents.md).

## Consequences

- Good: no agent hangs on a wait that cannot end, and the model learns why at once.
- Bad: a legitimate polling loop must run under `timeout`.
- Bad: a loop inside a script file is not seen.
