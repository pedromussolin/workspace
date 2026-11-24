---
name: release
description: Builds, publishes, moves and reports the release of the company repos (release branches, the merge into the environments, the PRs, a new date, the PR links for the GMUD) through the `ws release` commands, with a preview and an approval prompt before any GitHub write. Use when the user asks to build, publish, move or check a release ("monta a release de 20/11 com TS-101 e TS-102", "publica a release", "move a release de 20/11 para 27/11", "como está a release?"), to add a task to a release already built or published ("inclui a TS-103 na release de hoje", "essa tarefa entra na release") or types /release. The model may start it by itself; every GitHub write still waits for the user's approval box.
---

# Release

A release is the set of PRs, one per repo, that takes the finished tasks to production on a date. The
order is fixed: understand, build, validate, write the PR texts, preview, approval (the write).
The model decides, asks and writes the PR prose; `ws release` builds the branches, checks the rules,
calls `gh` and `git push`. Nothing goes to GitHub through the GitHub MCP, ever. Never run
`gh pr merge`, never push to `master` or to an environment branch (`sandbox`, `staging`): the user
merges the PRs on GitHub. Never wrap or
disguise a command to avoid the approval prompt. The model may start this skill by itself, but never
answers the approval box for the user: `publish` and `move` wait for the user's yes.

Terms: the release branch `release/YYYYMMDD` merges the task branches of a repo and goes to
production (`base_branch`). An environment (`[release.environments.NAME]` in the config: `sandbox`
with suffix `-sdbx` and `staging` with `-stg`, for example) has a copy of the code branch,
`<code branch><suffix>`, that merges `origin/<environment branch>`; the copy is always built for
each selected environment and its PR goes to the environment branch. `--env NAME ...` selects
environments (`production` is a valid name: the code branch, no copy); `new` without `--env`
builds the environments with `default = true`, `publish` takes production plus those. GMUD is the
change record of the deploy (skill `change-request`). A repo with one include is single-branch (the
PR comes from the task branch itself, its copy is `<task branch><suffix>`); with more,
multi-branch (a `release/DATE` branch is built).

Every command prints JSON on stdout and messages on stderr. Exit codes:
- 0: ok.
- 1: it evaluated and a rule failed.
- 2: it cannot evaluate. Causes: the config, `gh`, the gate settings or a merge in progress; a
  missing release folder or `release.toml`; a malformed DAY, a `--repo` outside `release.toml` or a
  bad `--project`; git or `gh` unable to answer.
- 3: a merge conflict that needs the user. It includes the Alembic stop below.

 Dates go in as `YYYYMMDD` or `YYYY-MM-DD`; the texts say `DD/MM/YYYY`. Add
`--project SLUG` when the current folder is not under the project. Exit 2 naming the config or the
gate: tell the user to read the README section "Release" and run `ws setup`.

## Steps

1. **Understand the request.** Ask only what is missing: the date, the tasks (keys such as
   `TS-101`), the repos, the task branches. Run `ws release status` (releases already found:
   `releases[]` with `date`, `folder`, `open_prs`). Then
   `ws release branches --task TS-101 TS-102 [--from-items SLUG] [--repo NAME ...]` (read-only;
   `--from-items` adds the tasks of that planning project and uses their `blocks`/`blocked_by` as
   order hints). Per repo it prints `branches[]` (`branch`, `key`, `local`, `remote`, `ahead`,
   `merged`, `sdbx`, `contains`, `migrations`), `suggested_order` and `problems`; also `unmatched`
   (keys with no branch). Show the user `suggested_order` and every `contains` line (this branch
   already holds those) and `migrations` line (each Alembic revision and its `down` revision),
   and the `problems` (a local branch behind its `origin` copy: ask the user to pull it). Propose the
   include list of each repo in that order and say which repos end up single-branch and which
   multi-branch. The order is the merge order: a branch that holds another goes after it, and
   chained migrations must follow their `down_revision`. The user confirms or changes it.
