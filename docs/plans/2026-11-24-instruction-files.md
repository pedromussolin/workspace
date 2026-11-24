# Instruction files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every rule of `~/repos/CLAUDE.md` gets one home, and the two global instruction files
become versioned files of this repo, linked by `ws setup`.

**Architecture:** `instructions/user.md` (linked as `~/.claude/CLAUDE.md`) holds the rules for
every folder and imports `docs/conventions/agents.md`; `instructions/company-repos.md` (linked as
`~/repos/CLAUDE.md`) holds the company rules. Copies elsewhere become links.

**Tech Stack:** Python 3.12 stdlib (`ws setup`), pytest, Markdown.

**Spec:** `docs/specs/2026-11-24-instruction-files-design.md`

## Global Constraints

- Confidentiality: no real company name, no `/home/<user>` path (write `~`); the hooks check it.
- `instructions/*.md` are PT-BR; `docs/conventions/`, skills and code are English.
- Rule text is moved, not reworded. The only changes: the merges this plan lists and the removal of
  the company name.
- No change in the company repos.
- `ws setup` never overwrites a file it did not create; `--check` changes nothing.
- pytest: `uv run pytest -q -p no:cacheprovider --basetemp=$HOME/.cache/ws-pytest/instructions`,
  then `chmod -R u+w` and `rm -rf` that folder.
- Commits: PT-BR, `feat:`/`fix:`/`docs:` prefix, at most 72 characters, no `Co-Authored-By`,
  never `--no-verify`; commit and push to `main` at the end of each task, the push in its own call.

## Review Focus

- `ws setup` run from a linked worktree (`~/repos/.workspace-wt/<name>`): it must not create
  `CLAUDE.md` in the worktrees folder. Test in Task 1.
- `~/repos/CLAUDE.md` is a regular file today: setup reports it and leaves it as is. Test in Task 1.
- A link that points elsewhere, or dangles: reported, untouched. Test in Task 1.
- A line of the old file with no home after the move: Task 2, step 6 checks each line.
- The `@~/…` import in `user.md` not resolved: Task 4, step 3 checks that `agents.md` loads.

---

### Task 1: `ws setup` links the instruction files

**Files:**
- Modify: `src/ws/config.py` (after `claude_skills_dir`)
- Modify: `src/ws/bootstrap.py` (`run_setup`, new `_link_instructions` after `_link_skills`)
- Modify: `src/ws/cli.py:75` only if `run_setup` needs the new path passed (it defaults)
- Test: `tests/test_bootstrap.py`
- Modify: `README.md` and `AGENTS.md` (the lines that say what `ws setup` links)

**Interfaces:**
- Produces: `config.claude_user_instructions_path() -> Path`, env override
  `WS_CLAUDE_USER_INSTRUCTIONS`, default `~/.claude/CLAUDE.md`.
- Produces: `bootstrap._link_instructions(setup: _Setup, repo: Path, user_instructions: Path) -> None`;
  `run_setup(..., user_instructions: Path | None = None)`, default from the function above.
- Links: `repo/instructions/user.md` → `user_instructions`;
  `repo/instructions/company-repos.md` → `repo.parent / "CLAUDE.md"`.
- Messages (`{name}` is `user.md` or `company-repos.md`): fixed `instructions {name}: link {link}`;
  need `instructions {name}: {link} exists and is not a link to this repo`; failure
  `instructions {name}: could not link {link}`; worktree need
  `instructions: {repo} is a linked worktree; run ws setup from the main clone`.

- [ ] **Step 1: Write the failing tests**

In the autouse `_clean_environment` fixture, set `WS_CLAUDE_USER_INSTRUCTIONS` to
`tmp_path / "home-claude" / "CLAUDE.md"`, so no test touches the real file. In `env`, write
`repo/instructions/user.md` and `repo/instructions/company-repos.md` (one line each). Tests:

- `test_links_instruction_files`: after `_setup(env)`, `needs == []`; both links are symlinks
  resolving to the repo files; `tmp_path / "CLAUDE.md"` is the company link; both fixed messages
  are in `result.fixed`.
- `test_check_does_not_link_instructions`: `_setup(env, check=True)` leaves both paths absent and
  lists both fixed messages.
- `test_regular_file_instead_of_instructions_link_untouched`: a regular `tmp_path / "CLAUDE.md"`
  with "keep me" gives exactly the need message for `company-repos.md`, and the text is unchanged.
- `test_instructions_link_elsewhere_or_dangling_is_a_conflict`: parametrize a link to another file
  and a link to a missing path at the user path; need message, link unchanged (`os.readlink`).
- `test_instructions_skipped_in_linked_worktree`: a folder with `instructions/` and a `.git` file
  (`gitdir: ...`); `_link_instructions` records only the worktree need and creates nothing.
- `test_second_run_is_noop` already covers the second run; it must keep passing.
- The exact `fixed` lists in `tests/test_bootstrap.py` (around lines 1271-1351) gain the two
  instruction messages where the links are still missing; update them.
