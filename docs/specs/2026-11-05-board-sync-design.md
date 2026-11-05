# Board sync: design

Date: 2026-11-05. Status: written, waiting for the user's review.

## Goal

Cards follow the code. When a card's code reaches the sandbox, the card goes to validation; when it
reaches production, the card is done. One command builds every move the code proves and asks for
one approval. The daily stops suggesting wrong moves.

## What went wrong (checked on 2026-11-05)

On 2026-11-04 the user merged the releases into `sandbox` and `master`, and the deploy ran; no card
moved. The review of 2026-11-05 found 10 open cards whose code was already inside the production
image tags (two of them still in "a fazer"), one card in the sandbox still in "a fazer", and two
cards with commits still in "a fazer". The causes:

1. **The rules ignore where the code is.** `ws.taskstatus` has two rules: R1 (todo + any commit or
   branch with the key → in progress) and R2 (in progress or review + any merged PR → validation).
   R2 does not look at the PR base, and no rule leads to done. The daily of 2026-11-05 suggested
   "em andamento" for cards already in production.
2. **Weak evidence.** R1 takes a branch name as proof of work: two branches with no commit of their
   own (TS-5464, TS-5532) became suggestions. Epics enter the rules: R2 suggested validation for
   the epic TS-5357.
3. **Nothing applies the moves.** Each move needs a `/card mover`; with wrong suggestions, none was
   applied.
4. **Stale refs.** The collector never fetches: `origin/*` is as old as the last manual fetch.

## Decisions (user, 2026-11-05)

- **D1. One command, one approval.** A command builds every move the code proves and sends it
  through the `/card` preview and apply (the same approval box). The daily offers it; the model
  also runs it when the user says they merged or deployed.
- **D2. Done means deployed.** A card is done when its code is inside the production image tag of
  the deploy repo. Merged into `master` but not deployed yet means ready for deploy.
- **D3. Code Review stays out.** No rule leads to `review`; a card already in review is treated as
  in progress.
- **D4. Everything is configurable.** Environment names, the branches of each environment (with
  per-repo overrides), the production proof and the Jira status names live in the local
  `config.toml`, so another company with other branch names needs only a new config.

## Decisions taken while writing (to confirm)

- **D5. Forward only.** A move never goes back on the ladder and never touches a card that is
  blocked, cancelled, done or an epic.
- **D6. The least advanced piece wins.** A card's position is the lowest position among its
  commits. One commit outside every environment holds the card in progress, and the preview names
  the branch that holds it. An abandoned branch therefore holds its card until it is deleted or
  merged; the reason is shown, so the user decides.
- **D7. Evidence is a commit, not a branch.** A piece is a non-merge commit whose subject carries
  the key (word boundary: `TS-554` never matches `TS-5549`), by any author. Merge commits are left
  out, so the `-sdbx` copies and the release merges add nothing. Local commits count for "in
  progress"; only remote refs count for the environments.
- **D8. Tested in the sandbox is the user's word.** Validation → ready for deploy has git proof
  only when the code reaches `master` (D2). Before that, the daily asks "Testado na sandbox?" for
  cards in validation for at least one workday.
- **D9. Fetch first.** `ws board status` runs `git fetch --prune <remote>` in every repo and deploy
  repo, in parallel (up to 8 at a time). It touches only remote-tracking refs. A failed fetch is a
  warning, and that repo's positions are marked stale.
- **D10. Bounded history.** Only commits of the last `lookback_days` (default 120) are read.
- **D11. One source of environment branches, later.** The gate's `environment_branches` and the
  release spec's `sandbox_branch` stay as they are. Deriving them from `[board]` is a follow-up.

## The ladder

| Position | Proof | Target status (canonical) |
|---|---|---|
| 0 | no commit with the key | none (stays) |
| 1 | a commit outside every environment (D6, D7) | `in_progress` |
| 2 | every commit inside an environment whose status is `validation` | `validation` |
| 3 | every commit inside an environment whose status is `ready_deploy` | `ready_deploy` |
| 4 | every commit inside an environment whose status is `done` | `done` |

The current status maps to a rung: `todo` 0, `in_progress` and `review` 1, `validation` 2,
`ready_deploy` 3, `done` 4. A move is proposed only when the target rung is above the current one.
Environments are not nested (a hotfix may reach `master` without passing `sandbox`), so each commit
takes the highest environment that contains it, and the card takes the lowest of its commits.

## Config (`config.toml`, outside the repo)

```toml
[board]
remote = "origin"          # default
lookback_days = 120        # default
fetch = true               # default

# In order, from the first environment to the last. `status` is the card status the
# environment proves; the statuses must rise along the list.
[[board.environments]]
name = "sandbox"
branches = ["sandbox", "staging"]
status = "validation"

[[board.environments]]
name = "master"
branches = ["master", "main"]
status = "ready_deploy"

[[board.environments]]
name = "production"
status = "done"
# Proof by image tag: every tag the pattern finds in the deploy repo's branch.
deploy_repo = "{repo}-argocd"
deploy_branch = "master"
image_tag = 'prod-([0-9a-f]{7,40})'

# Optional: other branch names for one repo.
[board.repos."some-repo".branches]
sandbox = ["homolog"]

# Jira status names of the statuses a move can reach.
[board.statuses]
in_progress = "Em andamento"
validation = "In Validation"
ready_deploy = "Ready Deploy"
done = "Concluído"
```

