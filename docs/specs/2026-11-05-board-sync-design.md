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

**Profiles, proofs and per-repo settings (user, 2026-11-05/06, replaces the first version of
D4).** The config must fit any company and any delivery structure, not only the current one. An
environment is a question — which commits are in it? — answered by one *proof*. A *profile* is an
ordered list of environments; each repo (or glob of repos) uses one profile and may switch some of
its environments off. Changing company means rewriting the profiles, never the code.

```toml
[board]
remote = "origin"            # default
lookback_days = 120          # default
fetch = true                 # default
default_profile = "gitops"   # the profile of every repo without its own

# A profile: environments in order, statuses rising. Each environment has one proof.
[[board.profiles.gitops.environments]]
name = "sandbox"
status = "validation"
proof = "branch"
branches = ["sandbox", "staging"]   # the first that exists on the remote

[[board.profiles.gitops.environments]]
name = "master"
status = "ready_deploy"
proof = "branch"
branches = ["master", "main"]

[[board.profiles.gitops.environments]]
name = "production"
status = "done"
proof = "file"                      # GitOps: image tags written in a deploy repo
deploy_repo = "{repo}-argocd"
deploy_branch = "master"
image_tag = 'prod-([0-9a-f]{7,40})'

# Release by tag in the code repo itself.
[[board.profiles.release-tag.environments]]
name = "main"
status = "ready_deploy"
proof = "branch"
branches = ["main"]

[[board.profiles.release-tag.environments]]
name = "production"
status = "done"
proof = "tag"
tag = "v*"                          # the most recent tag matching the glob

# Anything else (a deploy API, Kubernetes, an observability tool): a read-only command that
# prints the deployed shas, one per line.
[[board.profiles.api.environments]]
name = "production"
status = "done"
proof = "command"
command = ["~/bin/deployed-sha", "{repo}", "{env}"]
timeout = 20                        # seconds, default 20

[board.repos."some-repo"]
profile = "release-tag"

[board.repos."data-*"]
inactive = ["sandbox"]              # declared, switched off: proves nothing in these repos

[board.repos."*-argocd"]
ignore = true                       # deploy repos are proof sources, not code

[board.repos."*-workspace"]
ignore = true

# Status names in the tracker for the statuses a move can reach (global: one board).
[board.statuses]
in_progress = "Em andamento"
validation = "In Validation"
ready_deploy = "Ready Deploy"
done = "Concluído"
```

Every proof gives, for one repo and one environment, the commits that represent the environment;
a commit is in the environment when it is reachable from every one of them:
- `branch`: the tip of the first `<remote>/<name>` that exists.
- `tag`: the most recent tag (by creation date) whose name matches the glob, in the repo itself.
  Repos whose profile uses a `tag` proof are fetched with `--tags`; the others with `--no-tags`.
- `file`: every sha the `image_tag` pattern captures in `<remote>/<deploy_branch>` of the deploy
  repo (`deploy_repo` with `{repo}` replaced; a sibling under the same root). A captured sha that
  does not resolve in the repo while others do is a warning `deploy <repo>: tag <tag> not found
  in this repo`, and the environment holds (fail closed): it stays in the repo's cap and no commit
  of the repo is in it. When none resolves, the tags belong to another app: the environment is
  unavailable in that repo (warning `no image tag of this repo`).
- `command`: argv with `~`, `{repo}` and `{env}` expanded, run without a shell, with `timeout`;
  each stdout line is a sha (7 to 40 hex) that must resolve in the repo. A failure to run, a
  non-zero exit, a timeout, a line that is not a sha or an unresolved sha is a warning
  `proof <repo>/<env>: <error>`, and the environment holds (fail closed): it stays in the repo's
  cap and no commit of the repo is in it. Exit 0 with no sha means nothing is deployed there: the
  environment is unavailable in that repo. The command must only read; that is the user's
  responsibility, stated in the README.

Which settings a repo gets: the `[board.repos]` table whose key is the repo's exact name; else the
first table, in file order, whose key is a glob (`fnmatch`) matching the name; else none. A repo
table holds `ignore = true` alone, or any of `profile` (default `default_profile`) and `inactive`
(names of environments of that profile). An inactive environment is declared but proves nothing:
its proof is not run and it does not count in the repo's cap.

