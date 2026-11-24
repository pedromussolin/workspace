# Commands

How the `ws` CLI behaves. Decision: [0006](../adr/0006-script-first.md).

- Runtime code uses the standard library only; `pytest` and `ruff` are dev dependencies. [review]
- `uv` only, never `pip`: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`.
  [review]
- JSON on stdout for machines; PT-BR only in lines shown to people. [review]
- Exit codes:
  - 0: ok;
  - 1: a rule failed (`problems` in the JSON);
  - 2: setup needed (config, token, gate settings);
  - 3: the provider refused or is unreachable. Never retry a write after 3. [review]
- Help text uses neutral words. [test: tests/test_tracker_boundary.py]
- `ws` never edits `~/.claude/settings.json`: it prints what to add. The user runs `ws setup`.
  [test: tests/test_bootstrap.py]
- Config lives only in `~/.config/workspace/`: `config.toml`, and the company card policy
  `card-policies/<name>.toml` that `[card] policy` names (a company name is masked in the repo, so
  that layer never enters it). [review]
- Secrets live only in `~/.config/workspace/credentials`, which the model never reads. [gate]
- Data goes under `config.data_dir()`. Tests set `WS_DATA_DIR` and `WS_CONFIG_DIR`. [review]
- Outside the repo there are three places, one per kind of content:
  - `~/.config/workspace/`: configuration and secrets (`config.toml`, `card-policies/<name>.toml`,
    `names.toml`, `private/<slug>.md`, `credentials`);
  - `~/.local/share/workspace/`: local data to keep: the dictionaries, and `projects/<slug>/` for
    what a project never puts in git (worktrees, logs, locks, deploy files, evidence with real
    data), same slug as in the repo, created by `ws project new`, mode 700;
  - `~/.cache/workspace/`: what can be rebuilt. [review]

## Current behaviour

The `ws release` commands read exit 2 as "cannot evaluate" (config, `gh`, gate, a merge in
progress, a missing release folder or `release.toml`, a malformed date) and exit 1 as "evaluated,
and a rule failed". Pending previews and approval codes live in `src/ws/approval.py`.
