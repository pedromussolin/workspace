# `ws card start`: design

Date: 2026-11-15. Status: approved by the user (2026-11-15), option (a) on the four open questions
of the proposal. Plan: `docs/plans/2026-11-15-card-start.md`.

## Intent

One command does the ritual of starting a task: the branch is ready in each repo the task changes
and the card is moved to "in progress" with today as its start date. The ritual (find the repos,
fetch the base, name the branch, remember `--no-track`, move the card, set the start date) repeats
on every task and is deterministic, so it is a `ws` command (script first) and costs one step.

Reused: `ws card preview/apply` (drafts in `cards/drafts/`, a code, the gate's box as approval);
the `move` rule that sets an empty start date to the tracker's today; `gittools` (`switch -c ...
--no-track`, the dirty check of `assemble`); `[board]` (remote, repo tables, `statuses`);
`[standup] repo_roots` (default `~/repos`); the items of `2026-11-13-task-items-design.md`; the port.

## Goals, non-goals, anti-goals

- **Goals.** `ws card start TS-N` leaves a branch `<kind>/TS-N-<slug>` in each repo of the task,
  cut from the fresh remote base, and prints a preview code for the card's move; the user's yes in
  the apply box is the only tracker write. Reruns are safe. A failure says what changed and how to
  undo it.
- **Non-goals.** Commits, pushes, pull requests, the `-sdbx` copy (later, by merge); sprint, due
  date or assignee; stashing or cleaning the user's work tree.
- **Anti-goals.** No tracker write from `ws card start` (it never calls `apply`); no guessing (a
  missing repo or slug is a problem naming how to give it); no second write path (the card side is
  a plain `ws card` draft).

## Constraints

Standard library only. Reads go through the neutral `ws.tracker.port`; the Jira part stays in the
adapter and `ws card preview`. Skills use neutral words; the status name comes from config. Nothing
in an item depends on who runs `ws` (the repo is shared).

## Approaches

- **A. Local git first, then a card preview (picked).** One command; the git part is local and
  undoable (`git branch -D`), so it needs no approval; the card keeps its existing preview, gate and
  apply. Cost: two stages (command, then one box); the branch exists before the move is approved
  (harmless: wanted anyway).
- **B. A skill chains a git command and `/card move`.** Least code, but the order lives in prose:
  the model can skip or reorder a step. Breaks "script first".
- **C. One plan like `ws release`** (one preview for git and card, apply does both). A single
  approval, but a new apply path mixing local git with a tracker write, a box that must summarise
  git steps, and its own recovery when Jira fails after the branch. More code than the benefit.

The user picked A: the only external write keeps the box it already has.

## The command

`ws card start REF [--repo NAME]... [--kind K] [--desc SLUG] [--worktree] [--dry-run]`

- `--repo` (repeatable) replaces the inferred repos. `--kind` one of `feature`, `fix`, `chore`,
  `refact`, `test`, `hotfix`. `--desc` replaces the slug (`[a-z0-9]+(-[a-z0-9]+)*`, at most 40).
- `--worktree`: the branch goes to `<root>/.worktrees/<repo>-<REF>` (`<root>` = the repo's
  `repo_roots` entry); the current checkout is not touched. The folder is hidden so the daily, which
  reads the non-hidden children of `repo_roots`, does not count the repo twice.
- `--dry-run`: the read-only checks and the plan, nothing else.

Order. **Checks** (nothing changes if one fails): the card exists, is a card (level 0), is writable
(the user is its assignee or reporter, as in `ws card`), is not done or cancelled; repos and branch
name resolve; per repo: found under `repo_roots`, clean tree (`status --porcelain
--untracked-files=no`; skipped with `--worktree`), `git fetch <remote>` works, `<remote>/<base>`
exists. **Git**, per repo in order: `git switch -c <branch> --no-track <remote>/<base>` (or the
worktree form). **Card**: write the draft, run the preview code path, print the code.

Name: kind from the card's neutral type (`bug` → `fix`, any other → `feature`), `--kind` wins.
Slug from the title: drop the leading `[PREFIX]` groups, fold accents, lowercase, keep `[a-z0-9]+`
words, drop pt-BR stop words, first 5 words, cut at a word boundary to at most 40 characters.

Existing branches: a task branch is `<kind>/<REF>-<slug>`, never one ending `-sdbx`. Across all
repos, the computed name wins when it exists; else a single existing task branch is reused
everywhere (with a warning naming both); two different ones are a problem (pick with `--kind` and
`--desc`). Per repo: local → `switch` to it (no reset); only on the remote → `switch -c <branch>
--track <remote>/<branch>`; checked out in another worktree → left there, reported.

## Where the repos come from

1. `--repo`, always first.
2. The item whose `card = "REF"` under `projects/*/tasks/`: its `repos` key. `repos = []` means the
   task changes no repo: only the card part runs.
3. The title's first `[PREFIX]` in `[board.prefix_repos]`.
4. Else a problem naming the three ways. The skill asks the user and reruns with `--repo`.

## Config keys (local `config.toml`)

```toml
[board.repos."acme-api"]
base = "main"                 # new; default "master"; globs work as for the other repo keys

[board.prefix_repos]          # new: title prefix (no brackets, exact case) -> repos
BACK = ["acme-api"]
FRONT = ["acme-front"]
```

No fallback on `origin/HEAD`: it is often unset or stale in clones, and an explicit key plus one
default is deterministic. A missing `<remote>/<base>` names the key to set. The in-progress status
name is `[board.statuses] in_progress`; the remote is `[board] remote`.

## Item key `repos`

`repos = ["acme-api", "acme-front"]`: repo directory names (`[A-Za-z0-9][A-Za-z0-9._-]*`). A
workspace key, not a contract field: never sent to nor compared with the tracker; shape-checked.

## The draft

`~/.local/share/workspace/cards/drafts/start-REF.md`, rewritten on each run:

- card in `todo` or `blocked`: `op = "move"`, `key`, `to = <[board.statuses] in_progress>`; the move
  rule sets the start date only when empty;
- card already in progress or further (review, validation, ready to deploy) with no start date:
  `op = "edit"`, `key`, `start = <today in the tracker's time zone>` (needs the `start_date`
  capability; without it, a warning and no draft). It never moves a card backwards;
- in progress with a start date: no draft, no preview, said in the output.

The port gains `Card.start` and `Tracker.today()`; Jira reads `start_date_field` and `timeZone`.

## Output and exit codes

stdout is one JSON object: `ref`, `title`, `status`, `start`, `branch`, `repos_from` (`flag`,
`item`, `prefix`, `none`), `repos` (each `name`, `path`, `base`, `action` one of `create`, `track`,
`reuse`, `current`, `elsewhere`, and `worktree`), `card_change` (`move`, `start` or null), `draft`,
`preview` (the text `ws card preview` prints), `code`, `apply` (the exact command), `dry_run`,
`problems`, `warnings`, `undo`.

Exit codes, as `ws card`: 0 ok (also "nothing to write on the card"); 1 a problem (checks, a git
step, or the preview refused; `problems` says which); 2 setup (no `[board]`, invalid config, tracker
setup); 3 the tracker refused or is unreachable. Setup and tracker errors go to stderr as
`ws card start: ...`.

## Failure and rerun

- Dirty tree in any repo, or a failed fetch: stop before touching any repo (suggest commit, stash
  or `--worktree`).
- A git step fails after an earlier repo switched (e.g. an untracked file the base would
  overwrite): stop, no draft, exit 1; `undo` lists `git -C <path> switch <previous>` and
  `git -C <path> branch -D <branch>` (or `worktree remove`) for what this run created; never run.
- The preview refuses or the tracker fails after git: branches and draft stay; rerun. A rerun
  reuses the branches, rewrites the draft and prints a fresh code (the 30-minute rule stays).

## The skill

`/card` gains "Start" (`/card iniciar TS-N`): run `ws card start`, ask on problems only the user can
settle (which repos, a slug), show branches, warnings and the preview as printed, then run the
printed `apply` (its box is the approval). `undo` is shown and offered, never run without a yes.

## Left to the builder

Module split, stop-word list, PT-BR wording, JSON key order, how tests build the git remotes.