Validation (`ConfigInvalid` with the key path): `default_profile` names an existing profile; each
profile is non-empty, with unique environment names and statuses in `in_progress`..`done`
strictly rising; `proof` is one of `branch`, `tag`, `file`, `command`, with exactly its own keys
(`branches`; `tag`; `deploy_repo`, `deploy_branch`, `image_tag`; `command`, `timeout`) and no
others; `deploy_repo` formats with `{repo}` only; `image_tag` compiles with exactly one group;
`command` is a non-empty list of strings; repo tables reference existing profiles and
environments; unknown keys anywhere in `[board]` are refused, and the keys of the first version
(`environments` at the top, `ignore_repos`, `direct_deploy_repos`, a repo's `branches` or
`deploy_repo`) are refused with a message showing the new form; `[board.statuses]` has a name for
every status any profile uses, plus `in_progress`, and each name maps back to its own status
through the tracker's status mapping (`[jira.status_overrides]` today), so "forward only" never
rests on a wrong mapping. Without a `[board]` table, `ws board` exits 2 and says what to add; the
daily then falls back to the activity-only report.

## Positions (`ws.codeposition`, git only)

Per repo under `repo_roots`, after the fetch:

1. Commits: `git log --branches --remotes=<remote> --no-merges --since=<lookback>
   --format=%H%x1f%s` (branches and remote branches only: archived worktree refs, stashes and
   other refs are not work in progress), keys taken from the subject with the collector's
   `keys_in`. Only keys of the cards passed in are kept.
2. Environment refs: the proofs of the repo's profile, active environments only (see Config).
   The commit must be reachable from **every** commit a proof gives (all brands deployed); the
   preview names the tag that holds it, only when the commit already reached the environment
   just before the one the tag proves.
3. Membership: one `git rev-list --since=<lookback> <ref>` per environment ref, kept as a set.
   Each commit takes the highest environment that contains it; remote-only rules from D7 apply.
4. Output per key: `rung`, `environment` (the name, in the list of the repo that decided the
   rung, of the environment with that rung), `holding` (the branch or tag that keeps it lower,
   when one does), `repos` and `stale` (a fetch failed).

**A repo holds a card only as far as it can prove (refines D6, 2026-11-05).** Each repo has a cap:
the highest rung among the active environments of its profile whose proof gave commits or failed
(a proof that failed holds; a repo without the sandbox branch on the remote has no sandbox; a repo
without a remote has none). A commit that reached its repo's cap does not hold
the card. The card's rung is the lowest rung among the commits below their repo's cap; when every
commit is at its cap, the card takes the highest cap among them. A card with any commit is at least
in progress. So a repo without proofs only proves "in progress", and an ignored repo proves
nothing.

## Risks: alternative and warning (user, 2026-11-05)

Every risk found while planning has a way around it, a warning, or both. Warnings are short
English strings in `warnings`; the skills say them in PT-BR.

| Risk | Alternative | Warning |
|---|---|---|
| A fetch fails (no credentials, network) | the last fetched refs are used; moves still come, since old refs only under-report | `fetch <repo>: <error>`; positions from that repo carry `stale: true` |
| A repo has no `remote` (local or personal repo) | `ignore = true` in its `[board.repos."..."]` table leaves it out entirely | one line listing the repos without the remote that were not ignored (they prove only "in progress") |
| A card's code lives only in repos that cannot prove production (a deploy repo, a repo with no deploy tags) | a profile that fits the repo (`file`, `tag` or `command` proof); deploy and config repos are `ignore = true`, since one commit there may be for any environment | the card goes to `limited` ("the git proves only up to <status> in <repos>") |
| The deploy repo is not under `repo_roots`, or none of its tags belongs to the repo | a profile with the right `deploy_repo` for those repos | `deploy <repo>: <deploy repo> not found` or `deploy <repo>: no image tag of this repo in <deploy repo>`, only for repos with commits of open cards |
| A `command` proof fails, times out or prints an unknown sha | the environment holds in that repo (fail closed): it stays in the repo's cap and none of the repo's commits is in it, so they hold the card below it | `proof <repo>/<env>: <error>` |
| A key is the prefix of another (`TS-15`, `TS-150`) | keys are taken whole from the subject (word boundary), tested | none needed |
| A cards file without `is_epic` (old file, MCP fallback) | a card that is the `epic_key` of another card is an epic too | `cards without is_epic: epics known only as parents; run ws task list again` |

## Commands

- **`ws board status --cards FILE`**: fetch (D9), compute positions for the open cards of `FILE`
  (the `ws task list` output), apply the rules and print JSON: `moves` (key, from, to, Jira status
  name, reason), `held` (cards that stay, with the reason), `limited` (see Risks), `to_confirm`
  (D8) and `warnings`.
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
- A generic tracker (user, 2026-11-06): the config names the tool (`[tracker] kind`), each tool
  is an adapter with its own dependencies and scripts, and the skills are only the interface.
  A separate subproject with its own spec; this one keeps its drafts neutral (`op = "move"`,
  `key`, `to`) and its statuses canonical so it fits.
