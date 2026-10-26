# New-name check — design

- **Date:** 2026-10-26
- **Status:** v1, implemented on 2026-10-26. The flow was approved in conversation on the same
  day; the open point (stored or computed pending list) is decided: computed.
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
| Pending list | Computed, not stored: the same detection over the unpushed commits each time. No state file that can drift, and it works when `pre-commit` did not run. |

## Flow

1. **Commit (warn).** `pre-commit` and `commit-msg` find the new words in the added lines and in
   the message and print a warning. The commit goes through, and so does a failure of the warning
   itself (it is printed, not blocking).
2. **Push (block).** `pre-push` computes the new words of every pushed commit (lines and
   messages) against the text of the remote state, refuses the push while there are any, and
   prints the words. It fails closed: an error blocks.
3. **Review.** By default Claude asks in the conversation, every pending word (`ws names pending`)
   in one question, with its guess for each ("Acme: real name or harmless term?"). Without
   Claude, `ws names review` asks the same questions in the terminal.
4. **Answer.**
   - **Real name:** an entry in `names.toml` with an analog the user approves (`ws names add`);
     `ws mask --in-place` on the files; the unpushed commits that carry the name are rewritten.
     Once the name is in `names.toml`, the existing `pre-push` range check blocks any commit that
     still carries it, so a missed rewrite cannot be pushed. In v1 the rewrite is not automatic:
     `ws names review` lists the work-tree files and the unpushed commits that carry the name.
   - **Harmless term** (`Celery`, `Datadog`): appended to `.known-words` (`ws names known`),
     which is committed and shows in the diff. It holds only harmless words.
5. **Push** goes through once no pending word is left and the range check is clean.

## What counts as a new word

- A run of at least three letters that starts with an uppercase letter (`Acme`, `ACME`), in an
  added line or a commit message. Lowercase words are not checked. Words are cut at anything that
  is not a letter, so `ACME_API` gives `ACME` and `API`, and also at camelCase edges (`AcmeTheme`
  gives `Acme` and `Theme`, `HTTPServer` gives `HTTP` and `Server`), as `names.toml` matching
  treats those edges.
- It is known, and so ignored, when any of these holds (compared lowercased and without accents):
  - it appears anywhere in the tracked text files of the pushed state. That covers the first word
    of a sentence ("Depois" is known because "depois" is) and everything already in the repo,
    which was scanned and masked before. The pushed state is the remote's tip at `pre-push` (the
    remote sha, else `refs/remotes/<remote>/main`, else nothing: an empty vocabulary), and the
    upstream, else `origin/main`, else nothing elsewhere;
  - it is listed in `.known-words`, read from the commit being pushed (from the index when
    committing), so an entry counts once it is committed;
  - it is an analog in `names.toml`.
- A real name already in `names.toml` is not a new word: the existing check blocks it, as today.
- The words of a push are those of the added lines and messages of every pushed commit, even if
  a later commit removes the line: the removed line is in the published history. Commits
  reachable from `ws.scanBaseline` are left out, as in the range check.

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
| `src/ws/newwords.py` | new-word detection: vocabulary of the pushed state, `.known-words`, grouping of the places of each word |
| `src/ws/review.py` | `ws names review`: the terminal loop and the report of what carries the new real names |
| `src/ws/names.py` | `add_name`: appends an entry to `names.toml`, keeping its mode |
| `src/ws/cli.py` | the `ws names` commands below |
| `.githooks/pre-commit`, `commit-msg` | also run the new-word warning; the exit code still comes only from the current check |
| `.githooks/pre-push` | also blocks on new words, for each pushed range, besides the range check |
| `.known-words` | new file at the repo root, one word per line, `#` comments |
| root `CLAUDE.md` | one paragraph: what to do when the hook warns |

## Commands

| Command | What it does |
|---|---|
| `ws names check (--staged \| --message FILE \| --range REVS) [--against REV] [--tip REV] [--warn]` | Lists the new words; exit 1 when there are any, or always 0 with `--warn` (the commit hooks). `--against` is the revision whose text is the vocabulary (empty: nothing is pushed), `--tip` the commit whose `.known-words` counts for `--range` |
| `ws names pending [--range REVS] [--against REV] [--json]` | The new words of the unpushed commits (default `@{upstream}..HEAD`, else `origin/main..HEAD`) and where each appears |
| `ws names known WORD...` | Appends harmless words to `.known-words`, without repeats; commit the file |
| `ws names add REAL --analog ANALOG [--case-sensitive]` | Appends an entry to `names.toml`, keeping its mode and content; refuses a name already in the table or the analog of an entry |
| `ws names review` | Asks, for each pending word, real name (then its analog), harmless or skip; then lists the files and unpushed commits that carry the real names added |

The commands work on the repo that contains the current directory.

## Tests

- Detection: sentence-start word known through its lowercase form; accents; analog known;
  `.known-words` known; word in a commit message; a word already pushed is known.
- `pre-commit` warns and exits 0; `pre-push` blocks with the list and passes once the words are
  known or masked.
- `ws names review` with a temporary config dir: a real name lands in `names.toml`, a harmless
  term in `.known-words`.

## Decisions taken while implementing

- **Pending list computed.** The open point is closed: nothing is stored under
  `~/.config/workspace/`.
- **No vocabulary cache.** Building the vocabulary of the real repo (368 files) took about 0.12 s,
  under the 1 s that would justify a cache by tree sha, so every run builds it. Revisit if the
  repo grows by an order of magnitude.
- **camelCase edges split words**, an addition to the tokenization rule: a new name inside an
  identifier (`AcmeTheme`) is reported as the name, and the words flagged over the last 50 commits
  of this repo dropped by about a fifth (85 against 105).
- **The commit hooks never block on the warning**, not even when it fails; `pre-push` is the
  gate and fails closed, and it runs both checks for each range before it exits.
- **No history rewrite in v1.** `ws names review` only reports; the range check keeps blocking.
