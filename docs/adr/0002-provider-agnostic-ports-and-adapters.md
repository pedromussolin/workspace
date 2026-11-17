---
status: accepted
date: 2026-11-13
---

# Provider-agnostic ports and adapters

## Context and Problem Statement

The tracker code and the `/card` skill named one tracker everywhere: in module names, help texts,
messages and skill steps. Changing the tracker, or supporting a second one, meant touching every
command and skill. The observability tool and the production database used by `ws observe` had the
same risk.

## Decision Outcome

Every external system has a neutral port and one adapter per provider. The config chooses the
provider (`[tracker] kind`, `[observability] provider`, `[database.<name>] engine`). The provider
name appears only in the adapter, the config and the skill's `references/<kind>.md`. Adapters are
found by string and never imported at module top.

Decided on 2026-11-13 for the tracker (neutral vocabulary in `/card`, the neutral port behind
`ws task list`). Widened on 2026-11-15 to the tracker writes and to the observability and database
ports of `ws observe`; the rule now names tracker, observability, database, code host, secrets and
deploy. Rules: [providers](../conventions/providers.md).

## Consequences

- Good: a new provider is an adapter, a config section and a reference file; the commands and the
  skills do not change.
- Good: boundary tests catch a provider name or an adapter import in a neutral module.
- Bad: still coupled, to migrate later: the code host (`gh`), the gate's vendor registry, the
  config store and deploy manifest, the post-deploy probe, the migration chain.
- Bad: two adapter layouts today (a package per provider for the tracker, one module per provider
  for observability and database).
