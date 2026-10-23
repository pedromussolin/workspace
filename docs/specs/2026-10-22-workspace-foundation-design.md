# Workspace foundation — design

- **Date:** 2026-10-22
- **Status:** v2 (2026-10-23), waiting for review. v2 adds the lessons
  from `docs/research/2026-10-23-agent-workspace-concepts.md` and
  `docs/research/2026-10-23-dev-agent-kit-review.md`.
- **Scope:** subproject 1 of 3 (repo, migration, guardrails, CLI skeleton)

## Goal

A personal, private repo (`github.com/pedromussolin/workspace`) that becomes
the single home for personal planning projects and automations. It is AI
first: Claude does the judgment work through skills and MCP servers. Every
automation also has a deterministic fallback, the `ws` CLI, for when an MCP
server fails.

The work is split into three subprojects, each with its own spec and plan:

1. **Foundation** (this spec): repo, migration of the two existing
   workspaces, guardrails, `ws` CLI skeleton, versioned skills.
2. **Change requests (GMUD):** create the GMUD in the company Jira Service
   Management portal from a reviewed file.
3. **Jira board:** create/update issues, status from git, standup summary,
   board hygiene.

Subprojects 2 and 3 are designed after the Atlassian MCP is explored live
(boards, sprints, Service Management request types and fields).

## Decisions taken (brainstorming, 2026-10-22)

| Topic | Decision |
|---|---|
| AI + fallback | **File as contract, two executors.** The AI writes a file (the GMUD fields, a board change plan); the MCP applies it, and the `ws` CLI applies the same file through the REST API as fallback. Both paths support a dry run. Starts in subproject 2; subproject 1 lays the CLI. |
| Language | See "Language rule" below: code context in English, task/business context in PT-BR, chat in the language the user writes in. |
| Python | `uv` only, never `pip`. |
| Source of truth | `workspace`. The old repos get a "moved" notice and are archived on GitHub (read-only, reversible). Nothing is deleted, locally or remotely. |
| History | Migrated with full history, rewritten into the project subfolder, so `git log` and `git blame` keep working per file. |
| Tuning approved | Secrets hook; unified rules and private files; `ws mask`; versioned skills; generic tools; project template. |
| Board scope | Automations touch only issues assigned to the user. Never other developers' issues, never unassigned ones. Enforced in code (subproject 3). |
| GMUD target | The company Jira Service Management portal. The site URL lives only in local config. A personal API token is allowed for the fallback. |
| Enforcement (v2) | Hard rules are hooks or deny rules, never prose only. Every gate script fails closed: an internal error blocks. |
| Context budget (v2) | Root `CLAUDE.md` under 200 lines, project `CLAUDE.md` short, MEMORY.md an index; procedures live in skills. |
| Write skills (v2) | Skills that write outside the repo (Jira, GMUD) use `disable-model-invocation: true` and follow plan → validate → approval → execute. |
| Search (v2) | No RAG for now: structure plus grep. `ws search` (SQLite FTS5) only after measured misses; vectors last. |
| Reuse (v2) | From dev-agent-kit, only the ideas listed in "Reuse from dev-agent-kit"; its code is not copied. |

## Language rule

| English (code context) | PT-BR (task/business context) |
|---|---|
| `src/`, `tests/`, CLI commands, flags and messages | everything under `projetos/`: folder names, file names and prose |
| `skills/` (names and `SKILL.md`) | the project template content (`templates/project/`) |
| `docs/specs/`, root `README.md` and root `CLAUDE.md` | what the automations produce for people: GMUD text, Jira issues and comments, standup |
| config files (`names.toml`, `config.toml`), hook | commit messages |

Chat follows the language the user writes in. The root `CLAUDE.md` states
this rule.

## Context budget (v2)

Every always-loaded byte is paid on every turn. The workspace keeps the
always-loaded part small and pushes detail to on-demand loading:

| Always loaded | Budget | On demand |
|---|---|---|
| root `CLAUDE.md` | under 200 lines (target about 80) | project `CLAUDE.md`, read when working in that project |
| skill name + description | one or two sentences each: what it does and when to use it | `SKILL.md` body (under 500 lines), then its `references/` (one level deep) |
| `MEMORY.md` | one line per memory, an index | the memory files |
| MCP tool names | deferred schemas (Claude Code default) | schemas, loaded when a tool is used |