2. **Build.** Write `release.toml` in `~/.local/share/workspace/projects/<slug>/release-YYYYMMDD/`
   (`mkdir -p` first; Write tool):

   ```toml
   repos = ["shared", "bff", "front"]

   [include]
   shared = ["feature/TS-101-example"]
   bff = ["feature/TS-102-first", "feature/TS-103-second"]
   ```

   `repos` is the deploy order; `[include]` lists the task branches of each repo in the confirmed
   merge order; no task id or title goes in the file. Run `ws release new DATE [--env NAME ...]`.
   It builds locally only (branches, worktrees, merge commits); it never pushes. Read the JSON:
   - `repos[]`: per repo `shape`, `code_branch`, `tip`, `worktree`, `ahead`, `behind`, `heads`
     (`code`: the Alembic heads of the code branch), `environments` (per environment in scope:
     `branch`, `copy`, `exists`, `merged`, `differs`: files where the copy differs from the code
     branch, `heads`), `problems`, `warnings`, `ready`. Exit 0 means every repo is `ready: true`;
     exit 1, some is not: fix each problem. A `warnings` line "the NAME copy is skipped" means
     `origin/<branch>` does not exist in that repo.
   - `not_built` lists the repos skipped because the include order or the Alembic chain is wrong
     (or a stale branch). Their code was not built. It comes with `suggested_order`; exit is 1.
   - `suggested_order` (repo name to branches) appears when the order or the Alembic chain is
     wrong; that repo was not built. Say in one sentence why (for example "`feature/TS-103` already
     holds `feature/TS-102`, so it must come after it", or "two includes add a migration on the same
     parent revision"), propose the fixed `[include]` and, on the user's yes, rewrite it and rerun.
     Never reorder silently.
   - Exit 3: a merge conflict. `conflict` has `repo`, `worktree`, `merging` and `files`; `built` and
     `not_started` say how far it got. Resolve it in that worktree with the user: show the diff
     grouped by planned commit and commit only after the user's review (`chore(TS-N): ...`, up to 72
     characters, PT-BR, no co-author). Then rerun `ws release new DATE` until `ready: true` in
     every repo.
   - Exit 3 with `alembic_heads` and `message`, `files: []`, `merging: false`: the environment's
     copy would end up with two Alembic heads. There is no diff to show. The user fixes it in the
     copy's worktree (`<repo><suffix>`) with one commit. It adds exactly one `.py` migration under the repo's
     `alembic` folder, with `down_revision` set to both heads, and a subject like `chore(TS-N): ...`.
     The rules refuse anything else in that commit. Then the user reruns
     `ws release new DATE --env NAME`.
   - A single-branch repo that was already published and now has two includes stops with exit 2: the
     open PRs come from the task branch; the user decides how to move on.
   - Say which files each copy differs from the code branch in (`differs`) and why (what the
     environment branch has that the code lacks).
3. **Validate before publishing.** Ask whether the local validation was done; if not, offer it
   (the validation command of the repo; `ws validate` once it exists). The numbers in "Como validei"
   come only from runs the user or you made, never invented.
