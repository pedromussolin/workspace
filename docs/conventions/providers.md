# Providers

How `ws` and the skills stay free of any one provider. Decisions:
[0002](../adr/0002-provider-agnostic-ports-and-adapters.md),
[0005](../adr/0005-mcp-fallback-for-reads-only.md).

- Everything is provider- and technology-agnostic: tracker, observability, database, code host,
  secrets, deploy. Each has a neutral port plus one adapter per provider. [review]
- The config chooses the provider: `[tracker] kind`, `[observability] provider`,
  `[database.<name>] engine`. [review]
- The provider name appears only in the adapter, the config and the skill's
  `references/<kind>.md`. [test: tests/test_tracker_boundary.py; tests/test_observe_boundaries.py;
  tests/test_card_skill_words.py; tests/test_daily_skill.py]
- Adapters are found by string (an `ADAPTERS` map and `importlib`), never imported at module top.
  [test: tests/test_tracker_boundary.py; tests/test_observe_boundaries.py]
- Reads go through `ws` first. When a `ws` command fails, the skill falls back to the MCP of the
  provider selected in the config, following `references/<kind>.md`. With no reference or no
  working MCP, the skill says the data is missing. [test: tests/test_daily_skill.py]
- Writes never go through an MCP: only through `ws`, with the preview and the approval box. [gate]
- A capability that depends on the provider's plan or license is a flag in that provider's config
  section, and the adapter derives behaviour from it. Example: `[tracker.jira] premium`.
  [test: tests/test_card_initiative.py]

## Still coupled

From the provider-coupling audit, to migrate later: the code host (`gh`), the gate's vendor
registry, the config store and deploy manifest, the post-deploy probe, the migration chain.

## Current behaviour

The tracker keeps its `ADAPTERS` map in `src/ws/tracker/__init__.py`, with one package per
provider (`src/ws/tracker/<kind>/`). Observability and database build the module name from the
config value instead (`ws.observability.<provider>_adapter`, `ws.database.<engine>_adapter`), one
module per provider.
