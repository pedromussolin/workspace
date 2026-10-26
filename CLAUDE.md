# workspace: common rules

Personal, private repo: planning projects under `projects/`, versioned Claude skills, and the `ws`
CLI (Python, uv). Setup and command table: `README.md`. Project rules: the `CLAUDE.md` inside each
project folder, read when working there.

## Company-repo rules do not apply here

`~/repos/CLAUDE.md` is also loaded in this repo, because it sits under `~/repos`. Its git rules are
for the company repos and do not apply here: no `TS-…` branches or commit prefixes, no `-sdbx`
replication, no "never commit on master". Here the rule is: pull, commit and push straight to
`main`, without asking.

## Language

Names are English everywhere: every directory name and file name in the repo, code, CLI commands,
flags and messages. Content stays in the language of its context:

| English | PT-BR |
|---|---|
| every directory and file name, `projects/` included | prose under `projects/`: tasks, decisions, evidence, project `README.md` and `CLAUDE.md` |
| `src/`, `tests/`, CLI commands, flags and messages | the project template content (`templates/project/`) |
| `skills/` (names and `SKILL.md`) | what the automations produce for people: GMUD text, Jira issues and comments, standup |
| `docs/specs/`, root `README.md` and root `CLAUDE.md` | commit messages |
| config files (`names.toml`, `config.toml`), hook | |

A new file takes a short English slug, with the `NN-` prefix for tasks; proper nouns, analogs and
acronyms stay (`genius`, `gmud-ts-5383.md`). Chat follows the language the user writes in.
Migrated documents are not rewritten: a file with PT-BR content still has an English name.

## Confidentiality

This repo sits on a personal GitHub account. These never enter it:
- credentials, access tokens, passwords, keys, connection strings, `.env` content ("design token"
  is a different thing and is fine);
- internal hosts, URLs, IPs, ports, database or infrastructure user names, Parameter Store paths and
  values (write "replica host", `<sandbox-url>`);
- end-customer data (tax IDs, names of payers and assignors, contract values) and query dumps;
- build, test and lint logs of the company repos;
- company source code, patches included: cite `path/file.py:line` instead. Own generic prototypes
  in a project's `attachments/` are fine, with local test credentials only;
- real names of people, the company, partner brands, customers, administrators and suppliers: use
  the analog, also in file names, anchors, theme keys and cited paths. Numbers and metrics may
  stay;
- `/home/<user>` paths: always write `~`.

Masking: the table lives in `~/.config/workspace/names.toml`, read only through `ws mask`. Never
copy its entries into the repo. Outside the repo (chat, company repos) real names are used.

Enforcement starts after `ws setup`, which sets `core.hooksPath` (a fresh clone has no hooks) and
makes the hooks executable. The git hooks call `ws check-secrets` (secret patterns, real
names, company domains) and fail closed, also without `names.toml`: `pre-commit` and
`pre-merge-commit` check the staged lines, `commit-msg` the message, `pre-push` every pushed commit
(lines, message, author and committer e-mails). A Claude Code gate (`hooks/block_hook_bypass.py`)
blocks `--no-verify`, `git commit -n` and `core.hooksPath` overrides, in every repo. When a hook
blocks, fix the text or mask it (`ws mask --in-place FILE`); never skip the hook. A true false
positive goes to `.secrets-allow` (path glob, rule, regex) with a `#` reason above it: the file is
read from the index, an entry excuses only the span it matches, and you say in the reply that you
added it. The check cannot see names missing from `names.toml` or the content of binary files (a
staged binary is reported, not read).

New words: a capitalized word that is new to the repo may be a real name with no entry yet.
`pre-commit` and `commit-msg` warn about it and `pre-push` blocks until it is answered (`ws names
pending` lists them). Ask the user in the conversation, all pending words in one question with
your guess for each ("Acme: real name or harmless term?"), then apply the answer: `ws names add
REAL --analog ANALOG` and mask what carries it, or `ws names known WORD...` and commit
`.known-words`. A word goes to `.known-words` only after the user's answer, and the reply says
so. Never put the question on GitHub (issue, PR): it would carry the real name.

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
| `projects/<slug>/` | one planning project: `README.md`, `CLAUDE.md`, `CONTINUE.md`, `decisions.md`, `tasks/`, `evidence/`, `attachments/` |
| `projects/standalone/` | tasks that belong to no project: a `README.md` with the task table and `tasks/` |
| `templates/project/` | template copied by `ws project new <slug>` |
| `skills/` | versioned Claude skills, symlinked into `~/.claude/skills` by `ws setup` |
| `src/ws/`, `tests/` | the `ws` CLI and its pytest suite |
| `hooks/` | Claude Code hook scripts, registered in `~/.claude/settings.json` |
| `.githooks/`, `.secrets-allow` | git hooks (`pre-commit`, `pre-merge-commit`, `commit-msg`, `pre-push`) and the allowed exceptions |
| `docs/specs/`, `docs/plans/`, `docs/research/` | designs, implementation plans, research notes |

Outside the repo there are three places, one per kind of content:
- `~/.config/workspace/`: configuration and secrets (`names.toml`, `private/<slug>.md`,
  `credentials`);
- `~/.local/share/workspace/`: local data to keep: the dictionaries, and
  `projects/<slug>/` for what a project never puts in git (worktrees, logs, locks, deploy files,
  evidence with real data), same slug as in the repo, created by `ws project new`, mode 700;
- `~/.cache/workspace/`: what can be rebuilt.

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
