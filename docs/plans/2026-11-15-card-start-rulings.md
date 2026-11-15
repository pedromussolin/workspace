# ws card start: rulings and follow-ups

Decisions made on the user's behalf while building `ws card start` (plan `docs/plans/2026-11-15-card-start.md`), each with what it costs if wrong, and the small items left for later. Source: the execution log, deleted after the merge.

## User decisions

- Approach A, per-repo base (default master), repos from the item then the title prefix (--repo overrides), branch in the current checkout with --worktree opt-in (1a 2a 3a 4a, 15/11).
- The 12 builder decisions listed in the spec were approved as a block ('ok card', 15/11).

## Rulings

- Task 3: fix round 1 (7c57a87: fetch 60 s timeout, GIT_TERMINAL_PROMPT=0, ssh BatchMode; option-like branch names refused). complete. Merged. Ruling: accept the forced GIT_SSH_COMMAND for fetch — the user has no core.sshCommand/GIT_SSH_COMMAND set (checked) — cost if wrong: a custom ssh command is ignored by fetch only. superseded: the fix wave made fetch keep the user's GIT_SSH_COMMAND or core.sshCommand.
- Ruling: explicit --kind/--desc that differ from the task's single existing branch → a problem naming the existing branch (drop the flags to reuse it, or remove it first), not a silent reuse — the flags state intent; a silent second name or silent reuse both surprise — cost if wrong: one extra rerun without the flags.

## Deferred (follow-ups)

- Task 5: review Approved (sonnet). complete (cef388b..6bcf754). Merged into feat/card-start. minor (deferred): temp file open follows a symlink (O_EXCL/O_NOFOLLOW); no fsync.
- Task 2: review Approved (sonnet). complete (cef388b..02a3f8a). Merged into feat/card-start. minor (deferred): test for missing/empty timeZone.
- Task 3: fix round 1 (7c57a87: fetch 60 s timeout, GIT_TERMINAL_PROMPT=0, ssh BatchMode; option-like branch names refused). complete. Merged. Ruling: accept the forced GIT_SSH_COMMAND for fetch — the user has no core.sshCommand/GIT_SSH_COMMAND set (checked) — cost if wrong: a custom ssh command is ignored by fetch only. minor (deferred): respect an existing core.sshCommand.
- `codeposition._fetch_env` keeps its own simpler ssh rule; share it with `gittools.fetch` later.