Scripts bundled with a skill are executed, not read, so deterministic work
costs only its output.

## Repository layout

```
workspace/
├── CLAUDE.md                common rules: confidentiality, masking, commits, sync, language
├── README.md                index of projects, automations and setup
├── pyproject.toml           the `ws` CLI (uv project)
├── uv.lock
├── src/ws/                  CLI package
├── tests/                   pytest suite for `ws`
├── skills/                  versioned Claude skills, symlinked into ~/.claude/skills
│   └── change-request/      today's `criando-gmud`, moved and renamed
├── templates/
│   └── project/             template used by `ws project new` (PT-BR content)
├── projetos/
│   ├── artemis-v2/              ← artemis-workspace, with history
│   └── reestrutura-whitelabel/  ← whitelabel-workspace, with history
├── docs/specs/              one design per subproject
├── docs/research/           research notes and reviews that feed the specs
├── hooks/                   Claude Code hook scripts, registered in ~/.claude/settings.json
└── .githooks/pre-commit     git hook: runs `ws check-secrets --staged`
```

Two kinds of hook, both gates:
- **Git hooks** (`.githooks/`) run on `git commit` from anywhere: the
  terminal, the editor, Claude.
- **Claude Code hooks** (`hooks/`) run before or after Claude's tool
  calls. They also cover rules git cannot see, such as which files Claude
  may read.

## Private files (outside the repo)

Everything sensitive lives in `~/.config/workspace/`, never in git:

| File | Content |
|---|---|
| `names.toml` | Real name → analog table. Single source for `ws mask` and for the hook. Each entry: `real`, `analog`, optional `aliases`, and `case_sensitive` for names that are also common Portuguese words (a few partner names are). Also lists company domains to block. |
| `private/artemis-v2.md` | Moved from `~/repos/.artemis_v2/privado.md`. |
| `private/reestrutura-whitelabel.md` | Moved from `~/repos/.reestrutura_whitelabel/privado.md`. |
| `config.toml`, `credentials` | Jira site, API token (mode 600). Created in subproject 2. |

The old `privado.md` paths become symlinks to the new files, so stale
references still resolve. Heavy local folders (worktrees, logs, locks,
baseline failure lists, Playwright) stay where they are; the tools keep
finding them through the same `PRIV` environment variable they use today.

`names.toml` is built from the masking table in memory
(`artemis-workspace-nomes-mascarados`). That memory then points to the file
instead of holding the table.

## Guardrail: secrets hook

Today the confidentiality check is a manual `grep` written in each
project's `CLAUDE.md`. It becomes automatic:

- `.githooks/pre-commit` runs `ws check-secrets --staged`.
- `ws setup` sets `core.hooksPath=.githooks` in the clone.
- It checks only **added lines** of the staged diff, for:
  1. **Secret patterns:** the union of today's two greps (password, senha,
     secret, API key, credentials inside URLs, `.io` hosts, `10.x.x.x`
     IPs, `/home/<user>` paths). `token` is flagged only as an assignment
     (`token = …`, `token: …`) or as a known token prefix (GitHub `gh*_`,
     Atlassian `ATATT`). "Token de design" stays allowed.
  2. **Real names** from `names.toml`: accent-insensitive, word boundaries,
     case-sensitive only when the entry says so.
  3. **Company domains** listed in `names.toml`.
- On a hit it prints `file:line: term` and blocks the commit.
- **Fails closed:** without `names.toml` the hook blocks, so a fresh clone
  on another machine cannot commit unmasked text by accident.
- Known false positives go to `.secrets-allow` in the repo (pattern +
  path), reviewed like any other change.
- `ws check-secrets --all` scans the whole tree (used once in the
  migration).
- The AI never uses `git commit --no-verify`.
- **Fail closed (v2):** an exception inside the check blocks the commit.
  Git blocks on any non-zero exit. Claude Code blocks only on exit 2, so
  its hook scripts catch every error and exit 2.

## Guardrail: Claude Code hooks and deny rules (v2)

User-level, in `~/.claude/settings.json`, so they hold in every repo:

| Gate | Kind | Status |
|---|---|---|
| Block `git commit` commands carrying a Co-Authored-By trailer | `PreToolUse` hook on `Bash`, `hooks/block_co_authored_by.py` | done on 2026-10-23, tested live |
| Deny Claude's `Read` of `~/.config/workspace/credentials` | permission deny rule | this subproject |

