# Moving a release to another date

Use it when the user wants a published release to go on another date (`OLD` to `NEW`). A release
missed on its date is the usual reason, so `OLD` may be in the past; `NEW` may not.

1. **Ask** the new date and the reason in one sentence ("a validação da operação passou para a
   semana seguinte"). The reason goes into the comment the script leaves on the old PRs.
2. **Preview:** `ws release preview move OLD NEW --reason "TEXT" [--delete-old-branches]`
   (add `--project SLUG` when needed). It writes nothing to GitHub. On exit 1 it prints `problems`
   (for example `release/NEW` is already taken in a repo): fix or ask, then run it again.
   Otherwise it prints `code`, `summary`, `calls`, `next`, `warnings`, `residual_dates` and
   `left_in_old`.
3. **Show** the `summary` lines as printed, the code, every `warnings` line and every `residual_dates`
   entry (`repo`, `pr`, `text`): a line of a new body that still has a `DD/MM` or `DD/MM/YYYY` of
   the old date. The script changes `YYYYMMDD`, PR numbers and the `Release:` line only; prose such as
   "revisão de 23/10" may or may not be the release date, so the user decides each one. To change
   one, edit the PR on GitHub after the move or ask the user to. A `warnings` line "PR #N has no
   Release: line" is a single-branch PR whose date was not changed: say so.
4. **What the plan does**, per repo, for the user:
   - multi-branch: copies `release/OLD[-sdbx]` to `release/NEW[-sdbx]` (same commits), opens the
     new PRs with the new date, closes the old open PRs with a comment that points to the new one
     (a merged old PR gets a comment only), and fixes the cross-references between the new PRs;
   - single-branch: no branch and no new PR; only the `Release: DD/MM/YYYY` line of the code and
     sandbox PR descriptions changes;
   - with `--delete-old-branches`: deletes `release/OLD[-sdbx]` on `origin`, only when every PR
     from that head is closed or merged (or closed by this plan) and no open PR has it as its base.
     Otherwise the plan has a problem `release/OLD stays: ...` naming the PR; without the flag
     the old branches stay. Offer the flag only when the user wants the old branches gone;
   - local, after the pushes: the branches `release/OLD[-sdbx]` become `release/NEW[-sdbx]` (with
     their upstream), the worktrees and the folder `release-OLD/` become `release-NEW/` (with
     `release.toml`, `pr/` and `published.json`), and the drafts get the new date. All of it is a
     line of the `summary`. `left_in_old` lists what is in `release-OLD/` and will not move (a note
     of the user, say); the folder stays until the user clears it.
5. **Approval:** run `ws release move OLD NEW --reason "TEXT" [--delete-old-branches] --approve
   CODE` as its own Bash call, with exactly the flags of `next`. The approval gate shows the user
   the summary; the user's yes there is the approval. Never put the preview and this call in one
   command line.
6. **Read the result:** `done`, `failed`, `not_sent`, `uncertain`, `prs`, `warnings`, and
   `left_in_old` on success. Show the `warnings`, and tell the user what `left_in_old` holds.
   - `failed`: say which call failed and what was not sent; `not_moved_yet` lists what is still in
     `release-OLD/`. Rerun the preview (it plans what is still missing) before anything else.
   - `uncertain: true`: tell the user to check GitHub (the new PRs, the closed old ones). Never retry
     blindly: rerun the preview and show it.
7. **After:** tell the user that the GMUD window and the PR numbers changed, and offer
   `ws release status NEW --links` for the new block. A later `ws release publish NEW` (a second
   sandbox PR, for example) works from the moved folder.
