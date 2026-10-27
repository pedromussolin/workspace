# Release: design

Item 2 of "Next skills" in `docs/backlog.md`: a skill and a `ws release` command group that build,
publish, move and report the release branches of the company repos, so each deploy stops needing
its own one-off script. Status: design, 2026-10-27. Nothing here is implemented.

## Goal

The user says "release for 27/10 with TS-5424" (or "move the release to 28/10") and gets, in every
repo involved: `release/YYYYMMDD` (the code that goes to `master`) and `release/YYYYMMDD-sdbx` (the
same code plus the `sandbox` branch), the two pull requests (PRs) written in the user's style, and
the PR links ready for the GMUD (the change-request form). Every write to GitHub is previewed and
approved first; nothing is ever merged by the tool.

## Why

The real flow of 20/10 to 27/10 was done by hand and by two throwaway scripts: `renomear.py`
(23/10 to 26/10) and `renomear-27.py` (26/10 to 27/10) in
`~/repos/.reestrutura_whitelabel/release-20261027/`. Each one hard-coded the old PR numbers, the
titles and the reason text, and the second one dropped steps of the first (branch deletion, the
state check of the old PR). The release moved twice in four days, so "move" is not an exception
but part of the flow. A script with the same inputs every time, plus the rules written down as
checks, is cheaper and safer than copying the last script.

## What the real flow looks like (evidence)

- Per repo there are two local worktrees, `<repo>` on `release/DATE` and `<repo>-sdbx` on
  `release/DATE-sdbx`, in a folder named `release-DATE`
  (`projects/whitelabel-restructure/CONTINUE.md:10-12`).
- `release/DATE` = `origin/master` plus the task branches merged in order, with commit subjects
  such as `chore(TS-5424): junta a TS-5431, grupos por ambiente e sem migração` (git log of the
  worktrees). When `master` moved, it is merged into the release (`tasks/24-deploy.md`, entry
  "21/10, manhã").
- `release/DATE-sdbx` = the release plus a merge of `origin/sandbox`, with subjects such as
  `chore(TS-5431): atualiza com a sandbox`. Where `sandbox` has nothing beyond `master`, the tree
  is identical to the release; where it has, only that content comes along
  (`deploy/roteiro-de-deploy.md:210-214`, PR text of the `-sdbx` PRs).
- Two PRs per repo: `release/DATE` to `master`, titled `release(TS-id): summary`, and
  `release/DATE-sdbx` to `sandbox`, titled `chore(TS-id): release DATE do <repo> (sdbx)`. When
  the first sandbox PR is already merged and the release grows, a new PR from the same
  `-sdbx` branch is opened, titled `chore(TS-ids): summary (sdbx)` (front #238 then #239; draft
  `pr-front-sdbx-2.md`). Read with `gh pr list`, read-only, on 2026-10-27.
- Bodies follow the front repo's PR template (`.github/pull_request_template.md`: Tarefa, O que
  muda, Mudanças visíveis, Dependências, Como validei, O que não deu para exercitar, Regra de
  manutenção). The shared and BFF repos have no template and use the same shape in four
  sections: intro, `## O que traz`, `## Antes de subir`, `## Ordem e efeitos`, `## Como validei`
  (`release-20261027/pr-shared.md`, `pr-bff-sdbx.md`). The bodies link the other repos' PRs
  (`<org>/<repo>#N`) in the "depends on / order" text.
- Moving the date: the new branch is the old one pushed under a new name, at the same commit
  (`renomear-27.py:17-19`); the PR is recreated with the old title, body, labels and assignees,
  with the date and the PR numbers replaced (`:20-31`); the old PR is closed with a comment that
  links the new one (`:34`). The 26/10 script also commented on old PRs that were already merged
  instead of closing them, and deleted the old branches (`renomear.py:32-40`); the 27/10 script
  left the old branches and the notes say "apagar à mão" (`CONTINUE.md:24`).
- Deploy order of the services is shared, then BFF, then front (`deploy/roteiro-20261027.md:6`;
  `CONTINUE.md:25`); that is also the order the PRs reference each other.
- `deleteBranchOnMerge` is off in the repos, and the `master` branch has no protection rule readable
  by the user (404 on the protection endpoint); the user merges the PRs by hand in GitHub.