`ws setup` checks that both are registered and prints the JSON to add when
they are missing; it never edits `~/.claude/settings.json` itself.

## The `ws` CLI (subproject 1 scope)

- Python 3.12, uv project, installed with
  `uv tool install --editable ~/repos/workspace`, so `ws` is on the `PATH`
  for skills running from any directory.
- Standard library only in subproject 1 (`argparse`, `tomllib`,
  `subprocess`). `pytest` and `ruff` as dev dependencies.

| Command | What it does | Origin |
|---|---|---|
| `ws setup` | Idempotent. Sets the hooks path, symlinks `skills/*` into `~/.claude/skills/`, checks the files and permissions in `~/.config/workspace/`, checks the Claude Code gates above, and prints what is missing. | new |
| `ws check-secrets [--staged \| --all \| PATH…]` | The guardrail above. | today's two greps |
| `ws mask [--in-place \| --check] [FILE \| -]` | Replaces real names with analogs from `names.toml`. `--check` exits 1 if a real name remains (same engine as `check-secrets`). | new |
| `ws project new <slug>` | Copies `templates/project/` into `projetos/<slug>/`. | new |
| `ws slot [-n N] -- <cmd>` | Runs a heavy command in one of N slots (file lock), so parallel agents do not exhaust memory. | `ng-slot.sh` |
| `ws git assemble --base B --from WIP --to FINAL [--subjects FILE]` | Creates FINAL from B (`--no-track`), cherry-picks WIP, optionally rewrites subjects, and checks the 72-character limit. | `juntar-branch.py` (no hardcoded base) |
| `ws git merge-rehearsal --repo R --base B [--resolutions DIR] [--check CMD] BRANCH…` | Merges the branches over B in a throwaway worktree, applies known conflict resolutions, then runs an optional check command. | generic part of `merge-teste.sh` |

Project-specific scripts (`validar-leva.sh`, `smoke*.mjs`,
`portal-local.sh`, `bff-sandbox-proxy.mjs`, `mover.mjs`) stay where they
are, in `projetos/reestrutura-whitelabel/anexos/scripts/`, with their
current names. `ng-slot.sh` keeps working at its old path until the
whitelabel briefs switch to `ws slot`.

## Skill conventions (v2)

Every skill in `skills/` follows these rules:
- **Description:** what it does plus when to use it, in the third person.
  It is the only part always loaded, and it alone decides when the skill
  triggers.
- **Size:** `SKILL.md` under 500 lines. Detail goes to `references/`,
  linked one level deep.
- **Scripts:** deterministic steps are `ws` commands or bundled scripts,
  which Claude runs instead of reading.
- **Writes outside the repo** (Jira, GMUD, GitHub):
  - `disable-model-invocation: true`, so the skill runs only when the user
    types `/name`;
  - the flow is plan → validate (`ws … --dry-run`) → explicit approval →
    execute.
- **Evals:** each skill gets about 5 cases: should trigger, should not
  trigger, an edge case, and "must not write without approval". The tool
  that runs them (`claude plugin eval` or skill-creator evals) is chosen in
  subproject 2, with the first skill that writes. `change-request` moves in
  this subproject without evals; they are added in subproject 2.

## Knowledge base and search (v2)

The project notes are the workspace's memory. For a few hundred Markdown
files, grep over a good structure beats a vector index: it is exact,
always fresh, and auditable.
- **Structure:**
  - each project `README.md` is the index of its folder (task table,
    status);
  - one decision per row in `decisoes.md`;
  - one task per file.
- **New documents** created from the template start with a short header:
  `Status`, `Data` and `Tags`.
- **Migrated documents** are not rewritten.
- **`ws search`** (SQLite FTS5, ranked full-text search with snippets) is
  built only after real queries are seen to miss.
- **Vectors** (sqlite-vec and a local multilingual embedding model) come
  only if FTS5 still misses: notes mix PT-BR and English, and
  paraphrases are where embeddings help.

## Reuse from dev-agent-kit (v2)

The review found little worth carrying over. Ideas, not code:

| Idea | Where it lands |
|---|---|
| Structured result with evidence that the executor produced, never the model's word | the file contract of subprojects 2 and 3: the dry-run output is the evidence the approval gate checks |
| Process hygiene: kill the whole process group on timeout, cap output, redact secrets | `ws slot` and any later `ws` command that runs external processes |
| Loop and idle detection | later, only if `ws` ever drives an agent loop |
| CI template: actions pinned by SHA, `permissions: contents: read`, `persist-credentials: false` | a future CI for this repo (out of scope here) |