Validation (`ConfigInvalid` with the key path): unique environment names; `status` in
`in_progress`..`done` and strictly rising; each environment has `branches` or `deploy_repo` (not
both); `image_tag` compiles and has exactly one group; repo overrides name existing environments;
`[board.statuses]` has a name for every status an environment uses, plus `in_progress`. Without a
`[board]` table, `ws board` exits 2 and says what to add; the daily then falls back to the
activity-only report.

## Positions (`ws.codeposition`, git only)

Per repo under `repo_roots`, after the fetch:

1. Commits: `git log --all --no-merges --since=<lookback> --format=%H%x1f%s`, keys taken from the
   subject with the collector's `keys_in`. Only keys of the cards passed in are kept.
2. Environment refs: for `branches`, the first of `<remote>/<name>` that exists (per-repo override
   first). For `deploy_repo`, `git grep -hoE <image_tag> <remote>/<deploy_branch>` in the deploy
   repo (a sibling under the same root); each captured sha that resolves to a commit in this repo
   is a ref, and shas of other apps are ignored. The commit must be reachable from **every**
   resolved tag (all brands deployed); the preview names the tag that holds it.
3. Membership: one `git rev-list --since=<lookback> <ref>` per environment ref, kept as a set.
   Each commit takes the highest environment that contains it; remote-only rules from D7 apply.
4. Output per key: `rung`, `environment`, `holding` (the branch or tag that keeps it lower, when
   one does), `repos` and `stale` (a fetch failed).

**A repo holds a card only as far as it can prove (refines D6, 2026-11-05).** Each repo has a cap:
the highest rung among the environments it has (a deploy repo has `master` but no sandbox and no
image tag of its own; a personal repo has none). A commit that reached its repo's cap does not hold
the card. The card's rung is the lowest rung among the commits below their repo's cap; when every
commit is at its cap, the card takes the highest cap among them. A card with any commit is at least
in progress. So a personal repo only proves "in progress", and the deploy repo's `master` commit of
a card does not keep it from done once the code repos are deployed.

## Commands

- **`ws board status --cards FILE`**: fetch (D9), compute positions for the open cards of `FILE`
  (the `ws task list` output), apply the rules and print JSON: `moves` (key, from, to, Jira status
  name, reason), `held` (cards that stay, with the reason), `to_confirm` (D8) and `warnings`.
  Read-only for Jira.
- **`ws board drafts --board FILE`**: one `move` draft per move in a new folder under
  `cards/drafts/sync-<timestamp>/`; prints the folder. The existing `ws card preview <folder>` and
  `ws card apply <code>` do the rest: one preview, one approval box, the same checks (the
  transition must exist in Jira).
- **`ws standup report --board FILE`**: `moves` and the suggestions come from the board file; R1
  and R2 are removed from `ws.taskstatus` (the stuck check stays). Adds `to_confirm`. Without
  `--board`, no suggestions.

## Jira

`jira.FIELDS` gains `issuetype`; each card gets `is_epic` (`issuetype.hierarchyLevel >= 1`, which
does not depend on the type's name or language). The daily's MCP fallback asks for the same field.

## Skills

- **`daily`:** a new step after the cards: `ws board status --cards ... > board.json` (exit 2 or 1:
  go on without it and add a warning). The report runs with `--board`. The note becomes "Para
  você: /card sincronizar (N cards)" instead of the list of `/card mover`, and lists `to_confirm`
  as "Testado na sandbox? TS-5537 (desde 03/11)".
- **`card`:** a "sincronizar" flow: `ws board status`, `ws board drafts`, then the usual preview
  and apply. The description gains "/card sincronizar".
- **The model, outside the skill (D1):** when the user says they merged or deployed, the model runs
  the same commands; the apply still stops in the approval box, which is the hard rule. The
  trigger is recorded in memory, not in a skill, because `card` keeps
  `disable-model-invocation: true`.

## Tests

pytest, no network:
- Temp git repos with a bare remote: environments by branch, a deploy repo with two values files
  (two tags, one stale), merge vs non-merge commits, an empty branch, a local-only commit, a
  per-repo override, a hotfix that skips the sandbox, a key that is a prefix of another.
- Rules: forward only, epics and blocked or cancelled cards skipped, review counted as in progress.
- Config: each validation error.
- Report: moves and `to_confirm` from a board file; no suggestions without one.
- Evals: rerun only the daily cases whose fixtures change (`out-of-sync-card`, `daily-request`).

## Out of scope

- The Code Review status (D3); applying without approval; Jira automation or GitHub Actions.
- Moving other people's cards (the `/card` guard already refuses them).
- Chaining transitions when the workflow has no direct one: the preview shows the error and the
  user moves the card by hand.
- Unifying `environment_branches` and the release spec's `sandbox_branch` with `[board]` (D11).
