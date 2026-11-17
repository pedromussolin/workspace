# Skills

How a skill under `skills/` is written. Decisions:
[0004](../adr/0004-model-invocable-skills-behind-the-box.md),
[0006](../adr/0006-script-first.md).

- The description says what the skill does and when to use it, in the third person; it alone
  triggers the skill. [review]
- Every skill can be started by the model. Every write outside the repo goes behind the approval
  box (an `ask` rule or the gate). The model never answers the box for the user.
  `disable-model-invocation` is only for a skill whose writes are not all behind a box; today none
  has it. When the rule changes, sweep `skills/*/SKILL.md` at once.
  [test: tests/test_card_skill_invocation.py; tests/test_release_skill_invocation.py]
- `SKILL.md` and its rule files use neutral words. Vendor specifics go to `references/<kind>.md`,
  linked once. [test: tests/test_card_skill_words.py]
- Script first: a step that can be deterministic is a `ws` command or a bundled script. The model
  decides, asks and writes prose. It runs printed commands exactly as printed and never rebuilds
  them by hand (files, JSON, commands, git steps). [review]
- Usable both ways: every skill step can also be done by hand, as documented in the README and
  `docs/manual.md`. [review]
- `SKILL.md` stays under 500 lines, with detail one level deep in `references/`.
  [test: tests/test_card_skill_words.py]
- Instructions are in English; lines shown to the user are in PT-BR. [review]
- Card text talks about the task only, never the user, the AI or the conversation. [review]
- A new or changed skill gets evals. [review]

## Context budget

- Always-loaded files stay small: `AGENTS.md` and the root `CLAUDE.md` together under 200 lines,
  a project `CLAUDE.md` short, `MEMORY.md` an index. [review]
- Procedures live in skills; detail lives in the project files. [review]
