# Instruction files: one home per rule

## Why

`~/repos/CLAUDE.md` mixes four kinds of rules: how the user works (every folder), the workspace
tooling (agents, cards and hours), the company process (git, release, argocd) and the code rules of
each company repo. Several of them are also written in `docs/conventions/`, in the skills, in the
project `CLAUDE.md` files and in the `.ai/` folders of the front and the BFF. The copies already
diverge: `projects/whitelabel-restructure/CLAUDE.md` says "no push by Claude", while
`~/repos/CLAUDE.md` allows a push on the task branch. And `~/repos` is not a git repository, so the
file has no history and no backup.

The goal the user chose: each rule lives in one place, and every other file links to it.

## Goals

- Every rule has one home; no file repeats a rule that lives elsewhere.
- The two global instruction files are versioned in this repo and checked by its hooks.
- What Claude Code loads in each session stays the same, minus the duplicates: the general rules
  load in every folder, the company rules in every session under `~/repos`.

## Non-goals

- No change in the company repos in this task. A front or BFF line that their `.ai/` does not
  have yet stays in the company file and becomes a card proposal for the next sprint.
- No rewording of the rules beyond the move, the merge of two copies of one rule, and the removal
  of the company's real name.

## Anti-goals

- A rule lost in the move. Every line of the current `~/repos/CLAUDE.md` is accounted for: moved,
  merged or already present in its home.
- A rule that stops loading where it is needed, such as a code rule moved to a workspace project,
  which only loads when a file of that project is read.

## Approaches

- **A. This repo is the source, linked by symlink (chosen).** Two new files in this repo become
  `~/.claude/CLAUDE.md` and `~/repos/CLAUDE.md` through symlinks that `ws setup` creates, as it
  already does for the skills. Gains: history, diff, hook checks, one source. Costs: the text
  follows the confidentiality rules (only the company name has to go).
- **B. `~/repos/CLAUDE.md` stays the source, only deduplicated.** Less change and nothing to
  mask, but still no history, and this repo depends on a file outside it.

The user chose A. Tested on 24/11/2026 with `claude -p`: a symlinked project `CLAUDE.md` is
loaded; a symlinked `~/.claude/CLAUDE.md` is loaded, and so is an `@` import from it to a file
outside the folder, with no approval. An `@` import from a project `CLAUDE.md` to a file outside
its folder was not loaded in `-p` (Claude Code asks for approval first), so the design avoids
those.

## Design

### Where each kind of rule lives

| Home | Scope | Loaded |
|---|---|---|
| `instructions/user.md`, linked as `~/.claude/CLAUDE.md` | every folder | always |
| `docs/conventions/agents.md`, imported by `user.md` | agents, in every repo | always |
| `instructions/company-repos.md`, linked as `~/repos/CLAUDE.md` | company repos | under `~/repos` |
| a company repo's `.ai/` | that repo, shared with the team | in that repo |
| `docs/conventions/*` (other files) | this repo | in this repo |
| a skill (`skills/*/SKILL.md`, `references/`) | a procedure the skill runs | when it triggers |
| `projects/<slug>/CLAUDE.md` | that project | when a file of it is read |

A rule goes to the narrowest home where it fully holds. A procedure step goes to its skill, while a
permission or a limit (who pushes the production argocd, when the front may go) stays in the
global file, because it must hold even when the skill does not trigger. A narrower file links to
a wider one instead of repeating it, and a wider file never repeats a narrower one.

### Mapping of the current `~/repos/CLAUDE.md`

| Section | Goes to |
|---|---|
| intro, "Workspace" | `company-repos.md` |
| Comunicação, Bash, Leitura e contexto | `user.md` |
| Agentes | `docs/conventions/agents.md` (lines it lacks are merged in; its intro says "every repo") |
| Cards e horas | `company-repos.md`, without the company name; the `card` skill keeps the procedure |
| Repositórios, Git, Fluxo da tarefa | `company-repos.md`; release and argocd steps already in `release`, `change-request` or `deploy-check` leave, and the limits stay |
| Código: general and platform-cessao, shared-service | `company-repos.md` |
| Código: front and BFF | removed where their `.ai/` has it; the rest stays, with a card proposal |

### Other files

- Project `CLAUDE.md` files (`artemis-v2`, `whitelabel-restructure`, `valids`, `pre-trade`,
  `vm-migration`, `workspace`) and `templates/project/CLAUDE.md`: drop the paragraph about the
  company git rules (the root `CLAUDE.md` already says it), the writing rules that repeat
  `user.md`, and the code rules that live in `company-repos.md` (log as an event, migrations,
  scheduling only through the database). Project-specific rules stay. This also removes the
  "no push by Claude" divergence.
- `docs/conventions/*`: a rule that holds in every repo moves to `user.md` or `agents.md`; the
  convention keeps a one-line link, with its enforcement tag when this repo enforces it.
- Root `CLAUDE.md`, `AGENTS.md` (Layout table), `README.md` (setup) and
  `docs/conventions/language.md`: name `instructions/`, its two files and their PT-BR content (a
  row in the language table).

### `ws setup`

- A new step links `instructions/user.md` to `~/.claude/CLAUDE.md` and
  `instructions/company-repos.md` to `CLAUDE.md` in the parent folder of the clone (`~/repos`),
  in the same way as `_link_skills`: it creates a missing link, and it reports, never overwrites,
  a file that exists and is not a link to this repo. `--check` only reports.
- Tests cover the three cases (missing, right link, foreign file).

### Migration

1. Copy the current `~/repos/CLAUDE.md` to the private data folder
   (`~/.local/share/workspace/`); it carries real names and stays outside git.
2. Write the two files and the other changes; commit.
3. Remove `~/repos/CLAUDE.md` and run `ws setup`, which creates both links.
4. Check with `claude -p` in a company repo, in this repo and in a folder outside `~/repos` that
   each session loads what it should.

## Left to the builder

- The line-by-line mapping, written in the plan, with the home of each line.
- Which front and BFF lines their `.ai/` already has.
- The wording of the link lines in the conventions and in the project files.
- The name of the backup file and the exact `ws setup` messages.
