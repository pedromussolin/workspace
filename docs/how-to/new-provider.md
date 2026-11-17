# Add a port or a provider adapter

A port is the neutral side of an external system (tracker, observability, database, code host,
secrets, deploy); an adapter speaks to one provider. Rules:
[providers](../conventions/providers.md), [contracts](../conventions/contracts.md). Decisions:
[0002](../adr/0002-provider-agnostic-ports-and-adapters.md),
[0005](../adr/0005-mcp-fallback-for-reads-only.md).

1. **Define the port and its contract.** A neutral package `src/ws/<port>/` with the protocol in
   `port.py`, and the JSON it exchanges as a schema in `src/ws/data/contracts/` (step 1 of
   [new-command](new-command.md)). For a new provider of an existing port, skip this step.
2. **Add the adapter under `src/ws/<port>/<kind>/`.** The tracker does this
   (`src/ws/tracker/jira/`); observability and database keep one module per provider,
   `src/ws/<port>/<kind>_adapter.py` (current behaviour).
3. **Register it by string.** Name it in the port's `ADAPTERS` map and load it with `importlib`,
   never with a top-level import. The tracker's map is in `src/ws/tracker/__init__.py`;
   observability and database build the module name from the config value (current behaviour).
4. **Add the config section, with any capability flags.** The key that picks the provider
   (`[tracker] kind`, `[observability] provider`, `[database.<name>] engine`) and the provider's
   own section. A capability that depends on the provider's plan is a flag there, such as
   `[tracker.jira] premium`. Document the keys in the README, "Local config".
5. **Add `references/<kind>.md` with the MCP fallback.** In each skill that reads the port: the
   provider's calls for reads when the `ws` command fails, and what to say when nothing works.
   Never a write through the MCP.
6. **Extend the boundary test.** Add the new neutral modules to `tests/test_tracker_boundary.py`
   or to the neutral list of `tests/test_observe_boundaries.py`, so they import no adapter and
   name no provider.
7. **Add the eval mocks.** Declare the provider's MCP server in `.claude-plugin/plugin.json` with
   `"command": "false"` and add its answers under `evals/mocks/<server>/`; see
   [new-eval](new-eval.md).
8. **Run [validate-change](validate-change.md).**
