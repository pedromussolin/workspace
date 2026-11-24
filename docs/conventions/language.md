# Language

Which language names and content use.

- Names are English everywhere: every directory name and file name in the repo, code, CLI
  commands, flags and messages. [review]
- Content stays in the language of its context, as the table below shows. [review]
- A new file takes a short English slug, with the `NN-` prefix for tasks; proper nouns, analogs
  and acronyms stay (`genius`, `gmud-ts-5383.md`). [review]
- A planning project takes the short name of the product or feature (`pre-trade`), not of the
  delivery: later deliveries go in the same project, and the current delivery's scope goes in its
  `README.md`. [review]
- Chat follows the language the user writes in. [review]
- Migrated documents are not rewritten: a file with PT-BR content still has an English name.
  [review]

| English | PT-BR |
|---|---|
| every directory and file name, `projects/` included | prose under `projects/`: tasks, decisions, evidence, project `README.md` and `CLAUDE.md` |
| `src/`, `tests/`, CLI commands, flags and messages | the project template content (`templates/project/`) |
| `skills/` and `.claude/skills/` (names and `SKILL.md`) | what the automations produce for people: GMUD text, Jira issues and comments, standup |
| `docs/specs/`, `docs/conventions/`, `docs/how-to/`, `docs/adr/`, root `README.md`, `AGENTS.md`, `CONTRIBUTING.md` and `CLAUDE.md` | commit messages |
| config files (`names.toml`, `config.toml`), hook | the global instructions (`instructions/*.md`) |
