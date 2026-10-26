# workspace: common rules

Personal, private repo: planning projects under `projetos/`, versioned Claude skills, and the `ws`
CLI (Python, uv). Setup and command table: `README.md`. Project rules: the `CLAUDE.md` inside each
project folder, read when working there.

## Company-repo rules do not apply here

`~/repos/CLAUDE.md` is also loaded in this repo, because it sits under `~/repos`. Its git rules are
for the company repos and do not apply here: no `TS-…` branches or commit prefixes, no `-sdbx`
replication, no "never commit on master". Here the rule is: pull, commit and push straight to
`main`, without asking.

## Language

| English (code context) | PT-BR (task/business context) |
|---|---|
| `src/`, `tests/`, CLI commands, flags and messages | everything under `projetos/`: folder names, file names and prose |
| `skills/` (names and `SKILL.md`) | the project template content (`templates/project/`) |
| `docs/specs/`, root `README.md` and root `CLAUDE.md` | what the automations produce for people: GMUD text, Jira issues and comments, standup |
| config files (`names.toml`, `config.toml`), hook | commit messages |

Chat follows the language the user writes in. Nothing inside `projetos/` is renamed, and migrated
documents are not rewritten.

## Confidentiality

This repo sits on a personal GitHub account. These never enter it:
- credentials, access tokens, passwords, keys, connection strings, `.env` content ("design token"
  is a different thing and is fine);
- internal hosts, URLs, IPs, ports, database or infrastructure user names, Parameter Store paths and
  values (write "replica host", `<sandbox-url>`);
- end-customer data (tax IDs, names of payers and assignors, contract values) and query dumps;
- build, test and lint logs of the company repos;
- company source code, patches included: cite `path/file.py:line` instead. Own generic prototypes
  in a project's `anexos/` are fine, with local test credentials only;
- real names of people, the company, partner brands, customers, administrators and suppliers: use
  the analog, also in file names, anchors, theme keys and cited paths. Numbers and metrics may
  stay;
- `/home/<user>` paths: always write `~`.

Masking: the table lives in `~/.config/workspace/names.toml`, read only through `ws mask`. Never
copy its entries into the repo. Outside the repo (chat, company repos) real names are used.

Enforcement starts after `ws setup`, which sets `core.hooksPath` (a fresh clone has no hooks) and
reports a hook that is not executable. The git hooks call `ws check-secrets` (secret patterns, real
names, company domains) and fail closed, also without `names.toml`: `pre-commit` and
`pre-merge-commit` check the staged lines, `commit-msg` the message, `pre-push` every pushed commit
(lines, message, author and committer e-mails). A Claude Code gate (`hooks/block_hook_bypass.py`)
blocks `--no-verify`, `git commit -n` and `core.hooksPath` overrides, in every repo. When a hook
blocks, fix the text or mask it (`ws mask --in-place FILE`); never skip the hook. A true false
positive goes to `.secrets-allow` (path glob, rule, regex) with a `#` reason above it: the file is
read from the index, an entry excuses only the span it matches, and you say in the reply that you
added it. The check cannot see names missing from `names.toml` or the content of binary files (a
staged binary is reported, not read).

## Private values

Hosts, URLs, credentials and the real names behind the analogs live in
`~/.config/workspace/private/<slug>.md`, one file per project, outside git. Read it when a document
uses an analog or a placeholder such as "replica host". A new sensitive value goes there; the
repo gets only the generic reference. Never read `~/.config/workspace/credentials`.

## Sync and commits

- `git pull` before working. At the end of each iteration, commit and push straight to `main`,
  without asking.
- Atomic commits, prefix `docs:`, `chore:`, `feat:`, `fix:` or `test:`; no task ID; message in PT-BR,
  at most 72 characters.
- No `Co-Authored-By` trailer and no "Generated with" line. The commit is the user's responsibility.
- Run `git diff` before writing the message.

## Layout

| Path | What lives there |
|---|---|
| `projetos/<slug>/` | one planning project: `README.md`, `CLAUDE.md`, `CONTINUAR.md`, `decisoes.md`, `tarefas/`, `evidencias/`, `anexos/` |
| `templates/project/` | template copied by `ws project new <slug>` |
| `skills/` | versioned Claude skills, symlinked into `~/.claude/skills` by `ws setup` |
| `src/ws/`, `tests/` | the `ws` CLI and its pytest suite |
| `hooks/` | Claude Code hook scripts, registered in `~/.claude/settings.json` |
| `.githooks/`, `.secrets-allow` | git hooks (`pre-commit`, `pre-merge-commit`, `commit-msg`, `pre-push`) and the allowed exceptions |
| `docs/specs/`, `docs/plans/`, `docs/research/` | designs, implementation plans, research notes |

Heavy local folders of the projects (worktrees, logs, locks, Playwright) stay outside the repo,
under the paths their `CLAUDE.md` names.

## Python

`uv` only, never `pip`: `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`.
Runtime code uses the standard library only; `pytest` and `ruff` are dev dependencies. `ws` never
edits `~/.claude/settings.json`: it prints the JSON to add.

## Skills and context budget

- A skill description says what it does and when to use it, in the third person; it alone decides
  when the skill triggers. `SKILL.md` stays under 500 lines, detail goes to `references/` one level
  deep. Deterministic steps are `ws` commands or bundled scripts.
- A skill that writes outside the repo (Jira, GMUD, GitHub) sets `disable-model-invocation: true`
  and follows plan, validate (`--dry-run`), explicit approval, execute.
- Always-loaded files stay small: this file under 200 lines, project `CLAUDE.md` short,
  `MEMORY.md` an index. Procedures live in skills, detail in the project files.
- A hard rule is a hook or a deny rule, never prose alone.
