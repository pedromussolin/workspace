# Approval gates, phase 1: plan

Spec: [docs/specs/2026-10-28-approval-gates-design.md](../specs/2026-10-28-approval-gates-design.md).
The shared contract `hooks/gate/decision.py` (with `tests/test_gate_decision.py`) is on `main`
before the agents start; nobody changes it without the orchestrator.

## Execution

Five agents in parallel, one git worktree each, disjoint files. The orchestrator (Opus) reviews
each branch, runs the whole suite and merges into `main`. Final review: Opus, since the change
touches security and writes outside.

| Task | Files (only these) | Model | Effort | Why |
|---|---|---|---|---|
| 1. Gate core and Bash rules | `hooks/approval_gate.py`, `hooks/gate/shell.py`, `hooks/gate/bash_rules.py`, `hooks/block_hook_bypass.py`, `hooks/ask_card_apply.py` (removed), `tests/test_approval_gate.py`, `tests/test_gate_bash.py`, `tests/test_ask_card_apply_hook.py` (moved), `tests/test_hook_bypass_gate.py` | sonnet | xhigh | security parsing, many edge cases |
| 2. MCP catalog, summaries, confidentiality | `hooks/gate/catalog.json`, `hooks/gate/mcp_rules.py`, `tests/test_gate_mcp.py` | sonnet | medium | data and formatting against a fixed contract |
| 3. Card by hand and summary binding | `src/ws/card.py`, `tests/test_card.py` | sonnet | high | approval binding, existing tests to keep |
| 4. Setup: protected copy, rules, config | `src/ws/bootstrap.py`, `src/ws/config.py`, `tests/test_bootstrap.py`, `tests/test_claude_hooks.py`, `README.md` | sonnet | medium | extends an existing pattern |
| 5. Sandbox spike (phase 3) | `docs/research/2026-10-28-sandbox-spike.md`; throwaway files under `~/.cache/workspace/spike-sandbox/` | sonnet | xhigh | new terrain, measurements |

Interfaces between tasks:
- 1 → 2: `approval_gate.py` calls `gate.mcp_rules.decide(tool_name: str, tool_input: dict, cwd:
  str) -> Decision` for every `mcp__*` tool; 2 owns that function.
- 1 → 3: for `ws card apply ... --approve CODE` the gate reads
  `<WS_DATA_DIR or ~/.local/share/workspace>/cards/pending/<CODE>.json` and shows its `summary`
  (a list of strings). A missing or unreadable record still asks, saying so.
- 1, 2 → config: both read `[gate]` of `<WS_CONFIG_DIR or ~/.config/workspace>/config.toml` with
  `tomllib`; keys `push_without_asking` (list of paths, `~` allowed) and `personal_github_owners`
  (list of strings). A missing file or key means the strict default (ask; skip the
  confidentiality check and say so).
- 4 → all: the hooks are copied to `~/.claude/hooks/workspace/` and registered from there:
  `approval_gate.py` with the matcher `Bash|mcp__.*`, the two blocking hooks with `Bash`.

After the merge, by the orchestrator: `docs/manual.md`, the backlog, and the user's review of the
box text in a real session.