- `tests/test_claude_hooks.py:64` runs `run_setup` on a repo with no `instructions/`: the early
  return keeps it off the real files, with no change there.

- [ ] **Step 2: Run the tests and see them fail**

Run: `uv run pytest -q -p no:cacheprovider --basetemp=$HOME/.cache/ws-pytest/instructions tests/test_bootstrap.py`
Expected: the five new tests FAIL (no links, no attribute `_link_instructions`).

- [ ] **Step 3: Implement**

`_link_instructions` returns early when `repo / "instructions"` is not a folder, records the
worktree need and returns when `(repo / ".git").is_file()`, and otherwise follows
`_link_skills` (missing → `setup.fix` with `_link`; not the right link → `setup.need`). Call it
right after `_link_skills` in `run_setup`. Add one line to the `ws setup` description in
`README.md` and `AGENTS.md` ("links `instructions/` as `~/.claude/CLAUDE.md` and
`~/repos/CLAUDE.md`").

- [ ] **Step 4: Run the tests and see them pass**

Run the command of step 2, then the full suite once (same command, no file). Expected: all pass.
Then `uv run ruff check` and `uv run ruff format --check`.

- [ ] **Step 5: Commit and push**

`git commit -m "feat: ws setup liga os arquivos de instrução globais"`, then `git push` alone.

### Task 2: The two instruction files and the conventions

**Files:**
- Create: `instructions/user.md`, `instructions/company-repos.md`
- Modify: `docs/conventions/agents.md`, `docs/conventions/git.md`, `docs/conventions/testing.md`,
  `docs/conventions/language.md`, `docs/conventions/skills.md` (context budget line),
  `CLAUDE.md` (section "Company-repo rules do not apply here"), `AGENTS.md` (Layout table)

**Interfaces:**
- Consumes: the current `~/repos/CLAUDE.md` (read it in full first).
- Produces: section headings `## Comunicação`, `## Bash`, `## Leitura e contexto`, `## Agentes`
  in `user.md`; `## Workspace`, `## Cards e horas`, `## Repositórios`, `## Git`,
  `## Fluxo da tarefa`, `## Código` in `company-repos.md`. Task 3 links to them.

- [ ] **Step 1: Back up the current file**

Copy `~/repos/CLAUDE.md` to `~/.local/share/workspace/backup/repos-CLAUDE-20261124.md`, mode
`600`. It carries real names: never into the repo.

- [ ] **Step 2: Write `instructions/user.md`**

Top line: the file is linked as `~/.claude/CLAUDE.md` by `ws setup`, edits go to this file, and it
is versioned (no real name). Then Comunicação, Bash and Leitura e contexto, moved as they are.
Then `## Agentes` with one line and the import `@~/repos/workspace/docs/conventions/agents.md`.

- [ ] **Step 3: Write `instructions/company-repos.md`**

Same top line, for `~/repos/CLAUDE.md`. Then the intro and Workspace section, Cards e horas
(holds in the workspace too), and the company sections, applying this map:

| Current line | Action |
|---|---|
| "Card no Jira segue o padrão de preenchimento..." (it names the company and its profile file) | keep, as "o perfil de preenchimento da empresa (`~/.config/workspace/card-policies/`)" |
| "Prazo de card..." and "Prazo não é fim de sprint..." | move to the `card` skill (Task 3); leave one line pointing to `/card` |
| "Release: uma PR por repo para a sandbox..." | drop if `skills/release/references/pr-shapes.md` has both shapes (`release/<data>` and `-sdbx`); else keep. Keep "PR de card sozinho..." (a limit) |
| argocd line | keep whole (limits; no skill does the tag bump) |
| "Front: sem Angular Material..." and "Front: permissão por escopo..." | drop; add "Front e BFF: as regras de código ficam no `.ai/` de cada repo, que o `CLAUDE.md` dele importa." |
| Idioma line | drop "BFF e front em inglês (código e logs)" and "o `it(...)` do front em PT-BR"; keep the rest |
| shared-service features line | merge "(nada de FK, import ou chamada entre elas)" from `projects/pre-trade/CLAUDE.md` |
| every other line | move as it is |

- [ ] **Step 4: Merge the agent rules into `docs/conventions/agents.md`**

Intro: "How a controller briefs subagents, and how agents work, in every repo.
`instructions/user.md` imports this file." Merge, in English:
- the brief carries "the excerpts of the repo rules (`.ai/` in the company repos,
  `docs/conventions/` here) and of the documents the task uses, with their paths";
- after the 200k line: "A larger task is split into agents in sequence, each writing its delivery
  to a file for the next.";
- the wait line gains "An unavoidable wait runs under `timeout N`.";
- the sweep line gains "(`ps`), ending each one by its PID".
The `pgrep -f` line keeps its stricter current wording. The shell-variable line becomes a link to
`instructions/user.md` (Bash), keeping `[gate]`.

