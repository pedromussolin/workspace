---
status: accepted
date: 2026-10-27
---

# Script first

## Context and Problem Statement

The first skills had the model build by hand what a program could build: files, JSON, commands,
git steps. The results changed from run to run, mistakes slipped in, and each run spent tokens on
mechanical work.

## Decision Outcome

Whenever a step can be a deterministic script, it is one: a `ws` command or a script bundled with
the skill, and the skill calls it. The model only decides, asks and writes the prose. It runs
printed commands exactly as printed and never rebuilds them by hand. Every flow can also be done
by hand with the same commands (`docs/manual.md`). Rules: [skills](../conventions/skills.md),
[commands](../conventions/commands.md).

## Consequences

- Good: scripts make fewer mistakes, give the same result every time and cost fewer tokens.
- Good: a person can run the same flow without any AI.
- Bad: a new skill often needs a `ws` command, with its tests, before the skill itself.
