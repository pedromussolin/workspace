# Card review package: design

Date: 2026-11-15. Status: approved by the user (2026-11-15): a local Markdown file opened in VS
Code next to the diff; a `ws` collector plus a skill. Plan: `docs/plans/2026-11-15-card-review.md`.

## Intent

AI agents build the Artemis work in the company repos and the user reviews every change before it
is committed. About 15 reviews come before 24/11, each starting by rebuilding the same picture by
hand: which files changed, which are migrations or contract, what is uncommitted, which env vars
and tests moved, what the card asked. One file per card gives it: what changed and why, the risks,
where to look first, the tests, a checklist. The collection is deterministic, so it is a `ws`
command (script first); the skill only reads the diff, judges and writes the prose.

## Goals, non-goals, anti-goals

- **Goals.** `ws review pack TS-N` writes `pack.json`: per repo, every change of the task branch
  against its merge base with the remote base, committed or not, by kind, plus new migrations, env
  var names added or removed, test files and the card context. `/card-review TS-N` turns it into
  `review.md` (PT-BR) and prints its path. A rerun rebuilds both.
- **Non-goals.** Running tests, linters or builds (a later version may); other people's pull
  requests or remote branches; comparing two runs; the `-sdbx` copy.
- **Anti-goals.** No tracker writes; no commit, push, stash, switch or other change to the repos
  (the only git write is `git fetch`); nothing leaves the machine: the files never enter the
  workspace repo, an Artifact, the tracker, GitHub or a chat paste.

## Approaches

Output medium:
- **A. Local file (picked by the user).** Opens in VS Code beside the diff, `path:line` links jump
  to the code, it outlives the chat, and it may hold company code: it never leaves the data folder.
- **B. Chat answer.** Scrolls away, cannot sit beside the diff, costs context on each follow-up.
- **C. HTML page (Artifact).** Published to claude.ai: company code would leave the machine.

Who collects:
- **A. Collector plus skill (picked; script first).** Merge base, untracked files, renames,
  categories, migrations and env vars come out the same every time, for no tokens.
- **B. Skill only.** The model runs git by hand, forgets untracked files or the merge base, and
  varies between runs.

## The command

`ws review pack REF [--repo NAME]... [--project SLUG]`

- **Repos**, as `ws card start`: `--repo`, else the item's `repos` (the item whose `card = "REF"`),
  else the title's first `[PREFIX]` in `[board.prefix_repos]`, else a problem naming the three
  ways. A repo is the first `<root>/<name>` with `.git` under `[standup] repo_roots`.
- **Base**: `refs/remotes/<remote>/<base>` with `[board] remote` and `base_for(name)`, after
  `gittools.fetch`. A failed fetch is a warning (the last fetched base is used, `fetched: false`);
  a missing base ref is a problem naming `[board.repos."<name>"] base`.
- **Branch**: the current branch when `cardstart.is_task_branch(current, REF)`; else the only local
  task branch. Checked out in another worktree (such as `.worktrees/<repo>-<REF>`): read there.
  Checked out nowhere: committed changes only, with a warning. None, or two: a problem.
- **Changes**: the work tree against the merge base (`git diff -M <merge_base>`), plus untracked
  files (`git ls-files --others --exclude-standard`). Per file: `path`, `old_path` (rename, copy),
  `abs_path`, `status`, `added`/`deleted` lines (null for a binary), `binary`, `stages` (any of
  `committed`, `staged`, `unstaged`, `untracked`), `hunks` (first new-side line of each hunk, at
  most 20) and `category`. A file changed on the branch and reverted in the work tree is not listed.
- **Commits**: `sha` and `subject` of `<merge_base>..<branch>`, oldest first.

**Categories**, first match wins: the repo's config rules (in the order written), then the
defaults below, then `other`. Globs: `*` stays in a folder, `**` crosses folders (the envcheck rule).

| Category | Default globs (abridged) |
|---|---|
| `test` | `**/tests/**`, `**/test_*.py`, `**/*_test.py`, `**/conftest.py`, `**/*.spec.ts`, `**/__tests__/**` |
| `migration` | `**/alembic/versions/*.py`, `**/migrations/versions/*.py` |
| `contract` | `**/api/**`, `**/routes/**`, `**/routers/**`, `**/endpoints/**`, `**/controllers/**`, `**/schemas/**`, `**/serializers/**`, `**/openapi*.{json,yaml,yml}` |
| `model` | `**/models/**`, `**/models.py`, `**/entities/**` |
| `config` | `**/Dockerfile*`, `**/*.toml`, `**/*.ini`, `**/*.cfg`, `**/*.y*ml`, `**/.env*`, `**/requirements*.txt`, `**/package*.json`, `**/settings.py`, `**/config.py`, `**/environment*.ts`, `.github/**` |
| `front` | `**/*.ts`, `**/*.tsx`, `**/*.js`, `**/*.html`, `**/*.scss`, `**/*.css` |
| `other` | everything else (plain code, docs) |

