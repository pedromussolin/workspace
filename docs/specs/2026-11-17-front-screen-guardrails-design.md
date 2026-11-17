# Front screen guardrails (layers 1, 3 and 4)

Date: 17/11/2026. Size: small change (short design).

## Intent

Screens built by agents keep reaching the user off the portal's pattern, and the user finds it in
the browser. Latest case: the product settings page (TS-5624: loose layout, table header floating
in a grey block, helper text at body size, the browser's native `<input type="time">`). Older case,
kept only as an example and not fixed now: the collateral checks page ("Atualizar dados" and
"Exportar" floating in their own rows instead of the page header, which `architecture.md` already
requires).

The front repo already has the rules (`.ai/rules/`, ~1,700 lines), the skills (`new-page`,
`validate-change`), the reference screens (`.ai/context/reference-screens.md`) and smoke prints in
CI. What failed: the agents never loaded those skills (the briefs pointed at the task plan), the
same agent that built the screen judged its own prints, and there is no page anatomy to start from.

## Goals

- Every front agent starts from the repo's own skill and the reference screens.
- No screen reaches the user before someone who did not build it compares its prints with the
  reference screens.
- A new page starts from a canonical anatomy, so the layout is decided before the template.

## Non-goals

- Layer 2 (new `check-patterns` checks). The repo has no legacy lists, so each new check would
  force fixing every existing screen (collateral checks included). The user chose not to open a
  task for it; the collateral checks case stays as an example.
- Fixing existing screens.
- Changing tokens or `shared/ui` visuals.

## Anti-goals

- Long prose nobody reads: the anatomy fits one screen, the checklist about 15 lines.
- A review that repeats what lint, `check-patterns` and the smoke already catch.

## Approaches considered

Four layers, combinable: (1) brief that forces the repo skills; (2) new mechanical checks;
(3) independent visual review; (4) page anatomy. The user picked all four and then moved layer 2
out (example only, no task). Layer 1 is cheap and hits the TS-5624 root cause; layer 3 catches
what no rule can ("not clean"); layer 4 prevents at the source.

## Design

### Layer 1: the brief (workspace, the controller's process)

- `docs/conventions/agents.md` gains a "Front screens" rule: a brief for work in
  `apl-credit-whitelabel` names the repo skill to load first (`new-page`, `new-component`,
  `fix-bug`, `validate-change`), says to read `.ai/README.md` in its order, names the reference
  screens to open, requires the smoke prints and the independent review (layer 3) before the
  report, and the controller opens the prints before showing the user. [review]
- `templates/briefs/front-screen.md`: the brief skeleton (PT-BR), with those items as fixed text and
  slots for the task.

### Layer 3: independent visual review (front repo)

- New skill `.ai/skills/review-screen/SKILL.md` (PT-BR, like the others): "Revisa uma tela contra as
  telas de referência". Steps: build and smoke of the changed routes and of `/pre-trade` and
  `/liquidation-batches` (1440 px, 390 px, dark); walk a short checklist (anatomy order, page
  actions in `app-page-header`, view selector, filter bar, cards, tables, text scale, native
  controls, empty states and notices, button style and place, mobile); report each item as ok or
  deviation, with the print. It must be run by someone who did not build the screen: a fresh
  subagent in Claude Code, a new session in other tools, or a person.
- `validate-change` gains a step: a change that touches a page template or style runs
  `review-screen` before "pronto"; deviations are fixed or listed in the PR.
- `.ai/README.md` lists the new skill in the task table.

### Layer 4: page anatomy (front repo)

- `.ai/context/reference-screens.md` opens with a page anatomy section (title in PT-BR): the canonical order with a
  text sketch (breadcrumbs, `app-page-header` with the page actions on the right, page notice,
  view selector, filter bar or context selector, content in cards, empty states and notices by
  their components) and three variants: list (the scaffold already exists), detail and settings
  (sections of fields with the save action at the section's foot). The settings variant points
  to the product settings page once it is redone.
- `new-page` gains a first step: pick the page type and copy its anatomy before writing the
  template.

## Where it goes

- Workspace: layer 1, committed to `main`.
- Front: layers 3 and 4 in the TS-5624 branch (`feature/TS-5624-product-settings-page`), as
  `chore(TS-5624)` commits, by the repo rule "a pattern changes, `.ai/` changes in the same PR";
  the redone product settings page is the first screen through them. No new task (the user's
  call).

## Left to the builder

The checklist's exact wording, the sketch's ASCII, and how `review-screen` names the print files.