## Decisions (user)

- **Names and targets:** `release/YYYYMMDD` and `release/YYYYMMDD-sdbx`, PRs to `master`; the
  sandbox PR goes to `sandbox` (backlog, item 2; PR list above).
- **Code goes in the original, the `-sdbx` only receives merges**; and a change after the release
  exists goes first to its task branch, then to the release, then to the `-sdbx` after syncing
  with `origin/sandbox` (memory `fluxo-branch-original-e-sdbx.md`; `CONTINUE.md:28-30`;
  `deploy/roteiro-de-deploy.md:1059`).
- **Moving a release keeps the commit:** same commits under the new name, PRs redone, old ones
  closed with a link (`decisions.md`, D132, line 16).
- **Sandbox first, then production with the GMUD** (D40, `decisions.md:92`); the release is
  published only after the possible local validation (D58, `decisions.md:122`).
- **The user publishes and merges:** "Eu commito sem push e entrego a lista exata de branches. O
  [user] publica e abre as PRs" (`decisions.md:162`); commits in the company repos wait for the
  user's review (memory `revisar-antes-de-commitar.md`); the merges are the user's
  (`CONTINUE.md:34`).
- **Git rules of the company repos** (root `CLAUDE.md`): never commit on `master`, pull before any
  action, commit format `type(TS-id): message` in PT-BR with at most 72 characters, no
  `Co-Authored-By`.
- **Script first, and the gate** (root `CLAUDE.md` of this repo, backlog): the `ws` command does the
  mechanical part; every write to GitHub is plan, `--dry-run`, explicit approval, execute; the
  skill sets `disable-model-invocation: true`.
- **Branches from `master` use `--no-track`** (memory `branch-a-partir-de-master-usar-no-track.md`):
  otherwise the editor's Sync pushes to `master`.

## Decisions to confirm (proposals; the sources are silent or disagree)

1. **`-sdbx` always exists for a release.** The 10/10 decision says "`-sdbx` só quando o merge na
   `sandbox` der conflito" (`decisions.md:163`; `roteiro-de-deploy.md:1057`), but every release
   from 21/10 to 27/10 had one, even with an identical tree. Proposal: always, so the script has
   one path and the sandbox PR always comes from a branch named for the release. The 10/10 rule
   stays valid for task branches.
2. **Five commands, not three.** Besides `new`, `move` and `status`: `publish` (push and open the
   PRs) and `branches` (list the task branches of a task id, read-only). Reason: `new` builds
   branches and merges locally and writes nothing outside the machine, so it needs no approval
   gate; `publish` is the step that writes to GitHub and carries the gate. This keeps "dry-run
   writes nothing anywhere" true. The backlog said `new` prints the PR links: `publish` and
   `status --links` do.
3. **The release's main task id** (`--task TS-5424`) gives the PR title prefix and the merge
   commit prefix, because `release/DATE` carries no id in its name and the rule "the id is in
   the branch name" cannot apply. The id is the one the user used in the past titles.
4. **Merge commits made by the script** use `chore(TS-main): junta a TS-<number>, <slug as words>`
   (cut at 72 characters on a word) for each task branch,
   `chore(TS-main): atualiza com a sandbox` and `chore(TS-main): junta a release/DATE na sandbox`
   for the `-sdbx`. The only commits the script makes are clean merges; a conflict stops it, and
   the resolution commit waits for the user's review (rule above).
5. **Approval code like the card skill:** `--dry-run` prints the plan and a code (first 12
   characters of the SHA-256 of the plan); `--approve CODE` recomputes it and refuses on a
   mismatch, so the plan cannot change between the preview and the write.
6. **Old branches after a move are kept by default.** `--delete-old-branches` is opt-in, listed in
   the plan, and refused unless every PR from the old heads is closed or merged. Reason: the 27/10
   notes treat deletion as a manual, later step, and a remote deletion cannot be undone from here.
7. **`move` recreates the sandbox PR only if the old one is open.** An old sandbox PR already
   merged (as on 27/10) means the content is in `sandbox`; the new `-sdbx` branch is pushed and no
   PR is made, unless it carries commits that `origin/sandbox` lacks.
