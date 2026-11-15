---
name: card-review
description: Builds the local review package of a task before its changes are committed, from `ws review pack`, and writes a PT-BR `review.md` (what changed and why, risks, where to look first, tests, checklist). Use when the user asks to review a task's changes or for its review package ("/card-review TS-5431", "monta a revisão do TS-5431", "revisão do card TS-5431"). Read-only: never commits, pushes or writes to the task tracker.
---

# Card review

The user reviews every change the AI agents make before it is committed. `ws review pack REF` does
the deterministic part (which files changed, committed or not, by kind, new migrations, env vars,
tests, the task's context). You read the diff, judge it and write one file, `review.md`, that the
user opens in VS Code beside the diff. Lines to the user and `review.md` are PT-BR; these
instructions are in English.

The file carries company code, so it stays on this machine: it lives only under
`~/.local/share/workspace/projects/<slug>/reviews/<REF>/`, next to `pack.json` and the
`<repo>.diff` files.

## Steps

1. **Run the pack.** `ws review pack REF`. Add `--repo NAME` (repeatable) or `--project SLUG` only
   when the user's words name them. It prints one JSON object (the same as `pack.json`).
2. **Exit 1** lists `problems` (texts in English). Two cases. If the REF, `--repo` or `--project`
   is invalid, nothing is written: `pack_path`, `folder` and `review_path` are null and there is
   no `card`. Show the problems in PT-BR and stop, with no `review.md`. Otherwise the pack is written
   with its problems: show each one in PT-BR. Ask only what the user can settle: which repos (a
   numbered list, with the names under `[board.prefix_repos]` in `config.toml` as options) or the
   project slug. Then run the command again with `--repo` or `--project`. **Exit 2** (setup:
   `[board]` or the tracker settings) and **exit 3** (the tracker refused or is unreachable): show
   stderr (`ws review pack: ...`) as it is and stop.
3. **Read the pack.** Top level: `flags` (the checks that need a decision), `warnings`, `card`
   (`title`, `status`, `done_when`, the task's "Pronto quando") and `repos`. Per repo: `branch`,
   `worktree`, `diff_file`, `commits`, `files` (each with `path`, `old_path`, `abs_path`, `status`,
   `stages`, `added`, `deleted`, `binary`, `hunks`, `category`), `by_category`, `migrations`,
   `env`, `tests`. The per-repo problems, warnings and flags start with `<repo>: `: use it to tie
   each flag to its repo. The card-level ones (the card, its item, the choice of repos) have no
   prefix. `abs_path` is null for a deleted file, and for every file when the branch is checked out
   nowhere. `env` is null when no `.py` or shell file changed. `migrations` and `tests` can be null
   on a repo that failed. A failed repo has `diff_file` null and empty `files`: show its problem
   and skip its diff.
4. **Read the diff.** Per repo, use Read on its `diff_file`: the whole diff against the merge base
   (committed, staged and unstaged), then each untracked text file as a new file. Never run git
   in the repos, not even `diff_command` (it is there for the user). Each file's part starts with
   `diff --git a/<path> b/<path>`; a rename starts with `diff --git a/<old_path> b/<path>`, then
   `rename from` and `rename to`, and shows only the edited lines. For a long `diff_file`, Grep it
   for the `diff --git` line of a file and Read from there with offset and limit. Read in this
   order: files named by a flag, then categories `migration`, `contract`, `model`, `config`, then
   the rest. An untracked file over 1 MiB is one `# <path>: untracked, ... not shown` line, and an
   untracked symlink or nested repo is not in the file: use the counts.
   Never Read a null `abs_path`. Lockfiles and generated files are read by counts only (`added`,
   `deleted`), and a `binary` file is never read as text.
5. **Write `review.md`** with the Write tool at `review_path`, in PT-BR, with these parts:
   1. `# Revisão REF: <title>`, then one line with the status, the repos, the branch and
      `generated_at`.
   2. `## O que mudou e por quê`: per repo, tied to the task and to `done_when`.
   3. `## Riscos`: the `flags` first, each tied to its repo by the `<repo>: ` prefix, then migrations (several heads, an existing migration
      changed), contract changes, env vars (name each one; when `env` is null write "nenhuma alteração", or skip it; and say to check it in the Parameter
      Store, the AWS store where the apps read their settings), toggles (feature flags) and data
      (what the change does to existing rows). If there is nothing, write "nenhum".
   4. `## Olhar primeiro`: 3 to 8 links `[path:line](<abs_path>#L<line>)`, each with the reason. When `abs_path` is null, write
      plain `path:line` without a link. The
      line comes from `hunks` (the first new-side line of a hunk) or from the diff.
   5. `## Testes`: the test files changed and added, and what `done_when` asks that no test covers.
   6. `## Arquivos por tipo`, from `by_category`; then `## Checklist`, 5 to 8 `- [ ]` lines, short.
6. **Reply** with the absolute path of `review.md`, the line `code <path>` (to open it in VS Code)
   and the three biggest risks, one line each. Nothing more.

## Rules

- Short, direct sentences. Explain a technical term the first time it appears in `review.md`.
- Say "task" and "the task tracker", never a tracker's product name, in these instructions.
- Say only what the diff and the pack show. When you did not read a file, say so.
- A dirty work tree is fine: the uncommitted work is what gets reviewed.
- Rerun any time: `pack.json` and the `.diff` files are replaced and the earlier `review.md` is
  deleted, so write it again.
- Read-only on the repos: never commit, push, stash, switch branches or change a work tree. Run
  no git command in them: even `git diff` can rewrite the index. Do not run tests, linters or
  builds.
- Never write to the task tracker, publish an Artifact, paste the review into a chat, or copy it
  into the workspace repo or anywhere outside the folder above.
