---
name: checkpoint
description: Closes an iteration on a workspace project. Updates the project's CONTINUE.md ("Onde parei" and "Próximo passo"), decisions and task files, then validates, commits and pushes the project folder to main with the ws checkpoint commands. Use only when the user says so in words ("fecha a iteração", "checkpoint", "salva onde parei", or that the iteration is over); not when the model merely finishes a piece of work.
---

# Checkpoint

## Overview

At the end of an iteration the project folder says where the work stopped and what comes next, and
it is committed and pushed the same way every time. The daily reads the "Próximo passo" of each
project, so a checkpoint keeps its "Hoje" right. Prose written into the project is PT-BR; these
instructions are in English.

This skill is model-invocable (no `disable-model-invocation`) on purpose: it is the exception the
root `CLAUDE.md` makes for this repo, which says to commit and push to `main` at the end of each
iteration without asking. It writes nothing outside the repo and runs only on the user's words
listed in the description.

The `ws checkpoint` commands run git as `git -C <repo root>`, so the folder the session is in
does not matter. Never build the git steps by hand and never skip a hook.

## Steps

1. **Slug.** The project the session is working on (`projects/<slug>/`). If it is not clear, ask
   the user which one. `standalone` and `ai-studies` have no `CONTINUE.md` and are refused.
2. **Check.** Run `ws checkpoint check <slug>`: JSON verdict, exit 0 when ok.
3. **Update the files.**
   - `## Onde parei` in `CONTINUE.md`: what was done in this iteration, the state of branches and
     deploys.
   - `## Próximo passo`: the next concrete action, short (at most 15 non-blank lines and 1,500
     characters).
   - New decisions in `decisions.md`, and the task files touched.
   - Follow the project's own `CLAUDE.md` (PT-BR prose, analogs instead of real names).
4. **Check again.** Run `ws checkpoint check <slug>` until it is ok; fix what it lists.
5. **Diff.** Run `ws checkpoint diff <slug>` (changed and new files, diffstat, refused files) and
   write the message from it.
6. **Commit.** Run `ws checkpoint commit <slug> -m "docs: <what changed>"`. The message is PT-BR,
   prefix `docs:`, `chore:`, `feat:`, `fix:` or `test:`, at most 72 characters, with no
   co-author trailer and no "Generated with" line. The command validates, commits only
   `projects/<slug>/`, pulls with rebase, checks again and pushes to `main`.

## When the command refuses

- **Not on `main`** (detached HEAD or a worktree branch): tell the user and stop.
- **Files outside `projects/<slug>/` modified, staged or untracked:** list the paths, tell the
  user they must be committed separately, and stop. Do not stash, add or discard them.
- **Conflict on the pull:** the rebase is aborted and the local commit is kept. Show the
  conflicting paths and stop; never force-push and never resolve it silently.
- **New-word refusal at push** (`pre-push`): the commit stays local. Run `ws names pending`, ask
  the user one question with every word and your guess for each ("Acme: real name or harmless
  term?"), apply the answer (`ws names add REAL --analog ANALOG` and mask what carries it, or
  `ws names known WORD...` and commit `.known-words`), then run `ws checkpoint commit` again: it
  pushes the pending commit. Never put the question on GitHub.
- **Large or binary new file** (over 200 KB, under `evidence/` or `attachments/`): ask the user
  whether to include it. Only on a yes, run `commit` again with `--include PATH`.
- **Another hook refusal** (secrets, real names): fix or mask the text (`ws mask --in-place FILE`)
  and run `commit` again.
- **Non-fast-forward after the retry, or any other failure:** print the message as is and stop.

## Report

Reply in one or two lines: the slug, the commit message and whether it was pushed. If it was not,
say why and what the user has to do.
