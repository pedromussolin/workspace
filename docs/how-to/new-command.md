# Add a `ws` command

The parser is in `src/ws/cli.py`; larger families have their own `*_cli.py` module (`observe_cli.py`,
`release_cli.py`). Rules: [commands](../conventions/commands.md),
[contracts](../conventions/contracts.md), [safety](../conventions/safety.md),
[testing](../conventions/testing.md).

1. **Define the JSON contract and its schema.** Write the document the command reads or prints,
   with `"version": 1`, and its schema in `src/ws/data/contracts/<name>.schema.json`, using only
   the allowed keywords. Check documents with `ws.contracts.validate`, the same call in check and
   in execute. Add the schema name to `tests/test_contracts.py`, which lists its schemas. See
   [contracts](../conventions/contracts.md).
2. **Set the exit codes.** 0 ok, 1 a rule failed (`problems` in the JSON), 2 setup needed, 3 the
   provider refused or is unreachable. See [commands](../conventions/commands.md).
3. **Write neutral help.** No provider name in any help text: `tests/test_tracker_boundary.py`
   scans the whole parser.
4. **Put writes through preview, code and apply.** A command that writes outside the machine has
   a preview, which prints the PT-BR summary and the approval code and saves the pending record
   (`src/ws/approval.py`), and an apply with `--approve CODE`, which re-plans, compares and sends
   once. Give the apply an `ask` rule and a gate family: [new-gate-rule](new-gate-rule.md). See
   [safety](../conventions/safety.md).
5. **Add tests.** One file per command family under `tests/`. The `conftest.py` fixtures set
   `WS_CONFIG_DIR` and `WS_DATA_DIR`; use the fakes (`tests/fake_tracker.py`, `tests/fake_gh.py`),
   no network, and golden pins (`tests/golden/`) for user-visible previews. See
   [testing](../conventions/testing.md).
6. **Add the README row.** One row in "The `ws` command" table of the README, and a section in
   [docs/manual.md](../manual.md) when the command starts a new flow.
7. **Run [validate-change](validate-change.md).**