8. **No MCP fallback for GitHub writes** (same reasoning as the card skill: an MCP write would skip
   the checks). Without an authenticated `gh`, the command stops and says how to log in. Reads
   through `gh` only.
9. **Config lives in `~/.config/workspace/config.toml`** (`[release]`, below), and the release's
   working files in `~/.local/share/workspace/projects/<slug>/release-DATE/`, the same name the
   real worktree folder has today.
10. **Date input** accepts `YYYYMMDD` or `YYYY-MM-DD`; a date earlier than today is refused on `new`
    and `move`; the PT-BR text uses `DD/MM/YYYY`.

## Local config

```toml
[release]
sandbox_branch = "sandbox"
base_branch = "master"
# order = deploy order: PRs are created, and cross-referenced, in this order
[release.repos.shared]
slug = "<org>/apl-shared-service"
path = "~/repos/apl-shared-service"
[release.repos.bff]
slug = "<org>/apl-credit-whitelabel-api"
path = "~/repos/apl-credit-whitelabel-api"
[release.repos.front]
slug = "<org>/apl-credit-whitelabel"
path = "~/repos/apl-credit-whitelabel"
```

Missing keys: the command names them and points to the README section "Local config". `<org>` is
the GitHub organization of the company, never written in this repo.

## The files the model writes

Under `~/.local/share/workspace/projects/<slug>/release-DATE/`:

| File | Content |
|---|---|
| `release.toml` | `task = "TS-5424"`, `repos = ["shared", "bff", "front"]`, and per repo the task branches to merge, in order: `[include]` `shared = ["feature/TS-5416-..."]` |
| `pr/<repo>.md` | the master PR: TOML front matter between `+++` lines (`title`, optional `labels`, `assignees`), then the body in Markdown |
| `pr/<repo>-sdbx.md`, `pr/<repo>-sdbx-2.md`, ... | the sandbox PRs; the second and later ones are used when a previous sandbox PR is already merged |

A body refers to another repo's PR with `{pr:shared}` or `{pr:bff-sdbx}`; the script substitutes
`<org>/<repo>#N` once the PR exists. This replaces the string replacement of the old scripts and
fixes their stale-number risk. Worktrees: `<repo>/` and `<repo>-sdbx/` inside the same folder.

## The commands

All commands take `--project SLUG` when the folder cannot be found from the current directory,
read `[release]` from the config, `git fetch` every repo first (a read), and print JSON on stdout
and messages in English on stderr. Exit codes: 0 ok, 1 a rule failed, 2 a precondition is missing
(no `gh`, no config, a conflict in progress), 3 a merge conflict that needs the user.

### `ws release branches --task TS-N [--task TS-M ...]`

Read-only. Per repo: the local and remote branches whose name has the id (excluding `-sdbx`
copies), each with commits ahead of `origin/master`, whether it is already merged into
`origin/master`, and whether its `-sdbx` copy exists and contains it. Output: JSON list. The skill
uses it to propose the `include` lists.

### `ws release new DATE [--task TS-N] [--repo NAME ...]`

Local only: no push, no `gh` write. Reads `release.toml` (`--task` and `--repo` override it). Per
repo, in config order, idempotent (a step already done is skipped):

1. Create the worktree `release-DATE/<repo>` on a new `release/DATE` from `origin/master` with
   `--no-track`, if it does not exist.
2. Merge each `include` branch in order with `--no-ff`, skipping the ones already ancestors; merge
   `origin/master` if it moved. A conflict stops the command with exit 3: the merge stays in
   progress in the worktree and the JSON lists the files.
3. Create `release-DATE/<repo>-sdbx` on a new `release/DATE-sdbx` from the release tip
   (`--no-track`); merge `origin/sandbox`; on a rerun merge the release again, then
   `origin/sandbox`. A conflict stops as above, in the `-sdbx` worktree.
4. Run the rules below (R1 to R6) and print per repo: branch tips, commits ahead of `master`, the
   merged branches, the files where the `-sdbx` differs from the release, and `ready: true|false`.

It never merges into `master` or `sandbox`, never pushes, and makes no commit besides the clean
merges of step 2 and 3.

