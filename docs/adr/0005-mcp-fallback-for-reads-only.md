---
status: accepted
date: 2026-11-16
---

# MCP fallback for reads only

## Context and Problem Statement

The daily reads the tracker through `ws task list`. When that command fails (no token, the
provider refused), the skill used to fall back to one vendor's MCP tools named in `SKILL.md`. With
provider-agnostic ports ([0002](0002-provider-agnostic-ports-and-adapters.md)) the skill must stay
neutral, and an MCP write would skip the preview and the approval code of `ws`.

## Decision Outcome

Reads go through `ws` first. When a `ws` command fails, the skill falls back to the MCP of the
provider selected in the config, following `references/<kind>.md`. With no reference or no working
MCP, the skill says the data is missing. Writes never go through an MCP: only through `ws`, with
the preview and the approval box. First decided for the daily's tracker fallback, then made a
general rule on the same day. Rules: [providers](../conventions/providers.md).

## Consequences

- Good: a read still works when the `ws` path fails, and the skill text names no provider.
- Good: every write keeps one path, with its preview, code and box; the MCP write tools stay in
  the `ask` rules as a second guard.
- Bad: each skill that reads a port needs one reference file per provider.
- Bad: in the MCP fallback the model still builds the daily's `cards.json` by hand.
