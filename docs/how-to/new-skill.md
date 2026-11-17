# Add a skill

A daily-use skill is a folder `skills/<name>/` with a `SKILL.md` and, when needed, `references/`.
`ws setup` links it into `~/.claude/skills/`. Rules: [skills](../conventions/skills.md),
[providers](../conventions/providers.md), [safety](../conventions/safety.md). Examples:
`skills/daily/`, `skills/card/`.

1. **Decide the trigger and write the description.** Name the requests that should start the
   skill and the ones that should not (`skills/daily/SKILL.md` names both). The front matter holds
   `name` (the folder name) and `description` (what it does and when to use it, third person,
   with the phrases the user types). See [skills](../conventions/skills.md).
2. **Use neutral words.** `SKILL.md` and its rule files name no provider. Each provider's calls,
   and its MCP fallback for reads, go to `references/<kind>.md`, linked once.
   `tests/test_card_skill_words.py` shows how a test pins this. See
   [providers](../conventions/providers.md).
3. **Make it model-invocable, with each write behind a box.** No `disable-model-invocation`. Every
   write outside the repo runs a `ws` command that an `ask` rule or the gate covers, and the skill
   says that the model never answers the box. `tests/test_card_skill_invocation.py` pins this for
   `/card`. See [safety](../conventions/safety.md).
4. **Find the `ws` command it wraps, or write one first.** The README table "The `ws` command"
   lists them. If the deterministic part has no command yet, build it with
   [new-command](new-command.md) before the skill. The skill runs printed commands exactly as
   printed.
5. **Document the manual path.** Add the flow to [docs/manual.md](../manual.md) and the README, so
   every step can also be done without AI.
6. **Add evals with mocks.** Follow [new-eval](new-eval.md).
7. **Run [validate-change](validate-change.md).** Keep `SKILL.md` under 500 lines, instructions in
   English and the lines shown to the user in PT-BR. After the merge, the user runs `ws setup` to
   link the new skill.