4. **Write the PR drafts** in `release-DATE/pr/`, in PT-BR, in the user's style, following
   [references/pr-shapes.md](references/pr-shapes.md): the front matter, the titles per shape, the
   sections (the repo's template when it has one, else the four), the placeholders and the
   environment PRs. Summarize from the task cards and the diff; say what could not be exercised and what must
   exist before (Parameter Store, app roles). Show the user the drafts and fix them until they are
   right.
5. **Publish.** `ws release preview publish DATE [--repo NAME ...] [--env NAME ...]`. Without
   `--env` it plans production and the default environments; `--env sandbox` plans only the
   sandbox copy and its PR (the code branch is not pushed, no code PR is opened, and none is needed
   yet), `--env production` only the code PR. The environments are part of the plan: `publish` must
   get the same `--env` as the preview. It writes no repo and no GitHub; on exit 1 it prints `problems` (a rule, a draft, a repo not `ready`): fix and run it
   again. With `nothing_to_send: true` (exit 0, no `code`) nothing is pending: tell the user and do
   not run the approve step. Otherwise it prints `code`, `summary` (PT-BR lines), `calls` (every `git`/`gh` call),
   `next` and `warnings`. Show the `summary` lines as printed, every `warnings` line and the code. Then run
   `ws release publish DATE --approve CODE` (the same `--repo`/`--env`/`--project` flags) as its own Bash
   call, never in the same command line as the preview (it refuses in the same shell session). The
   approval gate stops it and shows the user the summary; the user's yes in that box is the
   approval. Never ask the user to type the code or say "ok" in chat instead. The preview is valid
   for 30 minutes and only for the plan it printed: if the state changes, `publish` refuses and a
   new preview is needed.
   Read the result: `done` (calls sent), `failed`, `not_sent`, `uncertain`, `prs` (the URLs). On
   success also `repos[]` (`repo`, `code_pr`, `code_url` and, per environment in scope, `<env>_pr`
   and `<env>_url`, plus `skipped`), `gmud` and `warnings`. Give
   the user the PR links and show the `warnings`.
   - `failed` set: say which call failed and what was not sent, then run the preview again; it plans
     only what is still missing.
   - `uncertain: true` (a timeout or a 5xx after sending): tell the user to check GitHub for the
     PR. Never retry blindly: rerun the preview and show what it now plans.
   - A repo whose code PR is already merged is reported as `skipped`.
6. **GMUD.** When the user asks for it, run `ws release status DATE --links`. `links` has one line
   per repo in deploy order, code PRs first and then each environment in config order
   (`apl-shared-service, PR #76: <url>`, `apl-shared-service (sandbox), PR #77: <url>`). Give it
   to the `change-request` skill. A `warnings` line "no code PR" (or "no ENV PR") means the links
   are incomplete.
7. **A new change after the release exists.** It goes to the task branch first, then to the code
   branch: add the task branch to `release.toml` and run `ws release new DATE`, which merges it in
   with the subject `chore(TS-N): junta a <branch>`; never a hand `git merge`, whose default
   subject ("Merge branch ...") breaks the commit rule that `ws release status` checks, then into each copy (`new` syncs it with
   `origin/<environment branch>` first). When the previous PR of an environment is already merged,
   write `pr/<repo>-<env>-2.md` (then `-3`, ...) and publish. A new task branch in a repo that was
   single-branch changes its shape: `new` stops with exit 2 and the user decides.
8. **Move to another date.** Follow [references/moving.md](references/moving.md): ask the new date
   and the reason in one sentence; preview, show the `summary` and every `residual_dates` line,
   approval in its own call (`nothing_to_send: true` means nothing to move: say so, no approval),
   then tell the user what changed. Only a new date in the past is
   refused; the old one may be past.
9. **Status.** `ws release status [DATE]` is read-only and needs no approval. With a date it prints
   per repo the shape, the worktree, the remote branches, `ahead`/`behind`, `environments` (the
   defaults and every environment whose copy exists) and `prs[]` (`kind`: `code` or the environment
   name, `number`, `state`, `base`, `url`, `mergeable`, `checks`); exit 1 when a rule fails. A row with `merged: true` means the release is already in master: that repo skips the
   rules. Show it short, in plain words.

## Never

- Merge a PR, push to `master` or to an environment branch, force-push, or write to GitHub by any route other
  than `ws release publish|move --approve`.
- Merge a task branch into a release branch or its copy by hand (`git merge`): step 7 does it.
- Delete a branch without `--delete-old-branches` and the user's yes (see the moving reference).
- Run the preview and the approval in the same Bash call, or hide the approval command in a
  script, a variable, `eval` or a background process.
- Invent numbers for "Como validei", or leave a placeholder or a task link out of a draft.
