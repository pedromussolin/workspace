---
status: accepted
date: 2026-11-15
---

# Versioned JSON contracts between ports

## Context and Problem Statement

With neutral ports, the core and each adapter exchange data that both sides must read the same
way. People write card drafts by hand, in Markdown with TOML front matter, while the AI and the
commands produce JSON. Each format had its own checks, so a draft could pass in one form and fail
in the other.

## Decision Outcome

Each port exchanges versioned JSON (`"version": 1`) with a schema in
`src/ws/data/contracts/*.schema.json`, validated by `ws.contracts.validate`, a small standard
library validator with a fixed set of keywords. A hand-edited file maps 1:1 to the JSON and
follows the same rules. Machine output of `ws` is JSON on stdout, and the same validator runs in
check and in execute. Rules: [contracts](../conventions/contracts.md).

## Consequences

- Good: people and AI write the same format; a `.md` draft and its `.json` twin produce the same
  requests.
- Good: a document that passes the check always loads in execute.
- Bad: the validator has no `oneOf`, so `card-write` is one flat closed schema and the
  per-operation rules live in code.
- Bad: the list form of `items` is not supported, and each call re-checks the schema.
