# Release: design

Item 2 of "Next skills" in `docs/backlog.md`: a skill and a `ws release` command group that build,
publish, move and report the release of the company repos, so each deploy stops needing its own
one-off script. Status: design, 2026-10-27, decisions of the user the same day. Nothing here is
implemented.

## Goal

The user says "release for 27/10 with TS-5416 and TS-5424" (or "move the release to 28/10") and
gets, in every repo involved, the code that goes to `master` and the two pull requests (PRs) written
in the user's style, and the PR links ready for the GMUD (the change-request form). With more than
one task branch in a repo the code is `release/YYYYMMDD`; with one, it is that task branch itself,
and no release branch exists. Every write to GitHub is previewed and approved first; nothing is
ever merged by the tool.


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

Taken before 2026-10-27:

- **Targets:** the code PR goes to `master`; the sandbox PR goes to `sandbox` (backlog, item 2; PR
  list above).
- **Code goes in the original, the `-sdbx` only receives merges**; and a change after the release
  exists goes first to its task branch, then to the release, then to the `-sdbx` (when there is
  one) after syncing with `origin/sandbox` (memory `fluxo-branch-original-e-sdbx.md`;
  `CONTINUE.md:28-30`; `deploy/roteiro-de-deploy.md:1059`).
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
  mechanical part; every write to GitHub is plan, preview, explicit approval, execute; the skill
  sets `disable-model-invocation: true`.
- **Branches from `master` use `--no-track`** (memory `branch-a-partir-de-master-usar-no-track.md`):
  otherwise the editor's Sync pushes to `master`.

## Decisions (user, 2026-10-27)

They replace the proposals this spec had under "Decisions to confirm".

1. **A release branch only when more than one task branch goes in** (counted per repo). With a
   single task branch, the two PRs (to `master` and to `sandbox`) come from the task branch itself;
   there is no `release/YYYYMMDD`. The `-sdbx` copy (of the release branch, or of the single task
   branch: `<branch>-sdbx`) exists **only when the merge into `sandbox` conflicts**: the 10/10
   decision stands (`decisions.md:163`; `roteiro-de-deploy.md:1057`). Without a conflict, the
   sandbox PR comes from the same branch as the `master` PR.
2. **Five commands:** `new` (builds the branches and merges locally; writes nothing outside the
   machine), `publish` (the only step that writes to GitHub: push and PRs), `move`, `status` and
   `branches` (read-only). The approval gate is on `publish` and `move`.
3. **No `--task`:** a release can hold several tasks. The PR description lists every task (key and
   link). Multi-branch release: the PR title is `release YYYYMMDD: <summary>`, with no key.
   Single-branch release: the title is the task's normal title by the company rule (for example
   `feat(TS-5431): ...`) and the release date goes in the description.
