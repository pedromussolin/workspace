---
name: checkpoint
description: Closes an iteration on a workspace project. Updates the project's CONTINUE.md ("Onde parei" and "Próximo passo"), decisions and task files, then validates, commits and pushes the project folder to main with the ws checkpoint commands. Use only in a workspace session, or when the user names the project, and only when the user says so in words ("fecha a iteração", "checkpoint", "salva onde parei", or that the iteration is over); not when the model merely finishes a piece of work, and not for a "checkpoint" said in a company-repo chat.
---

# Checkpoint

## Overview

At the end of an iteration the project folder says where the work stopped and what comes next, and
it is committed and pushed the same way every time. The daily reads the "Próximo passo" of each
project, so a checkpoint keeps its "Hoje" right. Prose written into the project is PT-BR; these
instructions are in English.

This skill is model-invocable (no `disable-model-invocation`) on purpose: it is the exception the
root `CLAUDE.md` makes for this repo, which says to commit and push to `main` at the end of each
iteration without asking. It pushes only to this repo's `main` and runs only on the user's words
listed in the description.

The `ws checkpoint` commands run git as `git -C <repo root>`, so the folder the session is in
does not matter. Never build the git steps by hand and never skip a hook.

## Steps

1. **Slug.** Run only in a workspace session or when the user names the project: a "checkpoint"
   said in a company-repo chat must not push the personal repo (tell the user and stop). The
   project is the one the session is working on (`projects/<slug>/`). If it is not clear, ask the
   user which one. `standalone` and `ai-studies` have no `CONTINUE.md` and are refused.
2. **Check.** Run `ws checkpoint check <slug>`: JSON verdict, exit 0 when ok.
3. **Update the files.**
   - `## Onde parei` in `CONTINUE.md`: what was done in this iteration, the state of branches and
     deploys.
   - If a required section is missing, rename its equivalent keeping the text (`## Onde está`
     becomes `## Onde parei`); never keep both and never replace content written before this
     iteration. Add `## Próximo passo` right after `## Onde parei`.
   - `## Próximo passo`: the next concrete action, short (at most 15 non-blank lines and 1,500
     characters).
   - New decisions in `decisions.md`, and the task files touched.
   - Follow the project's own `CLAUDE.md` (PT-BR prose, analogs instead of real names).
4. **Check again.** Run `ws checkpoint check <slug>` until it is ok; fix what it lists.
5. **Diff.** Run `ws checkpoint diff <slug>` (changed and new files, diffstat, refused files).
   Compare its file list with what this session touched and name any extra file in the report
   (another chat may be editing the same project). Write the message from it.
6. **Commit.** Run `ws checkpoint commit <slug> -m "docs: <what changed>"`. The message is PT-BR,
   prefix `docs:`, `chore:`, `feat:`, `fix:` or `test:`, at most 72 characters, with no
   co-author trailer and no "Generated with" line. The command validates, commits only
   `projects/<slug>/`, pulls with rebase, checks again and pushes to `main`.

## When the command refuses

- **Not on `main`** (detached HEAD or a worktree branch): tell the user and stop.
- **Files outside `projects/<slug>/` modified, staged or untracked:** list the paths, tell the
  user they must be committed separately, and stop. Do not stash, add or discard them. This
  refusal is normal when another chat is active in the repo: tell the user and stop.
- **Unpushed commits outside the project** (named by short sha and subject), **hooks not
  installed** (`ws setup`) or **"outro processo mudou arquivos durante o pull"**: tell the user
  and stop; the last one is solved by running the command again.
- **Conflict on the pull:** the rebase is aborted and the local commit is kept. Show the
  conflicting paths and stop; never force-push and never resolve it silently.
- **New-word refusal at push** (`pre-push`): the commit stays local. Run `ws names pending`, ask
  the user one question with every word and your guess for each ("Acme: real name or harmless
  term?"), then apply the answer. Never put the question on GitHub.
  - Harmless word: `ws names known WORD...`, then `ws checkpoint commit <slug> -m "chore: ..."`
    again. `.known-words` is the one outside file `commit` accepts; it goes in with that commit,
    which also pushes the pending one.
  - Real name: `ws names add REAL --analog ANALOG` (writes the local `names.toml`), mask the files
    (`ws mask --in-place FILE`), then `ws checkpoint commit <slug> -m "<same message>" --amend`.
    The first commit already carries the real word and `pre-push` checks every pushed commit, so
    a second commit would not clear it: `--amend` rewrites the single unpushed checkpoint commit.
    If more than one commit is unpushed or it touches other paths, `--amend` refuses: stop and
    tell the user.
  - Whenever a word went to `.known-words`, the reply says so.
  - `.secrets-allow` is outside the project: a refusal that needs it means stop and ask the user;
    never loop on "fix or mask".
- **Secret refusal at push** (`pre-push`): same path as a real name: mask the files, then
  `commit ... --amend`.
- **Large or binary new file** (a binary anywhere in the project, or a text file over 200 KB under
  `evidence/` or `attachments/`): ask the user
  whether to include it. Only on a yes, run `commit` again with `--include PATH`.
- **Another hook refusal** at commit time (secrets, real names): fix or mask the text
  (`ws mask --in-place FILE`) and run `commit` again.
- **Non-fast-forward after the retry, or any other failure:** print the message as is and stop.

## Report

Reply in one or two lines: the slug, the commit message and whether it was pushed. If it was not,
say why and what the user has to do. Mention the extra files from step 5 and any word added to
`.known-words`. The command's JSON lists `commits_pushed`; `pushed` is false when there was
nothing to push.
