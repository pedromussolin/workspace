# New-name check — design

- **Date:** 2026-10-26
- **Status:** v1. The flow was approved in conversation on 2026-10-26; the details under "What
  counts as a new word" and "Open points" are waiting for review.
- **Scope:** one addition to the confidentiality check. Everything else in the check stays as it
  is.

## Problem

`ws check-secrets` blocks only the real names already in `names.toml`. A new partner, client or
colleague written into a note before getting an entry passes every hook. That is the most likely
leak in this repo, and none of the open "Confidentiality check" items in `docs/backlog.md` covers
it.

## Decisions (2026-10-26)

| Topic | Decision |
|---|---|
| Rest of the check | Frozen. The other "Confidentiality check" backlog items move only when a real case shows up. |
| Where the user approves | Locally: in the conversation, or in the terminal. Never on GitHub (an issue, a PR comment): the question itself would carry the real name, and `names.toml` exists only on the user's machine. |
| Where it blocks | At push, not at commit. A local commit publishes nothing, so commits stay frictionless and nothing reaches GitHub without an answer. |

## Flow

1. **Commit (warn).** `pre-commit` and `commit-msg` find the new words in the added lines and in
   the message, add them to the pending list and print a warning. The commit goes through.
2. **Push (block).** `pre-push` refuses the push while the pending list is not empty, and prints
   the words.
3. **Review.** By default Claude asks in the conversation, every pending word in one question,
   with its guess for each ("Acme: real name or harmless term?"). Without Claude, `ws names review`
   asks the same questions in the terminal.
4. **Answer.**
   - **Real name:** an entry in `names.toml` with an analog the user approves; `ws mask
     --in-place` on the files; the unpushed commits that carry the name are rewritten. Once the
     name is in `names.toml`, the existing `pre-push` range check blocks any commit that still
     carries it, so a missed rewrite cannot be pushed.
   - **Harmless term** (`Celery`, `Datadog`): appended to `.known-words`, which is committed and
     shows in the diff. It holds only harmless words.
5. **Push** goes through once the pending list is empty and the range check is clean.

## What counts as a new word

- A run of at least three letters that starts with an uppercase letter (`Acme`, `ACME`), in an
  added line or a commit message. Lowercase words are not checked.
- It is known, and so ignored, when any of these holds (compared lowercased and without accents):
  - it appears anywhere in the tracked text files of the pushed state (`origin/main`). That
    covers the first word of a sentence ("Depois" is known because "depois" is) and everything
    already in the repo, which was scanned and masked before;
  - it is listed in `.known-words`;
  - it is an analog in `names.toml`.
- A real name already in `names.toml` is not a new word: the existing check blocks it, as today.

## Known limits

- A new real name that is also a common word already in the repo (as the case-sensitive entries
  of `names.toml` are) passes. Those keep entering `names.toml` by hand, as today.
- A name written in lowercase only is not caught.
- Between the commit and the review, the name sits in local history. It never leaves the machine.
- An AI-added `.known-words` entry needs no human click, like `.secrets-allow` (see
  `docs/backlog.md`). The root `CLAUDE.md` rule: a word goes to `.known-words` only after the
  user's answer, and the reply says so.

## Pieces

| Piece | Change |
|---|---|
| `src/ws/` | new-word detection (vocabulary of the pushed state, cached by its sha in `~/.cache/workspace/`); `ws names review` |
| `.githooks/pre-commit`, `commit-msg` | also run the new-word warning; the exit code still comes only from the current check |
| `.githooks/pre-push` | also blocks on pending words |
| `.known-words` | new file at the repo root, one word per line, `#` comments |
| root `CLAUDE.md` | one paragraph: what to do when the hook warns |

## Tests

- Detection: sentence-start word known through its lowercase form; accents; analog known;
  `.known-words` known; word in a commit message; a word already pushed is known.
- `pre-commit` warns and exits 0; `pre-push` blocks with the list and passes once the words are
  known or masked.
- `ws names review` with a temporary config dir: a real name lands in `names.toml`, a harmless
  term in `.known-words`.

## Open points

- **Pending list stored or computed.** The approved flow keeps it in a local file under
  `~/.config/workspace/`. It can instead be computed from the unpushed commits each time (the
  same detection over `origin/main..HEAD`): same behavior, no state file that can drift, and it
  also works when `pre-commit` did not run. Recommended: computed.
