# Checkpoint (end of an iteration): design

Item 3 of `docs/backlog.md` "Next skills". Status: design, 2026-10-27.

## Goal

At the end of each iteration on a project, the project folder in the workspace says where the work
stopped and what comes next, and it is committed and pushed, the same way every time. The daily
reads the "Próximo passo" of each project, so a checkpoint keeps the daily's "Hoje" right.

## Why

The user asked for every iteration to end with the workspace updated, pulled before, committed and
pushed after, without asking (memories "Artemis V2 sempre sincronizado" and "Whitelabel no
workspace"). Today each chat does it by hand, with a different shape each time; one project's
`CONTINUE.md` has no "## Próximo passo" at all, so the daily warns about it.

## Decisions (taken while the user was away, to confirm)

- **Required sections of `CONTINUE.md`:** `## Onde parei` and `## Próximo passo`, the template's
  names, each with text. `## Branches e worktrees` stays optional. Other sections are free.
- **The whitelabel project** gets the two sections added by the first checkpoint run there (the
  model writes them from its current "Onde está"); nothing else in that file is rewritten.
- **Model-invoked:** the skill writes only to the personal repo, whose rule is "commit and push to
  `main` without asking", so the model may invoke it (no `disable-model-invocation`).
- **Scope of a commit:** only files under `projects/<slug>/`. Anything else staged or changed →
  the command refuses and names the paths, so a checkpoint never sweeps in unrelated work.

## The commands

- `ws checkpoint check SLUG` — prints a JSON verdict for `projects/<slug>/`: `ok`, and the
  problems: `CONTINUE.md` missing; a required section missing or empty; `## Próximo passo` longer
  than 15 lines (it is read every morning: keep it short); `decisions.md` missing. Exit 0 when ok,
  1 otherwise.
- `ws checkpoint commit SLUG -m MESSAGE` — runs `git pull --rebase` first (refuses on conflict,
  with the message), runs the check (refuses unless ok), stages `projects/<slug>/` only, refuses
  when anything outside it is staged or modified, commits with the message (the repo's hooks run:
  secrets, new words), pushes, and prints the commit and the push result. The message must follow
  the repo rule (prefix `docs:`/`chore:`/`feat:`/`fix:`/`test:`, at most 72 characters): checked
  before committing. A hook refusal (secret, new word) is printed as is and nothing is pushed.

## The skill `checkpoint`

Triggers: the end of an iteration on a project ("fecha a iteração", "checkpoint", "salva onde
parei"), or the model finishing a chunk of work on a project folder.

1. `ws checkpoint check <slug>`.
2. Update `## Onde parei` (what was done in this iteration, the state of branches and deploys),
   `## Próximo passo` (the next concrete action, short), new decisions in `decisions.md`, and the
   task files touched. Rules of the project's `CLAUDE.md` apply (PT-BR prose, analogs for real
   names).
3. `ws checkpoint check <slug>` again until `ok`.
4. `ws checkpoint commit <slug> -m "docs: <what changed>"`. A new-word refusal → ask the user,
   all words in one question, as the root `CLAUDE.md` says; then commit again.

## Tests (pytest, throwaway repos with a bare remote)

The check: each problem with a passing and a failing case. The commit: pull before; refuses on a
failing check; refuses with a file outside the project modified; stages only the project; pushes
to the bare remote; a bad message is refused before committing.

## Out of scope

Task records under `projects/<p>/tasks/` with their own "Onde parei" (phase B, part 2); updating
Jira from a checkpoint.