Not carried over: the 29 role agents, the 31 skills and their copies,
provider fan-out, the Codex executor and the monitor.

## Project template and conventions

The migrated projects keep their folder and file names; nothing inside
`projetos/` is renamed. `templates/project/` captures the convention both
already share, so a new project starts the same way:

| Path | Purpose |
|---|---|
| `README.md` | visão geral, tabela de tarefas, situação atual |
| `CLAUDE.md` | regras específicas do projeto (as comuns ficam na raiz) |
| `CONTINUAR.md` | como um chat novo retoma o trabalho |
| `decisoes.md` | decisões pendentes e tomadas, com dono, data e motivo |
| `tarefas/` | uma tarefa por arquivo |
| `evidencias/` | números de produção com data e a consulta para repetir |
| `anexos/` | SQL, protótipos, scripts, briefs |

The Artemis project has no `CONTINUAR.md` today; one is created during the
migration from its README status.

## Migration

1. **Preflight:** both repos clean and in sync with `origin` (true on
   2026-10-22, checked again right before), and no other chat writing to
   them during the migration.
2. Install `git-filter-repo` with `uv tool install`.
3. Fresh clones into `~/.cache/workspace-migration/` (not `/tmp`, which
   disappears when WSL restarts).
4. `git filter-repo --to-subdirectory-filter projetos/<slug>` on each
   clone.
5. In `workspace`: skeleton commit, then
   `git merge --allow-unrelated-histories` of each rewritten clone.
6. Rules: common rules go up to the root `CLAUDE.md`; each project
   `CLAUDE.md` keeps only what is specific; absolute paths updated
   (`~/repos/workspace/projetos/…`, `~/.config/workspace/private/…`).
7. **Verify:**
   - file count per project matches the original;
   - `ws check-secrets --all` is clean;
   - `git log --follow` on a sample file shows the commits from before the
     migration.
8. **Publish:** `gh repo create pedromussolin/workspace --private`, push
   `main`.
9. **Freeze the old repos:** one commit in each adding a notice at the top
   of `README.md` and `CLAUDE.md` ("Movido para
   `workspace/projetos/<slug>` em 22/10/2026; este repo está arquivado"),
   push, `gh repo archive`. Local folders stay. A chat that later tries to
   push to them fails loudly instead of silently diverging.
10. **Outside the repo:**
    - private files moved to `~/.config/workspace/`, with symlinks at the
      old paths;
    - `names.toml` built;
    - `criando-gmud` becomes `skills/change-request/`, rewritten in English
      (its description still triggers on "GMUD"; the GMUD text it produces
      stays PT-BR), symlinked into `~/.claude/skills/`; the old folder goes
      to `~/.claude/skills/.trash/`;
    - memories updated to the new paths: the two sync rules, masking,
      parallel agents (script paths), the two-chats note and the workspace
      project memory.

## Sync and commit rules (root `CLAUDE.md`)

- `git pull` before working; at the end of each iteration, commit and push
  straight to `main`, without asking (same as today's workspaces).
- Atomic commits with prefixes `docs:`, `chore:`, `feat:`, `fix:`, `test:`;
  no task ID; message in PT-BR, at most 72 characters.
- No `Co-Authored-By`.
- The hook runs on every commit; a block is fixed, never bypassed.
- The company-repo git rules (`TS-…` branches and commits, `-sdbx`
  replication) stay in `~/repos/CLAUDE.md` and do not apply here.

## Testing

- `pytest` for `ws`:
  - `mask`: case flag, accents, aliases, idempotence;
  - `check-secrets`: each pattern, staged-only lines, fail-closed without
    `names.toml`, allowlist;
  - `project new`;
  - `slot`: two runs with `-n 1` serialize;
  - `git assemble` and `git merge-rehearsal` on temporary repos;
  - the Claude Code hook scripts: block, pass, and fail closed on bad
    input.
- `ruff check` clean.
- The migration checks in step 7.

## Out of scope (subprojects 2 and 3)

- Atlassian client, credentials, `ws cr …` (change request) and
  `ws jira …` commands, the `jira-board` skill.
- Exploring the Atlassian MCP live, before those specs.
- `ws search` and any vector index (see "Knowledge base and search").
- CI for this repo.
