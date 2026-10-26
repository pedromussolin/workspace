# Backlog

Open items left by subproject 1 (foundation), found by the final review and its re-review on
2026-10-26. None blocks daily use; each was weighed and parked.

## Next

The new-name check: catches a real name that is not in `names.toml` yet, which none of the items
below covers. Design: [docs/specs/2026-10-26-new-name-check-design.md](specs/2026-10-26-new-name-check-design.md).

## Confidentiality check

Frozen since 2026-10-26: these items move only when a real case shows up.

| Item | Why it waits | Fix when picked up |
|---|---|---|
| `pre-push` does not scan the lines a merge commit itself introduces (a conflict resolution) | `pre-commit` and `pre-merge-commit` catch them at commit time; this only matters when a hook did not run | scan merges with `git show --remerge-diff` in `--range` |
| An AI-added `.secrets-allow` entry needs no human click | the root `CLAUDE.md` asks the agent to say so in the reply | an `ask` permission rule on Edit and Write of `.secrets-allow` |
| File names are not scanned (a file named after a partner passes) | no such file today | check staged paths with the same name rules |
| Assignment shapes still missed: `DB_PASS=…`, camelCase `dbPassword=…`, a `\n` escape right before the keyword | rare in planning notes | widen `secret-assignment`, with prose and placeholder tests |
| Secret formats outside the spec's set: PEM headers, AWS `AKIA` keys, `Bearer`/JWT, Azure `AccountKey=` | the spec fixed the rule set | add one rule per format |
| `secret-assignment` is slow on very long `a_a_a_…` lines (seconds at 20 000 characters) | only synthetic or generated lines trigger it | bound the identifier prefix |
| PT-BR commit messages where senha, token or secret is followed by a colon and a word are blocked by `commit-msg` | rewording the message is enough | a message-scoped allow entry, or skip prose shapes in messages |
| `#` lines are skipped by `commit-msg` | same as git's comment stripping; `pre-push` scans the stored message | none needed unless messages are kept with `--cleanup=verbatim` |

## Gates and tools

| Item | Why it waits | Fix when picked up |
|---|---|---|
| The bypass gate misses `xargs git …`, `find -exec git …`, git aliases and quoted operators | best effort; `pre-push` scans every pushed commit | none planned |
| The bypass gate blocks plain reads such as `git config core.hooksPath` and `git grep -e --no-verify` | workaround: `git config --get`, or `--` before the pattern | allow read-only `git config` forms |
| `ws slot` overrides an inherited ignored SIGINT, and Ctrl+C reaches the child twice | harmless for build and test commands | keep `SIG_IGN` when inherited; do not forward SIGINT from a tty |
| The `check-secrets` tail line suggests `.secrets-allow` for a co-author trailer finding, which cannot be allowed | cosmetic | a rule-specific hint |
| README `ws check-secrets` row omits `--message` and `--range` | docs drift | update the row |
| The Claude `Read` deny rule does not cover `cat` of `~/.config/workspace/credentials` | the file does not exist yet | subproject 2, with the credentials |

## Projects and skills

| Item | Why it waits | Fix when picked up |
|---|---|---|
| `skills/change-request/references/tests.md` keeps the old 12-minute Docker recipe | a faster recipe exists in the user's notes | update the recipe |
| `projects/whitelabel-restructure/CONTINUE.md` "Leia antes" does not name the root `CLAUDE.md` | the project is active in another chat; the project `CLAUDE.md` already points there | one line, when that chat is idle |