### `ws release publish DATE [--repo NAME ...] (--dry-run | --approve CODE)`

The only step that writes to GitHub besides `move`. It requires `ready: true` for every repo and
the PR draft files. Per repo, in config order, the plan lists, and `--approve` executes:

| Step | Call | Condition |
|---|---|---|
| push release | `git push -u origin release/DATE` (never `-f`) | branch absent on `origin`, or `origin`'s tip is an ancestor |
| push sandbox copy | `git push -u origin release/DATE-sdbx` (never `-f`) | same |
| master PR | `gh pr create -R <slug> --base master --head release/DATE --title T --body-file F [--label L] [--assignee A]` | no open PR from this head; none merged |
| sandbox PR | `gh pr create -R <slug> --base sandbox --head release/DATE-sdbx ...` | no open PR from this head, and the `-sdbx` has commits that `origin/sandbox` lacks |
| second pass | `gh pr edit N -R <slug> --body-file F` | a body had a forward `{pr:...}` placeholder that was not known when it was created |

Reads it makes: `gh pr list -R <slug> --head BRANCH --state all --json number,state,baseRefName,
title,url,mergedAt`, `gh api repos/<slug>/branches/BRANCH` (GET). Output after approval: per repo
the two URLs, and a `gmud` block (see `status --links`). A repo whose master PR is already merged
is reported and skipped.

### `ws release move OLD NEW --reason TEXT [--delete-old-branches] (--dry-run | --approve CODE)`

Moves a release to another date for every repo that has `release/OLD`. The plan lists, and
`--approve` executes, per repo in config order:

| Step | Call | Note |
|---|---|---|
| refuse if taken | `gh api` GET of `release/NEW` and `gh pr list --head release/NEW` | NEW must be free in every repo, remote and local |
| copy branches | `git push origin refs/remotes/origin/release/OLD[-sdbx]:refs/heads/release/NEW[-sdbx]` | same commit, no rewrite (`renomear-27.py:17-19`) |
| read the old PRs | `gh pr view N -R <slug> --json title,body,labels,assignees,state,baseRefName,headRefName` | |
| new PR | `gh pr create ... --head release/NEW[-sdbx]` with title and body where `YYYYMMDD` (OLD) became NEW, labels and assignees copied, and `<org>/<repo>#N` of already moved repos replaced | only for PRs that were open; a merged old PR is left alone (decision 7) |
| close old | `gh pr close N -R <slug> --comment "Substituído por <url>: a release passou a ser a de DD/MM/YYYY, <reason>."` | open PRs; a merged one gets `gh pr comment` instead, as the 26/10 script did |
| second pass | `gh pr edit` of the new bodies that still point at an old number | forward references |
| delete old branches | `git push origin --delete release/OLD[-sdbx]` | only with the flag, only if every PR of that head is closed or merged and no open PR has it as its base |
| local rename | `git branch -m` of both branches in the worktrees, `git worktree move` of the folder to `release-NEW`, `git branch -u` | local, after the pushes |

The replacement touches `YYYYMMDD` and PR numbers only (with word boundaries, so `#73` never
matches `#730`). The result lists every remaining `DD/MM` or `DD/MM/YYYY` of the old date found in
the new bodies as `residual_dates`: the skill shows them and the user decides, because prose such
as "revisão de 23/10" may or may not be the release date.

### `ws release status [DATE] [--links]`