- [ ] **Step 5: Point the other conventions and docs**

- `git.md`: the "own short Bash call" line becomes a link to `instructions/user.md` (Bash), keeping
  `[review]`.
- `testing.md`: keep the pytest command; the tmpfs sentence becomes a link to the same section.
- `language.md`: a PT-BR row, "the global instructions (`instructions/*.md`)".
- `skills.md` context budget: add "`instructions/*.md` and `docs/conventions/agents.md`" to the
  always-loaded files that stay small.
- `AGENTS.md` Layout: row `instructions/` — "global Claude Code instructions (PT-BR), linked by
  `ws setup`: `user.md` as `~/.claude/CLAUDE.md`, `company-repos.md` as `~/repos/CLAUDE.md`".
- Root `CLAUDE.md`: `~/repos/CLAUDE.md` is a link to `instructions/company-repos.md`; its Cards e
  horas holds here, its company sections do not; the rules for every folder are in
  `instructions/user.md`.

- [ ] **Step 6: Check that no line was lost**

For each bullet of the backup, find its home (`grep -F` a distinctive phrase in `instructions/`,
`docs/conventions/agents.md`, `skills/release/`, the front and BFF `.ai/`, or the Task 3 card
rules). Every bullet has a hit, or is in the map above as dropped with its home named.

- [ ] **Step 7: Validate, commit and push**

Run `scripts/validate`. Commit
`docs: instruções globais no repo, com uma fonte por regra`, then `git push` alone. A hook
block is fixed in the text (`ws mask --in-place` when it is a name), never skipped.

### Task 3: Project files and the card due date

**Files:**
- Modify: `projects/{artemis-v2,whitelabel-restructure,valids,pre-trade,vm-migration,workspace}/CLAUDE.md`,
  `templates/project/CLAUDE.md`
- Modify: `skills/card/SKILL.md:21`, `skills/card/references/card-rules.md` §7

**Interfaces:**
- Consumes: the section names of Task 2.

- [ ] **Step 1: Trim the project files**

- Drop the paragraph about the company git rules (`artemis-v2` lines 77-79, `valids` 103-105,
  `whitelabel-restructure` 50-51; this removes the "sem push pelo Claude" divergence).
- Drop "PT-BR, enxuto: conclusão primeiro... termo técnico" (`artemis-v2` 43-44, `valids` 72-73,
  `vm-migration` 32). Keep [C]/[H], citing code, numbers, and each project's "conferir no ..." line
  (it names where to check).
- `artemis-v2`: drop "Logs como eventos" and "Migrations".
- `pre-trade`: drop the architecture, migration and scheduling bullets and the "Nada de FK..."
  sentence; keep the rest of the workflow-engine bullet and the sandbox line.
- The "regras comuns" paragraph of each file and the template: add "e as regras de trabalho em
  `instructions/`" so it names every common source.

- [ ] **Step 2: Move the due date rules into the `card` skill**

`card-rules.md` §7 gains, in English: the due date of a card that takes code to production is the
deploy day; of a post-deploy action, the day after; never the sprint's end by default; before
proposing to take a card out of a sprint, read the dates in the Sprint field; a card that misses
its release goes to the next release in the same sprint. `SKILL.md:21` proposes the due date by
that rule instead of "the sprint's end".

- [ ] **Step 3: Test**

Run pytest on `tests/test_card_skill_words.py tests/test_card_skill_invocation.py`. Run
`grep -rln "due" evals/` and, when a card case asserts a due date, run that case once
(`scripts/run-evals --case NAME --runs 1`, real API cost). Expected: pass.

- [ ] **Step 4: Validate, commit and push**

`scripts/validate`, then two commits: `docs: projetos apontam para as instruções globais` and
`fix: prazo do card é o dia da subida, não o fim da sprint`; `git push` alone.

### Task 4: Migration

**Files:** none in the repo.

- [ ] **Step 1: Swap the file for the link**

Confirm the backup of Task 2 exists, then `rm ~/repos/CLAUDE.md` and run `ws setup`. Expected:
"instructions user.md: link ..." and "instructions company-repos.md: link ..." among the fixes,
no instruction need.

- [ ] **Step 2: Check the links**

`ls -l ~/.claude/CLAUDE.md ~/repos/CLAUDE.md`: both point into `~/repos/workspace/instructions/`.

- [ ] **Step 3: Check what each session loads**

In `~/repos/apl-shared-service`, `~/repos/workspace` and a new folder under `~/.cache`, run
`timeout 120 claude -p --model haiku` asking, without tools, yes or no for three phrases:
"Fluxo da tarefa", "Explique todo termo técnico", "A brief carries". Expected: yes/yes/yes in the
two folders under `~/repos`, no/yes/yes outside. Remove the `~/.cache` folder.

- [ ] **Step 4: Report**

Tell the user the links, the three checks, the backup path, and that the front and BFF lines
needed no card proposal (all were already in their `.ai/`).
