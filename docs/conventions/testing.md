# Testing

Tests and evals. How-to: [validate a change](../how-to/validate-change.md),
[add an eval](../how-to/new-eval.md).

- Run pytest as `uv run pytest -q -p no:cacheprovider --basetemp=$HOME/.cache/ws-pytest/<name>`.
  Afterwards, `chmod -R u+w` that folder and `rm -rf` it. Why `/tmp` is avoided: see the Bash section of
  [`instructions/user.md`](../../instructions/user.md). [review]
- Tests use no network and no real provider. [review]
- Tests use no real names: fake accounts, `example.atlassian.net`, `db.invalid`. [hook]
- JavaScript tests run through the Docker node shim: `PATH=$HOME/.cache/ws-nodeshim:$PATH`.
  [review]
- Golden pins (`tests/golden/`) freeze user-visible previews and approval codes. Change them only
  on purpose. [test: tests/test_card_golden.py]
- A scanner-style test first proves that it flags a broken sample. [review]
- Run the full suite of a feature branch after every merge into it. [review]

## Evals

- Run them with `scripts/run-evals --case NAME --runs 1`. [review]
- Each MCP that a skill calls is declared in `.claude-plugin/plugin.json` with
  `"command": "false"` and mocked in `evals/mocks/<server>/`. [review]
- They cost real API money: run only new or changed cases. [review]
- Never loosen a grader to make it pass. [review]
