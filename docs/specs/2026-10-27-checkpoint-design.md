# Checkpoint (end of an iteration): design

Item 3 of `docs/backlog.md` "Next skills". Status: design, 2026-10-27, revised after a spec review
the same day.

## Goal

At the end of each iteration on a project, the project folder in the workspace says where the work
stopped and what comes next, and it is committed and pushed, the same way every time. The daily
reads the "Próximo passo" of each project, so a checkpoint keeps the daily's "Hoje" right.

## Why

The user asked for every iteration to end with the workspace updated and pushed, without asking
(root `CLAUDE.md`, "Sync and commits"). Today each chat does it by hand, with a different shape
each time; one project's `CONTINUE.md` has no "## Próximo passo", so the daily warns about it.

## Decisions (taken while the user was away, to confirm)

- **Required sections of `CONTINUE.md`:** `## Onde parei` and `## Próximo passo`, the template's
  names, each with text that is not the template's placeholder. `## Branches e worktrees` stays
  optional; other sections are free.
- **Model-invoked, on the user's words only:** "fecha a iteração", "checkpoint", "salva onde
  parei", or the user saying the iteration is over. This is the exception the root `CLAUDE.md`
  makes for this repo (commit and push to `main` without asking); a GitHub write anywhere else
  still needs `disable-model-invocation`.
- **Strict scope:** only `projects/<slug>/` (and `.known-words`, see below) goes into the commit;
  anything else modified, staged or untracked (not ignored) → refused, naming the paths, so the
  user commits it separately.
- **A push refused for a new word or a secret** (decided after the review of the skill): the local
  commit already carries the text, and `pre-push` checks every pushed commit, so a new commit on
  top does not clear it. A harmless word → `ws names known WORD`; `.known-words` is the one file
  outside the project that `commit` accepts, and it goes in a new commit with the next run. A real
  name or a secret → mask the files (`ws mask --in-place FILE`) and `ws checkpoint commit SLUG
  --amend`, which rewrites the unpushed checkpoint commit; allowed only when exactly one commit is
  unpushed and it touches only `projects/<slug>/` and `.known-words` (never a pushed commit).
- **The whitelabel project:** its first checkpoint renames `## Onde está` to `## Onde parei` and
  adds `## Próximo passo`; it runs in that project's own chat, not here, since other chats edit
  the file.

- **Decided after the final review (2026-10-27):** `commit` refuses unless the repo's git hooks are
  installed (`ws setup`), since they are the only scan before GitHub; it refuses when an unpushed
  commit touches anything outside `projects/<slug>/` and `.known-words`, naming those commits (push
  them separately first); its result lists `commits_pushed`, and `pushed` is true only when
  something was pushed; network git calls have a timeout and never prompt for credentials.

## The commands

All run git as `git -C <repo_root>`, never from the caller's folder. The slug must match
`^[a-z0-9][a-z0-9-]*$` and `projects/<slug>` must be a real folder (not a symlink) with a
`CONTINUE.md`; `standalone` and `ai-studies` have none and are refused with a clear message.

- `ws checkpoint check SLUG` — JSON verdict, exit 0 when ok, 1 otherwise. Problems: no
  `CONTINUE.md`; a required section missing, empty or equal to the template's placeholder text; the
  `## Próximo passo` section over 15 non-blank lines or 1,500 characters; no `decisions.md`. The
  sections are read with the daily's parser (`standup._section`), so the check and the daily never
  disagree.
- `ws checkpoint diff SLUG` — what a commit would take: the project's changed and new files and the
  diffstat; new binary files or files over 200 KB under `evidence/` or `attachments/` are listed
  as refused unless passed with `--include PATH`. The skill reads it before writing the message
  (root rule: run `git diff` before the message).
- `ws checkpoint commit SLUG -m MESSAGE [--include PATH...] [--amend]` — in this order (with
  `--amend`, step 3 amends the single unpushed checkpoint commit instead of adding one):
  1. refuse unless on branch `main` (no detached HEAD, no worktree branch);
  2. validate the message (prefix `docs:`/`chore:`/`feat:`/`fix:`/`test:`, at most 72
     characters), the check, and that nothing outside `projects/<slug>/` is modified, staged or
     untracked; refuse new large or binary files not passed with `--include`;
  3. `git add -A -- projects/<slug>` and commit (the hooks run; a refusal is printed as is);
     nothing to commit → go on to push any unpushed commit;
  4. `git pull --rebase origin main` on the now clean tree; on a conflict, `git rebase --abort`,
     keep the local commit, print the conflicting paths, stop (never force);
  5. run the check again (two chats' edits can merge cleanly and still break the sections);
  6. `git push origin main`; a non-fast-forward → one more pull and push, then report; a
     `pre-push` refusal (secrets, new words) leaves the commit local and is printed as is: the
     next run pushes it after the user answers.

## The skill `checkpoint`

1. Find the slug: from the project the session is working on, otherwise ask.
2. `ws checkpoint check <slug>`.
3. Update `## Onde parei` (what was done in this iteration, the state of branches and deploys),
   `## Próximo passo` (the next concrete action, short), new decisions in `decisions.md`, and the
   task files touched. The project's `CLAUDE.md` rules apply (PT-BR prose, analogs for real names).
4. `ws checkpoint check <slug>` again until ok.
5. `ws checkpoint diff <slug>`; write the message from it.
6. `ws checkpoint commit <slug> -m "docs: <what changed>"`. A new-word refusal at push → ask the
   user, all words in one question (root `CLAUDE.md`), apply the answer, run `commit` again (it
   pushes the pending commit).

## Tests (pytest, throwaway repos with a bare remote)

The check: each problem with a passing and a failing case, the placeholder text, the size limits.
The commit: an invalid or traversal slug; not on `main`; a file outside the project modified or
untracked; a new large file without `--include`; stages only the project; the pull runs after the
commit and a conflict aborts the rebase and keeps the commit; the check runs again after the pull;
pushes to the bare remote; nothing to commit pushes a pending commit; a bad message is refused
before committing.

## Out of scope

Task records under `projects/<p>/tasks/` with their own "Onde parei" (phase B, part 2); updating
Jira from a checkpoint.
