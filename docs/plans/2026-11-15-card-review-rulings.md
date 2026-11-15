# ws review pack: rulings and follow-ups

Decisions made on the user's behalf while building the per-card review package (plan `docs/plans/2026-11-15-card-review.md`), each with what it costs if wrong, and the small items left for later. Source: the execution log, deleted after the merge.

## User decisions

- The package is a local markdown file read in VS Code next to the diff (option 1), never in the workspace repo (15/11).

## Rulings

- Ruling: reviewdiff runs every work-tree diff against a temporary copy of the index (GIT_INDEX_FILE), and the pack writes each repo's full diff to `<repo>.diff` (mode 600) in the pack folder, so the skill reads that file instead of running git in the company repo; `diff_command` stays only as an informational string — keeps "git only fetches and reads" literal and avoids index.lock races with the user's editor — cost if wrong: one extra file per repo in the private pack folder.

## Deferred (follow-ups)

- Task 1: review Approved (sonnet). complete (3f519db..1da4430). Merged. minor (deferred): glob_regex recompiled per call; order tests for tests/migrations and environment.ts.
- Task 4: minor (deferred): _plain in jira_adapter duplicates cardrules.adf_text (move both into ws.adf with a flag once card rules pin behavior); a codeBlock inside a list item ('- ```') is not seen as a fence by done_when.
- Deferred: split-index repos still bump sharedindex mtime (content same, no lock); skill greps a/ b/ headers — pin --src-prefix/--dst-prefix if a repo sets diff.noprefix; fetch ConnectTimeout; _plain nested lists; boardconfig imports envcheck; untracked symlinks/nested repos not in diff_file; a codeBlock inside a list item; glob cache untested.
