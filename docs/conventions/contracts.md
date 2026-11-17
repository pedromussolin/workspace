# Contracts

What the ports exchange, and how people and AI write the same data. Decision:
[0003](../adr/0003-versioned-json-contracts.md).

- Each port exchanges versioned JSON (`"version": 1`) with a schema in
  `src/ws/data/contracts/*.schema.json`, validated by `ws.contracts.validate`.
  [test: tests/test_contracts.py]
- Allowed schema keywords: `type`, `required`, `properties`, `enum`, `items`,
  `additionalProperties: false`, and `const` for the version. [test: tests/test_contracts.py]
- People and AI write the same format. A hand-edited file (TOML, or Markdown front matter) maps
  1:1 to the JSON and follows the same rules. [test: tests/test_card_json_drafts.py]
- Machine output of `ws` is JSON on stdout. [review]
- The same validator runs in check and in execute. [review]

## Current behaviour

The validator has no `oneOf`: `card-write` is one flat closed schema, with the per-operation rules
in code. `tests/test_contracts.py` names its schemas instead of counting them. The list form of
`items` is not supported, and `ws observe new` still prints its JSON without `version`.
