# Git

Sync and commits in this repo.

- Pull before working. [review]
- At the end of each iteration, commit and push straight to `main`, without asking. [review]
- Commits are atomic, prefixed `feat:`, `fix:`, `docs:`, `chore:` or `test:`, with no task ID, in
  PT-BR, at most 72 characters. [review]
- Run `git diff` before writing the message. [review]
- No `Co-Authored-By` trailer: the commit is the user's responsibility. [hook]
- No "Generated with" line in the message. [review]
- Never `--no-verify`, `git commit -n` or a `core.hooksPath` override. [gate]
- `git push` and `gh` writes go in their own short Bash call: see the Bash section of
  [`instructions/user.md`](../../instructions/user.md). [review]
- The company-repo git rules do not apply here: no `TS-…` branches or commit prefixes, no `-sdbx`
  replication, no "never commit on master". [review]

## Current behaviour

`ws checkpoint commit` checks the prefix and the 72-character limit of its own commits, and
`ws git assemble` checks the limit of the subjects it rewrites. The Claude Code hook
`hooks/block_co_authored_by.py` also blocks a commit with a co-author trailer.