4. **Merge commits made by the script carry the key of the task branch being merged**
   (`chore(TS-5416): junta a feature/TS-5416-...`). Release-level merges, with `master` or with
   `sandbox`, carry all the release's keys (`chore(TS-5416, TS-5424): junta a release/20261027 na
   sandbox`), cut on a word to fit 72 characters. Only clean merges: a conflict stops the script,
   and the resolution waits for the user's review.
5. **The same approval as `/card`:** a preview command prints the plan and a 12-hex code (SHA-256 of
   the plan); the write is another command with `--approve CODE`, which Claude Code asks the user
   to confirm (an `ask` rule for `Bash(ws release publish:*)` and `Bash(ws release move:*)`, and a
   PreToolUse hook like `hooks/ask_card_apply.py`). The plan cannot change between the preview and
   the write; preview and write are separate shell calls. No writes through the GitHub MCP; without
   an authenticated `gh`, the command stops and says how to log in. Details in "The approval gate".
6. **Old branches after a move are kept.** `--delete-old-branches` is opt-in, listed in the plan,
   and refused unless every PR from the old heads is closed or merged.
7. **`move` recreates the sandbox PR only if the old one is open.** An old sandbox PR already merged
   means no new PR, unless the branch carries commits that `origin/sandbox` lacks. For a
   single-branch release, `move` only changes the date in the PR descriptions: there is no branch
   to rename.
8. **Config in `~/.config/workspace/config.toml`**, section `[release]`; working files and
   worktrees in `~/.local/share/workspace/projects/<slug>/release-DATE/`.
9. **Dates:** `YYYYMMDD` or `YYYY-MM-DD`; a past date is refused on `new` and `move`; texts use
   `DD/MM/YYYY`.

## The approval gate

Same design as `docs/specs/2026-10-27-card-write-design.md`, applied to `publish` and `move`.

- **The approval is a Claude Code prompt, not prose.** `ws setup` checks and prints (it never edits
  `~/.claude/settings.json`) `permissions.ask` rules for `Bash(ws release publish:*)` and
  `Bash(ws release move:*)`; until the user adds them, it reports a "needs you" line. A rule
  matches the command text, so it alone is not the barrier: a PreToolUse hook
  (`hooks/ask_release_write.py`) answers `ask` for any Bash command that, with quotes and
  backslashes removed, has `release` followed directly by `publish` or `move` as words, or
  `ws.release`, `from ws import release` or `run_publish`/`run_move` (so `uv run ws release
  publish`, `python -m ws`, `bash -c '...'`, an absolute path to `ws`, `--appr$(true)ove` or a
  variable holding the flag are asked too), and also for `ws` or `release` as a word together with
  a shell expansion or escape (`$`, a backtick, `{`, a backslash-newline) or `eval`, `base64`,
  `xxd`, `printf`; `status`, `branches`, `new` and the previews (`ws release preview publish`,
  `ws release preview move`) stay silent. It is a text hook: a script file the command runs, a
  background process in a new session (`setsid`, `nohup`) or an import route outside those patterns
  is not seen, and there the auto-mode classifier and the user's reading of each command remain
  the barrier (see "Known limit of the approval gate").
- **Preview and write are separate commands and separate shell calls.** The preview stores the
  session id of its shell (`os.getsid(0)`) and `--approve` refuses (exit 1, "a prévia e a
  aprovação precisam ser passos separados") in the same session, so one command line cannot preview
  and write (Claude Code runs each Bash call in its own session; a user running both by hand in one
  terminal uses another tab for the write). The preview is its own command so the prompt appears
  only at the real write.
- **The code** is the first 12 hex characters of the SHA-256 of the plan: repos, branches and their
  tips, every call with its arguments, the PR titles, bodies, labels and assignees (after the
  placeholders are resolved), and, for `move`, the old PR states and the reason. The preview stores
  a pending record `~/.local/share/workspace/projects/<slug>/release-DATE/pending/<code>.json`
  (mode 600) with the plan and today's date. There is no HMAC or signature on it: the prompt (rule
  plus hook) is the barrier; the record is only checked to be the user's own private file.
- **The write** refuses (exit 2) unless the Claude settings hold the `ask` rules and a real
  registration of the hook (a `PreToolUse` entry whose matcher covers `Bash` and whose command runs
  the script with python); and refuses (exit 1) unless a pending record with that code exists, is
  the user's own file with mode 600, is under 30 minutes old and not dated in the future, and the
  draft files are unchanged (same paths, same bytes). It recomputes the plan against the live
  state (branch tips, PR states) and refuses when it now differs from the code. It deletes the
  pending record **before** sending (at most once: a second `--approve` with the same code finds
  nothing), runs the calls in order, stops at the first failure and reports what was done. A
  timeout, a 5xx or a connection error after sending is reported as "resultado incerto: confira no
  GitHub", with no retry.

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
the GitHub organization of the company, never written in this repo. The task links in the PR
descriptions use the `[jira] site` of the `/card` config (`<site>/browse/TS-5416`); without it,
`new` and `publish` stop with exit 2 and say so. The README gets a "Release" section: the five
commands, this config, and the two `ask` rules and the hook that `ws setup` checks.

## The files the model writes

Under `~/.local/share/workspace/projects/<slug>/release-DATE/`:

| File | Content |
|---|---|
| `release.toml` | `repos = ["shared", "bff", "front"]` and, per repo, the task branches to include, in order: `[include]` `shared = ["feature/TS-5416-..."]`. No task id and no release title: the tasks come from the branch names and from each PR file |
| `pr/<repo>.md` | the code PR (to `master`): TOML front matter between `+++` lines (`title`, `tasks = ["TS-5416", ...]`, optional `labels`, `assignees`), then the body in Markdown |
| `pr/<repo>-sandbox.md` | the sandbox PR, same shape; written only when it needs its own text (see below) |
| `pr/<repo>-sandbox-2.md`, ... | later sandbox PRs, used when a previous sandbox PR is already merged and the branch grew |

There is no `--task` anywhere: the number of include branches of a repo decides its shape (one:
single-branch; more than one: multi-branch), and `tasks` in the front matter feeds the description.

A body may use these placeholders, resolved by the script:

- `{pr:shared}`, `{pr:bff-sandbox}`: `<org>/<repo>#N` of another PR, once it exists. This replaces
  the string replacement of the old scripts and fixes their stale-number risk.
- `{tasks}`: the list of `tasks`, one line each, key and link.
- `{release_date}`: the release date as `DD/MM/YYYY`. Mandatory in a single-branch PR (the date is
  not in its title) and written by the script as the first line, `Release: DD/MM/YYYY`; `move`
  changes that line.

Without a sandbox file, the sandbox PR takes the code PR's title, with ` (sdbx)` at the end, and its
body, with an added first paragraph saying it takes the code to the sandbox to validate before
`master` (and, when a `-sdbx` exists, what the `-sdbx` adds over it).

Worktrees: a multi-branch repo has `<repo>/` on `release/DATE`, and, when the merge into `sandbox`
conflicts, `<repo>-sdbx/` on `release/DATE-sdbx`. A single-branch repo has no worktree of the
script: the task branch is used as it is in the repo's own checkout, and, on a conflict,
`<repo>-sdbx/` holds `<branch>-sdbx`.

## The commands

All commands take `--project SLUG` when the folder cannot be found from the current directory,
read `[release]` from the config, `git fetch` every repo first (a read), and print JSON on stdout
and messages in English on stderr. Exit codes: 0 ok, 1 a rule failed, 2 a precondition is missing
(no `gh`, no config, no settings for the gate, a conflict in progress), 3 a merge conflict that
needs the user.

| Command | Input | Writes |
|---|---|---|
| `branches` | `--task TS-N` (repeatable), `--repo` | nothing |
| `new` | `DATE`, `--repo` | local branches, worktrees and merge commits only |
| `preview publish` | `DATE`, `--repo` | a pending record, on the machine |
| `publish` | `DATE`, `--repo`, `--approve CODE` | GitHub: push and PRs |
| `preview move` | `OLD NEW --reason TEXT [--delete-old-branches]` | a pending record |
| `move` | `OLD NEW --reason TEXT [--delete-old-branches] --approve CODE` | GitHub, and local renames |
| `status` | `[DATE] [--links]` | nothing |

### `ws release branches --task TS-N [--task TS-M ...]`

Read-only. Per repo: the local and remote branches whose name has the id (excluding `-sdbx`
copies), each with commits ahead of `origin/master`, whether it is already merged into
`origin/master`, and whether its `-sdbx` copy exists and contains it. Output: JSON list. The skill
uses it to propose the `include` lists (and so which repos are single- or multi-branch).

### `ws release new DATE [--repo NAME ...]`

Local only: no push, no `gh` write. Reads `release.toml` (`--repo` narrows it). Per repo, in config
order, idempotent (a step already done is skipped):

1. **Multi-branch (more than one include):** create the worktree `release-DATE/<repo>` on a new
   `release/DATE` from `origin/master` with `--no-track`, if it does not exist; merge each include
   in order with `--no-ff`, skipping the ones already ancestors; merge `origin/master` if it
   moved. **Single-branch:** build nothing; check that the task branch exists, has commits ahead
   of `origin/master`, and merge `origin/master` into it if it moved (the task branch is the code).
   If a repo had a single include that was already published and now has two, `new` stops with
   exit 2: the open PRs come from the task branch and the user decides how to move on.
2. A conflict in any merge stops the command with exit 3: the merge stays in progress in the
   worktree and the JSON lists the files.
3. **Sandbox:** test the merge of `origin/sandbox` into the code branch without touching anything
   (`git merge-tree --write-tree`). Clean: no `-sdbx` is made; the sandbox PR will come from the
   code branch. Conflict: create `release/DATE-sdbx` (or `<branch>-sdbx`) from the code branch tip
   with `--no-track` in `release-DATE/<repo>-sdbx`, merge `origin/sandbox` there and stop with exit
   3 as above; the user resolves it and commits after review. On a rerun, the existing `-sdbx`
   gets the code branch merged again, then `origin/sandbox`.
4. Run the rules below and print per repo: shape (`single` or `multi`), the code branch and its
   tip, commits ahead of `master`, the merged branches, whether an `-sdbx` exists and, if so, the
   files where it differs from the code branch, and `ready: true|false`.

It never merges into `master` or `sandbox`, never pushes, and makes no commit besides the clean
merges of steps 1 and 3.

### `ws release preview publish DATE [--repo NAME ...]` and `ws release publish DATE --approve CODE`

`publish` is the only step that writes to GitHub besides `move`. Both require `ready: true` for
every repo and the PR draft files. `preview publish` runs every check and prints the plan and the
code, writing nothing to any repo; `publish --approve` executes it. Per repo, in config order:

| Step | Call | Condition |
|---|---|---|
| push code branch | `git push -u origin <code branch>` (never `-f`) | branch absent on `origin`, or `origin`'s tip is an ancestor |
| push sandbox copy | `git push -u origin <branch>-sdbx` (never `-f`) | there is an `-sdbx`, same condition |
| code PR | `gh pr create -R <slug> --base master --head <code branch> --title T --body-file F [--label L] [--assignee A]` | no open PR from this head; none merged |
| sandbox PR | `gh pr create -R <slug> --base sandbox --head <sandbox head> ...` | no open PR from this head, and the head has commits that `origin/sandbox` lacks |
| second pass | `gh pr edit N -R <slug> --body-file F` | a body had a forward `{pr:...}` placeholder not known when it was created |

The sandbox head is the `-sdbx` branch when there is one, otherwise the code branch itself. Reads
it makes: `gh pr list -R <slug> --head BRANCH --state all --json number,state,baseRefName,title,
url,mergedAt`, `gh api repos/<slug>/branches/BRANCH` (GET). Output after approval: per repo the PR
URLs, and a `gmud` block (see `status --links`). A repo whose code PR is already merged is
reported and skipped.

### `ws release preview move OLD NEW --reason TEXT [--delete-old-branches]` and `ws release move ... --approve CODE`

Moves a release to another date for every repo that has it. `preview move` prints the plan and the
code; `move --approve` executes it. Per repo in config order:

| Step | Call | Note |
|---|---|---|
| refuse if taken | `gh api` GET of `release/NEW` and `gh pr list --head release/NEW` | multi-branch only; NEW must be free in every repo, remote and local |
| copy branches | `git push origin refs/remotes/origin/release/OLD[-sdbx]:refs/heads/release/NEW[-sdbx]` | multi-branch only; same commit, no rewrite (`renomear-27.py:17-19`) |
| read the old PRs | `gh pr view N -R <slug> --json title,body,labels,assignees,state,baseRefName,headRefName` | |
| new PR | `gh pr create ... --head release/NEW[-sdbx]` with title and body where `YYYYMMDD` (OLD) became NEW, labels and assignees copied, and `<org>/<repo>#N` of already moved repos replaced | multi-branch, only for PRs that were open; a merged old PR is left alone (decision 7) |
| close old | `gh pr close N -R <slug> --comment "Substituído por <url>: a release passou a ser a de DD/MM/YYYY, <reason>."` | open PRs; a merged one gets `gh pr comment` instead, as the 26/10 script did |
| edit date | `gh pr edit N -R <slug> --body-file F` | single-branch: the `Release: DD/MM/YYYY` line of the code and sandbox PR descriptions; no branch, no new PR, no close |
| second pass | `gh pr edit` of the new bodies that still point at an old number | forward references |
| delete old branches | `git push origin --delete release/OLD[-sdbx]` | only with the flag, only if every PR of that head is closed or merged and no open PR has it as its base |
| local rename | `git branch -m` of both branches in the worktrees, `git worktree move` of the folder to `release-NEW`, `git branch -u` | multi-branch, local, after the pushes |

A release can mix shapes (one repo single-branch, another multi-branch): each repo follows its own
column. The replacement touches `YYYYMMDD` and PR numbers only (with word boundaries, so `#73`
never matches `#730`) plus the `Release:` line. The result lists every remaining `DD/MM` or
`DD/MM/YYYY` of the old date found in the new bodies as `residual_dates`: the skill shows them and
the user decides, because prose such as "revisão de 23/10" may or may not be the release date.

### `ws release status [DATE] [--links]`

Read-only, no approval. Without DATE: the releases found (`release/*` branches on `origin` and
open PRs from them). With DATE, per repo: shape, worktree path and branch, remote branches present,
commits ahead and behind `origin/master`, the `-sdbx` mirror verdict when there is one, and the PRs
(number, state, base, mergeable, and the conclusions of the PR's status checks). Exit 1 when any
rule fails.

`--links` prints the block for the GMUD, one line per repo, in deploy order, in the form the
GMUD text uses (`apl-shared-service, PR #76: <url>`), code PRs first, sandbox PRs after. The
`change-request` skill reads it to fill the PR numbers of the "O que muda" and "Plano de
implantação" fields.

## The rules (checked by `new`, `publish`, `move` and `status`)

- **R1, never touch `master`:** no command pushes to `master` or `sandbox`, commits on them,
  force-pushes anything, or merges a PR (`gh pr merge` does not exist in the code). The PRs reach
  `master` only when the user merges them in GitHub.
- **R2, names:** a release branch is `release/YYYYMMDD` with a real date, and only exists when the
  repo has more than one include; a single-branch repo uses its task branch, whose name has the
  task id (`TS-\d+`); the sandbox copy is exactly the code branch name plus `-sdbx` and exists only
  after a real conflict with `origin/sandbox`; branches cut from `origin/master` or
  `origin/sandbox` are created with `--no-track`.
- **R3, code is current:** `origin/master` is an ancestor of the code branch (otherwise: "master
  moved, merge it", with the commit count), because the company rule is to pull before acting and
  the 21/10 flow had to merge `master` into both releases.
- **R4, the `-sdbx` mirrors the code branch (only when it exists):** the code branch tip is an
  ancestor of the `-sdbx` tip; `origin/sandbox` tip is an ancestor of it; no commit in
  `code..sdbx` that is not already in `origin/sandbox` is a non-merge commit, except the commits
  that resolve the conflict, which the user made after review (the copy never receives code of its
  own); and every file where `-sdbx` differs from the code branch is a file where `origin/sandbox`
  differs from `master` (so only `sandbox` content comes along; the BFF case of 21/10, where one
  sandbox-only change was dropped on purpose, still passes). The verdict lists the differing
  files. Without an `-sdbx`, `new` checks only that the merge test was clean.
- **R5, commits:** every commit the script makes matches
  `^(feat|chore|refact|fix|test)\(TS-\d+(, TS-\d+)*\): .+` (the key of the merged task branch, or
  all the release's keys for a release-level merge), has at most 72 characters, is in PT-BR, and
  carries no `Co-Authored-By` trailer. The command verifies the trailer is absent in the commits it
  lists (`code..sdbx` and the merges it made).
- **R6, PR text:**
  - multi-branch titles match `^release \d{8}: .+` (the date is the release's, no key);
  - single-branch titles match `^(feat|chore|refact|fix|test)\(TS-\d+\): .+` (the company rule) and
    the description has the `Release: DD/MM/YYYY` line;
  - a sandbox title is the code PR's title plus ` (sdbx)`, or its own file's title ending in
    ` (sdbx)`; at most 100 characters (the longest seen is about 95);
  - the description lists every task of `tasks` with key and link, and `tasks` has the key of every
    include branch of that repo;
  - the body, for a repo that has `.github/pull_request_template.md`, contains every `##` heading of
    the template; for a repo without one, the four headings of the shared and BFF PRs; no `{pr:...}`
    placeholder is left unresolved, and a code PR body that cites a PR of another repo cites the
    PR of this release (not an old date).
- **R7, one PR per head and base:** before creating, an open PR from the same head to the same
  base is reused, not duplicated (the plan says "already open, push only").
- **R8, move:** NEW is free everywhere; OLD and NEW differ and neither is in the past; the old PRs
  are closed only after the new ones exist (never the reverse, so a failure leaves two PRs, not
  none); the move stops at the first failing repo and the output says which repos are done and
  which are not, and a rerun skips what is done (a new PR from `release/NEW` already exists, or the
  description already has the new date).
- **R9, gate:** `publish` and `move` without `--approve CODE` write nothing; a wrong code writes
  nothing; the code is bound to the plan, including the PR texts; preview and write in the same
  shell session are refused.

## The skill `release`

`skills/release/SKILL.md` (English), invoked only by the user (`/release ...`),
`disable-model-invocation: true`; detail in `references/` (the PR section shapes, the moving
procedure). Steps:

1. **Understand the request.** Ask only what is missing: the date, the tasks, the repos involved,
   the task branches. Run `ws release status` (is there already one?) and `ws release branches
   --task ...` and propose the include lists with the merge order; the user confirms. Say which
   repos end up single-branch (the PRs come from the task branch) and which multi-branch.
2. **Build.** Write `release.toml`; run `ws release new DATE`. On exit 3, resolve the conflict in
   the worktree with the user; show the diff grouped by planned commit and commit only after the
   user's review. Rerun until `ready: true` in every repo. Say where an `-sdbx` was needed (a real
   conflict with `sandbox`) and which of its files differ from the code branch and why.
3. **Validate before publishing** (D58): ask whether the local validation was done; if not, offer
   it (item 5 of the backlog, `ws validate`, once it exists). Numbers in "Como validei" come only
   from runs the user or the skill actually made, never invented.
4. **Write the PR drafts** in PT-BR, in the user's style: from the repo's template if it has one,
   otherwise the four sections of the shared and BFF PRs; the task list through `{tasks}`; summary
   of the changes from the task cards and the diff; dependencies and the deploy order shared, BFF,
   front, with `{pr:...}` placeholders; what could not be exercised; what must exist before
   (Parameter Store, app roles). The title is `release YYYYMMDD: <summary>` for a multi-branch
   repo and the task's normal title for a single-branch one, with `{release_date}` in the body.
   The sandbox PR says it takes the code to the sandbox to validate before `master`.
5. **Publish.** `ws release preview publish DATE`; show the plan as printed (branches, PR titles,
   bases, the draft bodies) and the code; ask for a yes. Then, in a separate shell call,
   `ws release publish DATE --approve CODE`: Claude Code asks the user to allow it (the `ask` rule),
   and the user's yes in that prompt is the approval. Give the links.
6. **GMUD.** Run `ws release status DATE --links` and hand the block to the `change-request`
   skill when the user asks for the GMUD.
7. **After the release exists, a new change:** it goes to the task branch first, then to the code
   branch (`new` again merges it in), then into the `-sdbx` when there is one (`new` syncs with
   `origin/sandbox` first); if the previous sandbox PR is merged, write `pr/<repo>-sandbox-2.md`
   and publish. A new task branch in a repo that was single-branch changes its shape: `new` stops
   (exit 2) and the user decides.
8. **Move to another date:** ask the new date and the reason in one sentence; `ws release preview
   move OLD NEW --reason ...`; show the plan and every `residual_dates` line; ask for a yes; then,
   in a separate shell call, `ws release move OLD NEW --reason ... --approve CODE`; then tell the
   user the GMUD window and PR numbers changed and offer `ws release status NEW --links`.
9. The skill never merges a PR, never deletes a branch without the flag and the user's yes, and
   never pushes to `master` or `sandbox`.

## Tests (pytest, a fake `gh`, throwaway repos, no network)

Fixtures: a bare repo as `origin` per repo, with `master`, `sandbox` and two task branches, cloned
into `tmp_path`; a `gh` script placed first on `PATH`, which reads a JSON file of PRs and
branches, answers the read calls, and appends every call to a log file; a write call fails the
test when the code was not approved. All names in fixtures are invented (`acme`, `repo-a`).

- `branches`: finds the task branches by id, ignores the `-sdbx` copies, reports merged ones.
- `new`, shapes: two includes build `release/DATE` from `origin/master` with `--no-track` (no
  upstream configured) and merge them in order with the key of each branch in the merge subject; one
  include builds no release branch and no worktree; a clean `sandbox` makes no `-sdbx` (both
  shapes); a conflicting `sandbox` makes the `-sdbx`, stops with exit 3 and leaves the merge in
  progress with the file list; after the user's resolution a rerun gives `ready: true`.
- `new`, the rest: skips what is merged on a rerun; stops with exit 3 on a conflict with a task
  branch; merges `master` when it moved, with all the release's keys in the subject; a second
  include on a published single-branch repo exits 2; no push (the bare origin's refs are
  unchanged) and no `gh` call.
- Commit subjects: the single-key and the multi-key forms, cut on a word at 72 characters.
- Rules: each of R1 to R6 with one passing and one failing case (a release behind `master`; an
  `-sdbx` with a code commit of its own; an `-sdbx` file that does not come from `sandbox`; a
  commit with a trailer; a multi-branch title with a key; a single-branch title without a key or
  without the `Release:` line; a description missing a task of `tasks`; a missing template heading;
  an unresolved placeholder; a release branch for a single include).
- `preview publish`: no `gh` write in the log, no new ref in the bare origins, a code printed and
  a pending record (mode 600) stored; `publish --approve` with a wrong code, after editing a
  draft, after 30 minutes, with no pending record, or in the same shell session as the preview,
  does nothing; with the right code the log has exactly the planned calls in config order; the
  single-branch PRs have the task branch as head and the sandbox PR the same head when no `-sdbx`
  exists; the `{tasks}` list and `{release_date}` are rendered; a repeated run is a no-op (R7); a
  merged code PR is skipped; a second sandbox PR is created from `-sandbox-2.md` after the first
  merged; forward placeholders are resolved by the second pass; no push is `-f`.
- `move`: same-commit branches (`rev-parse` equal on both names); title and body replaced with word
  boundaries (`#73` vs `#730`); labels and assignees copied; the old PR closed after the new one
  exists; a merged old sandbox PR is commented, not recreated (and recreated when the branch has
  commits `origin/sandbox` lacks); a single-branch repo only gets the `Release:` line changed, with
  no push and no new PR; `residual_dates` listed; NEW taken in one repo or in the past: nothing is
  written to any repo; a failure in the second repo leaves the first done and a rerun finishes;
  old branches deleted only with the flag and only when every PR is closed or merged; the local
  rename and worktree move; the same gate cases as `publish`.
- `status`: the table for a clean release of each shape, a release behind `master`, a broken mirror
  (exit 1), `--links` order and format, no `gh` write.
- Gate: no code path calls `gh pr merge`, `git push` to `master`/`sandbox`, or `--force`
  (a test greps the module and the fake `gh` log); `ws setup` reports the missing `ask` rules and
  the hook; the hook asks for every way of writing an approval (the forms listed in "The approval
  gate") and stays silent for `status`, `branches`, `new` and the previews; `publish --approve` and
  `move --approve` exit 2 when the settings lack the rules or the hook.
- Confidentiality: a test runs `ws check-secrets` over the sample outputs and the fixtures, so
  the fixtures cannot carry a real name.

## Known limit of the approval gate

The hook reads the command's text, so it cannot be airtight. Named explicitly (2026-10-27): a
script file run by the shell, a background process started in a new session (`setsid`, `nohup`),
an import route built at run time, and a fully encoded command (e.g. `eval` of a `base64` string)
that names neither `ws` nor `release` are not seen by it. There, the `ask` rule does not match
either, and the barriers are the auto-mode classifier and the user's reading of each command. A
gate that does not rely on text (a per-preview secret the user supplies outside the chat) was
considered and left out on purpose, to keep the approval a single Claude Code prompt.

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
