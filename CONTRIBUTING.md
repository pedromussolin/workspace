# Contributing

For people who change this repo. AI tools start from [AGENTS.md](AGENTS.md); the rules are the
same for both and live in [docs/conventions/](docs/conventions/).

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone <this repo> ~/repos/workspace
cd ~/repos/workspace
uv tool install --editable .
ws setup
```

Run `ws setup` in your own terminal: it sets the git hooks path, links the skills, and shows the
diff of the protected copy of the Claude Code hooks before it writes it. It never edits
`~/.claude/settings.json`; it prints the JSON to add. `ws setup --check` only reports. Details:
[README.md](README.md), "Setup".

## Workflow

1. `git pull`.
2. To add a skill, a `ws` command, a provider, a gate rule or an eval, follow its guide in
   [docs/how-to/](docs/how-to/); each step links the rule it follows.
3. Validate the change: [validate-change](docs/how-to/validate-change.md) (`scripts/validate`,
   the focused tests, the full suite once, then the review).
4. Commit as [git](docs/conventions/git.md) says: atomic, prefix `feat:`, `fix:`, `docs:`,
   `chore:` or `test:`, PT-BR, at most 72 characters, no `Co-Authored-By`.
5. When a hook blocks, fix the text or mask it (`ws mask --in-place FILE`); never skip the hook.
   When it warns about new words, answer them with `ws names review` in your terminal and commit
   `.known-words`. See [confidentiality](docs/conventions/confidentiality.md).
6. Push to `main`.

## Where things are

| Path | What it holds |
|---|---|
| [AGENTS.md](AGENTS.md) | commands, layout, boundaries and the index of everything below |
| [docs/conventions/](docs/conventions/) | the rules, each with how it is enforced |
| [docs/how-to/](docs/how-to/) | step-by-step guides |
| [docs/adr/](docs/adr/README.md) | architecture decisions and why they were taken |
| [docs/manual.md](docs/manual.md) | every flow by hand, without AI |
| [README.md](README.md) | setup details, the local config and the `ws` command table |
