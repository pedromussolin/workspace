# Add a gate rule

The approval gate is `hooks/approval_gate.py`, a Claude Code hook that runs before every Bash and
MCP call. Its rules are in `hooks/gate/`: `bash_rules.py` for Bash, `mcp_rules.py` and
`catalog.json` for MCP tools, `decision.py` for the box text. Rules:
[safety](../conventions/safety.md), [agents](../conventions/agents.md). Decisions:
[0007](../adr/0007-gate-threat-model.md), [0008](../adr/0008-gate-denies-endless-waits.md).

1. **Choose ask or deny.** Ask when the command writes outside the machine and the user must see
   it first. Deny only when a box would just stall a background agent (a wait loop without
   `timeout`, a `pgrep -f` that matches itself); the reason goes to the model. See
   [safety](../conventions/safety.md).
2. **Write the box text.** Build it with `ask(...)` from `decision.py`: a short PT-BR title (the
   `TITLE_*` constants of `bash_rules.py`) and at most three lines, each a reason and the piece of
   the command that triggered it.
   - An MCP tool: `ws gate catalog ask SERVER TOOL...` for a write, `ws gate catalog pass ...`
     for a read; commit `hooks/gate/catalog.json`. When unsure, `ask`.
   - A `ws` command that writes: its `ask` rule joins `ASK_RULES` in `src/ws/bootstrap.py`, and
     the command joins the `ws` write family of `bash_rules.py` (`WS_WRITES`).
3. **Write tests only with the Write tool.** Add cases to `tests/test_gate_bash.py`,
   `tests/test_gate_mcp.py` or `tests/test_gate_decision.py` with the Write or Edit tool. The live
   gate reads the text of every Bash command, so a heredoc full of sample commands trips it.
4. **The user then runs `ws setup`.** In a terminal, it shows the diff of the protected copy of
   the hooks (`~/.claude/hooks/workspace/`) and asks before writing; run by an agent, it writes
   nothing there. It also prints the settings JSON with any `ask` rule that is missing.
5. **Run [validate-change](validate-change.md).**