```toml
[board.repos."acme-front"]
review_categories = { front = ["src/app/models/**"], contract = ["src/app/api/**"] }
```

**Signals** (per repo):
- `migrations`: the migration files at the merge base and in the new tree, read with
  `ws.release.migrations`: `added` (`path`, `revision`, `down_revision`), `changed_existing` (a
  migration that exists at the base and was modified or deleted), `heads_before`, `heads_after`.
- `env`: `ws.envcheck.scan_python` (and `scan_shell` for the profile's shell files) over the whole
  Python tree at the merge base and in the new tree, so a settings class whose base lives in an
  unchanged file still resolves; `added` (`name`, `required`, `where`) and `removed`. The profile
  is `[env_check.repos.<name>]` when present, else a plain one. Skipped when no `.py` or shell file
  changed.
- `tests`: test files `added` and `changed`.
- `flags` (top level, each prefixed `<repo>: `): an existing migration changed or deleted; more
  than one Alembic head after the change; a required env var added (check the Parameter Store); code
  changed with no test file changed.

**Card context** (read-only): `ref`, `title`, `type`, `status`, `done_when` (the `## Pronto
quando` section). The port gains the `description` capability and `Tracker.description(ref)` (plain
text; Jira converts ADF). Without it, or without the section, `done_when` is null with a warning.

**Output.** stdout is one JSON object, the same as `pack.json`: `ref`, `card`, `project`,
`folder`, `pack_path`, `review_path`, `generated_at`, `repos_from`, `repos` (each `name`, `path`,
`worktree`, `branch`, `base`, `base_ref`, `fetched`, `merge_base`, `diff_command`, `commits`,
`files`, `by_category` with `files`/`added`/`deleted`, `migrations`, `env`, `tests`), `flags`,
`problems`, `warnings`. `diff_command` is the exact read-only `git -C ... diff` for the skill.

**Files.** `~/.local/share/workspace/projects/<slug>/reviews/<REF>/` (`WS_DATA_DIR` moves the
root), folders mode 700, `pack.json` mode 600 (temp file and `os.replace`). Slug: `--project`, else
the item's project, else `standalone`. Each run rewrites `pack.json` and deletes an earlier
`review.md`, which no longer matches. Absolute paths and real names are fine: never published.

**Exit codes**, as `ws card start`: 0 ok; 1 problems (pack still written, with them); 2 setup (no
`[board]`, invalid config, tracker setup); 3 tracker refused or unreachable; on 2 and 3 nothing is
written and stderr says `ws review pack: ...`.

## The skill `card-review`

Not `review` nor `code-review` (both exist). Runs `ws review pack REF` (flags only from the user's
words); on exit 1 shows the problems in PT-BR and asks only what the user settles (repos, the
project), then reruns. Reads each repo's diff with `diff_command` per file, flagged and
`migration`, `contract`, `model`, `config` first; lockfiles and generated files by counts only;
untracked files with Read. Writes `review.md` beside `pack.json` in PT-BR:

1. `# Revisão REF: <title>`, a line with status, repos, branch and `generated_at`;
2. `## O que mudou e por quê`, per repo, tied to `done_when`;
3. `## Riscos`: `flags` first, then migrations, contract, env vars, toggles, data; or "nenhum";
4. `## Olhar primeiro`: 3 to 8 links `[path:line](<abs_path>#L<line>)`, each with the reason;
5. `## Testes`: changed and added test files, and what `done_when` asks that no test covers;
6. `## Arquivos por tipo` from `by_category`; `## Checklist`, 5 to 8 `- [ ]` lines.

Then it prints the absolute path of `review.md` (for `code <path>`) and the top three risks. It
never commits, pushes, runs tests, writes the tracker or copies the review anywhere.

## Failure and rerun

- No task branch, two task branches, a missing repo or base ref: a problem for that repo; the
  other repos are still collected and the pack is written with exit 1.
- A dirty tree is fine: the uncommitted work is what gets reviewed.
- A failed fetch, an unreadable migration or Python file: a warning; a failing git read: a problem.
- Rerun any time: `pack.json` is replaced and `review.md` deleted, then rewritten by the skill.

## Left to the builder

Default globs beyond the table, the skill's PT-BR wording, JSON key order, test fixtures.
