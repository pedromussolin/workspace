---
status: accepted
date: 2026-11-15
---

# Approval gate threat model

## Context and Problem Statement

The approval gate reads the text of each Bash command and asks before a write that leaves the
machine. While `ws release` was built, each review round found another way to reach a write
without the box: calling `ws` from Python, `subprocess`, aliases, runner modules, code read from
stdin. Every fix invited the next one, with no point at which the gate was done.

## Decision Outcome

The gate covers an agent's mistake or a plausible workaround, not deliberate obfuscation. Code the
gate cannot read asks. The checks inside `ws` stay the second layer: a valid preview code, the
pending record, the shell session and the 30-minute window. Forms that would need deliberate
obfuscation are parked with this decision. Rules: [safety](../conventions/safety.md).

## Consequences

- Good: the gate has a bounded set of rules that tests can pin.
- Good: what the gate cannot read asks instead of passing.
- Bad: a determined obfuscation could skip the box; `ws` still requires a valid preview code.
- Bad: the gate cannot see a script file that a command runs, text piped to `node`, or programs
  that start other programs (`xargs`, `find -exec`, `ssh`).
