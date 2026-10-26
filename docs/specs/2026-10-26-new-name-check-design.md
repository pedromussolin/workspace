# New-name check — design

- **Date:** 2026-10-26
- **Status:** v1, implemented on 2026-10-26. The flow was approved in conversation on the same
  day; the open point (stored or computed pending list) is decided: computed. The common-word
  dictionary (below) was added on the same day.
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
  - it is an analog in `names.toml`;
  - it is an ordinary word of the common-word dictionaries and stands at the start of a sentence
    (see "Common-word dictionary").
- A real name already in `names.toml` is not a new word: the existing check blocks it, as today.
- The code of the `ws` CLI (`src/`, `tests/`, `hooks/`, `.githooks/`) is not checked: it is
  English, written by us, and its tests use made-up names on purpose. Over the last 50 commits it
  was about 70% of the words reported. `ws check-secrets` still reads it for the names of the
  table. Notes, docs, skills and commit messages are checked.
- The words of a push are those of the added lines and messages of every pushed commit, even if
  a later commit removes the line: the removed line is in the published history. Commits
  reachable from `ws.scanBaseline` are left out, as in the range check.

## Common-word dictionary (2026-10-26)

Most new words are ordinary Portuguese or English words ("Parece", "Backlog") that happen to be
capitalized, and each one blocked the push until answered. A fourth source of known words, the
common-word dictionaries, clears them, with one restriction that keeps it safe.

| Topic | Decision |
|---|---|
| Sources | The Debian word lists of the packages `wamerican` (`usr/share/dict/american-english`) and `wbrazilian` (`usr/share/dict/brazilian`): UTF-8, one entry per line, about 316,000 words once folded. |
| Which entries count | Only entries that start with a lowercase letter and hold letters alone. A capitalized entry is a proper noun (a first name), and an entry with an apostrophe or hyphen never matches a word. Compared with `names.fold` (lowercase, no accents). |
| Where they live | The ws data dir first, `~/.local/share/workspace/dict/` (env `WS_DATA_DIR`), then `/usr/share/dict/` (env `WS_SYSTEM_DICT_DIR`, used by the tests). Each file is looked up on its own. |
| Who installs them | `ws setup`, without root: when neither place has both files it runs `apt-get download wamerican wbrazilian` in a temporary folder of the cache dir (apt checks the packages against its signed index), unpacks each with `dpkg -x` into its own folder, copies the two files to the data dir and removes the folder. Without `apt-get` or `dpkg`, or if the download fails, setup reports the manual command (`sudo apt-get install wamerican wbrazilian`) and goes on. `ws setup --check` never downloads. |
| When they clear a word | Only at the start of a sentence (rule below). In the middle of a sentence the word is still reported, and a word cleared in one place is still reported where it appears mid-sentence. |
| Without the dictionaries | The check still works, only stricter: nothing is cleared. The report adds one line saying so and that `ws setup` installs them (`ws names pending` prints it on stderr, so its list and `--json` stay clean). |

**Why only at a sentence start.** In the middle of a sentence a capitalized word is probably a
name, and a name is often an ordinary word: 7 of the 23 real names in the user's table are
dictionary words (a brand named after a common word, for one). Clearing them everywhere would let
those names through. At the start of a sentence the capital is explained by the grammar, so the
dictionary decides there, and nowhere else.

**The sentence-start rule.** Looking at the text before the word in its line, the word starts a
sentence when that text either

- matches `^[\s>#*\-+|`"'(\[]*(\d+[.)]\s*)?[\s*_`"'(\[]*$`: it is empty, or only a heading, quote,
  list item, ordered item (`1.` or `1)`), table cell start, emphasis, or an opening quote or
  bracket; or
- ends with `[.:!?|]\s*[*_`"'(\[]*`: a period, colon, `!`, `?` or table pipe, then optional
  spaces, emphasis or an opening quote or bracket.

The same rule applies to the lines of a commit message. camelCase parts keep their column, so
in `AcmeTheme` only `Acme` is at a sentence start.

**Measured.** Over the last 50 non-merge commits of `main` (notes and messages only, each commit
against its parent tree): without the dictionary 8 commits and 16 words are blocked; with it, 4
commits and 5 words. The words cleared are ordinary ones (`backlog`, `cleanup`, `survey`,
`revisit`).

**Speed.** Loading the dictionaries takes about 0.2 s, so `ws names check --staged` and `ws names
pending` on the real repo went from about 0.2 s to about 0.4 s. That is under the 1 s that would
justify a cache, so none exists; if it ever does, cache the folded set under the cache dir, keyed
by the size and mtime of the two source files.

## Known limits

- A new real name that is also a common word already in the repo (as the case-sensitive entries
  of `names.toml` are) passes. Those keep entering `names.toml` by hand, as today.
- A new real name that is a dictionary word, written as the first word of a sentence, passes too:
  the dictionary clears it there. In the middle of a sentence it is reported.
- A name written in lowercase only is not caught.
- Between the commit and the review, the name sits in local history. It never leaves the machine.
- An AI-added `.known-words` entry needs no human click, like `.secrets-allow` (see
  `docs/backlog.md`). The root `CLAUDE.md` rule: a word goes to `.known-words` only after the
  user's answer, and the reply says so.

## Pieces

| Piece | Change |
|---|---|
| `src/ws/newwords.py` | new-word detection: vocabulary of the pushed state, `.known-words`, word columns and the sentence-start rule, grouping of the places of each word |
| `src/ws/dictionary.py` | the common-word dictionaries: where they are read from, which entries count, and the download without root used by `ws setup` |
| `src/ws/review.py` | `ws names review`: the terminal loop and the report of what carries the new real names |
| `src/ws/names.py` | `add_name`: appends an entry to `names.toml`, keeping its mode |
| `src/ws/cli.py` | the `ws names` commands below |
| `src/ws/bootstrap.py` | `ws setup` installs the dictionaries (and fixes the rest of the clone by itself, see the README) |
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
- Dictionary: a dictionary word is cleared at each sentence start (line start, heading, quote, list
  and ordered item, table cell, after a period, colon, `!`, `?` or pipe, after emphasis) and
  reported in the middle of a sentence, also for camelCase parts; accents and case; commit message
  lines; the report line and the stderr note when the files are missing; entries that are
  capitalized, with an apostrophe or hyphen are skipped. The fake dictionaries of the tests hold
  made-up words, so no test reads the real ones.
- Install: fake `apt-get` and `dpkg` first on `PATH` (the suite never reaches the network, and a
  guard fails any test that would run the real `apt-get`): the happy path and its arguments, the
  work inside the cache dir and removed afterwards, a failed download, a failed unpack, a missing
  tool, a package without its file or with a link in its place.
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