Read-only, no approval. Without DATE: the releases found (`release/*` branches on `origin` and
open PRs from them). With DATE, per repo: worktree path and branch, remote branches present,
commits ahead and behind `origin/master`, the `-sdbx` mirror verdict, and the PRs (number, state,
base, mergeable, and the conclusions of the PR's status checks). Exit 1 when any rule fails.

`--links` prints the block for the GMUD, one line per repo, in deploy order, in the form the
GMUD text uses (`apl-shared-service, PR #76: <url>`), master PRs first, sandbox PRs after. The
`change-request` skill reads it to fill the PR numbers of the "O que muda" and "Plano de
implantação" fields.

## The rules (checked by `new`, `publish`, `move` and `status`)

- **R1, never touch `master`:** no command pushes to `master` or `sandbox`, commits on them,
  force-pushes anything, or merges a PR (`gh pr merge` does not exist in the code). The release
  PRs reach `master` only when the user merges them in GitHub.
- **R2, names:** `release/YYYYMMDD` is a real date; the sandbox copy is exactly that name plus
  `-sdbx`; branches cut from `origin/master` or `origin/sandbox` are created with `--no-track`.
- **R3, release is current:** `origin/master` is an ancestor of `release/DATE` (otherwise: "master
  moved, merge it", with the commit count), because the company rule is to pull before acting and
  the 21/10 flow had to merge `master` into both releases.
- **R4, the `-sdbx` mirrors the release:** the release tip is an ancestor of the `-sdbx` tip;
  `origin/sandbox` tip is an ancestor of it; no commit in `release..sdbx` that is not already in
  `origin/sandbox` is a non-merge commit (the copy never receives code of its own); and every file
  where `-sdbx` differs from the release is a file where `origin/sandbox` differs from `master`
  (so only `sandbox` content comes along; the BFF case of 21/10, where one sandbox-only change was
  dropped on purpose, still passes). The verdict lists the differing files.
- **R5, commits:** every commit the script makes matches `^(feat|chore|refact|fix|test)\(TS-\d+\): .+`,
  has at most 72 characters, is in PT-BR, and carries no `Co-Authored-By` trailer. The command
  verifies the trailer is absent in the commits it lists (`release..sdbx` and the merges it made).
- **R6, PR text:** the master title matches `^release\(TS-\d+(, TS-\d+)*\): .+`; the sandbox title
  `^chore\(TS-\d+(, TS-\d+)*\): .+ \(sdbx\)$`; at most 100 characters (the longest seen is about 95).
  The body, for a repo that has `.github/pull_request_template.md`, contains every `##` heading of
  the template; for a repo without one, the four headings of the shared and BFF PRs. No `{pr:...}`
  placeholder is left unresolved, and a master body that cites a PR of another repo cites the PR of
  this release (not an old date).
- **R7, one PR per head and base:** before creating, an open PR from the same head to the same
  base is reused, not duplicated (the plan says "already open, push only").
- **R8, move:** NEW is free everywhere; OLD and NEW differ; the old PRs are closed only after the
  new ones exist (never the reverse, so a failure leaves two PRs, not none); the move stops at the
  first failing repo and the output says which repos are done and which are not, and a rerun skips
  what is done (a new PR from `release/NEW` already exists).
- **R9, gate:** `publish` and `move` without `--approve CODE` write nothing; a wrong code writes
  nothing; the code is bound to the plan, including the PR texts.

## The skill `release`

`skills/release/SKILL.md` (English), invoked only by the user (`/release ...`),
`disable-model-invocation: true`; detail in `references/` (the PR section shapes, the moving
procedure). Steps:

1. **Understand the request.** Ask only what is missing: the date, the main task id, the repos
   involved, the task branches. Run `ws release status` (is there already one?) and `ws release
   branches --task ...` and propose the include lists with the merge order; the user confirms.
2. **Build.** Write `release.toml`; run `ws release new DATE`. On exit 3, resolve the conflict in
   the worktree with the user; show the diff grouped by planned commit and commit only after the
   user's review. Rerun until `ready: true` in every repo. Say which `-sdbx` files differ from the
   release and why.
3. **Validate before publishing** (D58): ask whether the local validation was done; if not, offer
   it (item 5 of the backlog, `ws validate`, once it exists). Numbers in "Como validei" come only
   from runs the user or the skill actually made, never invented.
4. **Write the PR drafts** in PT-BR, in the user's style: from the repo's template if it has one,
   otherwise the four sections of the shared and BFF PRs; summary of the changes from the task
   cards and the diff; dependencies and the deploy order shared, BFF, front, with
   `{pr:...}` placeholders; what could not be exercised; what must exist before (Parameter Store,
   app roles). The sandbox PR says it takes the release to the sandbox to validate before the
   `master`, and what the `-sdbx` adds over the release.
5. **Publish.** `ws release publish DATE --dry-run`; show the plan as is (branches, PR titles,
   bases, the draft bodies) and the code; ask for a yes. Only on an explicit yes:
   `--approve CODE`. Give the links.
6. **GMUD.** Run `ws release status DATE --links` and hand the block to the `change-request`
   skill when the user asks for the GMUD.
7. **After the release exists, a new change:** it goes to the task branch first, then to the
   release (`new` again merges it in), then into the `-sdbx` (`new` syncs with `origin/sandbox`
   first); if the previous sandbox PR is merged, write `pr/<repo>-sdbx-2.md` and publish.
8. **Move to another date:** ask the new date and the reason in one sentence; `ws release move OLD
   NEW --reason ... --dry-run`; show the plan and every `residual_dates` line; ask for a yes;
   `--approve CODE`; then tell the user the GMUD window and PR numbers changed and offer
   `ws release status NEW --links`.
9. The skill never merges a PR, never deletes a branch without the flag and the user's yes, and
   never pushes to `master` or `sandbox`.

## Tests (pytest, a fake `gh`, throwaway repos, no network)

Fixtures: a bare repo as `origin` per repo, with `master`, `sandbox` and two task branches, cloned
into `tmp_path`; a `gh` script placed first on `PATH`, which reads a JSON file of PRs and
branches, answers the read calls, and appends every call to a log file; a write call fails the
test when the code was not approved. All names in fixtures are invented (`acme`, `repo-a`).

- `branches`: finds the task branches by id, ignores the `-sdbx` copies, reports merged ones.
- `new`: builds the release from `origin/master` with `--no-track` (no upstream configured);
  merges the includes in order; skips what is merged on a rerun; stops with exit 3 on a conflict
  and leaves the merge in progress with the file list; merges `master` when it moved; builds the
  `-sdbx` and syncs it with `sandbox`; makes no push (the bare origin's refs are unchanged) and no
  `gh` call.
- Rules: each of R1 to R6 with one passing and one failing case (a release behind `master`; an
  `-sdbx` with a code commit of its own; an `-sdbx` file that does not come from `sandbox`; a
  commit with a trailer; a bad title; a missing template heading; an unresolved placeholder).
- `publish --dry-run`: no `gh` write in the log, no new ref in the bare origins, a code is printed;
  `--approve` with a wrong code, or after editing a draft, does nothing; with the right code the
  log has exactly the planned calls in config order; a repeated run is a no-op (R7); a merged
  master PR is skipped; a second sandbox PR is created from `-sdbx-2.md` after the first merged;
  forward placeholders are resolved by the second pass; no push is `-f`.
- `move`: same-commit branches (`rev-parse` equal on both names); title and body replaced with
  word boundaries (`#73` vs `#730`); labels and assignees copied; the old PR closed after the new
  one exists; a merged old sandbox PR is commented, not recreated; `residual_dates` listed;
  NEW taken in one repo: nothing is written to any repo; a failure in the second repo leaves the
  first done and a rerun finishes; old branches deleted only with the flag and only when every PR
  is closed or merged; the local rename and worktree move.
- `status`: the table for a clean release, a release behind `master`, a broken mirror (exit 1),
  `--links` order and format, no `gh` write.
- Gate: no code path calls `gh pr merge`, `git push` to `master`/`sandbox`, or `--force`
  (a test greps the module and the fake `gh` log).
- Confidentiality: a test runs `ws check-secrets` over the sample outputs and the fixtures, so
  the fixtures cannot carry a real name.

## Out of scope

- Merging the PRs, the image tags and the argocd values (`image.tag`, `DD_VERSION`), and the
  rollback tags: they are the deploy, done by the user (`roteiro-20261027.md:62-63, 102-104`).
- Writing the GMUD itself (`change-request` skill) and the Azure and Parameter Store steps of the
  deploy guide.
- Local validation of each repo (backlog item 5) and the replica queries.
- Task branches' own `-sdbx` copies outside a release, hotfix branches (`fix/...-sdbx`), and the
  approval of PR reviews or comments.
- Writes through the GitHub MCP, and any hook on the MCP's write tools (same backlog note as the
  card skill).
- Repos other than the ones in `[release.repos]`; a release spanning an extra repo (such as the
  assignment backend) is added by a config entry, with no code change.
